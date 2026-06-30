"""
Custom exceptions for the PowerStore CT Engine configuration system.

This module provides a comprehensive set of custom exceptions for
configuration management, environment detection, and related operations.
"""


class ConfigurationError(Exception):
    """Base exception for all configuration errors"""
    pass


class EnvironmentDetectionError(ConfigurationError):
    """Exception raised when environment detection fails"""
    pass


class ConfigurationValidationError(ConfigurationError):
    """Exception raised when configuration validation fails"""
    def __init__(self, message, field_name=None, value=None):
        self.field_name = field_name
        self.value = value
        super().__init__(message)


class ConfigurationLoadError(ConfigurationError):
    """Exception raised when configuration loading fails"""
    pass


class VaultConnectionError(ConfigurationError):
    """Exception raised when Vault connection fails"""
    pass


class VaultSecretNotFoundError(ConfigurationError):
    """Exception raised when a Vault secret is not found"""
    def __init__(self, secret_path):
        self.secret_path = secret_path
        super().__init__(f"Vault secret not found: {secret_path}")


class VaultAuthenticationError(ConfigurationError):
    """Exception raised when Vault authentication fails"""
    pass


class FeatureFlagError(ConfigurationError):
    """Exception raised when feature flag operations fail"""
    pass


class ConfigurationMigrationError(ConfigurationError):
    """Exception raised when configuration migration fails"""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Exception raised when configuration values are invalid"""
    def __init__(self, message, errors=None):
        self.errors = errors or []
        super().__init__(message)


class MissingConfigurationError(ConfigurationError):
    """Exception raised when required configuration is missing"""
    def __init__(self, field_name):
        self.field_name = field_name
        super().__init__(f"Required configuration field missing: {field_name}")


class ConfigurationAccessError(ConfigurationError):
    """Exception raised when configuration access is denied"""
    pass


class InconsistentConfigurationError(ConfigurationError):
    """Exception raised when configuration values are inconsistent"""
    def __init__(self, message, conflicts=None):
        self.conflicts = conflicts or {}
        super().__init__(message)