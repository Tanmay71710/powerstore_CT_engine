"""
Unit tests for feature flag system.

Tests are designed to be safe and non-destructive.
They only test feature flag logic and don't modify any data.
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, '/mnt/c/powerstore/All frameworks/ct engine/v4/powerstore_CT_engine')

from shared.feature_flags import (
    FeatureFlag,
    FeatureFlagManager,
    get_feature_flag_manager,
    is_feature_enabled,
    enable_feature,
    disable_feature,
    feature_flag
)
from shared.exceptions import FeatureFlagError


class TestFeatureFlag(unittest.TestCase):
    """Test FeatureFlag class"""
    
    def test_feature_flag_initialization(self):
        """Test feature flag initialization"""
        flag = FeatureFlag(
            name='test_flag',
            enabled=True,
            environments=['development', 'staging'],
            rollout_percentage=100,
            description='Test feature flag'
        )
        
        self.assertEqual(flag.name, 'test_flag')
        self.assertTrue(flag.enabled)
        self.assertEqual(flag.rollout_percentage, 100)
        self.assertEqual(flag.description, 'Test feature flag')
    
    def test_feature_flag_disabled(self):
        """Test disabled feature flag"""
        flag = FeatureFlag(
            name='disabled_flag',
            enabled=False,
            environments=['production']
        )
        
        self.assertFalse(flag.enabled)
        self.assertFalse(flag.is_enabled())
    
    def test_feature_flag_enabled(self):
        """Test enabled feature flag"""
        flag = FeatureFlag(
            name='enabled_flag',
            enabled=True,
            environments=['development', 'staging', 'production']
        )
        
        self.assertTrue(flag.enabled)
        self.assertTrue(flag.is_enabled())
    
    def test_feature_flag_environment_restriction(self):
        """Test feature flag environment restriction"""
        flag = FeatureFlag(
            name='dev_only_flag',
            enabled=True,
            environments=['development']
        )
        
        with patch('shared.feature_flags.get_environment') as mock_env:
            # Should be enabled in development
            mock_env.return_value.value = 'development'
            self.assertTrue(flag.is_enabled())
            
            # Should be disabled in production
            mock_env.return_value.value = 'production'
            self.assertFalse(flag.is_enabled())
    
    def test_feature_flag_rollout_percentage(self):
        """Test feature flag rollout percentage"""
        flag = FeatureFlag(
            name='rollout_flag',
            enabled=True,
            environments=['production'],
            rollout_percentage=50
        )
        
        # With user ID, should be deterministic
        with patch('shared.feature_flags.get_environment') as mock_env:
            mock_env.return_value.value = 'production'
            
            # Different users may get different results based on hash
            result1 = flag.is_enabled('user1')
            result2 = flag.is_enabled('user2')
            
            # Results should be consistent for same user
            result1_again = flag.is_enabled('user1')
            self.assertEqual(result1, result1_again)
    
    def test_feature_flag_user_targeting(self):
        """Test feature flag user targeting"""
        flag = FeatureFlag(
            name='targeted_flag',
            enabled=True,
            environments=['production'],
            target_users=['user1@example.com', 'user2@example.com']
        )
        
        with patch('shared.feature_flags.get_environment') as mock_env:
            mock_env.return_value.value = 'production'
            
            # Targeted users should have flag enabled
            self.assertTrue(flag.is_enabled('user1@example.com'))
            self.assertTrue(flag.is_enabled('user2@example.com'))
            
            # Non-targeted user should have flag disabled
            self.assertFalse(flag.is_enabled('user3@example.com'))
    
    def test_feature_flag_dependencies(self):
        """Test feature flag dependencies"""
        flag = FeatureFlag(
            name='dependent_flag',
            enabled=True,
            environments=['production'],
            dependencies=['base_flag']
        )
        
        with patch('shared.feature_flags.get_environment') as mock_env:
            mock_env.return_value.value = 'production'
            
            # Mock the feature flag manager to check dependencies
            with patch('shared.feature_flags.feature_flag_manager') as mock_manager:
                # When dependency is not enabled, flag should be disabled
                mock_manager.is_enabled.return_value = False
                self.assertFalse(flag.is_enabled())
                
                # When dependency is enabled, flag should be enabled
                mock_manager.is_enabled.return_value = True
                self.assertTrue(flag.is_enabled())
    
    def test_feature_flag_usage_stats(self):
        """Test feature flag usage statistics"""
        flag = FeatureFlag(
            name='stats_flag',
            enabled=True
        )
        
        # Initially no usage
        stats = flag.get_usage_stats()
        self.assertEqual(stats['usage_count'], 0)
        
        # Check flag (increments usage)
        flag.is_enabled()
        stats = flag.get_usage_stats()
        self.assertEqual(stats['usage_count'], 1)
        
        # Check again
        flag.is_enabled()
        stats = flag.get_usage_stats()
        self.assertEqual(stats['usage_count'], 2)


class TestFeatureFlagManager(unittest.TestCase):
    """Test FeatureFlagManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global feature flag manager
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
        
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / 'feature_flags.json'
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
        
        # Clear global feature flag manager
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
    
    def test_manager_initialization(self):
        """Test feature flag manager initialization"""
        manager = FeatureFlagManager()
        
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager._flags, dict)
        # Should have default flags loaded
        self.assertGreater(len(manager._flags), 0)
    
    def test_manager_loads_default_flags(self):
        """Test that manager loads default flags"""
        manager = FeatureFlagManager()
        
        # Should have default flags
        self.assertIn('new_ui', manager._flags)
        self.assertIn('advanced_monitoring', manager._flags)
    
    def test_manager_loads_from_config(self):
        """Test that manager loads flags from config file"""
        # Create test config file
        test_config = {
            'test_flag': {
                'enabled': True,
                'environments': ['development'],
                'rollout_percentage': 100,
                'description': 'Test flag'
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Create manager with custom config path
        manager = FeatureFlagManager()
        manager._config_path = str(self.config_path)
        manager._load_flags_from_config()
        
        self.assertIn('test_flag', manager._flags)
    
    def test_is_enabled(self):
        """Test checking if flag is enabled"""
        manager = FeatureFlagManager()
        
        # Test existing flag
        result = manager.is_enabled('new_ui')
        self.assertIsInstance(result, bool)
    
    def test_is_enabled_nonexistent_flag(self):
        """Test checking if non-existent flag is enabled"""
        manager = FeatureFlagManager()
        
        # Non-existent flag should return False
        result = manager.is_enabled('nonexistent_flag')
        self.assertFalse(result)
    
    def test_enable_flag(self):
        """Test enabling a flag"""
        manager = FeatureFlagManager()
        
        # Disable a flag first
        manager.disable_flag('advanced_monitoring')
        self.assertFalse(manager.is_enabled('advanced_monitoring'))
        
        # Enable it
        manager.enable_flag('advanced_monitoring')
        self.assertTrue(manager.is_enabled('advanced_monitoring'))
    
    def test_enable_nonexistent_flag(self):
        """Test enabling non-existent flag"""
        manager = FeatureFlagManager()
        
        with self.assertRaises(FeatureFlagError):
            manager.enable_flag('nonexistent_flag')
    
    def test_disable_flag(self):
        """Test disabling a flag"""
        manager = FeatureFlagManager()
        
        # Enable a flag first
        manager.enable_flag('new_ui')
        self.assertTrue(manager.is_enabled('new_ui'))
        
        # Disable it
        manager.disable_flag('new_ui')
        self.assertFalse(manager.is_enabled('new_ui'))
    
    def test_disable_nonexistent_flag(self):
        """Test disabling non-existent flag"""
        manager = FeatureFlagManager()
        
        with self.assertRaises(FeatureFlagError):
            manager.disable_flag('nonexistent_flag')
    
    def test_set_rollout_percentage(self):
        """Test setting rollout percentage"""
        manager = FeatureFlagManager()
        
        manager.set_rollout_percentage('new_ui', 50)
        flag = manager.get_flag('new_ui')
        self.assertEqual(flag.rollout_percentage, 50)
    
    def test_set_invalid_rollout_percentage(self):
        """Test setting invalid rollout percentage"""
        manager = FeatureFlagManager()
        
        with self.assertRaises(FeatureFlagError):
            manager.set_rollout_percentage('new_ui', 150)  # Invalid percentage
    
    def test_get_flag(self):
        """Test getting a specific flag"""
        manager = FeatureFlagManager()
        
        flag = manager.get_flag('new_ui')
        self.assertIsNotNone(flag)
        self.assertEqual(flag.name, 'new_ui')
    
    def test_get_nonexistent_flag(self):
        """Test getting non-existent flag"""
        manager = FeatureFlagManager()
        
        flag = manager.get_flag('nonexistent_flag')
        self.assertIsNone(flag)
    
    def test_get_all_flags(self):
        """Test getting all flags"""
        manager = FeatureFlagManager()
        
        flags = manager.get_all_flags()
        
        self.assertIsInstance(flags, dict)
        self.assertGreater(len(flags), 0)
        self.assertIn('new_ui', flags)
    
    def test_get_usage_stats(self):
        """Test getting usage statistics for all flags"""
        manager = FeatureFlagManager()
        
        stats = manager.get_usage_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('new_ui', stats)
    
    def test_add_flag(self):
        """Test adding a new flag"""
        manager = FeatureFlagManager()
        
        new_flag = FeatureFlag(
            name='new_test_flag',
            enabled=True,
            environments=['development'],
            description='New test flag'
        )
        
        manager.add_flag(new_flag)
        
        self.assertIn('new_test_flag', manager._flags)
    
    def test_add_duplicate_flag(self):
        """Test adding duplicate flag"""
        manager = FeatureFlagManager()
        
        existing_flag = FeatureFlag(
            name='new_ui',  # Already exists
            enabled=True
        )
        
        with self.assertRaises(FeatureFlagError):
            manager.add_flag(existing_flag)
    
    def test_remove_flag(self):
        """Test removing a flag"""
        manager = FeatureFlagManager()
        
        # Add a test flag
        test_flag = FeatureFlag(
            name='test_remove_flag',
            enabled=True
        )
        manager.add_flag(test_flag)
        
        # Remove it
        manager.remove_flag('test_remove_flag')
        
        self.assertNotIn('test_remove_flag', manager._flags)
    
    def test_remove_nonexistent_flag(self):
        """Test removing non-existent flag"""
        manager = FeatureFlagManager()
        
        with self.assertRaises(FeatureFlagError):
            manager.remove_flag('nonexistent_flag')
    
    def test_update_flag(self):
        """Test updating a flag"""
        manager = FeatureFlagManager()
        
        manager.update_flag('new_ui', description='Updated description')
        
        flag = manager.get_flag('new_ui')
        self.assertEqual(flag.description, 'Updated description')
    
    def test_update_nonexistent_flag(self):
        """Test updating non-existent flag"""
        manager = FeatureFlagManager()
        
        with self.assertRaises(FeatureFlagError):
            manager.update_flag('nonexistent_flag', description='test')
    
    def test_save_flags_to_config(self):
        """Test saving flags to configuration file"""
        manager = FeatureFlagManager()
        manager._config_path = str(self.config_path)
        
        manager.save_flags_to_config()
        
        # Check that file was created
        self.assertTrue(self.config_path.exists())
        
        # Check that it contains valid JSON
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        self.assertIsInstance(config, dict)


class TestGlobalFunctions(unittest.TestCase):
    """Test global feature flag functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global feature flag manager
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear global feature flag manager
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
    
    def test_get_feature_flag_manager(self):
        """Test global get_feature_flag_manager function"""
        manager = get_feature_flag_manager()
        self.assertIsInstance(manager, FeatureFlagManager)
        
        # Should return same instance on subsequent calls
        manager2 = get_feature_flag_manager()
        self.assertIs(manager, manager2)
    
    def test_is_feature_enabled_global(self):
        """Test global is_feature_enabled function"""
        result = is_feature_enabled('new_ui')
        self.assertIsInstance(result, bool)
    
    def test_enable_feature_global(self):
        """Test global enable_feature function"""
        enable_feature('new_ui')
        self.assertTrue(is_feature_enabled('new_ui'))
    
    def test_disable_feature_global(self):
        """Test global disable_feature function"""
        disable_feature('new_ui')
        self.assertFalse(is_feature_enabled('new_ui'))


class TestFeatureFlagDecorator(unittest.TestCase):
    """Test feature flag decorator"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear global feature flag manager
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear global feature flag manager
        import shared.feature_flags as ff_module
        ff_module.feature_flag_manager = None
    
    def test_feature_flag_decorator_enabled(self):
        """Test feature flag decorator when flag is enabled"""
        manager = get_feature_flag_manager()
        manager.enable_flag('new_ui')
        
        @feature_flag('new_ui')
        def test_function():
            return "executed"
        
        result = test_function()
        self.assertEqual(result, "executed")
    
    def test_feature_flag_decorator_disabled(self):
        """Test feature flag decorator when flag is disabled"""
        manager = get_feature_flag_manager()
        manager.disable_flag('new_ui')
        
        @feature_flag('new_ui')
        def test_function():
            return "executed"
        
        result = test_function()
        self.assertIsNone(result)
    
    def test_feature_flag_decorator_with_user_id(self):
        """Test feature flag decorator with user ID parameter"""
        manager = get_feature_flag_manager()
        manager.enable_flag('new_ui')
        
        @feature_flag('new_ui', user_id_param='user_id')
        def test_function(user_id):
            return f"executed for {user_id}"
        
        result = test_function(user_id='test@example.com')
        self.assertEqual(result, "executed for test@example.com")


if __name__ == '__main__':
    unittest.main()