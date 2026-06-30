import os
import logging
import warnings

logger = logging.getLogger(__name__)

# ============================================================================
# DEPRECATION WARNING
# ============================================================================
# This file is deprecated. Please use the new configuration management system:
# - from shared.environment import get_environment, is_development, etc.
# - from shared.config_loader import get_config, get_config_dict
# - from shared.config.base import BaseConfig
# - from shared.config.development import DevelopmentConfig
# - from shared.config.staging import StagingConfig
# - from shared.config.production import ProductionConfig
# ============================================================================

warnings.warn(
    "shared.config is deprecated. Use shared.config_loader and environment detection instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy configuration values (for backward compatibility)
POSTGRES_IP = '10.55.236.78'
USER = 'postgres'
POSTGRES_PASS = 'postgres'
QTEST_DB_NAME = 'qTest'
PERF_DB_NAME = 'performance'
TEST_RUNS = 'test_runs'
TEST_SET_EXECUTION = 'test_case_execution'
TEST_RUN_CONFIG = 'test_run_config'
TEST_CASE_CONFIG = 'test_case_config'
TEST_CASES = 'test_cases'
RELEASE_TABLE = 'cluster_lease_per_job'
TESTINIT_STAMP = 'testinit_stamp'
JOB_NAME = 'Trident/test_executer'
XPOOL_GROUPS = 'QA-TestRunner,FRAMEWORK'

DB_PARAMS = {
    "host": POSTGRES_IP,
    "dbname": QTEST_DB_NAME,
    "user": USER,
    "password": POSTGRES_PASS
}

PERF_PARAMS = {
    "host": POSTGRES_IP,
    "dbname": PERF_DB_NAME,
    "user": USER,
    "password": POSTGRES_PASS
}

MANAGER_GROUP_MAPPING = {
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


class Config:
    """Legacy Config class - use shared.config_loader instead"""
    
    def __init__(self):
        """Initialize with deprecation warning"""
        warnings.warn(
            "Config class is deprecated. Use shared.config_loader.get_config() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Try to use new config loader if available
        try:
            from .config_loader import get_config_dict
            self._config_dict = get_config_dict()
        except Exception:
            # Fallback to hardcoded values
            self._config_dict = {}
            logger.warning("Failed to load new config, using legacy values")
    
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        """Legacy database URI property"""
        try:
            from .config_loader import get_database_uri
            return get_database_uri()
        except Exception:
            return f'postgresql://{USER}:{POSTGRES_PASS}@{POSTGRES_IP}/{QTEST_DB_NAME}'
    
    @property
    def SQLALCHEMY_TRACK_MODIFICATIONS(self):
        """Legacy track modifications property"""
        return False
    
    @property
    def SECRET_KEY(self):
        """Legacy secret key property"""
        try:
            from .config_loader import get_config
            return get_config('SECRET_KEY', 'some_random_secret_value')
        except Exception:
            return 'some_random_secret_value'
    
    def __getattr__(self, name):
        """Dynamic attribute access for backward compatibility"""
        try:
            from .config_loader import get_config
            return get_config(name, None)
        except Exception:
            # Return legacy value if available
            return globals().get(name, None)
