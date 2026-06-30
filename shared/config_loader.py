"""
Configuration loader with precedence system for PowerStore CT Engine.

This module implements a sophisticated configuration loading system with
clear precedence rules: Environment variables > Config files > Vault > Defaults.
"""

import os
import logging
from typing import Dict, Any, Optional, Type
from pathlib import Path
from dotenv import load_dotenv
import json

from .environment import Environment, get_environment
from .config.base import BaseConfig
from .config.development import DevelopmentConfig
from .config.staging import StagingConfig
from .config.production import ProductionConfig
from .config.validation import ConfigValidator, validate_config_dict
from .exceptions import ConfigurationLoadError, ConfigurationValidationError

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Configuration loader with precedence system.
    
    Implements configuration loading with the following precedence:
    1. Environment variables (ENV_* prefix) - Highest priority
    2. Environment-specific config files (config.{environment}.py)
    3. Base configuration file (config/base.py)
    4. Vault secrets (environment-specific paths)
    5. Default values (hardcoded fallbacks) - Lowest priority
    """
    
    # Environment to config class mapping
    ENVIRONMENT_CONFIGS = {
        Environment.DEVELOPMENT: DevelopmentConfig,
        Environment.STAGING: StagingConfig,
        Environment.PRODUCTION: ProductionConfig
    }
    
    def __init__(self):
        """Initialize configuration loader"""
        self._environment: Optional[Environment] = None
        self._config_class: Optional[Type[BaseConfig]] = None
        self._loaded_config: Dict[str, Any] = {}
        self._config_sources: Dict[str, str] = {}
        self._validator = ConfigValidator()
        
    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load configuration with precedence system.
        
        Args:
            force_reload: Force reload even if already loaded
            
        Returns:
            Loaded configuration dictionary
            
        Raises:
            ConfigurationLoadError: If configuration loading fails
        """
        if self._loaded_config and not force_reload:
            logger.debug("Using cached configuration")
            return self._loaded_config
        
        logger.info("Loading configuration with precedence system...")
        
        try:
            # Step 1: Detect environment
            self._environment = get_environment()
            logger.info(f"Detected environment: {self._environment}")
            
            # Step 2: Load base configuration (lowest priority)
            base_config = self._load_base_config()
            self._loaded_config.update(base_config)
            self._config_sources['base'] = 'base_config'
            
            # Step 3: Load environment-specific configuration
            env_config = self._load_environment_config()
            self._loaded_config.update(env_config)
            self._config_sources['environment'] = f'config.{self._environment.value}'
            
            # Step 4: Load from Vault (if enabled)
            if env_config.get('VAULT_ENABLED', False):
                vault_config = self._load_vault_config()
                self._loaded_config.update(vault_config)
                self._config_sources['vault'] = 'vault_secrets'
            
            # Step 5: Load from environment variables (highest priority)
            env_var_config = self._load_environment_variables()
            self._loaded_config.update(env_var_config)
            self._config_sources['environment_variables'] = 'ENV_*'
            
            # Step 6: Validate final configuration
            self._validate_loaded_config()
            
            logger.info(f"Configuration loaded successfully from sources: {self._config_sources}")
            return self._loaded_config
            
        except Exception as e:
            error_msg = f"Configuration loading failed: {str(e)}"
            logger.error(error_msg)
            raise ConfigurationLoadError(error_msg)
    
    def _load_base_config(self) -> Dict[str, Any]:
        """Load base configuration with defaults"""
        logger.debug("Loading base configuration...")
        
        try:
            # Convert BaseConfig class to dictionary
            config_dict = {}
            for key, value in BaseConfig.__dict__.items():
                if not key.startswith('_') and not callable(value):
                    config_dict[key] = value
            
            logger.debug(f"Loaded {len(config_dict)} base configuration values")
            return config_dict
            
        except Exception as e:
            logger.error(f"Failed to load base configuration: {e}")
            raise ConfigurationLoadError(f"Base configuration load failed: {e}")
    
    def _load_environment_config(self) -> Dict[str, Any]:
        """Load environment-specific configuration"""
        logger.debug(f"Loading {self._environment} environment configuration...")
        
        try:
            config_class = self.ENVIRONMENT_CONFIGS.get(self._environment, BaseConfig)
            self._config_class = config_class
            
            # Convert environment config class to dictionary
            config_dict = {}
            for key, value in config_class.__dict__.items():
                if not key.startswith('_') and not callable(value):
                    config_dict[key] = value
            
            logger.debug(f"Loaded {len(config_dict)} environment-specific values")
            return config_dict
            
        except Exception as e:
            logger.error(f"Failed to load environment configuration: {e}")
            raise ConfigurationLoadError(f"Environment configuration load failed: {e}")
    
    def _load_vault_config(self) -> Dict[str, Any]:
        """Load configuration from Vault secrets"""
        logger.debug("Loading Vault configuration...")
        
        try:
            # Import vault client if available
            try:
                from .vault_client import VaultSecretManager, VaultAuthMethod, initialize_vault_manager
            except ImportError:
                logger.warning("Vault client not available, skipping Vault config")
                return {}
            
            # Get Vault configuration from environment config
            vault_enabled = self._loaded_config.get('VAULT_ENABLED', False)
            vault_url = self._loaded_config.get('VAULT_URL')
            vault_auth_method = self._loaded_config.get('VAULT_AUTH_METHOD', 'token')
            
            if not vault_enabled or not vault_url:
                logger.debug("Vault not enabled or not configured, skipping Vault config")
                return {}
            
            # Determine auth method
            try:
                auth_method = VaultAuthMethod(vault_auth_method)
            except ValueError:
                logger.warning(f"Invalid Vault auth method: {vault_auth_method}")
                return {}
            
            # Prepare auth parameters
            auth_params = {}
            
            if vault_auth_method == 'token':
                auth_params['token'] = os.getenv('VAULT_TOKEN')
            elif vault_auth_method == 'approle':
                auth_params['role_id'] = os.getenv('VAULT_ROLE_ID')
                auth_params['secret_id'] = os.getenv('VAULT_SECRET_ID')
            elif vault_auth_method == 'kubernetes':
                auth_params['role'] = self._loaded_config.get('VAULT_KUBERNETES_ROLE')
                auth_params['jwt'] = self._get_kubernetes_jwt()
            elif vault_auth_method == 'ldap':
                auth_params['username'] = os.getenv('VAULT_LDAP_USERNAME')
                auth_params['password'] = os.getenv('VAULT_LDAP_PASSWORD')
            elif vault_auth_method == 'userpass':
                auth_params['username'] = os.getenv('VAULT_USERNAME')
                auth_params['password'] = os.getenv('VAULT_PASSWORD')
            
            # Get cache TTL from config
            cache_ttl = self._loaded_config.get('VAULT_SECRET_CACHE_TTL', 300)
            
            # Initialize Vault manager with configuration
            try:
                vault_manager = initialize_vault_manager(
                    vault_url=vault_url,
                    auth_method=auth_method,
                    auth_params=auth_params,
                    cache_ttl=cache_ttl,
                    vault_enabled=True
                )
                
                # Check Vault health
                health = vault_manager.health_check()
                logger.info(f"Vault health: {health['status']}")
                
                if health['status'] not in ['connected', 'disabled']:
                    logger.warning(f"Vault not healthy: {health['status']}, skipping Vault config")
                    return {}
                
            except Exception as e:
                logger.warning(f"Failed to initialize Vault manager: {e}")
                return {}
            
            # Load common secrets
            common_secrets = vault_manager.load_secrets('common')
            
            # Load environment-specific secrets
            env_secrets = vault_manager.load_secrets(self._environment.value)
            
            # Combine secrets (environment-specific override common)
            vault_config = {**common_secrets, **env_secrets}
            
            # Convert Vault secret names to config keys
            config_dict = self._convert_vault_secrets_to_config(vault_config)
            
            logger.debug(f"Loaded {len(config_dict)} Vault configuration values")
            return config_dict
            
        except Exception as e:
            logger.warning(f"Failed to load Vault configuration: {e}")
            return {}
    
    def _convert_vault_secrets_to_config(self, vault_secrets: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Vault secret names to configuration keys.
        
        Args:
            vault_secrets: Dictionary of Vault secrets
            
        Returns:
            Configuration dictionary
        """
        config_dict = {}
        
        # Mapping from Vault secret names to config keys
        secret_to_config_mapping = {
            'database_host': 'DATABASE_HOST',
            'database_port': 'DATABASE_PORT',
            'database_name': 'DATABASE_NAME',
            'database_user': 'DATABASE_USER',
            'database_password': 'DATABASE_PASSWORD',
            'jenkins_url': 'JENKINS_URL',
            'jenkins_username': 'JENKINS_USERNAME',
            'jenkins_password': 'JENKINS_PASSWORD',
            'ldap_bind_dn_password': 'LDAP_BIND_DN_PASSWORD',
            'app_secret_key': 'SECRET_KEY',
            'session_secret_key': 'SESSION_COOKIE_SECRET_KEY'
        }
        
        for secret_name, secret_value in vault_secrets.items():
            config_key = secret_to_config_mapping.get(secret_name, secret_name.upper())
            config_dict[config_key] = secret_value
        
        return config_dict
    
    def _load_environment_variables(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        logger.debug("Loading environment variables...")
        
        config_dict = {}
        
        # Load .env file if exists
        env_files = ['.env', '.env.local', f'.env.{self._environment.value}']
        for env_file in env_files:
            env_path = Path(env_file)
            if env_path.exists():
                logger.debug(f"Loading environment file: {env_file}")
                load_dotenv(env_path)
        
        # Load environment variables with ENV_ prefix
        for key, value in os.environ.items():
            if key.startswith('ENV_'):
                config_key = key[4:]  # Remove ENV_ prefix
                config_dict[config_key] = self._convert_env_value(value)
                logger.debug(f"Loaded environment variable: {config_key}")
        
        logger.debug(f"Loaded {len(config_dict)} environment variable values")
        return config_dict
    
    def _convert_env_value(self, value: str) -> Any:
        """
        Convert environment variable string value to appropriate type.
        
        Args:
            value: String value from environment variable
            
        Returns:
            Converted value (int, bool, str, etc.)
        """
        # Try to convert to boolean
        if value.lower() in ['true', '1', 'yes', 'on']:
            return True
        if value.lower() in ['false', '0', 'no', 'off']:
            return False
        
        # Try to convert to integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try to convert to float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try to parse as JSON (for lists/dicts)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Return as string
        return value
    
    def _validate_loaded_config(self) -> None:
        """Validate the loaded configuration"""
        logger.debug("Validating loaded configuration...")
        
        config_dict = self._loaded_config
        environment = self._environment.value
        
        try:
            validate_config_dict(config_dict, environment)
            logger.debug("Configuration validation passed")
        except ConfigurationValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if not self._loaded_config:
            self.load_config()
        
        return self._loaded_config.get(key, default)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get complete configuration dictionary"""
        if not self._loaded_config:
            self.load_config()
        
        return self._loaded_config.copy()
    
    def get_environment(self) -> Environment:
        """Get current environment"""
        if not self._environment:
            self._environment = get_environment()
        return self._environment
    
    def get_config_sources(self) -> Dict[str, str]:
        """Get configuration source information"""
        return self._config_sources.copy()
    
    def _get_kubernetes_jwt(self) -> Optional[str]:
        """
        Get Kubernetes JWT token for Vault authentication.
        
        Returns:
            JWT token string or None
        """
        try:
            # Try to read JWT from Kubernetes service account
            jwt_path = '/var/run/secrets/kubernetes.io/serviceaccount/token'
            
            if os.path.exists(jwt_path):
                with open(jwt_path, 'r') as f:
                    jwt_token = f.read().strip()
                logger.debug("Successfully read Kubernetes JWT token")
                return jwt_token
            else:
                logger.warning("Kubernetes JWT token file not found")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to read Kubernetes JWT token: {e}")
            return None
    
    def reload_config(self) -> Dict[str, Any]:
        """Reload configuration (clears cache)"""
        logger.info("Reloading configuration...")
        self._loaded_config = {}
        self._config_sources = {}
        return self.load_config(force_reload=True)


# Global configuration loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """
    Get the global configuration loader instance.
    
    Returns:
        ConfigLoader instance
    """
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader()
        _config_loader.load_config()
    
    return _config_loader


def get_config(key: str, default: Any = None) -> Any:
    """
    Convenience function to get configuration value.
    
    Args:
        key: Configuration key
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    loader = get_config_loader()
    return loader.get_config(key, default)


def get_config_dict() -> Dict[str, Any]:
    """
    Convenience function to get complete configuration dictionary.
    
    Returns:
        Complete configuration dictionary
    """
    loader = get_config_loader()
    return loader.get_config_dict()


def reload_config() -> Dict[str, Any]:
    """
    Convenience function to reload configuration.
    
    Returns:
        Reloaded configuration dictionary
    """
    loader = get_config_loader()
    return loader.reload_config()


# Backward compatibility functions for existing code
def get_database_uri(database_name: Optional[str] = None) -> str:
    """
    Get database URI (backward compatibility).
    
    Args:
        database_name: Override database name
        
    Returns:
        Database URI string
    """
    loader = get_config_loader()
    
    host = loader.get_config('DATABASE_HOST')
    port = loader.get_config('DATABASE_PORT')
    user = loader.get_config('DATABASE_USER')
    password = loader.get_config('DATABASE_PASSWORD')
    db_name = database_name or loader.get_config('DATABASE_NAME')
    ssl_mode = loader.get_config('DATABASE_SSL_MODE', 'prefer')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}?sslmode={ssl_mode}"


# Legacy config.py compatibility
class Config:
    """Legacy Config class for backward compatibility"""
    
    def __init__(self):
        """Initialize legacy Config with new loader"""
        self._loader = get_config_loader()
        self._config_dict = self._loader.get_config_dict()
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Flask-SQLAlchemy database URI (backward compatibility)"""
        return get_database_uri()
    
    @property
    def SQLALCHEMY_TRACK_MODIFICATIONS(self) -> bool:
        """SQLAlchemy track modifications (backward compatibility)"""
        return self._loader.get_config('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    
    @property
    def SECRET_KEY(self) -> str:
        """Flask secret key (backward compatibility)"""
        return self._loader.get_config('SECRET_KEY', 'change-this-secret-key')
    
    def __getattr__(self, name: str) -> Any:
        """Dynamic attribute access for backward compatibility"""
        return self._loader.get_config(name, None)


if __name__ == '__main__':
    # Test configuration loader
    logging.basicConfig(level=logging.DEBUG)
    
    print("=== Configuration Loader Test ===")
    loader = ConfigLoader()
    config = loader.load_config()
    
    print(f"Environment: {loader.get_environment()}")
    print(f"Config Sources: {loader.get_config_sources()}")
    print(f"Database Host: {loader.get_config('DATABASE_HOST')}")
    print(f"Jenkins URL: {loader.get_config('JENKINS_URL')}")
    print(f"Debug Mode: {loader.get_config('DEBUG')}")
    
    print("\n=== Backward Compatibility Test ===")
    print(f"Database URI: {get_database_uri()}")
    print(f"Config Dict Keys: {list(get_config_dict().keys())[:10]}")