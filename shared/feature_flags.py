"""
Feature flag management system for PowerStore CT Engine.

This module provides per-environment feature flag system for controlled
feature rollouts and emergency control mechanisms.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from enum import Enum
from pathlib import Path
from datetime import datetime
import hashlib

from .environment import Environment, get_environment
from .config_loader import get_config
from .exceptions import FeatureFlagError

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Environment enumeration for feature flags"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class FeatureFlag:
    """
    Individual feature flag with runtime evaluation capabilities.
    
    Supports:
    - Environment-specific enablement
    - Percentage-based rollouts
    - User-based targeting
    - Dependency management
    """
    
    def __init__(
        self,
        name: str,
        enabled: bool = False,
        environments: List[str] = None,
        rollout_percentage: int = 0,
        description: str = "",
        target_users: List[str] = None,
        dependencies: List[str] = None
    ):
        """
        Initialize feature flag.
        
        Args:
            name: Feature flag name
            enabled: Whether flag is globally enabled
            environments: List of environments where flag is enabled
            rollout_percentage: Rollout percentage (0-100)
            description: Feature description
            target_users: List of targeted users
            dependencies: List of required feature flags
        """
        self.name = name
        self.enabled = enabled
        self.environments = environments or []
        self.rollout_percentage = rollout_percentage
        self.description = description
        self.target_users = target_users or []
        self.dependencies = dependencies or []
        self._usage_count = 0
        self._last_accessed = None
    
    def is_enabled(self, user_id: Optional[str] = None) -> bool:
        """
        Check if feature flag is enabled for specific user.
        
        Args:
            user_id: Optional user ID for user-based targeting
            
        Returns:
            True if feature is enabled for the user
        """
        # Update usage statistics
        self._usage_count += 1
        self._last_accessed = datetime.utcnow()
        
        # Check if globally disabled
        if not self.enabled:
            return False
        
        # Check environment compatibility
        current_env = get_environment().value
        if self.environments and current_env not in self.environments:
            return False
        
        # Check user-based targeting
        if user_id and self.target_users:
            if user_id not in self.target_users:
                return False
        
        # Check percentage-based rollout
        if self.rollout_percentage < 100:
            if not self._check_rollout_eligibility(user_id):
                return False
        
        # Check dependencies
        if self.dependencies:
            for dep_flag in self.dependencies:
                if not feature_flag_manager.is_enabled(dep_flag, user_id):
                    return False
        
        return True
    
    def _check_rollout_eligibility(self, user_id: Optional[str]) -> bool:
        """
        Check if user is eligible based on rollout percentage.
        
        Args:
            user_id: User ID for consistent hashing
            
        Returns:
            True if user is in rollout percentage
        """
        if user_id:
            # Use consistent hashing for user-based rollout
            hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            return (hash_value % 100) < self.rollout_percentage
        else:
            # Random rollout for non-user-specific
            import random
            return random.randint(0, 99) < self.rollout_percentage
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for this flag.
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            'usage_count': self._usage_count,
            'last_accessed': self._last_accessed.isoformat() if self._last_accessed else None
        }


class FeatureFlagManager:
    """
    Feature flag manager with runtime evaluation and management.
    
    Provides:
    - Flag evaluation logic
    - Flag management operations
    - Usage metrics
    - Environment-specific configuration
    """
    
    def __init__(self):
        """Initialize feature flag manager"""
        self._flags: Dict[str, FeatureFlag] = {}
        self._config_path = "feature_flags.json"
        self._load_flags_from_config()
    
    def _load_flags_from_config(self) -> None:
        """Load feature flags from configuration file"""
        try:
            config_path = Path(self._config_path)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    flags_config = json.load(f)
                
                for flag_name, flag_config in flags_config.items():
                    self._flags[flag_name] = FeatureFlag(
                        name=flag_name,
                        enabled=flag_config.get('enabled', False),
                        environments=flag_config.get('environments', []),
                        rollout_percentage=flag_config.get('rollout_percentage', 0),
                        description=flag_config.get('description', ''),
                        target_users=flag_config.get('target_users', []),
                        dependencies=flag_config.get('dependencies', [])
                    )
                
                logger.info(f"Loaded {len(self._flags)} feature flags from configuration")
            else:
                logger.warning(f"Feature flags config file not found: {self._config_path}")
                self._load_default_flags()
                
        except Exception as e:
            logger.error(f"Failed to load feature flags from config: {e}")
            self._load_default_flags()
    
    def _load_default_flags(self) -> None:
        """Load default feature flags"""
        default_flags = {
            'new_ui': FeatureFlag(
                name='new_ui',
                enabled=True,
                environments=['development', 'staging'],
                rollout_percentage=100,
                description='Enable new user interface'
            ),
            'advanced_monitoring': FeatureFlag(
                name='advanced_monitoring',
                enabled=False,
                environments=['production'],
                rollout_percentage=10,
                description='Enable advanced monitoring features'
            ),
            'kubernetes_scaling': FeatureFlag(
                name='kubernetes_scaling',
                enabled=True,
                environments=['staging', 'production'],
                rollout_percentage=100,
                description='Enable Kubernetes-based scaling'
            )
        }
        
        self._flags = default_flags
        logger.info(f"Loaded {len(default_flags)} default feature flags")
    
    def is_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_name: Name of the feature flag
            user_id: Optional user ID for user-based targeting
            
        Returns:
            True if flag is enabled, False otherwise
        """
        flag = self._flags.get(flag_name)
        if not flag:
            logger.warning(f"Feature flag not found: {flag_name}")
            return False
        
        return flag.is_enabled(user_id)
    
    def enable_flag(self, flag_name: str) -> None:
        """
        Enable a feature flag.
        
        Args:
            flag_name: Name of the feature flag to enable
        """
        flag = self._flags.get(flag_name)
        if flag:
            flag.enabled = True
            logger.info(f"Feature flag enabled: {flag_name}")
        else:
            raise FeatureFlagError(f"Feature flag not found: {flag_name}")
    
    def disable_flag(self, flag_name: str) -> None:
        """
        Disable a feature flag.
        
        Args:
            flag_name: Name of the feature flag to disable
        """
        flag = self._flags.get(flag_name)
        if flag:
            flag.enabled = False
            logger.info(f"Feature flag disabled: {flag_name}")
        else:
            raise FeatureFlagError(f"Feature flag not found: {flag_name}")
    
    def set_rollout_percentage(self, flag_name: str, percentage: int) -> None:
        """
        Set rollout percentage for a feature flag.
        
        Args:
            flag_name: Name of the feature flag
            percentage: Rollout percentage (0-100)
        """
        if not 0 <= percentage <= 100:
            raise FeatureFlagError("Rollout percentage must be between 0 and 100")
        
        flag = self._flags.get(flag_name)
        if flag:
            flag.rollout_percentage = percentage
            logger.info(f"Set rollout percentage for {flag_name}: {percentage}%")
        else:
            raise FeatureFlagError(f"Feature flag not found: {flag_name}")
    
    def get_flag(self, flag_name: str) -> Optional[FeatureFlag]:
        """
        Get a specific feature flag.
        
        Args:
            flag_name: Name of the feature flag
            
        Returns:
            FeatureFlag instance or None
        """
        return self._flags.get(flag_name)
    
    def get_all_flags(self) -> Dict[str, FeatureFlag]:
        """
        Get all feature flags.
        
        Returns:
            Dictionary of all feature flags
        """
        return self._flags.copy()
    
    def get_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get usage statistics for all flags.
        
        Returns:
            Dictionary of usage statistics per flag
        """
        stats = {}
        for flag_name, flag in self._flags.items():
            stats[flag_name] = flag.get_usage_stats()
        return stats
    
    def add_flag(self, flag: FeatureFlag) -> None:
        """
        Add a new feature flag.
        
        Args:
            flag: FeatureFlag instance to add
        """
        if flag.name in self._flags:
            raise FeatureFlagError(f"Feature flag already exists: {flag.name}")
        
        self._flags[flag.name] = flag
        logger.info(f"Added feature flag: {flag.name}")
    
    def remove_flag(self, flag_name: str) -> None:
        """
        Remove a feature flag.
        
        Args:
            flag_name: Name of the feature flag to remove
        """
        if flag_name not in self._flags:
            raise FeatureFlagError(f"Feature flag not found: {flag_name}")
        
        del self._flags[flag_name]
        logger.info(f"Removed feature flag: {flag_name}")
    
    def update_flag(self, flag_name: str, **kwargs) -> None:
        """
        Update a feature flag.
        
        Args:
            flag_name: Name of the feature flag to update
            **kwargs: Attributes to update
        """
        flag = self._flags.get(flag_name)
        if not flag:
            raise FeatureFlagError(f"Feature flag not found: {flag_name}")
        
        for key, value in kwargs.items():
            if hasattr(flag, key):
                setattr(flag, key, value)
            else:
                raise FeatureFlagError(f"Invalid attribute: {key}")
        
        logger.info(f"Updated feature flag: {flag_name}")
    
    def save_flags_to_config(self) -> None:
        """Save current feature flags to configuration file"""
        flags_config = {}
        
        for flag_name, flag in self._flags.items():
            flags_config[flag_name] = {
                'enabled': flag.enabled,
                'environments': flag.environments,
                'rollout_percentage': flag.rollout_percentage,
                'description': flag.description,
                'target_users': flag.target_users,
                'dependencies': flag.dependencies
            }
        
        try:
            with open(self._config_path, 'w') as f:
                json.dump(flags_config, f, indent=2)
            
            logger.info(f"Saved {len(self._flags)} feature flags to configuration")
            
        except Exception as e:
            logger.error(f"Failed to save feature flags to config: {e}")
            raise FeatureFlagError(f"Failed to save feature flags: {e}")


# Global feature flag manager instance
feature_flag_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """
    Get the global feature flag manager instance.
    
    Returns:
        FeatureFlagManager instance
    """
    global feature_flag_manager
    
    if feature_flag_manager is None:
        feature_flag_manager = FeatureFlagManager()
    
    return feature_flag_manager


# Convenience functions for common operations
def is_feature_enabled(flag_name: str, user_id: Optional[str] = None) -> bool:
    """
    Check if a feature flag is enabled.
    
    Args:
        flag_name: Name of the feature flag
        user_id: Optional user ID for user-based targeting
        
    Returns:
        True if flag is enabled, False otherwise
    """
    manager = get_feature_flag_manager()
    return manager.is_enabled(flag_name, user_id)


def enable_feature(flag_name: str) -> None:
    """
    Enable a feature flag.
    
    Args:
        flag_name: Name of the feature flag to enable
    """
    manager = get_feature_flag_manager()
    manager.enable_flag(flag_name)


def disable_feature(flag_name: str) -> None:
    """
    Disable a feature flag.
    
    Args:
        flag_name: Name of the feature flag to disable
    """
    manager = get_feature_flag_manager()
    manager.disable_flag(flag_name)


# Decorator for feature flag-based function execution
def feature_flag(flag_name: str, user_id_param: str = 'user_id'):
    """
    Decorator to conditionally execute function based on feature flag.
    
    Args:
        flag_name: Name of the feature flag to check
        user_id_param: Parameter name that contains user ID
        
    Usage:
        @feature_flag('new_ui')
        def new_ui_function():
            # This function only executes if new_ui flag is enabled
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get user_id from kwargs
            user_id = kwargs.get(user_id_param)
            
            if not is_feature_enabled(flag_name, user_id):
                logger.debug(f"Feature flag '{flag_name}' is disabled, skipping {func.__name__}")
                return None
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == '__main__':
    # Test feature flag system
    logging.basicConfig(level=logging.DEBUG)
    
    print("=== Feature Flag System Test ===")
    manager = FeatureFlagManager()
    
    # Test flag evaluation
    print(f"new_ui enabled: {manager.is_enabled('new_ui')}")
    print(f"advanced_monitoring enabled: {manager.is_enabled('advanced_monitoring')}")
    
    # Test flag management
    manager.enable_flag('advanced_monitoring')
    print(f"advanced_monitoring enabled after enable: {manager.is_enabled('advanced_monitoring')}")
    
    manager.disable_flag('advanced_monitoring')
    print(f"advanced_monitoring enabled after disable: {manager.is_enabled('advanced_monitoring')}")
    
    # Test usage stats
    stats = manager.get_usage_stats()
    print(f"Usage stats: {stats}")
    
    # Test all flags
    all_flags = manager.get_all_flags()
    print(f"All flags: {list(all_flags.keys())}")