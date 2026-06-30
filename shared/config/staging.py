"""
Staging environment configuration for PowerStore CT Engine.

This module provides staging-specific configuration overrides
that are optimized for pre-production testing and validation.
"""

from .base import BaseConfig


class StagingConfig(BaseConfig):
    """
    Staging environment configuration.
    
    Overrides base configuration with staging-specific settings
    optimized for pre-production testing and validation.
    """
    
    # Environment
    ENVIRONMENT = "staging"
    
    # Application Configuration
    DEBUG = False
    TESTING = False
    SECRET_KEY = "staging-secret-key-change-in-production"
    
    # Server Configuration
    HOST = "0.0.0.0"
    PORT = 5003
    
    # Database Configuration (Staging database)
    DATABASE_HOST = "staging-db.dell.com"
    DATABASE_PORT = 5432
    DATABASE_NAME = "qtest_staging"
    DATABASE_USER = "ct_engine_staging"
    DATABASE_PASSWORD = "staging-password-from-vault"
    DATABASE_SSL_MODE = "require"
    DATABASE_POOL_SIZE = 10
    DATABASE_MAX_OVERFLOW = 20
    
    # SQLAlchemy Configuration
    SQLALCHEMY_ECHO = False  # Disable SQL query logging in staging
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # Performance Database Configuration
    PERF_DATABASE_NAME = "performance_staging"
    
    # Jenkins Configuration (Staging Jenkins)
    JENKINS_URL = "https://staging-jenkins.dell.com"
    JENKINS_USERNAME = "ct-engine-staging"
    JENKINS_PASSWORD = "staging-jenkins-password-from-vault"
    JENKINS_TIMEOUT = 300
    JENKINS_RETRY_ATTEMPTS = 5
    
    # LDAP Configuration (Production LDAP)
    LDAP_URL = "ldaps://amer.dell.com:3269"
    LDAP_USE_SSL = True
    LDAP_CONNECT_TIMEOUT = 10
    
    # Kubernetes Configuration (Staging Kubernetes)
    KUBERNETES_ENABLED = True
    KUBERNETES_NAMESPACE = "staging"
    KUBERNETES_CONFIG_PATH = "/usr/src/app/ns5"
    KUBERNETES_CONTEXT = "staging-context"
    
    # XPool Configuration (Staging XPool)
    XPOOL_ENABLED = True
    XPOOL_BINARY_PATH = "/home/public/scripts/xpool_trident/test/xpool"
    XPOOL_GROUPS = "QA-TestRunner,FRAMEWORK"
    XPOOL_DEFAULT_USER = "svc_prdsysqafw"
    XPOOL_RESERVATION_LIMIT = 50
    XPOOL_TIMEOUT = 300
    
    # Monitoring Configuration
    MONITORING_ENABLED = True
    MONITORING_INTERVAL = 300
    
    # Logging Configuration
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # CORS Configuration (Controlled in staging)
    CORS_ENABLED = True
    CORS_ORIGINS = "https://staging.dell.com,https://staging-ui.dell.com"
    
    # Security Configuration (Production-like in staging)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    
    # API Configuration
    API_DOC_ENABLED = True
    
    # Feature Flags Configuration
    FEATURE_FLAGS_ENABLED = True
    
    # Vault Configuration (Staging Vault)
    VAULT_ENABLED = True
    VAULT_URL = "https://staging-vault.dell.com"
    VAULT_ROLE = "powerstore-ct-engine-staging"
    VAULT_SECRET_PATH = "secret/powerstore-ct-engine"
    VAULT_AUTH_METHOD = "kubernetes"
    VAULT_KUBERNETES_ROLE = "powerstore-ct-engine-staging"
    VAULT_TOKEN_TTL = 3600
    VAULT_SECRET_CACHE_TTL = 300
    
    # Test Execution Configuration
    TEST_EXECUTION_TIMEOUT = 7200  # 2 hours
    TEST_EXECUTION_RETRY_ATTEMPTS = 3
    TEST_EXECUTION_MAX_CONCURRENT = 20
    
    # Cluster Management Configuration
    CLUSTER_LEASE_TIMEOUT = 7200  # 2 hours
    CLUSTER_RELEASE_DELAY = 300
    
    # Email Configuration (Enabled in staging)
    EMAIL_ENABLED = True
    EMAIL_SMTP_HOST = "smtp.dell.com"
    EMAIL_SMTP_PORT = 587
    EMAIL_SMTP_USE_TLS = True
    EMAIL_FROM_ADDRESS = "powerstore-ct-engine-staging@dell.com"
    EMAIL_ADMIN_ADDRESSES = ["staging-team@dell.com"]
    
    # Slack Configuration (Enabled in staging)
    SLACK_ENABLED = True
    SLACK_WEBHOOK_URL = "staging-slack-webhook-from-vault"
    SLACK_DEFAULT_CHANNEL = "#staging-notifications"
    
    # Working Hours Configuration
    WORKING_HOURS_ENABLED = True
    WORKING_HOURS_START = "09:00"
    WORKING_HOURS_END = "18:00"
    WORKING_HOURS_TIMEZONE = "America/New_York"
    
    # Cache Configuration (Redis in staging)
    CACHE_ENABLED = True
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = "redis://staging-redis.dell.com:6379/0"
    
    # Rate Limiting Configuration
    RATE_LIMITING_ENABLED = True
    RATE_LIMIT_PER_MINUTE = 120
    RATE_LIMIT_PER_HOUR = 2000
    
    # File Upload Configuration
    UPLOAD_ENABLED = True
    UPLOAD_MAX_SIZE = 10485760  # 10MB
    UPLOAD_FOLDER = "/tmp/uploads"
    
    # Backup Configuration (Enabled in staging)
    BACKUP_ENABLED = True
    BACKUP_INTERVAL = 86400  # 24 hours
    BACKUP_RETENTION_DAYS = 7
    BACKUP_FOLDER = "/tmp/backups"
    
    # Health Check Configuration
    HEALTH_CHECK_ENABLED = True
    HEALTH_CHECK_INTERVAL = 60
    
    # Metrics Configuration
    METRICS_ENABLED = True
    METRICS_PORT = 9090
    
    @classmethod
    def validate(cls) -> bool:
        """Validate staging configuration"""
        # Staging-specific validations
        if not cls.VAULT_ENABLED:
            raise ValueError("Vault should be enabled in staging")
        
        if not cls.KUBERNETES_ENABLED:
            raise ValueError("Kubernetes should be enabled in staging")
        
        if cls.SESSION_COOKIE_SECURE == False:
            raise ValueError("SESSION_COOKIE_SECURE should be True in staging")
        
        return super().validate()