"""
Unit tests for environment detection system.

Tests are designed to be safe and non-destructive.
They only test logic and don't modify any data or systems.
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '/mnt/c/powerstore/All frameworks/ct engine/v4/powerstore_CT_engine')

from shared.environment import (
    Environment,
    EnvironmentDetector,
    EnvironmentDetectionError,
    get_environment,
    is_development,
    is_staging,
    is_production
)


class TestEnvironmentEnum(unittest.TestCase):
    """Test Environment enum"""
    
    def test_environment_values(self):
        """Test that environment enum has correct values"""
        self.assertEqual(Environment.DEVELOPMENT.value, "development")
        self.assertEqual(Environment.STAGING.value, "staging")
        self.assertEqual(Environment.PRODUCTION.value, "production")
    
    def test_environment_string_conversion(self):
        """Test environment enum to string conversion"""
        self.assertEqual(str(Environment.DEVELOPMENT), "development")
        self.assertEqual(str(Environment.STAGING), "staging")
        self.assertEqual(str(Environment.PRODUCTION), "production")


class TestEnvironmentDetector(unittest.TestCase):
    """Test EnvironmentDetector class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = EnvironmentDetector()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir)
    
    def test_detector_initialization(self):
        """Test detector initialization"""
        self.assertIsNotNone(self.detector)
        self.assertIsNone(self.detector._cached_environment)
        self.assertEqual(len(self.detector._detection_sources), 0)
    
    def test_environment_variable_detection(self):
        """Test environment detection from environment variable"""
        # Test with development environment
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            env = self.detector._detect_from_env_variable()
            self.assertEqual(env, Environment.DEVELOPMENT)
        
        # Test with staging environment
        with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}):
            env = self.detector._detect_from_env_variable()
            self.assertEqual(env, Environment.STAGING)
        
        # Test with production environment
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            env = self.detector._detect_from_env_variable()
            self.assertEqual(env, Environment.PRODUCTION)
    
    def test_environment_variable_invalid(self):
        """Test environment detection with invalid environment variable"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'invalid'}):
            with self.assertRaises(EnvironmentDetectionError):
                self.detector._detect_from_env_variable()
    
    def test_environment_variable_missing(self):
        """Test environment detection when variable is missing"""
        env = self.detector._detect_from_env_variable()
        self.assertIsNone(env)
    
    def test_filesystem_detection(self):
        """Test environment detection from filesystem markers"""
        # Create test .env.development file
        env_file = Path(self.temp_dir) / '.env.development'
        env_file.write_text('ENVIRONMENT=development')
        
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        try:
            env = self.detector._detect_from_filesystem()
            # Should detect from .env.development file
            self.assertIsNotNone(env)
        finally:
            os.chdir(original_cwd)
    
    def test_filesystem_detection_no_files(self):
        """Test environment detection when no filesystem markers exist"""
        env = self.detector._detect_from_filesystem()
        self.assertIsNone(env)
    
    def test_network_context_detection_localhost(self):
        """Test network context detection with localhost"""
        with patch('socket.gethostname', return_value='localhost'):
            env = self.detector._detect_from_network_context()
            # Should detect development from localhost
            self.assertEqual(env, Environment.DEVELOPMENT)
    
    def test_network_context_detection_no_match(self):
        """Test network context detection with no matching patterns"""
        with patch('socket.gethostname', return_value='unknown-host'):
            with patch('socket.gethostbyname', return_value='10.0.0.1'):
                env = self.detector._detect_from_network_context()
                self.assertIsNone(env)
    
    def test_default_detection(self):
        """Test default environment detection"""
        env = self.detector._detect_default()
        self.assertEqual(env, Environment.DEVELOPMENT)
    
    def test_full_detection_with_env_var(self):
        """Test full environment detection with environment variable"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}):
            env = self.detector.detect_environment()
            self.assertEqual(env, Environment.STAGING)
            self.assertIn('ENVIRONMENT variable', self.detector._detection_sources)
    
    def test_detection_caching(self):
        """Test that environment detection is cached"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            # First detection
            env1 = self.detector.detect_environment()
            # Second detection (should use cache)
            env2 = self.detector.detect_environment()
            
            self.assertEqual(env1, env2)
            self.assertEqual(env1, Environment.PRODUCTION)
    
    def test_detection_force_redetect(self):
        """Test force re-detection"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            # First detection
            env1 = self.detector.detect_environment()
            
            # Change environment
            with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}, clear=True):
                # Force re-detection
                env2 = self.detector.detect_environment(force_redetect=True)
                
                self.assertEqual(env1, Environment.DEVELOPMENT)
                self.assertEqual(env2, Environment.STAGING)
    
    def test_production_validation_debug_mode(self):
        """Test production validation with debug mode enabled"""
        # Create detector with production environment
        detector = EnvironmentDetector()
        detector._cached_environment = Environment.PRODUCTION
        
        with patch.dict(os.environ, {'DEBUG': 'true'}):
            result = detector.validate_environment(Environment.PRODUCTION)
            self.assertFalse(result)
    
    def test_production_validation_test_database(self):
        """Test production validation with test database name"""
        detector = EnvironmentDetector()
        detector._cached_environment = Environment.PRODUCTION
        
        with patch.dict(os.environ, {'DB_NAME': 'test_db'}):
            result = detector.validate_environment(Environment.PRODUCTION)
            self.assertFalse(result)
    
    def test_get_environment_info(self):
        """Test getting environment information"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            info = self.detector.get_environment_info()
            
            self.assertIn('environment', info)
            self.assertIn('detection_sources', info)
            self.assertIn('kubernetes_available', info)
            self.assertIn('hostname', info)
            self.assertIn('validation_passed', info)


class TestGlobalFunctions(unittest.TestCase):
    """Test global environment functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear cached detector
        import shared.environment as env_module
        env_module._environment_detector = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear cached detector
        import shared.environment as env_module
        env_module._environment_detector = None
    
    def test_get_environment(self):
        """Test global get_environment function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}):
            env = get_environment()
            self.assertEqual(env, Environment.STAGING)
    
    def test_is_development(self):
        """Test is_development function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            self.assertTrue(is_development())
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            self.assertFalse(is_development())
    
    def test_is_staging(self):
        """Test is_staging function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'staging'}):
            self.assertTrue(is_staging())
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            self.assertFalse(is_staging())
    
    def test_is_production(self):
        """Test is_production function"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            self.assertTrue(is_production())
        
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            self.assertFalse(is_production())


class TestEnvironmentDecorators(unittest.TestCase):
    """Test environment-based decorators"""
    
    def test_require_production_decorator(self):
        """Test require_production decorator"""
        from shared.environment import require_production, EnvironmentDetectionError
        
        @require_production
        def production_only_function():
            return "success"
        
        # Test with production environment
        with patch('shared.environment.is_production', return_value=True):
            result = production_only_function()
            self.assertEqual(result, "success")
        
        # Test with non-production environment
        with patch('shared.environment.is_production', return_value=False):
            with self.assertRaises(EnvironmentDetectionError):
                production_only_function()
    
    def test_require_non_production_decorator(self):
        """Test require_non_production decorator"""
        from shared.environment import require_non_production, EnvironmentDetectionError
        
        @require_non_production
        def non_production_function():
            return "success"
        
        # Test with development environment
        with patch('shared.environment.is_production', return_value=False):
            result = non_production_function()
            self.assertEqual(result, "success")
        
        # Test with production environment
        with patch('shared.environment.is_production', return_value=True):
            with self.assertRaises(EnvironmentDetectionError):
                non_production_function()


if __name__ == '__main__':
    unittest.main()