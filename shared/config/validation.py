"""
Configuration validation framework for PowerStore CT Engine.

This module provides schema-based configuration validation using Pydantic
to ensure all required configuration is present and valid per environment.
"""

import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError
from enum import Enum
import logging

from ..exceptions import ConfigurationValidationError

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Environment enumeration for validation"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseConfig(BaseModel):
    """Database configuration validation schema"""
    host: str = Field(..., description="Database host address")
    port: int = Field(..., ge=1, le=65535, description="Database port")
    name: str = Field(..., min_length=1, description="Database name")
    user: str = Field(..., min_length=1, description="Database username")
    password: str = Field(..., min_length=8, description="Database password")
    ssl_mode: str = Field(default="prefer", description="SSL mode")
    pool_size: int = Field(default=5, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, le=50, description="Max overflow connections")
    
    @field_validator('host')
    @classmethod
    def validate_host(cls, v):
        """Validate database host format"""
        if not re.match(r'^[\w\.\-]+$', v):
            raise ConfigurationValidationError(
                f"Invalid database host format: {v}",
                field_name="host",
                value=v
            )
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate database name"""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ConfigurationValidationError(
                f"Invalid database name format: {v}",
                field_name="name",
                value=v
            )
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ConfigurationValidationError(
                "Database password must be at least 8 characters",
                field_name="password"
            )
        return v


class JenkinsConfig(BaseModel):
    """Jenkins configuration validation schema"""
    url: str = Field(..., description="Jenkins server URL")
    username: str = Field(..., min_length=1, description="Jenkins username")
    password: str = Field(..., min_length=1, description="Jenkins password")
    timeout: int = Field(default=300, ge=30, le=1800, description="Jenkins timeout in seconds")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    retry_delay: int = Field(default=5, ge=1, le=60, description="Retry delay in seconds")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate Jenkins URL format"""
        if not re.match(r'^https?://', v):
            raise ConfigurationValidationError(
                f"Jenkins URL must start with http:// or https://: {v}",
                field_name="url",
                value=v
            )
        return v


class LDAPConfig(BaseModel):
    """LDAP configuration validation schema"""
    url: str = Field(..., description="LDAP server URL")
    base_dn: str = Field(..., min_length=1, description="LDAP base DN")
    bind_dn: str = Field(..., min_length=1, description="LDAP bind DN")
    use_ssl: bool = Field(default=True, description="Use SSL for LDAP")
    connect_timeout: int = Field(default=10, ge=1, le=60, description="Connection timeout")
    search_timeout: int = Field(default=5, ge=1, le=30, description="Search timeout")
    
    @field_validator('url')
    @classmethod
    def validate_ldap_url(cls, v):
        """Validate LDAP URL format"""
        if not re.match(r'^ldaps?://', v):
            raise ConfigurationValidationError(
                f"LDAP URL must start with ldap:// or ldaps://: {v}",
                field_name="url",
                value=v
            )
        return v


class VaultConfig(BaseModel):
    """Vault configuration validation schema"""
    enabled: bool = Field(default=False, description="Vault integration enabled")
    url: str = Field(default="", description="Vault server URL")
    role: str = Field(default="", description="Vault role")
    secret_path: str = Field(default="", description="Vault secret base path")
    auth_method: str = Field(default="kubernetes", description="Vault authentication method")
    token_ttl: int = Field(default=3600, ge=300, le=86400, description="Token TTL in seconds")
    cache_ttl: int = Field(default=300, ge=60, le=3600, description="Cache TTL in seconds")
    
    @model_validator(mode='after')
    def validate_vault_url(self):
        """Validate Vault URL format if Vault is enabled"""
        if self.enabled and self.url and not re.match(r'^https?://', self.url):
            raise ConfigurationValidationError(
                f"Vault URL must start with http:// or https:// when enabled: {self.url}",
                field_name="url",
                value=self.url
            )
        return self


class SecurityConfig(BaseModel):
    """Security configuration validation schema"""
    secret_key: str = Field(..., min_length=32, description="Application secret key")
    session_cookie_secure: bool = Field(default=False, description="Use secure cookies")
    session_cookie_httponly: bool = Field(default=True, description="HTTP only cookies")
    session_samesite: str = Field(default="Lax", description="SameSite cookie policy")
    
    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        """Validate secret key strength"""
        if len(v) < 32:
            raise ConfigurationValidationError(
                "Secret key must be at least 32 characters",
                field_name="secret_key"
            )
        return v
    
    @field_validator('session_samesite')
    @classmethod
    def validate_samesite(cls, v):
        """Validate SameSite policy"""
        valid_values = ['Strict', 'Lax', 'None']
        if v not in valid_values:
            raise ConfigurationValidationError(
                f"SameSite must be one of {valid_values}",
                field_name="session_samesite",
                value=v
            )
        return v


class AppConfig(BaseModel):
    """Complete application configuration validation schema"""
    environment: Environment
    debug: bool = Field(default=False, description="Debug mode")
    database: DatabaseConfig
    jenkins: JenkinsConfig
    ldap: LDAPConfig
    vault: VaultConfig
    security: SecurityConfig
    
    @model_validator(mode='after')
    def validate_production_settings(self):
        """Validate production-specific security requirements"""
        if self.environment == Environment.PRODUCTION:
            if self.debug:
                raise ConfigurationValidationError(
                    "DEBUG must be False in production",
                    field_name="debug"
                )
            if not self.security.session_cookie_secure:
                raise ConfigurationValidationError(
                    "SESSION_COOKIE_SECURE must be True in production",
                    field_name="session_cookie_secure"
                )
        return self


class ConfigValidator:
    """
    Configuration validator with schema-based validation.
    
    Provides comprehensive validation for all configuration sections
    with environment-specific rules and dependencies.
    """
    
    def __init__(self):
        """Initialize configuration validator"""
        self._errors: List[ConfigurationValidationError] = []
        self._warnings: List[str] = []
    
    def validate_config(self, config_dict: Dict[str, Any], environment: str) -> bool:
        """
        Validate complete configuration against schema.
        
        Args:
            config_dict: Configuration dictionary to validate
            environment: Environment name (development, staging, production)
            
        Returns:
            True if validation passes, False otherwise
            
        Raises:
            ConfigurationValidationError: If validation fails
        """
        self._errors = []
        self._warnings = []
        
        logger.info(f"Validating configuration for environment: {environment}")
        
        try:
            # Convert environment string to enum
            env_enum = Environment(environment)
            
            # Build configuration model with Pydantic V2 error handling
            try:
                app_config = AppConfig(
                    environment=env_enum,
                    debug=config_dict.get('DEBUG', False),
                    database=DatabaseConfig(
                        host=config_dict.get('DATABASE_HOST', ''),
                        port=config_dict.get('DATABASE_PORT', 5432),
                        name=config_dict.get('DATABASE_NAME', ''),
                        user=config_dict.get('DATABASE_USER', ''),
                        password=config_dict.get('DATABASE_PASSWORD', ''),
                        ssl_mode=config_dict.get('DATABASE_SSL_MODE', 'prefer'),
                        pool_size=config_dict.get('DATABASE_POOL_SIZE', 5),
                        max_overflow=config_dict.get('DATABASE_MAX_OVERFLOW', 10)
                    ),
                    jenkins=JenkinsConfig(
                        url=config_dict.get('JENKINS_URL', ''),
                        username=config_dict.get('JENKINS_USERNAME', ''),
                        password=config_dict.get('JENKINS_PASSWORD', ''),
                        timeout=config_dict.get('JENKINS_TIMEOUT', 300),
                        retry_attempts=config_dict.get('JENKINS_RETRY_ATTEMPTS', 3),
                        retry_delay=config_dict.get('JENKINS_RETRY_DELAY', 5)
                    ),
                    ldap=LDAPConfig(
                        url=config_dict.get('LDAP_URL', ''),
                        base_dn=config_dict.get('LDAP_BASE_DN', ''),
                        bind_dn=config_dict.get('LDAP_BIND_DN', ''),
                        use_ssl=config_dict.get('LDAP_USE_SSL', True),
                        connect_timeout=config_dict.get('LDAP_CONNECT_TIMEOUT', 10),
                        search_timeout=config_dict.get('LDAP_SEARCH_TIMEOUT', 5)
                    ),
                    vault=VaultConfig(
                        enabled=config_dict.get('VAULT_ENABLED', False),
                        url=config_dict.get('VAULT_URL', ''),
                        role=config_dict.get('VAULT_ROLE', ''),
                        secret_path=config_dict.get('VAULT_SECRET_PATH', ''),
                        auth_method=config_dict.get('VAULT_AUTH_METHOD', 'kubernetes'),
                        token_ttl=config_dict.get('VAULT_TOKEN_TTL', 3600),
                        cache_ttl=config_dict.get('VAULT_SECRET_CACHE_TTL', 300)
                    ),
                    security=SecurityConfig(
                        secret_key=config_dict.get('SECRET_KEY', ''),
                        session_cookie_secure=config_dict.get('SESSION_COOKIE_SECURE', False),
                        session_cookie_httponly=config_dict.get('SESSION_COOKIE_HTTPONLY', True),
                        session_samesite=config_dict.get('SESSION_COOKIE_SAMESITE', 'Lax')
                    )
                )
            except ValidationError as e:
                # Convert Pydantic V2 validation errors to our format
                for error in e.errors():
                    field_name = '.'.join(str(loc) for loc in error['loc']) if error['loc'] else 'general'
                    message = error['msg']
                    input_value = error.get('input') if 'input' in error else None
                    self._errors.append(ConfigurationValidationError(
                        f"{field_name}: {message}",
                        field_name=field_name,
                        value=input_value
                    ))
                raise ConfigurationValidationError(
                    f"Configuration validation failed: {str(e)}"
                )
            
            # Environment-specific validation
            self._validate_environment_specific(config_dict, env_enum)
            
            # Check for warnings
            if self._warnings:
                for warning in self._warnings:
                    logger.warning(f"Configuration warning: {warning}")
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            error_msg = f"Configuration validation failed: {str(e)}"
            logger.error(error_msg)
            self._errors.append(ConfigurationValidationError(error_msg))
            return False
    
    def _validate_environment_specific(self, config_dict: Dict[str, Any], environment: Environment):
        """
        Validate environment-specific configuration rules.
        
        Args:
            config_dict: Configuration dictionary
            environment: Environment enum
        """
        if environment == Environment.PRODUCTION:
            # Production-specific validations
            if not config_dict.get('VAULT_ENABLED'):
                self._warnings.append("Vault should be enabled in production")
            
            if not config_dict.get('KUBERNETES_ENABLED'):
                self._warnings.append("Kubernetes should be enabled in production")
            
            if config_dict.get('LOG_LEVEL') == 'DEBUG':
                self._warnings.append("LOG_LEVEL should not be DEBUG in production")
            
            # Check for placeholder values
            placeholder_patterns = ['from-vault', 'change-this', 'default']
            for key, value in config_dict.items():
                if isinstance(value, str) and any(pattern in value.lower() for pattern in placeholder_patterns):
                    self._errors.append(ConfigurationValidationError(
                        f"Placeholder value detected for {key}: {value}",
                        field_name=key,
                        value=value
                    ))
        
        elif environment == Environment.DEVELOPMENT:
            # Development-specific validations
            if config_dict.get('SESSION_COOKIE_SECURE') and not config_dict.get('DEBUG'):
                self._warnings.append("SESSION_COOKIE_SECURE may cause issues in development")
        
        elif environment == Environment.STAGING:
            # Staging-specific validations
            if not config_dict.get('VAULT_ENABLED'):
                self._warnings.append("Vault should be enabled in staging")
    
    def get_errors(self) -> List[ConfigurationValidationError]:
        """Get list of validation errors"""
        return self._errors
    
    def get_warnings(self) -> List[str]:
        """Get list of validation warnings"""
        return self._warnings
    
    def has_errors(self) -> bool:
        """Check if there are validation errors"""
        return len(self._errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are validation warnings"""
        return len(self._warnings) > 0
    
    def format_errors(self) -> str:
        """Format validation errors for display"""
        if not self._errors:
            return "No validation errors"
        
        error_messages = []
        for error in self._errors:
            if error.field_name:
                error_messages.append(f"{error.field_name}: {error}")
            else:
                error_messages.append(str(error))
        
        return "\n".join(error_messages)


# Predefined configuration schemas for common validation scenarios
CONFIG_SCHEMA = {
    'database': DatabaseConfig,
    'jenkins': JenkinsConfig,
    'ldap': LDAPConfig,
    'vault': VaultConfig,
    'security': SecurityConfig,
    'app': AppConfig
}


def validate_config_dict(config_dict: Dict[str, Any], environment: str) -> bool:
    """
    Convenience function to validate configuration dictionary.
    
    Args:
        config_dict: Configuration dictionary to validate
        environment: Environment name
        
    Returns:
        True if validation passes
        
    Raises:
        ConfigurationValidationError: If validation fails
    """
    validator = ConfigValidator()
    result = validator.validate_config(config_dict, environment)
    
    if not result:
        raise ConfigurationValidationError(
            f"Configuration validation failed:\n{validator.format_errors()}"
        )
    
    return result