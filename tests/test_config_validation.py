"""
Unit tests for configuration validation system.

Tests are designed to be safe and non-destructive.
They only test validation logic and don't modify any data.
"""

import unittest
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config.validation import (
    DatabaseConfig,
    JenkinsConfig,
    LDAPConfig,
    VaultConfig,
    SecurityConfig,
    AppConfig,
    ConfigValidator,
    Environment,
    validate_config_dict
)
from shared.exceptions import ConfigurationValidationError


class TestDatabaseConfig(unittest.TestCase):
    """Test DatabaseConfig validation"""
    
    def test_valid_database_config(self):
        """Test valid database configuration"""
        config = DatabaseConfig(
            host='localhost',
            port=5432,
            name='testdb',
            user='testuser',
            password='testpass123',
            ssl_mode='require'
        )
        self.assertEqual(config.host, 'localhost')
        self.assertEqual(config.port, 5432)
    
    def test_invalid_host_format(self):
        """Test invalid database host format"""
        with self.assertRaises(ConfigurationValidationError):
            DatabaseConfig(
                host='invalid host with spaces',
                port=5432,
                name='testdb',
                user='testuser',
                password='testpass123'
            )
    
    def test_invalid_port_range(self):
        """Test invalid port range"""
        with self.assertRaises(Exception):  # Pydantic validation error
            DatabaseConfig(
                host='localhost',
                port=99999,  # Invalid port
                name='testdb',
                user='testuser',
                password='testpass123'
            )
    
    def test_invalid_database_name(self):
        """Test invalid database name format"""
        with self.assertRaises(ConfigurationValidationError):
            DatabaseConfig(
                host='localhost',
                port=5432,
                name='invalid-db-name',
                user='testuser',
                password='testpass123'
            )
    
    def test_weak_password(self):
        """Test weak password validation"""
        with self.assertRaises(ConfigurationValidationError):
            DatabaseConfig(
                host='localhost',
                port=5432,
                name='testdb',
                user='testuser',
                password='weak'  # Too short
            )
    
    def test_strong_password(self):
        """Test strong password validation"""
        config = DatabaseConfig(
            host='localhost',
            port=5432,
            name='testdb',
            user='testuser',
            password='strongPassword123'
        )
        self.assertEqual(config.password, 'strongPassword123')


class TestJenkinsConfig(unittest.TestCase):
    """Test JenkinsConfig validation"""
    
    def test_valid_jenkins_config(self):
        """Test valid Jenkins configuration"""
        config = JenkinsConfig(
            url='https://jenkins.example.com',
            username='jenkins_user',
            password='jenkins_password',
            timeout=300
        )
        self.assertEqual(config.url, 'https://jenkins.example.com')
    
    def test_invalid_jenkins_url(self):
        """Test invalid Jenkins URL format"""
        with self.assertRaises(ConfigurationValidationError):
            JenkinsConfig(
                url='invalid-url',
                username='jenkins_user',
                password='jenkins_password'
            )
    
    def test_jenkins_url_without_protocol(self):
        """Test Jenkins URL without protocol"""
        with self.assertRaises(ConfigurationValidationError):
            JenkinsConfig(
                url='jenkins.example.com',
                username='jenkins_user',
                password='jenkins_password'
            )
    
    def test_invalid_timeout_range(self):
        """Test invalid timeout range"""
        with self.assertRaises(Exception):  # Pydantic validation error
            JenkinsConfig(
                url='https://jenkins.example.com',
                username='jenkins_user',
                password='jenkins_password',
                timeout=5000  # Too long
            )


class TestLDAPConfig(unittest.TestCase):
    """Test LDAPConfig validation"""
    
    def test_valid_ldap_config(self):
        """Test valid LDAP configuration"""
        config = LDAPConfig(
            url='ldaps://ldap.example.com:636',
            base_dn='DC=example,DC=com',
            bind_dn='CN=admin,DC=example,DC=com',
            use_ssl=True
        )
        self.assertEqual(config.url, 'ldaps://ldap.example.com:636')
    
    def test_invalid_ldap_url(self):
        """Test invalid LDAP URL format"""
        with self.assertRaises(ConfigurationValidationError):
            LDAPConfig(
                url='invalid-ldap-url',
                base_dn='DC=example,DC=com',
                bind_dn='CN=admin,DC=example,DC=com'
            )
    
    def test_ldap_url_without_protocol(self):
        """Test LDAP URL without protocol"""
        with self.assertRaises(ConfigurationValidationError):
            LDAPConfig(
                url='ldap.example.com',
                base_dn='DC=example,DC=com',
                bind_dn='CN=admin,DC=example,DC=com'
            )


class TestVaultConfig(unittest.TestCase):
    """Test VaultConfig validation"""
    
    def test_valid_vault_config_disabled(self):
        """Test valid Vault configuration when disabled"""
        config = VaultConfig(
            enabled=False,
            url='http://localhost:8200'
        )
        self.assertFalse(config.enabled)
    
    def test_valid_vault_config_enabled(self):
        """Test valid Vault configuration when enabled"""
        config = VaultConfig(
            enabled=True,
            url='https://vault.example.com:8200',
            role='test-role'
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.url, 'https://vault.example.com:8200')
    
    def test_invalid_vault_url_when_enabled(self):
        """Test invalid Vault URL when enabled"""
        with self.assertRaises(ConfigurationValidationError):
            VaultConfig(
                enabled=True,
                url='invalid-url'
            )
    
    def test_invalid_token_ttl(self):
        """Test invalid token TTL"""
        with self.assertRaises(Exception):  # Pydantic validation error
            VaultConfig(
                enabled=False,
                url='http://localhost:8200',
                token_ttl=100000  # Too long
            )


class TestSecurityConfig(unittest.TestCase):
    """Test SecurityConfig validation"""
    
    def test_valid_security_config(self):
        """Test valid security configuration"""
        config = SecurityConfig(
            secret_key='very-secret-key-at-least-32-characters-long',
            session_cookie_secure=True,
            session_cookie_httponly=True,
            session_samesite='Strict'
        )
        self.assertEqual(config.secret_key, 'very-secret-key-at-least-32-characters-long')
    
    def test_weak_secret_key(self):
        """Test weak secret key validation"""
        with self.assertRaises(ConfigurationValidationError):
            SecurityConfig(
                secret_key='short-key'
            )
    
    def test_invalid_samesite_policy(self):
        """Test invalid SameSite policy"""
        with self.assertRaises(ConfigurationValidationError):
            SecurityConfig(
                secret_key='very-secret-key-at-least-32-characters-long',
                session_samesite='Invalid'
            )
    
    def test_valid_samesite_policies(self):
        """Test valid SameSite policies"""
        for policy in ['Strict', 'Lax', 'None']:
            config = SecurityConfig(
                secret_key='very-secret-key-at-least-32-characters-long',
                session_samesite=policy
            )
            self.assertEqual(config.session_samesite, policy)


class TestAppConfig(unittest.TestCase):
    """Test AppConfig validation"""
    
    def test_valid_development_config(self):
        """Test valid development configuration"""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            debug=True,
            database=DatabaseConfig(
                host='localhost',
                port=5432,
                name='testdb',
                user='testuser',
                password='testpass123'
            ),
            jenkins=JenkinsConfig(
                url='https://jenkins.example.com',
                username='jenkins_user',
                password='jenkins_password'
            ),
            ldap=LDAPConfig(
                url='ldaps://ldap.example.com:636',
                base_dn='DC=example,DC=com',
                bind_dn='CN=admin,DC=example,DC=com'
            ),
            vault=VaultConfig(enabled=False, url='http://localhost:8200'),
            security=SecurityConfig(
                secret_key='very-secret-key-at-least-32-characters-long'
            )
        )
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertTrue(config.debug)
    
    def test_production_with_debug_enabled(self):
        """Test production configuration with debug enabled (should fail)"""
        with self.assertRaises(Exception):  # Pydantic validation error
            AppConfig(
                environment=Environment.PRODUCTION,
                debug=True,  # Invalid for production
                database=DatabaseConfig(
                    host='localhost',
                    port=5432,
                    name='testdb',
                    user='testuser',
                    password='testpass123'
                ),
                jenkins=JenkinsConfig(
                    url='https://jenkins.example.com',
                    username='jenkins_user',
                    password='jenkins_password'
                ),
                ldap=LDAPConfig(
                    url='ldaps://ldap.example.com:636',
                    base_dn='DC=example,DC=com',
                    bind_dn='CN=admin,DC=example,DC=com'
                ),
                vault=VaultConfig(enabled=True, url='https://vault.example.com'),
                security=SecurityConfig(
                    secret_key='very-secret-key-at-least-32-characters-long',
                    session_cookie_secure=True
                )
            )
    
    def test_production_with_insecure_cookies(self):
        """Test production configuration with insecure cookies (should fail)"""
        with self.assertRaises(Exception):  # Pydantic validation error
            AppConfig(
                environment=Environment.PRODUCTION,
                debug=False,
                database=DatabaseConfig(
                    host='localhost',
                    port=5432,
                    name='testdb',
                    user='testuser',
                    password='testpass123'
                ),
                jenkins=JenkinsConfig(
                    url='https://jenkins.example.com',
                    username='jenkins_user',
                    password='jenkins_password'
                ),
                ldap=LDAPConfig(
                    url='ldaps://ldap.example.com:636',
                    base_dn='DC=example,DC=com',
                    bind_dn='CN=admin,DC=example,DC=com'
                ),
                vault=VaultConfig(enabled=True, url='https://vault.example.com'),
                security=SecurityConfig(
                    secret_key='very-secret-key-at-least-32-characters-long',
                    session_cookie_secure=False  # Invalid for production
                )
            )


class TestConfigValidator(unittest.TestCase):
    """Test ConfigValidator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.validator = ConfigValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        self.assertIsNotNone(self.validator)
        self.assertEqual(len(self.validator._errors), 0)
        self.assertEqual(len(self.validator._warnings), 0)
    
    def test_validate_valid_config(self):
        """Test validating valid configuration"""
        config_dict = {
            'DEBUG': True,
            'DATABASE_HOST': 'localhost',
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
            'VAULT_URL': 'http://localhost:8200',
            'SESSION_COOKIE_SECURE': False,
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax'
        }
        
        result = self.validator.validate_config(config_dict, 'development')
        self.assertTrue(result)
    
    def test_validate_invalid_database_config(self):
        """Test validating invalid database configuration"""
        config_dict = {
            'DEBUG': True,
            'DATABASE_HOST': 'invalid host with spaces',  # Invalid
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
        
        result = self.validator.validate_config(config_dict, 'development')
        self.assertFalse(result)
        self.assertTrue(self.validator.has_errors())
    
    def test_validate_production_config_warnings(self):
        """Test validating production configuration with warnings"""
        config_dict = {
            'DEBUG': False,
            'DATABASE_HOST': 'localhost',
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
            'VAULT_ENABLED': False,  # Warning in production
            'KUBERNETES_ENABLED': False,  # Warning in production
            'SESSION_COOKIE_SECURE': True,
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Strict'
        }
        
        result = self.validator.validate_config(config_dict, 'production')
        # Should pass validation but have warnings
        self.assertTrue(result)
        self.assertTrue(self.validator.has_warnings())
    
    def test_get_errors(self):
        """Test getting validation errors"""
        config_dict = {
            'DEBUG': True,
            'DATABASE_HOST': 'invalid host',
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
        
        self.validator.validate_config(config_dict, 'development')
        errors = self.validator.get_errors()
        
        self.assertGreater(len(errors), 0)
        self.assertIsInstance(errors[0], ConfigurationValidationError)
    
    def test_get_warnings(self):
        """Test getting validation warnings"""
        config_dict = {
            'DEBUG': False,
            'DATABASE_HOST': 'localhost',
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
            'KUBERNETES_ENABLED': False,
            'SESSION_COOKIE_SECURE': True,
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Strict'
        }
        
        self.validator.validate_config(config_dict, 'production')
        warnings = self.validator.get_warnings()
        
        # Production without Vault should have warnings
        self.assertGreater(len(warnings), 0)
    
    def test_format_errors(self):
        """Test formatting validation errors"""
        config_dict = {
            'DEBUG': True,
            'DATABASE_HOST': 'invalid host',
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
        
        self.validator.validate_config(config_dict, 'development')
        error_string = self.validator.format_errors()
        
        self.assertIsInstance(error_string, str)
        self.assertIn('DATABASE_HOST', error_string)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience validation functions"""
    
    def test_validate_config_dict_valid(self):
        """Test validate_config_dict with valid config"""
        config_dict = {
            'DEBUG': True,
            'DATABASE_HOST': 'localhost',
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
        
        result = validate_config_dict(config_dict, 'development')
        self.assertTrue(result)
    
    def test_validate_config_dict_invalid(self):
        """Test validate_config_dict with invalid config"""
        config_dict = {
            'DEBUG': True,
            'DATABASE_HOST': 'invalid host',
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
        
        with self.assertRaises(ConfigurationValidationError):
            validate_config_dict(config_dict, 'development')


if __name__ == '__main__':
    unittest.main()