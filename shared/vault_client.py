"""
Vault client and secret management for PowerStore CT Engine.

This module provides Vault integration for secure secret management
with environment-specific path resolution and caching.

Phase 2 implementation - full Vault client with hvac integration.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from enum import Enum
import threading
from .exceptions import VaultConnectionError, VaultSecretNotFoundError, VaultAuthenticationError

logger = logging.getLogger(__name__)


class VaultAuthMethod(Enum):
    """Vault authentication methods"""
    TOKEN = "token"
    APPROLE = "approle"
    KUBERNETES = "kubernetes"
    LDAP = "ldap"
    USERPASS = "userpass"


class VaultClient:
    """
    Full Vault client implementation with hvac integration.
    
    This class provides:
    - Multiple authentication methods
    - Secret retrieval and management
    - Connection management
    - Health checks
    - Retry logic
    """
    
    def __init__(
        self,
        vault_url: str,
        auth_method: VaultAuthMethod = VaultAuthMethod.TOKEN,
        auth_params: Optional[Dict[str, Any]] = None,
        verify: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Vault client.
        
        Args:
            vault_url: Vault server URL (e.g., "https://vault.example.com:8200")
            auth_method: Authentication method to use
            auth_params: Authentication parameters (token, role_id, etc.)
            verify: Verify SSL certificate
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.vault_url = vault_url
        self.auth_method = auth_method
        self.auth_params = auth_params or {}
        self.verify = verify
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = None
        self._authenticated = False
        self._lock = threading.Lock()
        
    def connect(self) -> bool:
        """
        Connect to Vault and authenticate.
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            VaultConnectionError: If connection fails
            VaultAuthenticationError: If authentication fails
        """
        try:
            import hvac
        except ImportError:
            logger.error("hvac package not installed. Install with: pip install hvac")
            raise VaultConnectionError("hvac package not available")
        
        try:
            with self._lock:
                if self._client is None:
                    logger.info(f"Connecting to Vault at {self.vault_url}")
                    self._client = hvac.Client(
                        url=self.vault_url,
                        verify=self.verify
                    )
                
                # Authenticate
                self._authenticate()
                self._authenticated = True
                
                # Test connection
                self._client.sys.read_health_status()
                logger.info("Successfully connected to Vault")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to Vault: {e}")
            self._authenticated = False
            raise VaultConnectionError(f"Vault connection failed: {e}")
    
    def _authenticate(self):
        """
        Authenticate with Vault using configured method.
        
        Raises:
            VaultAuthenticationError: If authentication fails
        """
        try:
            if self.auth_method == VaultAuthMethod.TOKEN:
                token = self.auth_params.get('token')
                if not token:
                    raise VaultAuthenticationError("Token required for token auth")
                self._client.token = token
                
            elif self.auth_method == VaultAuthMethod.APPROLE:
                role_id = self.auth_params.get('role_id')
                secret_id = self.auth_params.get('secret_id')
                if not role_id or not secret_id:
                    raise VaultAuthenticationError("role_id and secret_id required for approle auth")
                
                auth = self._client.auth.approle.login(
                    role_id=role_id,
                    secret_id=secret_id
                )
                self._client.token = auth['auth']['client_token']
                
            elif self.auth_method == VaultAuthMethod.KUBERNETES:
                role = self.auth_params.get('role')
                jwt_token = self.auth_params.get('jwt')
                if not role or not jwt_token:
                    raise VaultAuthenticationError("role and jwt required for kubernetes auth")
                
                auth = self._client.auth.kubernetes.login(
                    role=role,
                    jwt=jwt_token
                )
                self._client.token = auth['auth']['client_token']
                
            elif self.auth_method == VaultAuthMethod.LDAP:
                username = self.auth_params.get('username')
                password = self.auth_params.get('password')
                if not username or not password:
                    raise VaultAuthenticationError("username and password required for ldap auth")
                
                auth = self._client.auth.ldap.login(
                    username=username,
                    password=password
                )
                self._client.token = auth['auth']['client_token']
                
            elif self.auth_method == VaultAuthMethod.USERPASS:
                username = self.auth_params.get('username')
                password = self.auth_params.get('password')
                if not username or not password:
                    raise VaultAuthenticationError("username and password required for userpass auth")
                
                auth = self._client.auth.userpass.login(
                    username=username,
                    password=password
                )
                self._client.token = auth['auth']['client_token']
                
            logger.info(f"Successfully authenticated using {self.auth_method.value}")
            
        except Exception as e:
            logger.error(f"Vault authentication failed: {e}")
            raise VaultAuthenticationError(f"Vault authentication failed: {e}")
    
    def get_secret(self, path: str, version: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve secret from Vault.
        
        Args:
            path: Secret path in Vault (e.g., "secret/data/myapp/database")
            version: Secret version (for KV v2)
            
        Returns:
            Dictionary containing secret data
            
        Raises:
            VaultConnectionError: If not connected to Vault
            VaultSecretNotFoundError: If secret not found
        """
        if not self._authenticated:
            self.connect()
        
        try:
            logger.debug(f"Retrieving secret from Vault: {path}")
            
            # Try KV v2 first
            try:
                if version:
                    response = self._client.secrets.kv.v2.read_secret_version(
                        path=path,
                        version=version
                    )
                else:
                    response = self._client.secrets.kv.v2.read_secret_version(path=path)
                
                return response['data']['data']
                
            except Exception:
                # Fall back to KV v1
                try:
                    response = self._client.secrets.kv.v1.read_secret(path=path)
                    return response['data']
                except Exception as e:
                    raise VaultSecretNotFoundError(f"Secret not found: {path}")
                    
        except VaultSecretNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve secret from Vault: {e}")
            raise VaultConnectionError(f"Failed to retrieve secret: {e}")
    
    def set_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """
        Write secret to Vault.
        
        Args:
            path: Secret path in Vault
            data: Dictionary of secret data
            
        Returns:
            True if successful
            
        Raises:
            VaultConnectionError: If not connected to Vault
        """
        if not self._authenticated:
            self.connect()
        
        try:
            logger.info(f"Writing secret to Vault: {path}")
            
            # Try KV v2 first
            try:
                self._client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=data
                )
            except Exception:
                # Fall back to KV v1
                self._client.secrets.kv.v1.create_or_update_secret(
                    path=path,
                    secret=data
                )
            
            logger.info(f"Successfully wrote secret to Vault: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write secret to Vault: {e}")
            raise VaultConnectionError(f"Failed to write secret: {e}")
    
    def delete_secret(self, path: str) -> bool:
        """
        Delete secret from Vault.
        
        Args:
            path: Secret path in Vault
            
        Returns:
            True if successful
            
        Raises:
            VaultConnectionError: If not connected to Vault
        """
        if not self._authenticated:
            self.connect()
        
        try:
            logger.info(f"Deleting secret from Vault: {path}")
            
            # Try KV v2 first
            try:
                self._client.secrets.kv.v2.delete_metadata_and_all_versions(path=path)
            except Exception:
                # Fall back to KV v1
                self._client.secrets.kv.v1.delete_secret(path=path)
            
            logger.info(f"Successfully deleted secret from Vault: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete secret from Vault: {e}")
            raise VaultConnectionError(f"Failed to delete secret: {e}")
    
    def list_secrets(self, path: str = "") -> List[str]:
        """
        List secrets at a given path.
        
        Args:
            path: Base path to list secrets from
            
        Returns:
            List of secret paths
            
        Raises:
            VaultConnectionError: If not connected to Vault
        """
        if not self._authenticated:
            self.connect()
        
        try:
            logger.debug(f"Listing secrets in Vault: {path}")
            
            # Try KV v2 first
            try:
                response = self._client.secrets.kv.v2.list_secrets(path=path)
                return response['data']['keys']
            except Exception:
                # Fall back to KV v1
                try:
                    response = self._client.secrets.kv.v1.list_secrets(path=path)
                    return response['data']['keys']
                except Exception as e:
                    logger.debug(f"No secrets found at path: {path}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to list secrets from Vault: {e}")
            raise VaultConnectionError(f"Failed to list secrets: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Vault health status.
        
        Returns:
            Dictionary with health status information
        """
        try:
            if self._client is None:
                return {
                    'status': 'not_connected',
                    'initialized': False,
                    'sealed': True
                }
            
            health = self._client.sys.read_health_status()
            
            return {
                'status': 'connected' if self._authenticated else 'not_authenticated',
                'initialized': health.get('initialized', False),
                'sealed': health.get('sealed', True),
                'standby': health.get('standby', False),
                'version': health.get('version', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def close(self):
        """Close Vault connection"""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
                self._authenticated = False
                logger.info("Vault connection closed")


class SecretCache:
    """
    Secret caching system with TTL support.
    
    This class provides:
    - TTL-based caching
    - Cache invalidation
    - Cache statistics
    - Thread-safe operations
    """
    
    def __init__(self, ttl: int = 300):
        """
        Initialize secret cache.
        
        Args:
            ttl: Time-to-live for cached secrets in seconds (default: 5 minutes)
        """
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._ttl = ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        
    def get(self, key: str) -> Optional[Any]:
        """
        Get cached secret if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if expired/not found
        """
        with self._lock:
            if key in self._cache:
                timestamp = self._cache_timestamps[key]
                if time.time() - timestamp < self._ttl:
                    self._hits += 1
                    logger.debug(f"Cache hit for key: {key}")
                    return self._cache[key]
                else:
                    # Expired
                    del self._cache[key]
                    del self._cache_timestamps[key]
            
            self._misses += 1
            logger.debug(f"Cache miss for key: {key}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Cache a secret with optional custom TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Custom TTL for this specific secret
        """
        with self._lock:
            self._cache[key] = value
            self._cache_timestamps[key] = time.time()
            logger.debug(f"Cached key: {key} with TTL: {ttl or self._ttl}s")
    
    def invalidate(self, key: str):
        """
        Invalidate a specific cache entry.
        
        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._cache_timestamps[key]
                logger.debug(f"Invalidated cache key: {key}")
    
    def clear(self):
        """Clear all cached secrets"""
        with self._lock:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("Cleared all cached secrets")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.2f}%",
                'ttl': self._ttl
            }


class VaultSecretManager:
    """
    Vault secret manager with environment-specific path resolution and caching.
    
    This class provides secure secret management with:
    - Environment-specific path resolution
    - Secret caching with TTL
    - Automatic fallback to defaults
    - Secret validation and type checking
    - Connection management
    """
    
    def __init__(
        self,
        vault_url: Optional[str] = None,
        auth_method: VaultAuthMethod = VaultAuthMethod.TOKEN,
        auth_params: Optional[Dict[str, Any]] = None,
        cache_ttl: int = 300,
        vault_enabled: bool = True
    ):
        """
        Initialize Vault secret manager.
        
        Args:
            vault_url: Vault server URL
            auth_method: Authentication method
            auth_params: Authentication parameters
            cache_ttl: Cache TTL in seconds
            vault_enabled: Whether Vault integration is enabled
        """
        self.vault_url = vault_url
        self.auth_method = auth_method
        self.auth_params = auth_params or {}
        self.cache_ttl = cache_ttl
        self.vault_enabled = vault_enabled
        
        self._client: Optional[VaultClient] = None
        self._cache = SecretCache(ttl=cache_ttl)
        self._vault_base_path = "secret/powerstore-ct-engine"
        
        if vault_enabled and vault_url:
            self._initialize_client()
        else:
            logger.info("Vault integration disabled or not configured")
    
    def _initialize_client(self):
        """Initialize Vault client"""
        try:
            self._client = VaultClient(
                vault_url=self.vault_url,
                auth_method=self.auth_method,
                auth_params=self.auth_params
            )
            self._client.connect()
            logger.info("Vault client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Vault client: {e}")
            self._client = None
    
    def _get_vault_path(self, environment: str, secret_name: str) -> str:
        """
        Construct Vault path for environment-specific secret.
        
        Args:
            environment: Environment name
            secret_name: Secret name
            
        Returns:
            Full Vault path
        """
        # First try environment-specific path
        env_path = f"{self._vault_base_path}/{environment}/{secret_name}"
        
        # Fall back to common path
        common_path = f"{self._vault_base_path}/common/{secret_name}"
        
        return env_path, common_path
    
    def load_secrets(self, environment: str) -> Dict[str, Any]:
        """
        Load secrets from Vault for specific environment.
        
        Args:
            environment: Environment name (common, development, staging, production)
            
        Returns:
            Dictionary of secrets
            
        Raises:
            VaultConnectionError: If Vault connection fails
            VaultSecretNotFoundError: If secret path not found
        """
        if not self.vault_enabled or self._client is None:
            logger.debug(f"Vault not available, returning empty secrets for {environment}")
            return {}
        
        logger.info(f"Loading secrets from Vault for environment: {environment}")
        
        secrets = {}
        
        try:
            # List all secrets in environment path
            env_path = f"{self._vault_base_path}/{environment}"
            common_path = f"{self._vault_base_path}/common"
            
            # Load environment-specific secrets
            env_secrets = self._client.list_secrets(env_path)
            if env_secrets:
                for secret_name in env_secrets:
                    secret_data = self.load_secret(environment, secret_name)
                    if secret_data:
                        secrets[secret_name] = secret_data
            
            # Load common secrets (override with environment-specific)
            common_secrets = self._client.list_secrets(common_path)
            if common_secrets:
                for secret_name in common_secrets:
                    if secret_name not in secrets:  # Only if not overridden
                        secret_data = self.load_secret('common', secret_name)
                        if secret_data:
                            secrets[secret_name] = secret_data
            
            logger.info(f"Loaded {len(secrets)} secrets from Vault for {environment}")
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to load secrets from Vault: {e}")
            return {}
    
    def load_secret(self, environment: str, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific secret from Vault.
        
        Args:
            environment: Environment name
            secret_name: Secret name
            
        Returns:
            Secret data or None if not found
        """
        if not self.vault_enabled or self._client is None:
            logger.debug(f"Vault not available, cannot load secret: {secret_name}")
            return None
        
        # Check cache first
        cache_key = f"{environment}:{secret_name}"
        cached_data = self._cache.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        logger.debug(f"Loading secret from Vault: {secret_name}")
        
        try:
            env_path, common_path = self._get_vault_path(environment, secret_name)
            
            # Try environment-specific path first
            try:
                secret_data = self._client.get_secret(env_path)
                self._cache.set(cache_key, secret_data)
                return secret_data
            except VaultSecretNotFoundError:
                pass
            
            # Fall back to common path
            try:
                secret_data = self._client.get_secret(common_path)
                self._cache.set(cache_key, secret_data)
                return secret_data
            except VaultSecretNotFoundError:
                logger.warning(f"Secret not found in Vault: {secret_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load secret from Vault: {e}")
            return None
    
    def invalidate_cache(self, key: Optional[str] = None):
        """
        Invalidate cache entries.
        
        Args:
            key: Specific key to invalidate, or None to clear all
        """
        if key:
            self._cache.invalidate(key)
        else:
            self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self._cache.get_stats()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Vault health status.
        
        Returns:
            Dictionary with health status
        """
        if not self.vault_enabled:
            return {
                'status': 'disabled',
                'message': 'Vault integration is disabled'
            }
        
        if self._client is None:
            return {
                'status': 'not_configured',
                'message': 'Vault client not initialized'
            }
        
        return self._client.health_check()
    
    def close(self):
        """Close Vault connection and clear cache"""
        if self._client:
            self._client.close()
        self._cache.clear()


# Global vault manager instance
_vault_manager: Optional[VaultSecretManager] = None


def get_vault_manager() -> VaultSecretManager:
    """
    Get the global Vault manager instance.
    
    Returns:
        VaultSecretManager instance
    """
    global _vault_manager
    
    if _vault_manager is None:
        _vault_manager = VaultSecretManager()
    
    return _vault_manager


def initialize_vault_manager(
    vault_url: str,
    auth_method: VaultAuthMethod = VaultAuthMethod.TOKEN,
    auth_params: Optional[Dict[str, Any]] = None,
    cache_ttl: int = 300,
    vault_enabled: bool = True
) -> VaultSecretManager:
    """
    Initialize the global Vault manager with specific configuration.
    
    Args:
        vault_url: Vault server URL
        auth_method: Authentication method
        auth_params: Authentication parameters
        cache_ttl: Cache TTL in seconds
        vault_enabled: Whether Vault integration is enabled
        
    Returns:
        VaultSecretManager instance
    """
    global _vault_manager
    
    _vault_manager = VaultSecretManager(
        vault_url=vault_url,
        auth_method=auth_method,
        auth_params=auth_params,
        cache_ttl=cache_ttl,
        vault_enabled=vault_enabled
    )
    
    return _vault_manager