"""
Unit tests for configuration loader system.

Tests are designed to be safe and non-destructive.
They only test configuration loading logic and don't modify any data.
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config_loader import (
    ConfigLoader,
    get_config_loader,
    get_config,
    get_config_dict,
    reload_config,
    get_database_uri,
    Config
)
from shared.environment import Environment
from shared.exceptions import ConfigurationLoadError


class TestConfigLoader(unittest.TestCase):
    """Test ConfigLoader class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
        
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def test_loader_initialization(self):
        """Test config loader initialization"""
        loader = ConfigLoader()
        self.assertIsNotNone(loader)
        self.assertIsNone(loader._environment)
        self.assertEqual(len(loader._loaded_config), 0)
    
    def test_load_base_config(self):
        """Test loading base configuration"""
        loader = ConfigLoader()
        base_config = loader._load_base_config()
        
        self.assertIsInstance(base_config, dict)
        self.assertIn('DATABASE_HOST', base_config)
        self.assertIn('JENKINS_URL', base_config)
        self.assertIn('LDAP_URL', base_config)
    
    def test_load_environment_config_development(self):
        """Test loading development configuration"""
        loader = ConfigLoader()
        loader._environment = Environment.DEVELOPMENT
        env_config = loader._load_environment_config()
        
        self.assertIsInstance(env_config, dict)
        self.assertIn('DEBUG', env_config)
        # Development should have debug enabled
        self.assertTrue(env_config.get('DEBUG', False))
    
    def test_load_environment_config_production(self):
        """Test loading production configuration"""
        loader = ConfigLoader()
        loader._environment = Environment.PRODUCTION
        env_config = loader._load_environment_config()
        
        self.assertIsInstance(env_config, dict)
        self.assertIn('DEBUG', env_config)
        # Production should have debug disabled
        self.assertFalse(env_config.get('DEBUG', True))
    
    def test_convert_env_value_boolean(self):
        """Test converting environment variable values to boolean"""
        loader = ConfigLoader()
        
        # Test true values
        self.assertTrue(loader._convert_env_value('true'))
        self.assertTrue(loader._convert_env_value('True'))
        self.assertTrue(loader._convert_env_value('TRUE'))
        self.assertTrue(loader._convert_env_value('1'))
        self.assertTrue(loader._convert_env_value('yes'))
        self.assertTrue(loader._convert_env_value('on'))
        
        # Test false values
        self.assertFalse(loader._convert_env_value('false'))
        self.assertFalse(loader._convert_env_value('False'))
        self.assertFalse(loader._convert_env_value('FALSE'))
        self.assertFalse(loader._convert_env_value('0'))
        self.assertFalse(loader._convert_env_value('no'))
        self.assertFalse(loader._convert_env_value('off'))
    
    def test_convert_env_value_integer(self):
        """Test converting environment variable values to integer"""
        loader = ConfigLoader()
        
        self.assertEqual(loader._convert_env_value('42'), 42)
        self.assertEqual(loader._convert_env_value('0'), 0)
        self.assertEqual(loader._convert_env_value('-1'), -1)
    
    def test_convert_env_value_float(self):
        """Test converting environment variable values to float"""
        loader = ConfigLoader()
        
        self.assertEqual(loader._convert_env_value('3.14'), 3.14)
        self.assertEqual(loader._convert_env_value('0.0'), 0.0)
        self.assertEqual(loader._convert_env_value('-1.5'), -1.5)
    
    def test_convert_env_value_string(self):
        """Test converting environment variable values to string"""
        loader = ConfigLoader()
        
        self.assertEqual(loader._convert_env_value('hello'), 'hello')
        self.assertEqual(loader._convert_env_value('world'), 'world')
    
    def test_load_environment_variables(self):
        """Test loading configuration from environment variables"""
        loader = ConfigLoader()
        loader._environment = Environment.DEVELOPMENT
        
        with patch.dict(os.environ, {
            'ENV_DATABASE_HOST': 'test-host',
            'ENV_DATABASE_PORT': '5433',
            'ENV_DEBUG': 'true'
        }):
            env_config = loader._load_environment_variables()
            
            self.assertEqual(env_config.get('DATABASE_HOST'), 'test-host')
            self.assertEqual(env_config.get('DATABASE_PORT'), 5433)
            self.assertTrue(env_config.get('DEBUG'))
    
    def test_load_config_full(self):
        """Test full configuration loading"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            config = loader.load_config()
            
            self.assertIsInstance(config, dict)
            self.assertIn('DATABASE_HOST', config)
            self.assertIn('JENKINS_URL', config)
            self.assertIn('DEBUG', config)
    
    def test_config_caching(self):
        """Test that configuration is cached"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # First load
            config1 = loader.load_config()
            # Second load (should use cache)
            config2 = loader.load_config()
            
            self.assertEqual(config1, config2)
    
    def test_config_reload(self):
        """Test configuration reload"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            config1 = loader.load_config()
            
            # Change environment
            with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}, clear=True):
                config2 = loader.reload_config()
                
                # Configs should be different after reload
                self.assertNotEqual(config1.get('ENVIRONMENT'), config2.get('ENVIRONMENT'))
    
    def test_get_config(self):
        """Test getting specific configuration value"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            loader.load_config()
            
            db_host = loader.get_config('DATABASE_HOST')
            self.assertIsNotNone(db_host)
            
            # Test with default value
            missing_value = loader.get_config('MISSING_KEY', 'default')
            self.assertEqual(missing_value, 'default')
    
    def test_get_config_dict(self):
        """Test getting complete configuration dictionary"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            loader.load_config()
            
            config = loader.get_config_dict()
            
            self.assertIsInstance(config, dict)
            self.assertGreater(len(config), 0)
    
    def test_get_environment(self):
        """Test getting current environment"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}):
            env = loader.get_environment()
            self.assertEqual(env, Environment.STAGING)
    
    def test_get_config_sources(self):
        """Test getting configuration source information"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            loader.load_config()
            
            sources = loader.get_config_sources()
            
            self.assertIsInstance(sources, dict)
            self.assertIn('base', sources)


class TestGlobalFunctions(unittest.TestCase):
    """Test global configuration functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def test_get_config_loader(self):
        """Test global get_config_loader function"""
        loader = get_config_loader()
        self.assertIsInstance(loader, ConfigLoader)
        
        # Should return same instance on subsequent calls
        loader2 = get_config_loader()
        self.assertIs(loader, loader2)
    
    def test_get_config_global(self):
        """Test global get_config function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            db_host = get_config('DATABASE_HOST')
            self.assertIsNotNone(db_host)
    
    def test_get_config_dict_global(self):
        """Test global get_config_dict function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            config = get_config_dict()
            self.assertIsInstance(config, dict)
    
    def test_reload_config_global(self):
        """Test global reload_config function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            config1 = get_config_dict()
            
            with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}, clear=True):
                config2 = reload_config()
                
                self.assertIsInstance(config2, dict)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def test_get_database_uri(self):
        """Test get_database_uri function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            uri = get_database_uri()
            
            self.assertIsInstance(uri, str)
            self.assertIn('postgresql://', uri)
    
    def test_get_database_uri_with_override(self):
        """Test get_database_uri with database name override"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            uri = get_database_uri('custom_db')
            
            self.assertIn('custom_db', uri)
    
    def test_legacy_config_class(self):
        """Test legacy Config class for backward compatibility"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            config = Config()
            
            # Should have database URI property
            db_uri = config.SQLALCHEMY_DATABASE_URI
            self.assertIsNotNone(db_uri)
            
            # Should have secret key property
            secret = config.SECRET_KEY
            self.assertIsNotNone(secret)


class TestEnvironmentVariablePrecedence(unittest.TestCase):
    """Test configuration precedence with environment variables"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
        
        # Clear global config loader
        import shared.config_loader as cl_module
        cl_module._config_loader = None
    
    def test_env_var_overrides_config(self):
        """Test that environment variables override config files"""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'development',
            'ENV_DATABASE_HOST': 'override-host'
        }):
            loader = ConfigLoader()
            config = loader.load_config()
            
            # Environment variable should override config file
            self.assertEqual(config.get('DATABASE_HOST'), 'override-host')
    
    def test_env_var_precedence_order(self):
        """Test environment variable precedence"""
        loader = ConfigLoader()
        
        # Base config has default value
        base_config = loader._load_base_config()
        base_host = base_config.get('DATABASE_HOST')
        
        # Environment variable should override
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'development',
            'ENV_DATABASE_HOST': 'env-override-host'
        }):
            config = loader.load_config()
            env_host = config.get('DATABASE_HOST')
            
            self.assertNotEqual(base_host, env_host)
            self.assertEqual(env_host, 'env-override-host')


if __name__ == '__main__':
    unittest.main()