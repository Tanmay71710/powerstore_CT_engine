"""
Integration tests for configuration management system.

Tests are designed to be safe and non-destructive.
They test the complete configuration loading flow without modifying data.
"""

import unittest
import os
from unittest.mock import patch

import sys
sys.path.insert(0, '/mnt/c/powerstore/All frameworks/ct engine/v4/powerstore_CT_engine')

from shared.environment import get_environment, get_environment_info
from shared.config_loader import get_config, get_config_dict, get_database_uri
from shared.config.validation import validate_config_dict
from shared.feature_flags import is_feature_enabled, get_feature_flag_manager


class TestConfigurationIntegration(unittest.TestCase):
    """Integration tests for complete configuration flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global instances
        import shared.config_loader as cl_module
        cl_module._config_loader = None
        
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear global instances
        import shared.config_loader as cl_module
        cl_module._config_loader = None
        
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
    
    def test_complete_configuration_flow(self):
        """Test complete configuration loading flow"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # Step 1: Detect environment
            environment = get_environment()
            self.assertIsNotNone(environment)
            
            # Step 2: Load configuration
            config = get_config_dict()
            self.assertIsInstance(config, dict)
            self.assertGreater(len(config), 0)
            
            # Step 3: Validate configuration
            validate_config_dict(config, environment.value)
            
            # Step 4: Get specific configuration values
            db_host = get_config('DATABASE_HOST')
            self.assertIsNotNone(db_host)
    
    def test_configuration_precedence(self):
        """Test configuration precedence order"""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'development',
            'ENV_DATABASE_HOST': 'override-host'
        }):
            config = get_config_dict()
            
            # Environment variable should override config file
            self.assertEqual(config.get('DATABASE_HOST'), 'override-host')
    
    def test_database_uri_generation(self):
        """Test database URI generation"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            uri = get_database_uri()
            
            self.assertIsInstance(uri, str)
            self.assertIn('postgresql://', uri)
            self.assertIn('localhost', uri)  # Development default
    
    def test_environment_specific_configuration(self):
        """Test environment-specific configuration loading"""
        # Test development
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            import shared.config_loader as cl_module
            cl_module._config_loader = None
            
            config = get_config_dict()
            self.assertTrue(config.get('DEBUG', False))
        
        # Test production
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            import shared.config_loader as cl_module
            cl_module._config_loader = None
            
            config = get_config_dict()
            self.assertFalse(config.get('DEBUG', True))
    
    def test_feature_flags_integration(self):
        """Test feature flags integration with configuration"""
        manager = get_feature_flag_manager()
        
        # Feature flags should be available
        flag = manager.get_flag('new_ui')
        self.assertIsNotNone(flag)
        
        # Should be able to check flag status
        result = is_feature_enabled('new_ui')
        self.assertIsInstance(result, bool)
    
    def test_configuration_validation_integration(self):
        """Test configuration validation in integration context"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            config = get_config_dict()
            
            # Should validate without errors
            try:
                validate_config_dict(config, 'development')
                validation_passed = True
            except Exception:
                validation_passed = False
            
            self.assertTrue(validation_passed)
    
    def test_environment_info_integration(self):
        """Test environment information in integration context"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}):
            info = get_environment_info()
            
            self.assertIn('environment', info)
            self.assertIn('detection_sources', info)
            self.assertIn('hostname', info)
            self.assertEqual(info['environment'], 'staging')
    
    def test_configuration_reload_integration(self):
        """Test configuration reload in integration context"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # Initial load
            config1 = get_config_dict()
            
            # Reload
            from shared.config_loader import reload_config
            config2 = reload_config()
            
            # Both should be valid configurations
            self.assertIsInstance(config1, dict)
            self.assertIsInstance(config2, dict)


class TestBackwardCompatibilityIntegration(unittest.TestCase):
    """Integration tests for backward compatibility"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global instances
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear global instances
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def test_legacy_config_compatibility(self):
        """Test that legacy config still works"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # Old-style import should still work
            from shared.config import Config
            
            config = Config()
            
            # Should have database URI
            db_uri = config.SQLALCHEMY_DATABASE_URI
            self.assertIsNotNone(db_uri)
            
            # Should have secret key
            secret = config.SECRET_KEY
            self.assertIsNotNone(secret)
    
    def test_legacy_database_params_compatibility(self):
        """Test that legacy database parameters still work"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            from shared.config import DB_PARAMS, PERF_PARAMS
            
            # Legacy parameters should still be available
            self.assertIsInstance(DB_PARAMS, dict)
            self.assertIn('host', DB_PARAMS)
            self.assertIn('dbname', DB_PARAMS)
            
            self.assertIsInstance(PERF_PARAMS, dict)
            self.assertIn('host', PERF_PARAMS)
            self.assertIn('dbname', PERF_PARAMS)


class TestErrorHandlingIntegration(unittest.TestCase):
    """Integration tests for error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global instances
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear global instances
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def test_invalid_environment_handling(self):
        """Test handling of invalid environment"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'invalid_env'}):
            # Should fallback to development with warning
            environment = get_environment()
            self.assertIsNotNone(environment)
    
    def test_missing_configuration_handling(self):
        """Test handling of missing configuration values"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # Missing configuration should return None or default
            missing_value = get_config('NONEXISTENT_KEY', 'default_value')
            self.assertEqual(missing_value, 'default_value')
    
    def test_configuration_error_handling(self):
        """Test handling of configuration errors"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # Try to validate invalid configuration
            invalid_config = {
                'DATABASE_HOST': 'invalid host with spaces',
                'DATABASE_PORT': 5432,
                'DATABASE_NAME': 'testdb',
                'DATABASE_USER': 'testuser',
                'DATABASE_PASSWORD': 'testpass123',
                'JENKINS_URL': 'https://jenkins.example.com',
                'JENKINS_USERNAME': 'jenkins_user',
                'JENKINS_PASSWORD': 'jenkins_password',
                'LDAP_URL': 'ldaps://ldap.example.com:636',
                'LDAP_BASE_DN': 'DC=example,DC=com',
                'LDAP_BIND_DN': 'CN=admin,DC=example,DC=com',
                'SECRET_KEY': 'very-secret-key-at-least-32-characters-long',
                'VAULT_ENABLED': False,
                'SESSION_COOKIE_SECURE': False,
                'SESSION_COOKIE_HTTPONLY': True,
                'SESSION_COOKIE_SAMESITE': 'Lax'
            }
            
            # Should raise validation error
            with self.assertRaises(Exception):
                validate_config_dict(invalid_config, 'development')


if __name__ == '__main__':
    unittest.main()