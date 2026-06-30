"""
Production environment configuration for PowerStore CT Engine.

This module provides production-specific configuration overrides
that are optimized for production deployment with maximum security.
"""

from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """
    Production environment configuration.
    
    Overrides base configuration with production-specific settings
    optimized for production deployment with maximum security.
    """
    
    # Environment
    ENVIRONMENT = "production"
    
    # Application Configuration
    DEBUG = False
    TESTING = False
    SECRET_KEY = "production-secret-key-from-vault"  # Must come from Vault
    
    # Server Configuration
    HOST = "0.0.0.0"
    PORT = 5003
    
    # Database Configuration (Production database)
    DATABASE_HOST = "prod-db.dell.com"
    DATABASE_PORT = 5432
    DATABASE_NAME = "qtest"
    DATABASE_USER = "ct_engine_prod"
    DATABASE_PASSWORD = "production-password-from-vault"  # Must come from Vault
    DATABASE_SSL_MODE = "require"
    DATABASE_POOL_SIZE = 20
    DATABASE_MAX_OVERFLOW = 40
    
    # SQLAlchemy Configuration
    SQLALCHEMY_ECHO = False  # Never enable SQL query logging in production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'pool_size': 20,
        'max_overflow': 40
    }
    
    # Performance Database Configuration
    PERF_DATABASE_NAME = "performance"
    
    # Jenkins Configuration (Production Jenkins)
    JENKINS_URL = "https://osj-ngm-03-prd.cec.delllabs.net"
    JENKINS_USERNAME = "svc_prdsysqafw"
    JENKINS_PASSWORD = "production-jenkins-password-from-vault"  # Must come from Vault
    JENKINS_TIMEOUT = 600  # Longer timeout for production
    JENKINS_RETRY_ATTEMPTS = 5
    JENKINS_RETRY_DELAY = 10
    
    # LDAP Configuration (Production LDAP)
    LDAP_URL = "ldaps://amer.dell.com:3269"
    LDAP_USE_SSL = True
    LDAP_CONNECT_TIMEOUT = 10
    
    # Kubernetes Configuration (Production Kubernetes)
    KUBERNETES_ENABLED = True
    KUBERNETES_NAMESPACE = "isg-pse-sysqa-prd"
    KUBERNETES_CONFIG_PATH = "/usr/src/app/ns5"
    KUBERNETES_CONTEXT = "production-context"
    
    # XPool Configuration (Production XPool)
    XPOOL_ENABLED = True
    XPOOL_BINARY_PATH = "/home/public/scripts/xpool_trident/prd/xpool"
    XPOOL_GROUPS = "QA-TestRunner,FRAMEWORK"
    XPOOL_DEFAULT_USER = "svc_prdsysqafw"
    XPOOL_RESERVATION_LIMIT = 100
    XPOOL_TIMEOUT = 300
    
    # Monitoring Configuration
    MONITORING_ENABLED = True
    MONITORING_INTERVAL = 300
    
    # Logging Configuration
    LOG_LEVEL = "WARNING"  # Higher log level in production
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # CORS Configuration (Strict in production)
    CORS_ENABLED = True
    CORS_ORIGINS = "https://prod.dell.com,https://prod-ui.dell.com"
    
    # Security Configuration (Maximum security in production)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    
    # API Configuration
    API_DOC_ENABLED = False  # Disable API docs in production
    
    # Feature Flags Configuration
    FEATURE_FLAGS_ENABLED = True
    
    # Vault Configuration (Production Vault)
    VAULT_ENABLED = True
    VAULT_URL = "https://production-vault.dell.com"
    VAULT_ROLE = "powerstore-ct-engine-prod"
    VAULT_SECRET_PATH = "secret/powerstore-ct-engine"
    VAULT_AUTH_METHOD = "kubernetes"
    VAULT_KUBERNETES_ROLE = "powerstore-ct-engine-prod"
    VAULT_KUBERNETES_AUTH_PATH = "auth/kubernetes"
    VAULT_TOKEN_TTL = 1800  # 30 minutes
    VAULT_SECRET_CACHE_TTL = 600  # 10 minutes
    
    # Test Execution Configuration
    TEST_EXECUTION_TIMEOUT = 7200  # 2 hours
    TEST_EXECUTION_RETRY_ATTEMPTS = 3
    TEST_EXECUTION_MAX_CONCURRENT = 50
    
    # Cluster Management Configuration
    CLUSTER_LEASE_TIMEOUT = 7200  # 2 hours
    CLUSTER_RELEASE_DELAY = 300
    
    # Email Configuration (Enabled in production)
    EMAIL_ENABLED = True
    EMAIL_SMTP_HOST = "smtp.dell.com"
    EMAIL_SMTP_PORT = 587
    EMAIL_SMTP_USE_TLS = True
    EMAIL_FROM_ADDRESS = "powerstore-ct-engine@dell.com"
    EMAIL_ADMIN_ADDRESSES = ["prod-team@dell.com", "oncall@dell.com"]
    
    # Slack Configuration (Enabled in production)
    SLACK_ENABLED = True
    SLACK_WEBHOOK_URL = "production-slack-webhook-from-vault"
    SLACK_DEFAULT_CHANNEL = "#prod-notifications"
    
    # Working Hours Configuration
    WORKING_HOURS_ENABLED = True
    WORKING_HOURS_START = "09:00"
    WORKING_HOURS_END = "18:00"
    WORKING_HOURS_TIMEZONE = "America/New_York"
    
    # Cache Configuration (Redis in production)
    CACHE_ENABLED = True
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = "redis://prod-redis.dell.com:6379/0"
    
    # Rate Limiting Configuration (Stricter in production)
    RATE_LIMITING_ENABLED = True
    RATE_LIMIT_PER_MINUTE = 60
    RATE_LIMIT_PER_HOUR = 1000
    
    # File Upload Configuration
    UPLOAD_ENABLED = True
    UPLOAD_MAX_SIZE = 10485760  # 10MB
    UPLOAD_FOLDER = "/tmp/uploads"
    
    # Backup Configuration (Enabled in production)
    BACKUP_ENABLED = True
    BACKUP_INTERVAL = 86400  # 24 hours
    BACKUP_RETENTION_DAYS = 30
    BACKUP_FOLDER = "/tmp/backups"
    
    # Health Check Configuration
    HEALTH_CHECK_ENABLED = True
    HEALTH_CHECK_INTERVAL = 60
    
    # Metrics Configuration
    METRICS_ENABLED = True
    METRICS_PORT = 9090
    
    @classmethod
    def validate(cls) -> bool:
        """Validate production configuration"""
        # Production-specific validations
        if not cls.VAULT_ENABLED:
            raise ValueError("Vault must be enabled in production")
        
        if not cls.KUBERNETES_ENABLED:
            raise ValueError("Kubernetes must be enabled in production")
        
        if cls.DEBUG:
            raise ValueError("DEBUG must be False in production")
        
        if cls.SESSION_COOKIE_SECURE == False:
            raise ValueError("SESSION_COOKIE_SECURE must be True in production")
        
        if cls.API_DOC_ENABLED:
            raise ValueError("API documentation should be disabled in production")
        
        if cls.LOG_LEVEL == "DEBUG":
            raise ValueError("LOG_LEVEL should not be DEBUG in production")
        
        # Check for production secrets
        if cls.SECRET_KEY == "production-secret-key-from-vault":
            raise ValueError("SECRET_KEY must be set from Vault in production")
        
        if cls.DATABASE_PASSWORD == "production-password-from-vault":
            raise ValueError("DATABASE_PASSWORD must be set from Vault in production")
        
        return super().validate()