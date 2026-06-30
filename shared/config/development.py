"""
Development environment configuration for PowerStore CT Engine.

This module provides development-specific configuration overrides
that are optimized for local development and testing.
"""

from .base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """
    Development environment configuration.
    
    Overrides base configuration with development-specific settings
    optimized for local development and testing.
    """
    
    # Environment
    ENVIRONMENT = "development"
    
    # Application Configuration
    DEBUG = True
    TESTING = True
    SECRET_KEY = "development-secret-key-change-in-production"
    
    # Server Configuration
    HOST = "localhost"
    PORT = 5000
    
    # Database Configuration (Development defaults)
    DATABASE_HOST = "localhost"
    DATABASE_PORT = 5432
    DATABASE_NAME = "qtest_dev"
    DATABASE_USER = "postgres"
    DATABASE_PASSWORD = "postgres"
    DATABASE_SSL_MODE = "disable"
    DATABASE_POOL_SIZE = 2
    DATABASE_MAX_OVERFLOW = 5
    
    # SQLAlchemy Configuration
    SQLALCHEMY_ECHO = True  # Enable SQL query logging in development
    
    # Performance Database Configuration
    PERF_DATABASE_NAME = "performance_dev"
    
    # Jenkins Configuration (Consistent across all environments)
    JENKINS_URL = "https://osj-ngm-03-prd.cec.delllabs.net"
    JENKINS_USERNAME = "svc_prdsysqafw"
    JENKINS_PASSWORD = "jenkins-password-from-vault"
    JENKINS_TIMEOUT = 120  # Shorter timeout for development
    
    # LDAP Configuration (Development LDAP or mock)
    LDAP_URL = "ldaps://amer.dell.com:3269"
    LDAP_USE_SSL = True
    LDAP_CONNECT_TIMEOUT = 10
    
    # Kubernetes Configuration (Disabled for local development)
    KUBERNETES_ENABLED = False
    KUBERNETES_NAMESPACE = "dev"
    
    # XPool Configuration (Mock or development instance)
    XPOOL_ENABLED = True
    XPOOL_BINARY_PATH = "/home/public/scripts/xpool_trident/dev/xpool"
    XPOOL_GROUPS = "QA-TestRunner,FRAMEWORK"
    XPOOL_DEFAULT_USER = "svc_prdsysqafw"
    XPOOL_RESERVATION_LIMIT = None
    
    # Monitoring Configuration (More frequent in development)
    MONITORING_ENABLED = True
    MONITORING_INTERVAL = 60  # Check every minute in development
    
    # Logging Configuration (More verbose in development)
    LOG_LEVEL = "DEBUG"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    
    # CORS Configuration (Permissive in development)
    CORS_ENABLED = True
    CORS_ORIGINS = "*"
    
    # Security Configuration (Relaxed in development)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # API Configuration
    API_DOC_ENABLED = True
    
    # Feature Flags Configuration (All flags enabled in development)
    FEATURE_FLAGS_ENABLED = True
    
    # Vault Configuration (Disabled or development Vault)
    VAULT_ENABLED = False
    VAULT_URL = "http://localhost:8200"
    VAULT_SECRET_PATH = "secret/powerstore-ct-engine"
    
    # Test Execution Configuration (Shorter timeouts in development)
    TEST_EXECUTION_TIMEOUT = 1800  # 30 minutes
    TEST_EXECUTION_RETRY_ATTEMPTS = 1
    
    # Cluster Management Configuration
    CLUSTER_LEASE_TIMEOUT = 1800  # 30 minutes in development
    
    # Email Configuration (Disabled in development)
    EMAIL_ENABLED = False
    
    # Slack Configuration (Disabled in development)
    SLACK_ENABLED = False
    
    # Working Hours Configuration (Disabled in development)
    WORKING_HOURS_ENABLED = False
    
    # Cache Configuration (Simple cache in development)
    CACHE_ENABLED = True
    CACHE_TYPE = "simple"
    
    # Rate Limiting Configuration (Relaxed in development)
    RATE_LIMITING_ENABLED = False
    
    # File Upload Configuration
    UPLOAD_ENABLED = True
    UPLOAD_MAX_SIZE = 52428800  # 50MB in development
    UPLOAD_FOLDER = "/tmp/uploads"
    
    # Backup Configuration (Disabled in development)
    BACKUP_ENABLED = False
    
    # Health Check Configuration
    HEALTH_CHECK_ENABLED = True
    HEALTH_CHECK_INTERVAL = 30  # More frequent in development
    
    # Metrics Configuration
    METRICS_ENABLED = True
    
    @classmethod
    def validate(cls) -> bool:
        """Validate development configuration"""
        # Development-specific validations
        if cls.DEBUG and cls.SESSION_COOKIE_SECURE:
            raise ValueError("SESSION_COOKIE_SECURE should be False in development with DEBUG=True")
        
        return super().validate()