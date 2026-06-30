"""
Environment Detection System for PowerStore CT Engine

This module provides robust multi-source environment detection to reliably
identify development, staging, and production environments.

Detection Priority Order:
1. Explicit ENVIRONMENT environment variable
2. Filesystem markers (.env file, /etc/environment, /app/ENVIRONMENT)
3. Network context (IP ranges, DNS suffixes)
4. Kubernetes namespace/labels
5. Default to development with warning
"""

import os
import socket
import logging
from enum import Enum
from typing import Optional, Dict, List
from pathlib import Path
import json
import re

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Environment enumeration with strict type safety"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    
    def __str__(self) -> str:
        return self.value


class EnvironmentDetectionError(Exception):
    """Custom exception for environment detection failures"""
    pass


class EnvironmentDetector:
    """
    Multi-source environment detection system with fallback mechanisms.
    
    Implements robust environment detection using multiple sources with
    clear precedence and validation.
    """
    
    # Environment-specific markers
    ENVIRONMENT_MARKERS = {
        Environment.DEVELOPMENT: ['.env.development', '.env.dev', 'dev'],
        Environment.STAGING: ['.env.staging', '.env.stage', 'staging'],
        Environment.PRODUCTION: ['.env.production', '.env.prod', 'production']
    }
    
    # Network context patterns
    NETWORK_PATTERNS = {
        Environment.DEVELOPMENT: [
            r'192\.168\.\d+\.\d+',  # Private network
            r'10\.0\.\d+\.\d+',       # Private network
            r'172\.16\.\d+\.\d+',     # Private network
            r'localhost',
            r'127\.0\.0\.1'
        ],
        Environment.STAGING: [
            r'staging\.dell\.com',
            r'stage\.dell\.com',
            r'staging-.*\.dell\.com'
        ],
        Environment.PRODUCTION: [
            r'prod\.dell\.com',
            r'production\.dell\.com',
            r'.*\.dell\.com'
        ]
    }
    
    # Kubernetes namespace patterns
    KUBERNETES_NAMESPACES = {
        Environment.DEVELOPMENT: ['dev', 'development', 'dev-*'],
        Environment.STAGING: ['staging', 'stage', 'staging-*'],
        Environment.PRODUCTION: ['prod', 'production', 'prod-*']
    }
    
    def __init__(self):
        """Initialize environment detector with caching"""
        self._cached_environment: Optional[Environment] = None
        self._detection_sources: List[str] = []
        self._kubernetes_available = self._check_kubernetes_available()
        
    def detect_environment(self, force_redetect: bool = False) -> Environment:
        """
        Detect the current environment using multi-source detection.
        
        Args:
            force_redetect: Force re-detection even if cached
            
        Returns:
            Detected Environment enum value
            
        Raises:
            EnvironmentDetectionError: If detection fails completely
        """
        if self._cached_environment and not force_redetect:
            logger.debug(f"Using cached environment: {self._cached_environment}")
            return self._cached_environment
            
        logger.info("Starting environment detection...")
        
        # Try detection methods in priority order
        detection_methods = [
            self._detect_from_env_variable,
            self._detect_from_filesystem,
            self._detect_from_network_context,
            self._detect_from_kubernetes,
            self._detect_default
        ]
        
        for method in detection_methods:
            try:
                environment = method()
                if environment:
                    self._cached_environment = environment
                    logger.info(f"Environment detected via {method.__name__}: {environment}")
                    logger.info(f"Detection sources: {self._detection_sources}")
                    return environment
            except Exception as e:
                logger.warning(f"Detection method {method.__name__} failed: {e}")
                continue
                
        raise EnvironmentDetectionError("All environment detection methods failed")
    
    def _detect_from_env_variable(self) -> Optional[Environment]:
        """Detect environment from explicit ENVIRONMENT variable"""
        env_var = os.environ.get('ENVIRONMENT', '').lower()
        
        if not env_var:
            logger.debug("No ENVIRONMENT variable set")
            return None
            
        self._detection_sources.append("ENVIRONMENT variable")
        
        try:
            return Environment(env_var)
        except ValueError:
            logger.warning(f"Invalid ENVIRONMENT value: {env_var}")
            raise EnvironmentDetectionError(f"Invalid environment: {env_var}")
    
    def _detect_from_filesystem(self) -> Optional[Environment]:
        """Detect environment from filesystem markers"""
        # Check for .env files
        env_files = ['.env', '.env.local']
        for env_file in env_files:
            env_path = Path(env_file)
            if env_path.exists():
                self._detection_sources.append(f"filesystem ({env_file})")
                return self._detect_from_env_file(env_path)
        
        # Check for system environment files
        system_files = ['/etc/environment', '/app/ENVIRONMENT']
        for sys_file in system_files:
            sys_path = Path(sys_file)
            if sys_path.exists():
                self._detection_sources.append(f"filesystem ({sys_file})")
                return self._detect_from_system_file(sys_path)
        
        logger.debug("No filesystem markers found")
        return None
    
    def _detect_from_env_file(self, env_path: Path) -> Optional[Environment]:
        """Detect environment from .env file"""
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('ENVIRONMENT='):
                        env_value = line.split('=', 1)[1].strip().strip('"\'')
                        try:
                            return Environment(env_value.lower())
                        except ValueError:
                            logger.warning(f"Invalid ENVIRONMENT in {env_path}: {env_value}")
        except Exception as e:
            logger.warning(f"Failed to read {env_path}: {e}")
        
        return None
    
    def _detect_from_system_file(self, sys_path: Path) -> Optional[Environment]:
        """Detect environment from system environment file"""
        try:
            with open(sys_path, 'r') as f:
                content = f.read().lower()
                
                for env, markers in self.ENVIRONMENT_MARKERS.items():
                    for marker in markers:
                        if marker in content:
                            return env
        except Exception as e:
            logger.warning(f"Failed to read {sys_path}: {e}")
        
        return None
    
    def _detect_from_network_context(self) -> Optional[Environment]:
        """Detect environment from network context"""
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            
            logger.debug(f"Network context - hostname: {hostname}, ip: {ip_address}")
            
            # Check against network patterns
            for env, patterns in self.NETWORK_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, hostname, re.IGNORECASE) or \
                       re.search(pattern, ip_address):
                        self._detection_sources.append(f"network context ({pattern})")
                        return env
                        
        except Exception as e:
            logger.warning(f"Network context detection failed: {e}")
        
        logger.debug("No matching network patterns found")
        return None
    
    def _detect_from_kubernetes(self) -> Optional[Environment]:
        """Detect environment from Kubernetes context"""
        if not self._kubernetes_available:
            logger.debug("Kubernetes not available")
            return None
            
        try:
            from kubernetes import config, client
            
            # Load in-cluster config
            config.load_incluster_config()
            
            # Get current namespace
            with client.ApiClient() as api:
                namespace = open('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read()
                
                logger.debug(f"Kubernetes namespace: {namespace}")
                
                # Check namespace patterns
                for env, patterns in self.KUBERNETES_NAMESPACES.items():
                    for pattern in patterns:
                        if re.match(pattern.replace('*', '.*'), namespace, re.IGNORECASE):
                            self._detection_sources.append(f"Kubernetes namespace ({namespace})")
                            return env
                
                # Try to detect from pod labels
                v1 = client.CoreV1Api()
                pod_name = socket.gethostname()
                pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                
                if pod.metadata.labels:
                    env_label = pod.metadata.labels.get('environment')
                    if env_label:
                        try:
                            return Environment(env_label.lower())
                        except ValueError:
                            logger.warning(f"Invalid environment label: {env_label}")
                            
        except Exception as e:
            logger.warning(f"Kubernetes detection failed: {e}")
        
        return None
    
    def _detect_default(self) -> Environment:
        """Default to development with warning"""
        logger.warning("No environment detected, defaulting to DEVELOPMENT")
        logger.warning("Set ENVIRONMENT variable explicitly to avoid this warning")
        self._detection_sources.append("default fallback")
        return Environment.DEVELOPMENT
    
    def _check_kubernetes_available(self) -> bool:
        """Check if Kubernetes is available"""
        try:
            from kubernetes import config
            # Try to load in-cluster config
            config.load_incluster_config()
            return True
        except Exception:
            try:
                # Try to load kube config
                config.load_kube_config()
                return True
            except Exception:
                return False
    
    def validate_environment(self, environment: Environment) -> bool:
        """
        Validate the detected environment for consistency.
        
        Args:
            environment: The detected environment
            
        Returns:
            True if validation passes, False otherwise
        """
        logger.info(f"Validating environment: {environment}")
        
        # Check for consistency across detection sources
        if len(self._detection_sources) > 1:
            logger.info(f"Multiple detection sources: {self._detection_sources}")
        
        # Production-specific validations
        if environment == Environment.PRODUCTION:
            # Check for production safeguards
            if not self._check_production_safeguards():
                logger.error("Production safeguards not in place!")
                return False
        
        return True
    
    def _check_production_safeguards(self) -> bool:
        """Check if production safeguards are in place"""
        safeguards = []
        
        # Check for debug mode
        if os.environ.get('DEBUG', '').lower() in ['true', '1']:
            logger.error("DEBUG mode enabled in production!")
            safeguards.append(False)
        else:
            safeguards.append(True)
        
        # Check for test database
        db_name = os.environ.get('DB_NAME', '')
        if 'test' in db_name.lower() or 'dev' in db_name.lower():
            logger.error(f"Test/dev database in production: {db_name}")
            safeguards.append(False)
        else:
            safeguards.append(True)
        
        return all(safeguards)
    
    def get_environment_info(self) -> Dict[str, any]:
        """
        Get comprehensive environment information.
        
        Returns:
            Dictionary with environment detection details
        """
        environment = self.detect_environment()
        
        return {
            'environment': str(environment),
            'detection_sources': self._detection_sources,
            'kubernetes_available': self._kubernetes_available,
            'hostname': socket.gethostname(),
            'validation_passed': self.validate_environment(environment)
        }


# Global environment detector instance
_environment_detector: Optional[EnvironmentDetector] = None


def get_environment(force_redetect: bool = False) -> Environment:
    """
    Get the current environment using the global detector.
    
    Args:
        force_redetect: Force re-detection even if cached
        
    Returns:
        Current Environment enum value
    """
    global _environment_detector
    
    if _environment_detector is None:
        _environment_detector = EnvironmentDetector()
    
    return _environment_detector.detect_environment(force_redetect=force_redetect)


def get_environment_info() -> Dict[str, any]:
    """
    Get comprehensive environment information.
    
    Returns:
        Dictionary with environment detection details
    """
    global _environment_detector
    
    if _environment_detector is None:
        _environment_detector = EnvironmentDetector()
    
    return _environment_detector.get_environment_info()


def is_development() -> bool:
    """Check if current environment is development"""
    return get_environment() == Environment.DEVELOPMENT


def is_staging() -> bool:
    """Check if current environment is staging"""
    return get_environment() == Environment.STAGING


def is_production() -> bool:
    """Check if current environment is production"""
    return get_environment() == Environment.PRODUCTION


def require_production(func):
    """
    Decorator to require production environment.
    
    Raises:
    EnvironmentDetectionError: If not in production
    """
    def wrapper(*args, **kwargs):
        if not is_production():
            raise EnvironmentDetectionError(
                f"{func.__name__} requires production environment"
            )
        return func(*args, **kwargs)
    return wrapper


def require_non_production(func):
    """
    Decorator to require non-production environment.
    
    Raises:
    EnvironmentDetectionError: If in production
    """
    def wrapper(*args, **kwargs):
        if is_production():
            raise EnvironmentDetectionError(
                f"{func.__name__} not allowed in production environment"
            )
        return func(*args, **kwargs)
    return wrapper


# Convenience functions for common checks
def is_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    return os.environ.get('DEBUG', '').lower() in ['true', '1']


def is_kubernetes() -> bool:
    """Check if running in Kubernetes"""
    global _environment_detector
    if _environment_detector is None:
        _environment_detector = EnvironmentDetector()
    return _environment_detector._kubernetes_available


if __name__ == '__main__':
    # Test environment detection
    logging.basicConfig(level=logging.DEBUG)
    
    print("=== Environment Detection Test ===")
    print(f"Detected Environment: {get_environment()}")
    print(f"Environment Info: {json.dumps(get_environment_info(), indent=2)}")
    print(f"Is Development: {is_development()}")
    print(f"Is Staging: {is_staging()}")
    print(f"Is Production: {is_production()}")
    print(f"Is Debug Mode: {is_debug_mode()}")
    print(f"Is Kubernetes: {is_kubernetes()}")