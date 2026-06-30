#!/usr/bin/env python3
"""
Secret Migration Tool for PowerStore CT Engine

This tool helps migrate secrets from configuration files and environment
variables to HashiCorp Vault. It supports discovery, dry-run, execution,
validation, and rollback of secret migrations.

Usage:
    python migrate_secrets.py --discover
    python migrate_secrets.py --dry-run
    python migrate_secrets.py --execute
    python migrate_secrets.py --validate
    python migrate_secrets.py --rollback
"""

import os
import sys
import re
import json
import argparse
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.vault_client import VaultClient, VaultAuthMethod, initialize_vault_manager
from shared.environment import get_environment
from shared.exceptions import VaultConnectionError, VaultSecretNotFoundError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecretDiscoverer:
    """
    Discover secrets in the codebase.
    """
    
    # Patterns that might indicate secrets
    SECRET_PATTERNS = [
        r'password\s*=\s*["\']([^"\']+)["\']',
        r'secret\s*=\s*["\']([^"\']+)["\']',
        r'token\s*=\s*["\']([^"\']+)["\']',
        r'api_key\s*=\s*["\']([^"\']+)["\']',
        r'webhook_url\s*=\s*["\']([^"\']+)["\']',
        r'DATABASE_PASSWORD\s*=\s*["\']([^"\']+)["\']',
        r'JENKINS_PASSWORD\s*=\s*["\']([^"\']+)["\']',
        r'LDAP_BIND_DN_PASSWORD\s*=\s*["\']([^"\']+)["\']',
        r'SECRET_KEY\s*=\s*["\']([^"\']+)["\']',
    ]
    
    # Files to scan
    CONFIG_FILES = [
        'shared/config/base.py',
        'shared/config/development.py',
        'shared/config/staging.py',
        'shared/config/production.py',
        '.env.development',
        '.env.staging',
        '.env.production',
    ]
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.discovered_secrets: Dict[str, List[Dict[str, Any]]] = {}
        
    def discover(self) -> Dict[str, Any]:
        """
        Discover all secrets in the codebase.
        
        Returns:
            Dictionary of discovered secrets organized by file
        """
        logger.info("Starting secret discovery...")
        
        for config_file in self.CONFIG_FILES:
            file_path = self.base_path / config_file
            if not file_path.exists():
                logger.warning(f"File not found: {config_file}")
                continue
            
            secrets = self._scan_file(file_path)
            if secrets:
                self.discovered_secrets[config_file] = secrets
                logger.info(f"Found {len(secrets)} potential secrets in {config_file}")
        
        return self.discovered_secrets
    
    def _scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Scan a single file for secrets.
        
        Args:
            file_path: Path to the file to scan
            
        Returns:
            List of discovered secrets
        """
        secrets = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            for pattern in self.SECRET_PATTERNS:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    secret_value = match.group(1)
                    
                    # Filter out obvious non-secrets
                    if self._is_likely_secret(secret_value):
                        secrets.append({
                            'pattern': pattern,
                            'value': secret_value,
                            'line': content[:match.start()].count('\n') + 1,
                            'context': self._get_context(content, match.start())
                        })
            
        except Exception as e:
            logger.error(f"Error scanning file {file_path}: {e}")
        
        return secrets
    
    def _is_likely_secret(self, value: str) -> bool:
        """
        Determine if a value is likely a secret.
        
        Args:
            value: The value to check
            
        Returns:
            True if likely a secret
        """
        # Filter out placeholder values
        placeholders = [
            'from-vault',
            'change-this',
            'example',
            'your-secret',
            'placeholder',
            'postgres',
            'admin',
            'password',
            'secret'
        ]
        
        value_lower = value.lower()
        for placeholder in placeholders:
            if placeholder in value_lower:
                return False
        
        # Check if it looks like a real secret
        # (not too short, not just alphanumeric, etc.)
        if len(value) < 8:
            return False
        
        if value.isalnum() and len(value) < 16:
            return False
        
        return True
    
    def _get_context(self, content: str, position: int) -> str:
        """Get context around a match"""
        start = max(0, position - 50)
        end = min(len(content), position + 50)
        return content[start:end]


class SecretMigrator:
    """
    Migrate secrets to Vault.
    """
    
    # Mapping of config keys to Vault paths
    VAULT_PATH_MAPPING = {
        'DATABASE_PASSWORD': 'database/password',
        'DATABASE_HOST': 'database/host',
        'JENKINS_PASSWORD': 'jenkins/password',
        'JENKINS_USERNAME': 'jenkins/username',
        'LDAP_BIND_DN_PASSWORD': 'ldap/bind_dn_password',
        'SECRET_KEY': 'app/secret_key',
        'EMAIL_SMTP_PASSWORD': 'email/smtp_password',
        'SLACK_WEBHOOK_URL': 'slack/webhook_url',
        'CACHE_REDIS_PASSWORD': 'redis/password',
    }
    
    def __init__(
        self,
        vault_url: str,
        auth_method: VaultAuthMethod,
        auth_params: Dict[str, Any],
        environment: str,
        dry_run: bool = False
    ):
        self.vault_url = vault_url
        self.auth_method = auth_method
        self.auth_params = auth_params
        self.environment = environment
        self.dry_run = dry_run
        self.vault_client: Optional[VaultClient] = None
        self.migration_log: List[Dict[str, Any]] = []
        
    def connect(self):
        """Connect to Vault"""
        try:
            self.vault_client = VaultClient(
                vault_url=self.vault_url,
                auth_method=self.auth_method,
                auth_params=self.auth_params
            )
            self.vault_client.connect()
            logger.info("Connected to Vault successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Vault: {e}")
            raise
    
    def migrate_secret(self, key: str, value: str) -> bool:
        """
        Migrate a single secret to Vault.
        
        Args:
            key: Configuration key
            value: Secret value
            
        Returns:
            True if successful
        """
        if key not in self.VAULT_PATH_MAPPING:
            logger.warning(f"No Vault path mapping for key: {key}")
            return False
        
        vault_path_suffix = self.VAULT_PATH_MAPPING[key]
        vault_path = f"secret/powerstore-ct-engine/{self.environment}/{vault_path_suffix}"
        
        logger.info(f"Migrating {key} to {vault_path}")
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would write secret to {vault_path}")
            self.migration_log.append({
                'key': key,
                'vault_path': vault_path,
                'status': 'dry-run',
                'timestamp': datetime.now().isoformat()
            })
            return True
        
        try:
            secret_data = {
                key: value,
                'migrated_at': datetime.now().isoformat(),
                'migrated_by': 'secret_migration_tool'
            }
            
            self.vault_client.set_secret(vault_path, secret_data)
            
            self.migration_log.append({
                'key': key,
                'vault_path': vault_path,
                'status': 'success',
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Successfully migrated {key} to Vault")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate {key} to Vault: {e}")
            self.migration_log.append({
                'key': key,
                'vault_path': vault_path,
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return False
    
    def migrate_from_config(self, config_file: str) -> int:
        """
        Migrate secrets from a configuration file.
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            Number of secrets migrated
        """
        logger.info(f"Migrating secrets from {config_file}")
        
        migrated_count = 0
        config_path = Path(config_file)
        
        if not config_path.exists():
            logger.error(f"Config file not found: {config_file}")
            return 0
        
        try:
            with open(config_path, 'r') as f:
                content = f.read()
            
            # Extract secrets from config
            for key, vault_path_suffix in self.VAULT_PATH_MAPPING.items():
                pattern = f'{key}\\s*=\\s*["\']([^"\']+)["\']'
                matches = re.findall(pattern, content)
                
                for value in matches:
                    if self._is_likely_secret(value):
                        if self.migrate_secret(key, value):
                            migrated_count += 1
        
        except Exception as e:
            logger.error(f"Error migrating from {config_file}: {e}")
        
        return migrated_count
    
    def _is_likely_secret(self, value: str) -> bool:
        """Check if value is likely a secret"""
        placeholders = ['from-vault', 'change-this', 'example', 'placeholder']
        value_lower = value.lower()
        
        for placeholder in placeholders:
            if placeholder in value_lower:
                return False
        
        return len(value) >= 8
    
    def validate_migration(self) -> Dict[str, Any]:
        """
        Validate that all secrets were migrated successfully.
        
        Returns:
            Validation results
        """
        logger.info("Validating migration...")
        
        results = {
            'total': len(self.migration_log),
            'successful': 0,
            'failed': 0,
            'dry_run': 0,
            'details': []
        }
        
        for entry in self.migration_log:
            status = entry['status']
            results[status] = results.get(status, 0) + 1
            results['details'].append(entry)
        
        logger.info(f"Validation results: {results}")
        return results
    
    def create_backup(self, config_file: str) -> str:
        """
        Create backup of configuration file before migration.
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            Path to backup file
        """
        config_path = Path(config_file)
        backup_path = config_path.with_suffix('.py.backup')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = config_path.with_suffix(f'.py.backup.{timestamp}')
        
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        return str(backup_path)
    
    def rollback(self, backup_path: str, original_path: str) -> bool:
        """
        Rollback migration by restoring from backup.
        
        Args:
            backup_path: Path to backup file
            original_path: Path to original file
            
        Returns:
            True if successful
        """
        try:
            shutil.copy2(backup_path, original_path)
            logger.info(f"Rolled back {original_path} from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            return False
    
    def save_migration_log(self, log_file: str = 'migration_log.json'):
        """Save migration log to file"""
        with open(log_file, 'w') as f:
            json.dump(self.migration_log, f, indent=2)
        logger.info(f"Saved migration log to {log_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Secret Migration Tool for PowerStore CT Engine'
    )
    
    parser.add_argument(
        '--action',
        choices=['discover', 'dry-run', 'execute', 'validate', 'rollback'],
        required=True,
        help='Action to perform'
    )
    
    parser.add_argument(
        '--vault-url',
        default='http://localhost:8200',
        help='Vault server URL'
    )
    
    parser.add_argument(
        '--auth-method',
        choices=['token', 'approle', 'kubernetes', 'ldap', 'userpass'],
        default='token',
        help='Vault authentication method'
    )
    
    parser.add_argument(
        '--token',
        help='Vault token (for token auth)'
    )
    
    parser.add_argument(
        '--role-id',
        help='AppRole role ID (for approle auth)'
    )
    
    parser.add_argument(
        '--secret-id',
        help='AppRole secret ID (for approle auth)'
    )
    
    parser.add_argument(
        '--environment',
        default='development',
        help='Target environment'
    )
    
    parser.add_argument(
        '--config-file',
        help='Configuration file to migrate'
    )
    
    parser.add_argument(
        '--backup-path',
        help='Backup file path for rollback'
    )
    
    parser.add_argument(
        '--base-path',
        default='.',
        help='Base path for discovery'
    )
    
    args = parser.parse_args()
    
    # Determine environment
    environment = args.environment or get_environment().value
    
    logger.info(f"Running secret migration tool")
    logger.info(f"Action: {args.action}")
    logger.info(f"Environment: {environment}")
    
    # Prepare auth params
    auth_method = VaultAuthMethod(args.auth_method)
    auth_params = {}
    
    if args.auth_method == 'token' and args.token:
        auth_params['token'] = args.token
    elif args.auth_method == 'approle':
        auth_params['role_id'] = args.role_id
        auth_params['secret_id'] = args.secret_id
    elif args.auth_method == 'kubernetes':
        auth_params['role'] = 'powerstore-ct-engine'
        auth_params['jwt'] = os.getenv('VAULT_KUBERNETES_JWT')
    elif args.auth_method == 'ldap':
        auth_params['username'] = os.getenv('VAULT_LDAP_USERNAME')
        auth_params['password'] = os.getenv('VAULT_LDAP_PASSWORD')
    elif args.auth_method == 'userpass':
        auth_params['username'] = os.getenv('VAULT_USERNAME')
        auth_params['password'] = os.getenv('VAULT_PASSWORD')
    
    # Execute action
    if args.action == 'discover':
        discoverer = SecretDiscoverer(args.base_path)
        secrets = discoverer.discover()
        
        print("\n=== Discovered Secrets ===")
        for file_path, file_secrets in secrets.items():
            print(f"\n{file_path}:")
            for secret in file_secrets:
                print(f"  - {secret['pattern']}")
                print(f"    Value: {secret['value'][:20]}...")
                print(f"    Line: {secret['line']}")
        
        print(f"\nTotal secrets found: {sum(len(s) for s in secrets.values())}")
    
    elif args.action in ['dry-run', 'execute']:
        if not args.config_file:
            logger.error("--config-file is required for dry-run/execute")
            sys.exit(1)
        
        migrator = SecretMigrator(
            vault_url=args.vault_url,
            auth_method=auth_method,
            auth_params=auth_params,
            environment=environment,
            dry_run=(args.action == 'dry-run')
        )
        
        if args.action == 'execute':
            migrator.connect()
        
        # Create backup if executing
        if args.action == 'execute':
            backup_path = migrator.create_backup(args.config_file)
        
        # Migrate secrets
        migrated_count = migrator.migrate_from_config(args.config_file)
        logger.info(f"Migrated {migrated_count} secrets")
        
        # Validate migration
        results = migrator.validate_migration()
        print(f"\n=== Migration Results ===")
        print(f"Total: {results['total']}")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        print(f"Dry-run: {results['dry_run']}")
        
        # Save migration log
        migrator.save_migration_log()
        
        if args.action == 'execute':
            print(f"\nBackup created at: {backup_path}")
            print("To rollback, use:")
            print(f"  python migrate_secrets.py --rollback --backup-path {backup_path} --config-file {args.config_file}")
    
    elif args.action == 'validate':
        # Load migration log
        try:
            with open('migration_log.json', 'r') as f:
                migration_log = json.load(f)
            
            print("\n=== Migration Log ===")
            for entry in migration_log:
                print(f"{entry['timestamp']}: {entry['key']} -> {entry['vault_path']} ({entry['status']})")
            
            successful = sum(1 for e in migration_log if e['status'] == 'success')
            failed = sum(1 for e in migration_log if e['status'] == 'failed')
            
            print(f"\nSummary: {successful} successful, {failed} failed")
            
        except FileNotFoundError:
            logger.error("Migration log not found. Run migration first.")
    
    elif args.action == 'rollback':
        if not args.backup_path or not args.config_file:
            logger.error("--backup-path and --config-file are required for rollback")
            sys.exit(1)
        
        migrator = SecretMigrator(
            vault_url=args.vault_url,
            auth_method=auth_method,
            auth_params=auth_params,
            environment=environment
        )
        
        success = migrator.rollback(args.backup_path, args.config_file)
        if success:
            print("Rollback successful")
        else:
            print("Rollback failed")
            sys.exit(1)


if __name__ == '__main__':
    main()