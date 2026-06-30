#!/usr/bin/env python3
"""
Dummy Value Identification and Update Script for PowerStore CT Engine

This script identifies and updates dummy/placeholder values in the codebase
with real values from a configuration file.

Usage:
    python update_dummy_values.py --identify
    python update_dummy_values.py --update
    python update_dummy_values.py --update --config-file custom_values.json
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime

# Base directory
BASE_DIR = Path(__file__).parent

# Configuration for dummy value patterns
DUMMY_PATTERNS = {
    'database': {
        'patterns': [
            r'DATABASE_HOST\s*=\s*"localhost"',
            r'DATABASE_HOST\s*=\s*"staging-db\.dell\.com"',
            r'DATABASE_HOST\s*=\s*"prod-db\.dell\.com"',
            r'DATABASE_USER\s*=\s*"postgres"',
            r'DATABASE_PASSWORD\s*=\s*"postgres"',
            r'DATABASE_PASSWORD\s*=\s*"staging-password-from-vault"',
            r'DATABASE_PASSWORD\s*=\s*"production-password-from-vault"',
        ],
        'description': 'Database connection parameters',
        'files': [
            'shared/config/base.py',
            'shared/config/development.py',
            'shared/config/staging.py',
            'shared/config/production.py',
            '.env.development',
            '.env.staging',
            '.env.production',
        ]
    },
    'jenkins': {
        'patterns': [
            r'JENKINS_URL\s*=\s*"http://localhost:8080"',
            r'JENKINS_URL\s*=\s*"https://jenkins\.example\.com"',
            r'JENKINS_URL\s*=\s*"https://staging-jenkins\.dell\.com"',
            r'JENKINS_USERNAME\s*=\s*"admin"',
            r'JENKINS_PASSWORD\s*=\s*"admin"',
            r'JENKINS_PASSWORD\s*=\s*"staging-jenkins-password-from-vault"',
            r'JENKINS_PASSWORD\s*=\s*"production-jenkins-password-from-vault"',
        ],
        'description': 'Jenkins connection parameters',
        'files': [
            'shared/config/base.py',
            'shared/config/development.py',
            'shared/config/staging.py',
            'shared/config/production.py',
            '.env.development',
            '.env.staging',
            '.env.production',
        ]
    },
    'vault': {
        'patterns': [
            r'VAULT_URL\s*=\s*"http://localhost:8200"',
            r'VAULT_URL\s*=\s*"https://vault\.example\.com"',
            r'VAULT_URL\s*=\s*"https://staging-vault\.dell\.com"',
            r'VAULT_URL\s*=\s*"https://production-vault\.dell\.com"',
        ],
        'description': 'Vault server URLs',
        'files': [
            'shared/config/base.py',
            'shared/config/development.py',
            'shared/config/staging.py',
            'shared/config/production.py',
            '.env.development',
            '.env.staging',
            '.env.production',
        ]
    },
    'secret_keys': {
        'patterns': [
            r'SECRET_KEY\s*=\s*"change-this-secret-key"',
            r'SECRET_KEY\s*=\s*"development-secret-key-for-local-testing-only"',
            r'SECRET_KEY\s*=\s*"staging-secret-key-from-vault"',
            r'SECRET_KEY\s*=\s*"production-secret-key-from-vault"',
            r"SECRET_KEY\s*=\s*'change-this-secret-key'",
            r"SECRET_KEY\s*=\s*'staging-secret-key-from-vault'",
            r"SECRET_KEY\s*=\s*'production-secret-key-from-vault'",
        ],
        'description': 'Application secret keys',
        'files': [
            'shared/config/base.py',
            'shared/config/development.py',
            'shared/config/staging.py',
            'shared/config/production.py',
            '.env.development',
            '.env.staging',
            '.env.production',
            'execution_engine/app.py',
            'manager_engine/app.py',
        ]
    },
    'ldap': {
        'patterns': [
            r'LDAP_URL\s*=\s*"ldaps://ldap\.example\.com"',
            r'LDAP_BASE_DN\s*=\s*"DC=example,DC=com"',
            r'LDAP_BIND_DN\s*=\s*"CN=admin,DC=example,DC=com"',
        ],
        'description': 'LDAP connection parameters',
        'files': [
            'shared/config/base.py',
            'shared/config/staging.py',
            'shared/config/production.py',
        ]
    },
    'email': {
        'patterns': [
            r'@example\.com',
            r'staging-team@dell\.com',
            r'prod-team@dell\.com',
        ],
        'description': 'Email addresses',
        'files': [
            'shared/config/staging.py',
            'shared/config/production.py',
            'tests/test_feature_flags.py',
        ]
    },
    'redis': {
        'patterns': [
            r'redis://localhost:6379',
            r'redis://staging-redis\.dell\.com',
            r'redis://prod-redis\.dell\.com',
        ],
        'description': 'Redis connection URLs',
        'files': [
            'shared/config/base.py',
            'shared/config/staging.py',
            'shared/config/production.py',
        ]
    }
}

# Default real values mapping (to be customized)
DEFAULT_REAL_VALUES = {
    'development': {
        'DATABASE_HOST': 'localhost',
        'DATABASE_USER': 'postgres',
        'DATABASE_PASSWORD': 'postgres',
        'JENKINS_URL': 'http://localhost:8080',
        'JENKINS_USERNAME': 'admin',
        'JENKINS_PASSWORD': 'admin',
        'VAULT_URL': 'http://localhost:8200',
        'SECRET_KEY': 'development-secret-key-for-local-testing-only',
        'REDIS_URL': 'redis://localhost:6379/0',
    },
    'staging': {
        'DATABASE_HOST': 'staging-db.dell.com',
        'DATABASE_USER': 'ct_engine_staging',
        'DATABASE_PASSWORD': 'staging-password-from-vault',
        'JENKINS_URL': 'https://staging-jenkins.dell.com',
        'JENKINS_USERNAME': 'ct-engine-staging',
        'JENKINS_PASSWORD': 'staging-jenkins-password-from-vault',
        'VAULT_URL': 'https://staging-vault.dell.com',
        'SECRET_KEY': 'staging-secret-key-from-vault',
        'REDIS_URL': 'redis://staging-redis.dell.com:6379/0',
        'EMAIL_ADMIN': 'staging-team@dell.com',
    },
    'production': {
        'DATABASE_HOST': 'prod-db.dell.com',
        'DATABASE_USER': 'ct_engine_prod',
        'DATABASE_PASSWORD': 'production-password-from-vault',
        'JENKINS_URL': 'https://osj-ngm-03-prd.cec.delllabs.net',
        'JENKINS_USERNAME': 'svc_prdsysqafw',
        'JENKINS_PASSWORD': 'production-jenkins-password-from-vault',
        'VAULT_URL': 'https://production-vault.dell.com',
        'SECRET_KEY': 'production-secret-key-from-vault',
        'REDIS_URL': 'redis://prod-redis.dell.com:6379/0',
        'EMAIL_ADMIN': 'prod-team@dell.com',
    }
}


class DummyValueIdentifier:
    """Identify dummy values in the codebase"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.findings: List[Dict[str, Any]] = []
        
    def identify(self) -> List[Dict[str, Any]]:
        """Identify all dummy values in the codebase"""
        print("🔍 Identifying dummy values in the codebase...")
        
        for category, config in DUMMY_PATTERNS.items():
            print(f"\n📂 Scanning {category} ({config['description']})...")
            
            for pattern in config['patterns']:
                self._scan_pattern(category, pattern, config['files'])
        
        return self.findings
    
    def _scan_pattern(self, category: str, pattern: str, files: List[str]):
        """Scan specific pattern in files"""
        for file_path in files:
            full_path = self.base_dir / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    line_number = content[:match.start()].count('\n') + 1
                    line_content = content.split('\n')[line_number - 1].strip()
                    
                    self.findings.append({
                        'category': category,
                        'file': file_path,
                        'line': line_number,
                        'pattern': pattern,
                        'match': match.group(),
                        'line_content': line_content,
                        'needs_update': self._needs_update(match.group())
                    })
                    
                    if self._needs_update(match.group()):
                        print(f"  ⚠️  {file_path}:{line_number} - {match.group()}")
                    
            except Exception as e:
                print(f"  ❌ Error scanning {file_path}: {e}")
    
    def _needs_update(self, match: str) -> bool:
        """Determine if a match needs updating"""
        # These patterns indicate placeholder values that need real values
        placeholder_indicators = [
            'localhost',
            'admin',
            'postgres',
            'example.com',
            'change-this',
            'from-vault',
            'staging-vault.dell.com',
            'production-vault.dell.com',
            'staging-db.dell.com',
            'prod-db.dell.com',
        ]
        
        match_lower = match.lower()
        for indicator in placeholder_indicators:
            if indicator in match_lower:
                return True
        
        return False
    
    def generate_report(self) -> str:
        """Generate a detailed report of findings"""
        report = []
        report.append("=" * 80)
        report.append("DUMMY VALUE IDENTIFICATION REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Total findings: {len(self.findings)}")
        report.append(f"Needs update: {sum(1 for f in self.findings if f['needs_update'])}")
        report.append("")
        
        # Group by category
        categories = {}
        for finding in self.findings:
            if finding['category'] not in categories:
                categories[finding['category']] = []
            categories[finding['category']].append(finding)
        
        for category, findings in categories.items():
            report.append(f"\n{'=' * 80}")
            report.append(f"Category: {category.upper()}")
            report.append(f"{'=' * 80}")
            
            for finding in findings:
                status = "⚠️  NEEDS UPDATE" if finding['needs_update'] else "✅ OK"
                report.append(f"\n{status}")
                report.append(f"  File: {finding['file']}")
                report.append(f"  Line: {finding['line']}")
                report.append(f"  Pattern: {finding['pattern']}")
                report.append(f"  Match: {finding['match']}")
                report.append(f"  Line: {finding['line_content']}")
        
        return "\n".join(report)


class DummyValueUpdater:
    """Update dummy values with real values"""
    
    def __init__(self, base_dir: Path, real_values: Dict[str, Any]):
        self.base_dir = base_dir
        self.real_values = real_values
        self.updates: List[Dict[str, Any]] = []
        self.backup_dir = base_dir / '.backup_dummy_values'
        
    def update(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """Update dummy values with real values"""
        print("🔄 Updating dummy values...")
        
        if not dry_run:
            self.backup_dir.mkdir(exist_ok=True)
            print(f"📁 Backups will be saved to: {self.backup_dir}")
        
        # Update configuration files
        self._update_config_files(dry_run)
        
        # Update environment files
        self._update_env_files(dry_run)
        
        return self.updates
    
    def _update_config_files(self, dry_run: bool):
        """Update Python configuration files"""
        config_files = [
            'shared/config/base.py',
            'shared/config/development.py',
            'shared/config/staging.py',
            'shared/config/production.py',
        ]
        
        for config_file in config_files:
            self._update_file(config_file, dry_run)
    
    def _update_env_files(self, dry_run: bool):
        """Update environment files"""
        env_files = [
            '.env.development',
            '.env.staging',
            '.env.production',
        ]
        
        for env_file in env_files:
            self._update_file(env_file, dry_run)
    
    def _update_file(self, file_path: str, dry_run: bool):
        """Update a single file"""
        full_path = self.base_dir / file_path
        if not full_path.exists():
            return
        
        # Determine environment from file name
        environment = self._get_environment_from_file(file_path)
        if not environment:
            return
        
        values = self.real_values.get(environment, {})
        if not values:
            print(f"⚠️  No real values found for environment: {environment}")
            return
        
        try:
            with open(full_path, 'r') as f:
                content = f.read()
            
            original_content = content
            updated = False
            
            # Update each value
            for key, new_value in values.items():
                # Pattern to match key=value
                pattern = rf'{key}\s*=\s*["\']([^"\']+)["\']'
                
                def replace_func(match):
                    old_value = match.group(1)
                    # Only replace if it's a dummy value
                    if self._is_dummy_value(old_value):
                        return f'{key}="{new_value}"'
                    return match.group(0)
                
                new_content = re.sub(pattern, replace_func, content)
                
                if new_content != content:
                    content = new_content
                    updated = True
                    print(f"  ✅ Updated {key} in {file_path}")
            
            if updated:
                if not dry_run:
                    # Create backup
                    backup_path = self.backup_dir / f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(backup_path, 'w') as f:
                        f.write(original_content)
                    
                    # Write updated content
                    with open(full_path, 'w') as f:
                        f.write(content)
                    
                    self.updates.append({
                        'file': file_path,
                        'backup': str(backup_path),
                        'environment': environment,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    print(f"  🔍 [DRY-RUN] Would update {file_path}")
            else:
                print(f"  ℹ️  No updates needed for {file_path}")
                
        except Exception as e:
            print(f"  ❌ Error updating {file_path}: {e}")
    
    def _get_environment_from_file(self, file_path: str) -> str:
        """Extract environment name from file path"""
        if 'development' in file_path:
            return 'development'
        elif 'staging' in file_path:
            return 'staging'
        elif 'production' in file_path:
            return 'production'
        elif 'base' in file_path:
            return 'development'  # Base config uses development defaults
        return None
    
    def _is_dummy_value(self, value: str) -> bool:
        """Check if a value is a dummy/placeholder"""
        dummy_indicators = [
            'localhost',
            'admin',
            'postgres',
            'example.com',
            'change-this',
            'from-vault',
            'staging-vault.dell.com',
            'production-vault.dell.com',
            'staging-db.dell.com',
            'prod-db.dell.com',
        ]
        
        value_lower = value.lower()
        for indicator in dummy_indicators:
            if indicator in value_lower:
                return True
        
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Identify and update dummy values in the codebase'
    )
    
    parser.add_argument(
        '--identify',
        action='store_true',
        help='Identify dummy values without updating'
    )
    
    parser.add_argument(
        '--update',
        action='store_true',
        help='Update dummy values with real values'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    
    parser.add_argument(
        '--config-file',
        help='Path to custom real values JSON file'
    )
    
    parser.add_argument(
        '--output-report',
        help='Path to save the identification report'
    )
    
    args = parser.parse_args()
    
    if not args.identify and not args.update:
        parser.print_help()
        sys.exit(1)
    
    # Load real values
    real_values = DEFAULT_REAL_VALUES
    if args.config_file:
        config_path = Path(args.config_file)
        if config_path.exists():
            with open(config_path, 'r') as f:
                real_values = json.load(f)
            print(f"📄 Loaded custom values from: {args.config_file}")
        else:
            print(f"⚠️  Config file not found: {args.config_file}")
            print("Using default values")
    
    # Identify dummy values
    identifier = DummyValueIdentifier(BASE_DIR)
    findings = identifier.identify()
    
    # Generate and save report
    report = identifier.generate_report()
    print(f"\n{report}")
    
    if args.output_report:
        report_path = Path(args.output_report)
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_path}")
    
    # Update if requested
    if args.update:
        updater = DummyValueUpdater(BASE_DIR, real_values)
        updates = updater.update(dry_run=args.dry_run)
        
        if updates:
            print(f"\n✅ Updated {len(updates)} files")
            for update in updates:
                print(f"  - {update['file']} (backup: {update['backup']})")
        else:
            print("\nℹ️  No files needed updating")
    
    print("\n✨ Done!")


if __name__ == '__main__':
    main()