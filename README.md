# PowerStore CT Engine

## Overview

The PowerStore CT Engine is a comprehensive test execution framework that supports multiple environments (development, staging, production) with sophisticated configuration management, Docker-based deployment, and automated test execution capabilities.

## Features

- **Multi-Environment Support**: Development, Staging, and Production environments
- **Configuration Management**: Sophisticated configuration system with precedence (env vars > config files > vault > defaults)
- **Docker-Based Deployment**: Containerized services with environment-specific builds
- **Automated Test Execution**: Jenkins integration for automated test execution
- **XPOOL Integration**: Resource management for test execution
- **Kubernetes Support**: Native Kubernetes integration for cluster management
- **Database Integration**: PostgreSQL for test execution tracking
- **LDAP Authentication**: Enterprise authentication support

## Architecture

The framework consists of three main engines:

1. **Execution Engine**: Handles test execution and monitoring
2. **Manager Engine**: Manages test sets, configurations, and cluster operations
3. **Monitor Engine**: Monitors cluster health and test execution status

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose (optional, for local development)
- Python 3.9+
- PostgreSQL 13+
- Access to Dell EMC Artifactory (for internal packages)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Tanmay71710/powerstore_CT_engine.git
   cd powerstore_CT_engine
   ```

2. **Set up environment configuration**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env with your environment-specific settings
   nano .env
   ```

3. **Configure your environment**
   ```bash
   # Set the environment (development, staging, or production)
   export ENVIRONMENT=development
   ```

### Running Locally

#### Using Docker (Recommended)

```bash
# Build the Docker image for your environment
docker build --build-arg ENV=development -t powerstore-ct-engine:dev .

# Run the execution engine
docker run -e APP_NAME=execution -e ENVIRONMENT=development -p 5000:5000 powerstore-ct-engine:dev

# Run the manager engine
docker run -e APP_NAME=manager -e ENVIRONMENT=development -p 5002:5002 powerstore-ct-engine:dev

# Run the monitor engine
docker run -e APP_NAME=monitor -e ENVIRONMENT=development powerstore-ct-engine:dev
```

#### Using Python Directly

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
export ENVIRONMENT=development

# Run the execution engine
python execution_engine/app.py --port 5000 --test_set_name your_test_set

# Run the manager engine
python manager_engine/app.py

# Run the monitor engine
python monitor_engine/app.py
```

## Environment Configuration

### Environment Variables

The framework supports the following environment variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ENVIRONMENT` | Environment name (development/staging/production) | development | Yes |
| `APP_NAME` | Service to run (execution/manager/monitor) | execution | No |
| `APP_PORT` | Port for the service | 5000 | No |
| `DATABASE_PASSWORD` | Database password | postgres | Yes (prod) |
| `JENKINS_PASSWORD` | Jenkins password | - | Yes (prod) |
| `SECRET_KEY` | Flask secret key | - | Yes (prod) |

### Configuration Files

Configuration is managed through a sophisticated system:

1. **Base Configuration** (`shared/config/base.py`): Default values
2. **Environment-Specific** (`shared/config/{environment}.py`): Environment overrides
3. **Environment Variables**: Highest precedence
4. **Vault Secrets**: Optional secret management

For detailed configuration information, see [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md).

## Testing

### Run Unit Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_config_loader.py -v

# Run with coverage
python -m pytest tests/ --cov=shared --cov=execution_engine --cov=manager_engine
```

### Run Integration Tests

```bash
# Set environment
export ENVIRONMENT=development

# Run integration tests
python -m pytest tests/test_integration.py -v
```

### Test with Different Environments

```bash
# Test with staging configuration
ENVIRONMENT=staging python -m pytest tests/ -v

# Test with production configuration
ENVIRONMENT=production python -m pytest tests/ -v
```

## Deployment

### Development Deployment

```bash
# Build and run with development configuration
docker build --build-arg ENV=development -t ct-engine:dev .
docker run -e APP_NAME=execution -e ENVIRONMENT=development -p 5000:5000 ct-engine:dev
```

### Staging Deployment

```bash
# Build with staging configuration
docker build --build-arg ENV=staging -t ct-engine:staging .

# Push to registry
docker tag ct-engine:staging your-registry/ct-engine:staging
docker push your-registry/ct-engine:staging

# Deploy to staging
kubectl apply -f k8s/staging/
```

### Production Deployment

```bash
# Build with production configuration
docker build --build-arg ENV=production -t ct-engine:prod .

# Push to registry
docker tag ct-engine:prod your-registry/ct-engine:prod
docker push your-registry/ct-engine:prod

# Deploy to production
kubectl apply -f k8s/production/
```

For detailed deployment guides, see [DEPLOYMENT.md](DEPLOYMENT.md).

## API Documentation

### Execution Engine API

- **GET /health**: Health check endpoint
- **POST /test_sets**: Create test set
- **GET /test_sets/{id}**: Get test set details
- **POST /test_execution**: Start test execution
- **GET /test_execution/{id}**: Get test execution status

### Manager Engine API

- **GET /health**: Health check endpoint
- **GET /clusters**: List clusters
- **POST /clusters/{id}/lease**: Lease cluster
- **DELETE /clusters/{id}/lease**: Release cluster

### Monitor Engine API

- **GET /health**: Health check endpoint
- **GET /clusters/status**: Get cluster status
- **GET /test_executions/active**: Get active test executions

For complete API documentation, see [API.md](API.md).

## Troubleshooting

### Common Issues

#### Container won't start

**Problem**: Docker container fails to start

**Solution**: Check logs with `docker logs <container_id>` and verify environment variables are set correctly.

#### Environment detection fails

**Problem**: Wrong environment detected

**Solution**: Set `ENVIRONMENT` variable explicitly: `export ENVIRONMENT=staging`

#### Database connection fails

**Problem**: Cannot connect to PostgreSQL database

**Solution**: 
- Verify database is running: `psql -h 10.55.236.78 -U postgres -d qTest`
- Check `DATABASE_PASSWORD` environment variable
- Verify network connectivity

#### Jenkins integration fails

**Problem**: Cannot trigger Jenkins jobs

**Solution**:
- Verify `JENKINS_PASSWORD` is set correctly
- Check Jenkins URL accessibility
- Verify Jenkins user has proper permissions

For more troubleshooting information, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Security

### Secret Management

- **Development**: Use `.env` file (never commit secrets)
- **Staging**: Use environment variables or Vault
- **Production**: Must use Vault or secure secret management

### Docker Security

- Containers run as non-root user (`appuser`)
- SSL certificate verification enabled
- Security scanning recommended before deployment

### Best Practices

1. Never commit secrets to repository
2. Use different secrets for each environment
3. Rotate secrets regularly
4. Use Vault for production secrets
5. Enable SSL verification in production
6. Run security scans on Docker images

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python -m pytest tests/`
5. Submit a pull request

## Support

For issues and questions:
- Create an issue in the repository
- Contact the DevOps team
- Check documentation in `/docs` directory

## License

[Your License Here]

## Version History

- **4.0.0**: Current version with environment configuration system
- Previous versions: See git history
