"""
Base configuration with sensible defaults for PowerStore CT Engine.

This module provides the base configuration that serves as the foundation
for all environment-specific configurations. It contains default values
that should be overridden in environment-specific files.
"""

import os
from typing import Dict, List, Optional
from pathlib import Path


class BaseConfig:
    """
    Base configuration class with sensible defaults.
    
    This class provides default values for all configuration options
    that can be overridden in environment-specific configurations.
    """
    
    # Application Configuration
    APP_NAME: str = "powerstore-ct-engine"
    APP_VERSION: str = "4.0.0"
    DEBUG: bool = False
    TESTING: bool = False
    SECRET_KEY: str = "change-this-secret-key-in-production"
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    
    # Database Configuration
    DATABASE_HOST: str = "10.55.236.78"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "qTest"
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str = "postgres"
    DATABASE_SSL_MODE: str = "prefer"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    
    # SQLAlchemy Configuration
    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ECHO: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: Dict = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'pool_size': 5,
        'max_overflow': 10
    }
    
    # Performance Database Configuration
    PERF_DATABASE_NAME: str = "performance"
    
    # Table Names
    TEST_RUNS_TABLE: str = "test_runs"
    TEST_SET_EXECUTION_TABLE: str = "test_case_execution"
    TEST_RUN_CONFIG_TABLE: str = "test_run_config"
    TEST_CASE_CONFIG_TABLE: str = "test_case_config"
    TEST_CASES_TABLE: str = "test_cases"
    RELEASE_TABLE: str = "cluster_lease_per_job"
    TESTINIT_STAMP_TABLE: str = "testinit_stamp"
    
    # Jenkins Configuration
    JENKINS_URL: str = "https://osj-ngm-03-prd.cec.delllabs.net"
    JENKINS_USERNAME: str = "svc_prdsysqafw"
    JENKINS_PASSWORD: str = "jenkins-password-from-vault"
    JENKINS_JOB_NAME: str = "Trident/test_executer"
    JENKINS_DEV_JOB_NAME: str = "Trident/dev_test_executer"
    JENKINS_TIMEOUT: int = 300
    JENKINS_RETRY_ATTEMPTS: int = 3
    JENKINS_RETRY_DELAY: int = 5
    
    # LDAP Configuration
    LDAP_URL: str = "ldaps://amer.dell.com:3269"
    LDAP_BASE_DN: str = "DC=dell,DC=com"
    LDAP_BIND_DN: str = "CN=svc_prdsysqafw,OU=Service Accounts,DC=amer,DC=dell,DC=com"
    LDAP_USE_SSL: bool = True
    LDAP_TLS_VERSION: str = "PROTOCOL_SSLv23"
    LDAP_CONNECT_TIMEOUT: int = 10
    LDAP_SEARCH_TIMEOUT: int = 5
    
    # Kubernetes Configuration
    KUBERNETES_ENABLED: bool = False
    KUBERNETES_NAMESPACE: str = "default"
    KUBERNETES_CONFIG_PATH: str = "/usr/src/app/ns5"
    KUBERNETES_CONTEXT: str = ""
    
    # XPool Configuration
    XPOOL_ENABLED: bool = True
    XPOOL_BINARY_PATH: str = "/home/public/scripts/xpool_trident/prd/xpool"
    XPOOL_GROUPS: str = "QA-TestRunner,FRAMEWORK"
    XPOOL_DEFAULT_USER: str = "svc_prdsysqafw"
    XPOOL_RESERVATION_LIMIT: Optional[int] = None
    XPOOL_TIMEOUT: int = 300
    XPOOL_RETRY_ATTEMPTS: int = 3
    
    # Monitoring Configuration
    MONITORING_ENABLED: bool = True
    MONITORING_INTERVAL: int = 300  # 5 minutes
    MONITORING_TIMEOUT: int = 60
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "app.log"
    LOG_MAX_BYTES: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # CORS Configuration
    CORS_ENABLED: bool = True
    CORS_ORIGINS: str = "*"
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["Content-Type", "Authorization"]
    
    # Security Configuration
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    PERMANENT_SESSION_LIFETIME: int = 3600  # 1 hour
    
    # API Configuration
    API_PREFIX: str = "/api/v1"
    API_TITLE: str = "PowerStore CT Engine API"
    API_VERSION: str = "1.0"
    API_DOC_ENABLED: bool = True
    
    # Feature Flags Configuration
    FEATURE_FLAGS_ENABLED: bool = True
    FEATURE_FLAGS_CONFIG_PATH: str = "feature_flags.json"
    
    # Vault Configuration
    VAULT_ENABLED: bool = False
    VAULT_URL: str = "http://localhost:8200"
    VAULT_ROLE: str = "powerstore-ct-engine"
    VAULT_SECRET_PATH: str = "secret/powerstore-ct-engine"
    VAULT_AUTH_METHOD: str = "kubernetes"
    VAULT_KUBERNETES_ROLE: str = "powerstore-ct-engine"
    VAULT_KUBERNETES_AUTH_PATH: str = "auth/kubernetes"
    VAULT_TOKEN_TTL: int = 3600  # 1 hour
    VAULT_SECRET_CACHE_TTL: int = 300  # 5 minutes
    
    # Manager Team Mapping (moved from hardcoded to config)
    MANAGER_GROUP_MAPPING: Dict[str, str] = {}
    
    # Test Execution Configuration
    TEST_EXECUTION_TIMEOUT: int = 7200  # 2 hours
    TEST_EXECUTION_RETRY_ATTEMPTS: int = 2
    TEST_EXECUTION_RETRY_DELAY: int = 60
    TEST_EXECUTION_MAX_CONCURRENT: int = 10
    
    # Cluster Management Configuration
    CLUSTER_LEASE_TIMEOUT: int = 7200  # 2 hours
    CLUSTER_RELEASE_DELAY: int = 300  # 5 minutes
    CLUSTER_HEALTH_CHECK_INTERVAL: int = 60
    
    # Email Configuration (for notifications)
    EMAIL_ENABLED: bool = False
    EMAIL_SMTP_HOST: str = "smtp.dell.com"
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_USE_TLS: bool = True
    EMAIL_FROM_ADDRESS: str = "powerstore-ct-engine@dell.com"
    EMAIL_ADMIN_ADDRESSES: List[str] = []
    
    # Slack Configuration (for notifications)
    SLACK_ENABLED: bool = False
    SLACK_WEBHOOK_URL: str = ""
    SLACK_DEFAULT_CHANNEL: str = "#test-notifications"
    
    # Working Hours Configuration
    WORKING_HOURS_ENABLED: bool = False
    WORKING_HOURS_START: str = "09:00"
    WORKING_HOURS_END: str = "18:00"
    WORKING_HOURS_TIMEZONE: str = "America/New_York"
    
    # Cache Configuration
    CACHE_ENABLED: bool = True
    CACHE_TYPE: str = "simple"  # simple, redis, memcached
    CACHE_REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_DEFAULT_TIMEOUT: int = 300
    
    # Rate Limiting Configuration
    RATE_LIMITING_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # File Upload Configuration
    UPLOAD_ENABLED: bool = True
    UPLOAD_MAX_SIZE: int = 10485760  # 10MB
    UPLOAD_ALLOWED_EXTENSIONS: List[str] = ["txt", "csv", "json", "yaml"]
    UPLOAD_FOLDER: str = "/tmp/uploads"
    
    # Backup Configuration
    BACKUP_ENABLED: bool = False
    BACKUP_INTERVAL: int = 86400  # 24 hours
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_FOLDER: str = "/tmp/backups"
    
    # Health Check Configuration
    HEALTH_CHECK_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL: int = 60
    HEALTH_CHECK_TIMEOUT: int = 10
    
    # Metrics Configuration
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    METRICS_PATH: str = "/metrics"
    
    @classmethod
    def get_database_uri(cls, database_name: Optional[str] = None) -> str:
        """
        Construct database URI from configuration.
        
        Args:
            database_name: Override database name from config
            
        Returns:
            PostgreSQL database URI
        """
        db_name = database_name or cls.DATABASE_NAME
        ssl_mode = cls.DATABASE_SSL_MODE
        
        return (
            f"postgresql://{cls.DATABASE_USER}:{cls.DATABASE_PASSWORD}"
            f"@{cls.DATABASE_HOST}:{cls.DATABASE_PORT}/{db_name}"
            f"?sslmode={ssl_mode}"
        )
    
    @classmethod
    def get_jenkins_url(cls, path: Optional[str] = None) -> str:
        """
        Get full Jenkins URL with optional path.
        
        Args:
            path: Optional path to append
            
        Returns:
            Full Jenkins URL
        """
        url = cls.JENKINS_URL.rstrip('/')
        if path:
            return f"{url}/{path.lstrip('/')}"
        return url
    
    @classmethod
    def get_vault_secret_path(cls, environment: str, secret_name: str) -> str:
        """
        Construct Vault secret path for environment and secret.
        
        Args:
            environment: Environment name (development, staging, production)
            secret_name: Name of the secret
            
        Returns:
            Full Vault secret path
        """
        return f"{cls.VAULT_SECRET_PATH}/{environment}/{secret_name}"
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate base configuration.
        
        Returns:
            True if configuration is valid
        """
        # Check for obvious misconfigurations
        if cls.SECRET_KEY == "change-this-secret-key-in-production":
            raise ValueError("Default SECRET_KEY must be changed in production")
        
        if cls.DATABASE_PASSWORD == "postgres":
            raise ValueError("Default database password must be changed")
        
        return True


# Default manager group mapping (can be overridden in environment configs)
DEFAULT_MANAGER_GROUP_MAPPING = {
    "SysQA-Core-DataPath": "itay.kaufman@dell.com",
    "SysQA-Control-SVC": "shay.goldshmidt@dell.com",
    "SysQA-Control-TMA": "noa.braun@dell.com",
    "SysQA-Core-DM": "itay.kaufman@dell.com",
    "SysQA-Core-FRU": "shay.goldshmidt@dell.com",
    "SysQA-Core-HA": "aviv.kolberg@dell.com",
    "SysQA-Core-HW": "shay.goldshmidt@dell.com",
    "SysQA-Core-Install": "ming.yue@dell.com",
    "SysQA-Core-Upgrade": "aviv.kolberg@dell.com",
    "SysQA-Core-Virtualization": "itay.kaufman@dell.com",
    "SysQA-CEV-HostAttach": "nisan.rumovich@dell.com",
    "SysQA-Control-Connectivity": "nisan.rumovich@dell.com",
    "SysQA-Scale-DM": "aviad.magendavid@dell.com",
    "SysQA-In-Market": "steven.shen@dell.com",
    "SysQA-MPTC": "ming.yue@dell.com"
}

# Set default manager group mapping
BaseConfig.MANAGER_GROUP_MAPPING = DEFAULT_MANAGER_GROUP_MAPPING