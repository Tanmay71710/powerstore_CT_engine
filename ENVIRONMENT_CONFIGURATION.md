# Environment Configuration Guide

This document describes the environment-specific configuration for the PowerStore CT Engine framework, including XPOOL binary paths and Docker build configurations.

## Overview

The framework supports multiple environments with specific configurations for development, staging, and production deployments. Each environment has optimized settings for infrastructure resources, package sources, and build parameters.

## Environment-Specific XPOOL Configuration

XPOOL binary paths vary by environment to ensure proper cluster reservation and management in each deployment context.

### Configuration Files

- **Base Configuration**: `shared/config/base.py` - Default values
- **Development Configuration**: `shared/config/development.py` - Local development settings
- **Staging Configuration**: `shared/config/staging.py` - Pre-production settings
- **Production Configuration**: `shared/config/production.py` - Production deployment settings

### XPOOL Binary Paths by Environment

| Environment | Configuration File | XPOOL Binary Path | Purpose |
|-------------|-------------------|-------------------|---------|
| **Base/Default** | `shared/config/base.py` | `/home/public/scripts/xpool_trident/prd/xpool` | Default production path |
| **Development** | `shared/config/development.py` | `/home/public/scripts/xpool_trident/dev/xpool` | Development XPool instance |
| **Staging** | `shared/config/staging.py` | `/home/public/scripts/xpool_trident/test/xpool` | Staging/test XPool instance |
| **Production** | `shared/config/production.py` | `/home/public/scripts/xpool_trident/prd/xpool` | Production XPool instance |

### XPOOL Configuration Parameters

Each environment includes additional XPOOL-specific settings:

```python
# Common XPOOL settings across environments
XPOOL_ENABLED: bool = True
XPOOL_GROUPS: str = "QA-TestRunner,FRAMEWORK"
XPOOL_DEFAULT_USER: str = "svc_prdsysqafw"
XPOOL_RESERVATION_LIMIT: Optional[int] = None  # Varies by environment
XPOOL_TIMEOUT: int = 300
XPOOL_RETRY_ATTEMPTS: int = 3
```

### Environment-Specific Reservation Limits

- **Development**: No reservation limit (`None`)
- **Staging**: 50 concurrent reservations
- **Production**: 100 concurrent reservations

### Database Configuration

Database configuration is consistent across all environments to ensure unified data access:

```python
# Common database settings across all environments
DATABASE_HOST: str = "10.55.236.78"
DATABASE_PORT: int = 5432
DATABASE_NAME: str = "qTest"
DATABASE_USER: str = "postgres"
DATABASE_PASSWORD: str = "postgres"
DATABASE_SSL_MODE: str = "prefer"
DATABASE_POOL_SIZE: int = 5
DATABASE_MAX_OVERFLOW: int = 10
PERF_DATABASE_NAME: str = "performance"
```

### Environment Variable Configuration (.env Files)

The framework supports optional `.env` files for environment-specific overrides. These files are git-ignored and should be created locally by developers.

#### Available .env Files

- **`.env.example`** - Template file (committed to repository)
- **`.env`** - Local overrides (git-ignored)
- **`.env.local`** - Local personal overrides (git-ignored)
- **`.env.development`** - Development-specific overrides (git-ignored)
- **`.env.staging`** - Staging-specific overrides (git-ignored)
- **`.env.production`** - Production-specific overrides (git-ignored)

#### Setting Up .env Files

```bash
# Copy the example file for your environment
cp .env.example .env.development

# Edit with your local overrides
nano .env.development
```

#### Example .env.development

```bash
# Environment Detection
ENVIRONMENT=development

# Database Configuration (overrides Python config)
ENV_DATABASE_HOST=10.55.236.78
ENV_DATABASE_PASSWORD=postgres

# Jenkins Configuration
ENV_JENKINS_URL=https://osj-ngm-03-prd.cec.delllabs.net
ENV_JENKINS_USERNAME=svc_prdsysqafw

# XPOOL Configuration
ENV_XPOOL_BINARY_PATH=/home/public/scripts/xpool_trident/dev/xpool
```

#### Configuration Precedence

The framework loads configuration in this order (later sources override earlier ones):

1. **Base Configuration** (`shared/config/base.py`)
2. **Environment Configuration** (`shared/config/{environment}.py`)
3. **Vault Configuration** (if enabled)
4. **.env Files** (if they exist)
5. **System Environment Variables** (ENV_* prefix)

#### When to Use .env Files

**Use .env files when:**
- You need local development overrides
- You want to keep secrets out of code
- You need environment-specific personal settings
- You're testing with different configurations

**Don't use .env files when:**
- The Python config files have everything you need
- You're using Vault for secrets management
- You prefer system environment variables
- You want to keep configuration simple

### Jenkins Configuration

Jenkins configuration is consistent across all environments to ensure unified CI/CD integration:

```python
# Common Jenkins settings across all environments
JENKINS_URL: str = "https://osj-ngm-03-prd.cec.delllabs.net"
JENKINS_USERNAME: str = "svc_prdsysqafw"
JENKINS_PASSWORD: str = "jenkins-password-from-vault"
JENKINS_JOB_NAME: str = "Trident/test_executer"
JENKINS_DEV_JOB_NAME: str = "Trident/dev_test_executer"
```

### Environment-Specific Jenkins Timeouts

While the Jenkins server and credentials are consistent, timeout values vary by environment:

- **Development**: 120 seconds (faster feedback for local development)
- **Staging**: 300 seconds (standard timeout for pre-production)
- **Production**: 600 seconds (longer timeout for production builds)

## Environment-Specific Docker Configuration

Docker builds support environment-specific configurations through build arguments, enabling different base images, package sources, and installation methods per environment.

### Docker Build Argument

The Dockerfiles use the `ENV` build argument to determine the environment:

```dockerfile
ARG ENV=production
ENV ENV=${ENV}
```

### Main Dockerfile (`Dockerfile`)

#### Build Commands by Environment

```bash
# Development build - uses public PyPI
docker build --build-arg ENV=development -t powerstore-ct-engine:dev .

# Staging build - uses internal Artifactory
docker build --build-arg ENV=staging -t powerstore-ct-engine:staging .

# Production build - uses internal Artifactory (default)
docker build --build-arg ENV=production -t powerstore-ct-engine:prod .
```

#### Environment-Specific Package Installation

The Dockerfile conditionally installs packages based on the environment:

```dockerfile
# Install vaultInteraction from appropriate PyPI based on environment
RUN if [ "$ENV" = "development" ]; then \
    pip install --no-cache-dir vaultInteraction; \
    else \
    pip install --trusted-host pstore.artifactory.cec.lab.emc.com \
        --extra-index-url https://pstore.artifactory.cec.lab.emc.com/artifactory/api/pypi/cyclone-pypi/simple \
        vaultInteraction; \
    fi
```

**Development Environment:**
- Uses public PyPI (`https://pypi.org/simple`)
- No trusted host configuration required
- Faster builds for local development

**Staging/Production Environments:**
- Uses internal Artifactory PyPI
- Requires trusted host configuration
- Ensures consistent package versions across deployments

### Manager Engine Dockerfile (`manager_engine/Dockerfile`)

The manager engine Dockerfile follows the same pattern:

```dockerfile
ARG ENV=production
ENV ENV=${ENV}

# Install packages based on environment
RUN if [ "$ENV" = "development" ]; then \
    pip install --no-cache-dir -r requirements.txt; \
    else \
    pip install --trusted-host pstore.artifactory.cec.lab.emc.com \
        --no-cache-dir -r requirements.txt; \
    fi
```

## Configuration Usage

### Loading Environment Configuration

The framework automatically loads the appropriate configuration based on the environment variable:

```python
import os
from shared.config import DevelopmentConfig, StagingConfig, ProductionConfig, BaseConfig

# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'staging': StagingConfig,
    'production': ProductionConfig
}

environment = os.getenv('ENVIRONMENT', 'development')
config_class = config_map.get(environment, BaseConfig)
config = config_class()
```

### Accessing XPOOL Configuration

```python
from shared.config import DevelopmentConfig

# Access XPOOL binary path
xpool_path = DevelopmentConfig.XPOOL_BINARY_PATH
# Returns: "/home/public/scripts/xpool_trident/dev/xpool"

# Access XPOOL groups
xpool_groups = DevelopmentConfig.XPOOL_GROUPS
# Returns: "QA-TestRunner,FRAMEWORK"
```

### Docker Build Integration

When building Docker images, the environment variable is passed as a build argument and becomes available within the container:

```bash
# Build with environment argument
docker build --build-arg ENV=staging -t myapp:staging .

# The ENV variable is available in the running container
docker run -e ENV=staging myapp:staging
```

## Environment Comparison

### Development Environment

**Purpose**: Local development and testing

**Characteristics**:
- XPOOL: Development instance (`/dev/xpool`)
- Jenkins: Production server with 120s timeout
- Docker: Public PyPI, no reservation limits
- Database: Shared PostgreSQL (10.55.236.78), SSL prefer
- Logging: DEBUG level with verbose output
- Kubernetes: Disabled
- Vault: Disabled

**Use Case**: Fast iteration, local testing, debugging

### Staging Environment

**Purpose**: Pre-production testing and validation

**Characteristics**:
- XPOOL: Test instance (`/test/xpool`)
- Jenkins: Production server with 300s timeout
- Docker: Internal Artifactory, 50 reservation limit
- Database: Shared PostgreSQL (10.55.236.78), SSL prefer
- Logging: INFO level
- Kubernetes: Enabled with staging namespace
- Vault: Enabled for staging secrets

**Use Case**: Integration testing, UAT, release validation

### Production Environment

**Purpose**: Production deployment

**Characteristics**:
- XPOOL: Production instance (`/prd/xpool`)
- Jenkins: Production server with 600s timeout
- Docker: Internal Artifactory, 100 reservation limit
- Database: Shared PostgreSQL (10.55.236.78), SSL prefer
- Logging: WARNING level (minimal output)
- Kubernetes: Enabled with production namespace
- Vault: Enabled for production secrets
- Security: Maximum security settings

**Use Case**: Live production deployment, customer-facing services

## Best Practices

1. **Always specify environment**: Use `--build-arg ENV` when building Docker images
2. **Test in staging first**: Validate changes in staging before production deployment
3. **Use appropriate XPOOL**: Ensure XPOOL binary path matches your deployment environment
4. **Secure production secrets**: Use Vault for production credentials and secrets
5. **Monitor resource limits**: Respect XPOOL reservation limits in each environment
6. **Validate configuration**: Use the `validate()` method to check configuration before deployment

## Troubleshooting

### XPOOL Binary Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory: '/home/public/scripts/xpool_trident/dev/xpool'`

**Solution**: Ensure the correct XPOOL binary path is configured for your environment in the appropriate config file.

### Docker Build Failures

**Error**: Package installation failures during Docker build

**Solution**: 
- Verify the `ENV` build argument is set correctly
- Check network connectivity to the appropriate PyPI source
- For non-development environments, verify Artifactory accessibility

### Configuration Validation Errors

**Error**: `ValueError: Vault must be enabled in production`

**Solution**: Ensure production-specific configuration requirements are met before deployment.

## Related Files

- `shared/config/base.py` - Base configuration with defaults
- `shared/config/development.py` - Development environment configuration
- `shared/config/staging.py` - Staging environment configuration  
- `shared/config/production.py` - Production environment configuration
- `Dockerfile` - Main application Dockerfile
- `manager_engine/Dockerfile` - Manager engine Dockerfile
- `shared/utils.py` - Utility functions using XPOOL configuration

## Maintenance

When adding new environment-specific settings:

1. Add default values to `shared/config/base.py`
2. Override in environment-specific config files as needed
3. Update this documentation
4. Test configuration loading in each environment
5. Validate configuration changes before deployment
