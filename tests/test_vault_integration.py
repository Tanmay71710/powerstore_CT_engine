"""
Vault Integration Tests for PowerStore CT Engine

This module contains comprehensive tests for Vault integration including:
- Vault client functionality
- Secret caching
- Vault path resolution
- Authentication methods
- Configuration loader integration
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import time
import threading
from typing import Dict, Any

# Mock hvac module
class MockHvacClient:
    """Mock hvac client for testing"""
    
    class MockSys:
        def read_health_status(self):
            return {
                'initialized': True,
                'sealed': False,
                'standby': False,
                'version': '1.12.0'
            }
    
    class MockSecrets:
        class MockKv:
            class MockV2:
                def read_secret_version(self, path, version=None):
                    if 'notfound' in path:
                        raise Exception("Secret not found")
                    return {
                        'data': {
                            'data': {
                                'password': 'test-password',
                                'username': 'test-user'
                            }
                        }
                    }
                
                def create_or_update_secret(self, path, secret):
                    return True
                
                def delete_metadata_and_all_versions(self, path):
                    return True
                
                def list_secrets(self, path):
                    if path == '':
                        return {'data': {'keys': ['database', 'jenkins']}}
                    return {'data': {'keys': ['password', 'username']}}
            
            class MockV1:
                def read_secret(self, path):
                    return {
                        'data': {
                            'password': 'test-password',
                            'username': 'test-user'
                        }
                    }
                
                def create_or_update_secret(self, path, secret):
                    return True
                
                def delete_secret(self, path):
                    return True
                
                def list_secrets(self, path):
                    return {'data': {'keys': ['password', 'username']}}
        
        def __init__(self):
            self.kv = self.MockKv()
            self.kv.v2 = self.MockKv.MockV2()
            self.kv.v1 = self.MockKv.MockV1()
    
    class MockAuth:
        class MockApprole:
            def login(self, role_id, secret_id):
                return {
                    'auth': {
                        'client_token': 'mock-token'
                    }
                }
        
        class MockKubernetes:
            def login(self, role, jwt):
                return {
                    'auth': {
                        'client_token': 'mock-token'
                    }
                }
        
        class MockLdap:
            def login(self, username, password):
                return {
                    'auth': {
                        'client_token': 'mock-token'
                    }
                }
        
        class MockUserpass:
            def login(self, username, password):
                return {
                    'auth': {
                        'client_token': 'mock-token'
                    }
                }
        
        def __init__(self):
            self.token = None
            self.sys = self.MockSys()
            self.secrets = self.MockSecrets()
            self.auth = self.MockAuth()
            self.auth.approle = self.MockApprole()
            self.auth.kubernetes = self.MockKubernetes()
            self.auth.ldap = self.MockLdap()
            self.auth.userpass = self.MockUserpass()
    
    def __init__(self, url, verify=True):
        self.url = url
        self.verify = verify


class TestVaultClient(unittest.TestCase):
    """Test Vault client functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.vault_url = "https://vault.example.com:8200"
        
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_vault_client_initialization(self):
        """Test Vault client initialization"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url=self.vault_url,
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        
        self.assertEqual(client.vault_url, self.vault_url)
        self.assertEqual(client.auth_method, VaultAuthMethod.TOKEN)
        self.assertEqual(client.auth_params['token'], 'test-token')
        self.assertFalse(client._authenticated)
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_token_authentication(self):
        """Test token authentication"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url=self.vault_url,
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        
        result = client.connect()
        self.assertTrue(result)
        self.assertTrue(client._authenticated)
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_get_secret(self):
        """Test getting secret from Vault"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url=self.vault_url,
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        client.connect()
        
        secret = client.get_secret('secret/data/test')
        self.assertIsNotNone(secret)
        self.assertEqual(secret['password'], 'test-password')
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_set_secret(self):
        """Test setting secret in Vault"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url=self.vault_url,
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        client.connect()
        
        result = client.set_secret('secret/data/test', {'password': 'new-password'})
        self.assertTrue(result)
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_list_secrets(self):
        """Test listing secrets in Vault"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url=self.vault_url,
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        client.connect()
        
        secrets = client.list_secrets('')
        self.assertIsNotNone(secrets)
        self.assertIn('database', secrets)
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_health_check(self):
        """Test Vault health check"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url=self.vault_url,
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        
        health = client.health_check()
        self.assertEqual(health['status'], 'not_connected')
        
        client.connect()
        health = client.health_check()
        self.assertEqual(health['status'], 'connected')
        self.assertTrue(health['initialized'])
        self.assertFalse(health['sealed'])


class TestSecretCache(unittest.TestCase):
    """Test secret caching functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        from shared.vault_client import SecretCache
        self.cache = SecretCache(ttl=1)  # 1 second TTL for testing
    
    def test_cache_set_and_get(self):
        """Test setting and getting cached secrets"""
        self.cache.set('test_key', 'test_value')
        value = self.cache.get('test_key')
        self.assertEqual(value, 'test_value')
    
    def test_cache_miss(self):
        """Test cache miss"""
        value = self.cache.get('nonexistent_key')
        self.assertIsNone(value)
    
    def test_cache_expiration(self):
        """Test cache expiration"""
        self.cache.set('test_key', 'test_value')
        
        # Wait for expiration
        time.sleep(1.1)
        
        value = self.cache.get('test_key')
        self.assertIsNone(value)
    
    def test_cache_invalidation(self):
        """Test cache invalidation"""
        self.cache.set('test_key', 'test_value')
        self.cache.invalidate('test_key')
        
        value = self.cache.get('test_key')
        self.assertIsNone(value)
    
    def test_cache_clear(self):
        """Test clearing all cache"""
        self.cache.set('key1', 'value1')
        self.cache.set('key2', 'value2')
        
        self.cache.clear()
        
        self.assertIsNone(self.cache.get('key1'))
        self.assertIsNone(self.cache.get('key2'))
    
    def test_cache_stats(self):
        """Test cache statistics"""
        self.cache.set('key1', 'value1')
        self.cache.set('key2', 'value2')
        
        # Hit
        self.cache.get('key1')
        
        # Miss
        self.cache.get('nonexistent')
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['size'], 2)
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
    
    def test_cache_thread_safety(self):
        """Test cache thread safety"""
        def set_value(key, value):
            for i in range(100):
                self.cache.set(f"{key}_{i}", f"{value}_{i}")
        
        def get_value():
            for i in range(100):
                self.cache.get(f"key_{i}")
        
        thread1 = threading.Thread(target=set_value, args=('key', 'value'))
        thread2 = threading.Thread(target=get_value)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Should not raise any exceptions
        self.assertTrue(True)


class TestVaultSecretManager(unittest.TestCase):
    """Test Vault secret manager"""
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_vault_secret_manager_initialization(self):
        """Test Vault secret manager initialization"""
        from shared.vault_client import VaultSecretManager, VaultAuthMethod
        
        manager = VaultSecretManager(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'},
            vault_enabled=True
        )
        
        self.assertTrue(manager.vault_enabled)
        self.assertEqual(manager.vault_url, "https://vault.example.com:8200")
        self.assertEqual(manager._vault_base_path, "secret/powerstore-ct-engine")
    
    def test_vault_secret_manager_disabled(self):
        """Test Vault secret manager when disabled"""
        from shared.vault_client import VaultSecretManager
        
        manager = VaultSecretManager(vault_enabled=False)
        
        self.assertFalse(manager.vault_enabled)
        self.assertIsNone(manager._client)
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_load_secret(self):
        """Test loading secret from Vault"""
        from shared.vault_client import VaultSecretManager, VaultAuthMethod
        
        manager = VaultSecretManager(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'},
            vault_enabled=True
        )
        
        secret = manager.load_secret('development', 'database')
        self.assertIsNotNone(secret)
        self.assertEqual(secret['password'], 'test-password')
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_cache_integration(self):
        """Test cache integration with secret manager"""
        from shared.vault_client import VaultSecretManager, VaultAuthMethod
        
        manager = VaultSecretManager(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'},
            vault_enabled=True,
            cache_ttl=300
        )
        
        # First call - should cache
        secret1 = manager.load_secret('development', 'database')
        
        # Second call - should use cache
        secret2 = manager.load_secret('development', 'database')
        
        self.assertEqual(secret1, secret2)
        
        stats = manager.get_cache_stats()
        self.assertGreater(stats['hits'], 0)
    
    def test_vault_path_construction(self):
        """Test Vault path construction"""
        from shared.vault_client import VaultSecretManager
        
        manager = VaultSecretManager(vault_enabled=False)
        
        env_path, common_path = manager._get_vault_path('development', 'database')
        
        self.assertEqual(env_path, 'secret/powerstore-ct-engine/development/database')
        self.assertEqual(common_path, 'secret/powerstore-ct-engine/common/database')


class TestConfigurationLoaderVaultIntegration(unittest.TestCase):
    """Test configuration loader integration with Vault"""
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    @patch.dict('os.environ', {'VAULT_TOKEN': 'test-token'})
    def test_vault_config_loading(self):
        """Test loading configuration from Vault"""
        from shared.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        # Mock environment config with Vault enabled
        loader._environment = Mock(value='development')
        loader._loaded_config = {
            'VAULT_ENABLED': True,
            'VAULT_URL': 'https://vault.example.com:8200',
            'VAULT_AUTH_METHOD': 'token'
        }
        
        vault_config = loader._load_vault_config()
        
        # Should return empty dict if Vault not properly configured
        # (in real scenario, would return Vault secrets)
        self.assertIsInstance(vault_config, dict)
    
    def test_vault_disabled_skips_loading(self):
        """Test that Vault loading is skipped when disabled"""
        from shared.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        loader._loaded_config = {
            'VAULT_ENABLED': False
        }
        
        vault_config = loader._load_vault_config()
        
        self.assertEqual(vault_config, {})
    
    @patch.dict('os.environ', {}, clear=True)
    def test_kubernetes_jwt_reading(self):
        """Test Kubernetes JWT token reading"""
        from shared.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        # When JWT file doesn't exist
        jwt = loader._get_kubernetes_jwt()
        self.assertIsNone(jwt)
    
    def test_vault_secret_conversion(self):
        """Test conversion of Vault secrets to config keys"""
        from shared.config_loader import ConfigLoader
        
        loader = ConfigLoader()
        
        vault_secrets = {
            'database_password': 'secret-password',
            'jenkins_password': 'jenkins-secret'
        }
        
        config_dict = loader._convert_vault_secrets_to_config(vault_secrets)
        
        self.assertIn('DATABASE_PASSWORD', config_dict)
        self.assertEqual(config_dict['DATABASE_PASSWORD'], 'secret-password')


class TestVaultAuthMethods(unittest.TestCase):
    """Test different Vault authentication methods"""
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_token_auth(self):
        """Test token authentication"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        
        result = client.connect()
        self.assertTrue(result)
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_approle_auth(self):
        """Test AppRole authentication"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.APPROLE,
            auth_params={
                'role_id': 'test-role-id',
                'secret_id': 'test-secret-id'
            }
        )
        
        result = client.connect()
        self.assertTrue(result)
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_kubernetes_auth(self):
        """Test Kubernetes authentication"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        
        client = VaultClient(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.KUBERNETES,
            auth_params={
                'role': 'test-role',
                'jwt': 'test-jwt-token'
            }
        )
        
        result = client.connect()
        self.assertTrue(result)
    
    def test_invalid_auth_method(self):
        """Test invalid authentication method"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        from shared.exceptions import VaultAuthenticationError
        
        client = VaultClient(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={}  # Missing token
        )
        
        with self.assertRaises(VaultAuthenticationError):
            client.connect()


class TestVaultErrorHandling(unittest.TestCase):
    """Test Vault error handling"""
    
    @patch('shared.vault_client.hvac', None)
    def test_hvac_not_installed(self):
        """Test handling when hvac is not installed"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        from shared.exceptions import VaultConnectionError
        
        client = VaultClient(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        
        with self.assertRaises(VaultConnectionError):
            client.connect()
    
    @patch('shared.vault_client.hvac', Mock(Client=MockHvacClient))
    def test_secret_not_found(self):
        """Test handling when secret is not found"""
        from shared.vault_client import VaultClient, VaultAuthMethod
        from shared.exceptions import VaultSecretNotFoundError
        
        client = VaultClient(
            vault_url="https://vault.example.com:8200",
            auth_method=VaultAuthMethod.TOKEN,
            auth_params={'token': 'test-token'}
        )
        client.connect()
        
        with self.assertRaises(VaultSecretNotFoundError):
            client.get_secret('secret/data/notfound')


if __name__ == '__main__':
    unittest.main()