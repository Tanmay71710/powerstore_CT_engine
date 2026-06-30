from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON
from marshmallow import fields, post_dump
from sqlalchemy.orm import relationship, foreign
from flask_marshmallow import Marshmallow

# Legacy database and marshmallow instances (for backward compatibility)
db = SQLAlchemy()
ma = Marshmallow()

# New configuration management system
from .environment import (
    Environment,
    get_environment,
    is_development,
    is_staging,
    is_production,
    require_production,
    require_non_production
)
from .config_loader import (
    ConfigLoader,
    get_config_loader,
    get_config,
    get_config_dict,
    reload_config,
    Config as NewConfig
)
from .exceptions import (
    ConfigurationError,
    EnvironmentDetectionError,
    ConfigurationValidationError,
    VaultConnectionError,
    VaultSecretNotFoundError,
    FeatureFlagError
)
from .feature_flags import (
    FeatureFlag,
    FeatureFlagManager,
    get_feature_flag_manager,
    is_feature_enabled,
    enable_feature,
    disable_feature,
    feature_flag
)

# Import ldap module for backward compatibility
try:
    from . import ldap
except ImportError:
    ldap = None

__all__ = [
    # Legacy compatibility
    'db',
    'ma',
    # Environment detection
    'Environment',
    'get_environment',
    'is_development',
    'is_staging',
    'is_production',
    'require_production',
    'require_non_production',
    # Configuration management
    'ConfigLoader',
    'get_config_loader',
    'get_config',
    'get_config_dict',
    'reload_config',
    'NewConfig',
    # Exceptions
    'ConfigurationError',
    'EnvironmentDetectionError',
    'ConfigurationValidationError',
    'VaultConnectionError',
    'VaultSecretNotFoundError',
    'FeatureFlagError',
    # Feature flags
    'FeatureFlag',
    'FeatureFlagManager',
    'get_feature_flag_manager',
    'is_feature_enabled',
    'enable_feature',
    'disable_feature',
    'feature_flag',
    # Legacy
    'ldap'
]