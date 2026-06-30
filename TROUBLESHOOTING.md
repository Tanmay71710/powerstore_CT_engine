# Troubleshooting Guide

This guide provides solutions to common issues encountered when working with the PowerStore CT Engine.

## Table of Contents

- [General Issues](#general-issues)
- [Docker Issues](#docker-issues)
- [Configuration Issues](#configuration-issues)
- [Database Issues](#database-issues)
- [Jenkins Integration Issues](#jenkins-integration-issues)
- [Kubernetes Issues](#kubernetes-issues)
- [Test Execution Issues](#test-execution-issues)
- [Performance Issues](#performance-issues)

## General Issues

### Application Won't Start

**Symptoms**: Application fails to start or immediately crashes

**Possible Causes**:
- Missing environment variables
- Incorrect configuration
- Missing dependencies
- Port conflicts

**Solutions**:

1. **Check environment variables**
   ```bash
   # Verify ENVIRONMENT is set
   echo $ENVIRONMENT
   
   # Set if missing
   export ENVIRONMENT=development
   ```

2. **Check configuration loading**
   ```bash
   # Test configuration system
   python -c "from shared.config_loader import get_config_dict; print(get_config_dict())"
   ```

3. **Check logs**
   ```bash
   # Docker logs
   docker logs <container_name>
   
   # Kubernetes logs
   kubectl logs <pod-name>
   ```

4. **Verify port availability**
   ```bash
   # Check if port is in use
   netstat -tuln | grep 5000
   
   # Use different port if needed
   export APP_PORT=5001
   ```

### Import Errors

**Symptoms**: `ModuleNotFoundError` or import failures

**Possible Causes**:
- Missing dependencies
- Incorrect Python path
- Virtual environment issues

**Solutions**:

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Check Python path**
   ```bash
   # Verify Python path includes project root
   python -c "import sys; print(sys.path)"
   ```

3. **Use virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

## Docker Issues

### Container Won't Start

**Symptoms**: Docker container fails to start or exits immediately

**Possible Causes**:
- Build failures
- Missing environment variables
- Permission issues
- Resource constraints

**Solutions**:

1. **Check build logs**
   ```bash
   # Rebuild with no cache to see full logs
   docker build --no-cache --build-arg ENV=development -t ct-engine:dev .
   ```

2. **Run container with debugging**
   ```bash
   # Run container interactively
   docker run -it --rm \
     -e APP_NAME=execution \
     -e ENVIRONMENT=development \
     -p 5000:5000 \
     ct-engine:dev \
     /bin/bash
   ```

3. **Check container logs**
   ```bash
   docker logs <container_id>
   docker logs <container_id> --tail 100
   docker logs -f <container_id>
   ```

4. **Verify environment variables**
   ```bash
   docker run -it --rm \
     -e APP_NAME=execution \
     -e ENVIRONMENT=development \
     ct-engine:dev \
     env
   ```

### Permission Denied Errors

**Symptoms**: Permission errors when running containers

**Possible Causes**:
- Running as root user
- File permission issues
- Volume mount permissions

**Solutions**:

1. **Check container user**
   ```bash
   docker run -it --rm ct-engine:dev whoami
   ```

2. **Fix file permissions**
   ```bash
   # Change ownership of mounted volumes
   sudo chown -R 1000:1000 ./data
   ```

3. **Run with proper user**
   ```bash
   docker run -it --rm \
     -u 1000:1000 \
     -e APP_NAME=execution \
     ct-engine:dev
   ```

### Image Build Failures

**Symptoms**: Docker build fails during image creation

**Possible Causes**:
- Network issues
- Missing base images
- Build argument errors
- Syntax errors in Dockerfile

**Solutions**:

1. **Check network connectivity**
   ```bash
   # Test Docker registry access
   docker pull python:3.9-slim
   ```

2. **Verify build arguments**
   ```bash
   docker build \
     --build-arg ENV=development \
     --build-arg BASE_IMAGE=python:3.9-slim \
     -t ct-engine:dev .
   ```

3. **Check Dockerfile syntax**
   ```bash
   # Validate Dockerfile
   docker build --no-cache -t test-build .
   ```

## Configuration Issues

### Environment Detection Fails

**Symptoms**: Wrong environment detected or detection fails

**Possible Causes**:
- Missing ENVIRONMENT variable
- Incorrect .env file
- Network detection issues

**Solutions**:

1. **Set environment explicitly**
   ```bash
   export ENVIRONMENT=staging
   ```

2. **Check .env file**
   ```bash
   # Verify .env file exists and is correct
   cat .env
   
   # Load .env file
   source .env  # Linux/Mac
   # or
   export $(cat .env | xargs)
   ```

3. **Test environment detection**
   ```bash
   python -c "from shared.environment import get_environment; print(get_environment())"
   ```

### Configuration Loading Errors

**Symptoms**: Configuration fails to load or uses wrong values

**Possible Causes**:
- Missing configuration files
- Syntax errors in config files
- Vault connection issues

**Solutions**:

1. **Test configuration loading**
   ```bash
   python -c "from shared.config_loader import get_config_dict; print(get_config_dict())"
   ```

2. **Check configuration files**
   ```bash
   # Verify config files exist
   ls -la shared/config/
   
   # Check for syntax errors
   python -m py_compile shared/config/base.py
   python -m py_compile shared/config/development.py
   ```

3. **Validate configuration**
   ```bash
   python -c "from shared.config.validation import validate_config_dict; from shared.config_loader import get_config_dict; validate_config_dict(get_config_dict())"
   ```

### Secret Management Issues

**Symptoms**: Secrets not loaded or incorrect

**Possible Causes**:
- Missing environment variables
- Vault connection issues
- Incorrect secret paths

**Solutions**:

1. **Check environment variables**
   ```bash
   # List all environment variables
   env | grep -E "(DATABASE|JENKINS|SECRET)"
   ```

2. **Test Vault connection**
   ```bash
   # Test Vault access
   vault status
   vault kv get secret/ct-engine/production
   ```

3. **Set secrets manually for testing**
   ```bash
   export DATABASE_PASSWORD=your-password
   export JENKINS_PASSWORD=your-jenkins-password
   export SECRET_KEY=your-secret-key
   ```

## Database Issues

### Database Connection Failures

**Symptoms**: Cannot connect to PostgreSQL database

**Possible Causes**:
- Database not running
- Incorrect credentials
- Network connectivity issues
- Firewall blocking

**Solutions**:

1. **Test database connectivity**
   ```bash
   # Test with psql
   psql -h 10.55.236.78 -U postgres -d qTest
   
   # Test with Python
   python -c "import psycopg2; conn = psycopg2.connect('host=10.55.236.78 user=postgres dbname=qTest password=postgres'); print('Connected')"
   ```

2. **Check database is running**
   ```bash
   # Check PostgreSQL service
   systemctl status postgresql
   
   # Check if port is accessible
   telnet 10.55.236.78 5432
   nc -zv 10.55.236.78 5432
   ```

3. **Verify credentials**
   ```bash
   # Check database password
   echo $DATABASE_PASSWORD
   
   # Test with correct credentials
   PGPASSWORD=your-password psql -h 10.55.236.78 -U postgres -d qTest
   ```

### Database Schema Issues

**Symptoms**: Table not found, column errors

**Possible Causes**:
- Missing migrations
- Incorrect schema version
- Database not initialized

**Solutions**:

1. **Run database migrations**
   ```bash
   # Run Flask migrations
   flask db upgrade
   
   # Or with Python
   python -c "from shared.database import db; from execution_engine.app import app; app.app_context().push(); db.create_all()"
   ```

2. **Check database schema**
   ```bash
   # List tables
   psql -h 10.55.236.78 -U postgres -d qTest -c "\dt"
   
   # Describe table
   psql -h 10.55.236.78 -U postgres -d qTest -c "\d test_executions"
   ```

3. **Initialize database**
   ```bash
   # Create database schema
   python -c "from shared.database import init_db; init_db()"
   ```

## Jenkins Integration Issues

### Jenkins Connection Failures

**Symptoms**: Cannot connect to Jenkins server

**Possible Causes**:
- Jenkins URL incorrect
- Authentication failures
- Network connectivity issues
- SSL certificate issues

**Solutions**:

1. **Test Jenkins connectivity**
   ```bash
   # Test Jenkins URL
   curl -k https://osj-ngm-03-prd.cec.delllabs.net
   
   # Test with authentication
   curl -k -u svc_prdsysqafw:your-password https://osj-ngm-03-prd.cec.delllabs.net/api/json
   ```

2. **Check Jenkins credentials**
   ```bash
   # Verify credentials
   echo $JENKINS_USERNAME
   echo $JENKINS_PASSWORD
   ```

3. **Test Jenkins integration**
   ```bash
   python -c "from shared.jenkins_module import MyJenkins; j = MyJenkins(); print(j.get_version())"
   ```

### Job Triggering Failures

**Symptoms**: Jenkins jobs fail to trigger

**Possible Causes**:
- Job name incorrect
- Missing parameters
- Permission issues
- Jenkins job disabled

**Solutions**:

1. **Verify job exists**
   ```bash
   # List Jenkins jobs
   python -c "from shared.jenkins_module import MyJenkins; j = MyJenkins(); print(j.get_all_jobs())"
   ```

2. **Check job configuration**
   ```bash
   # Get job info
   python -c "from shared.jenkins_module import MyJenkins; j = MyJenkins(); print(j.get_job_info('Trident/test_executer'))"
   ```

3. **Test job trigger**
   ```bash
   python -c "from shared.jenkins_module import MyJenkins; j = MyJenkins(); j.build_job('Trident/test_executer', parameters={'test': 'value'})"
   ```

## Kubernetes Issues

### Pod Not Starting

**Symptoms**: Kubernetes pods fail to start

**Possible Causes**:
- Image pull errors
- Resource constraints
- Configuration errors
- Secret missing

**Solutions**:

1. **Describe pod for details**
   ```bash
   kubectl describe pod <pod-name> -n ct-engine-production
   ```

2. **Check pod events**
   ```bash
   kubectl get events -n ct-engine-production --sort-by='.lastTimestamp'
   ```

3. **Check pod logs**
   ```bash
   kubectl logs <pod-name> -n ct-engine-production
   kubectl logs <pod-name> -n ct-engine-production --previous
   ```

4. **Verify secrets**
   ```bash
   kubectl get secrets -n ct-engine-production
   kubectl describe secret ct-db-secret -n ct-engine-production
   ```

### Service Not Accessible

**Symptoms**: Cannot access Kubernetes service

**Possible Causes**:
- Service not exposed
- Wrong port
- Network policies
- DNS issues

**Solutions**:

1. **Check service status**
   ```bash
   kubectl get svc -n ct-engine-production
   kubectl describe svc ct-execution -n ct-engine-production
   ```

2. **Test service endpoint**
   ```bash
   # Port forward for testing
   kubectl port-forward svc/ct-execution 5000:5000 -n ct-engine-production
   
   # Test endpoint
   curl http://localhost:5000/health
   ```

3. **Check network policies**
   ```bash
   kubectl get networkpolicies -n ct-engine-production
   ```

## Test Execution Issues

### Test Execution Fails

**Symptoms**: Tests fail to execute or hang

**Possible Causes**:
- Invalid test set
- Missing resources
- Jenkins job failures
- Configuration errors

**Solutions**:

1. **Validate test set**
   ```bash
   # Check test set exists
   python -c "from shared.routes import get_test_set; print(get_test_set('your_test_set'))"
   ```

2. **Check test execution logs**
   ```bash
   # View execution logs
   docker logs ct-execution
   kubectl logs <pod-name> -n ct-engine-production
   ```

3. **Verify Jenkins job**
   ```bash
   # Check Jenkins job status
   python -c "from shared.jenkins_module import MyJenkins; j = MyJenkins(); print(j.get_job_info('Trident/test_executer'))"
   ```

### XPOOL Integration Issues

**Symptoms**: XPOOL resource allocation fails

**Possible Causes**:
- XPOOL binary not found
- Incorrect XPOOL path
- Permission issues
- Resource exhaustion

**Solutions**:

1. **Verify XPOOL binary**
   ```bash
   # Check XPOOL binary exists
   ls -la /home/public/scripts/xpool_trident/prd/xpool
   
   # Test XPOOL command
   /home/public/scripts/xpool_trident/prd/xpool list -x -a
   ```

2. **Check XPOOL configuration**
   ```bash
   # Verify XPOOL path in config
   python -c "from shared.config_loader import get_config_dict; print(get_config_dict().get('XPOOL_BINARY_PATH'))"
   ```

3. **Test XPOOL connectivity**
   ```bash
   # Test XPOOL with groups
   /home/public/scripts/xpool_trident/prd/xpool list -x -g QA-TestRunner
   ```

## Performance Issues

### Slow Performance

**Symptoms**: Application responds slowly

**Possible Causes**:
- Resource constraints
- Database query performance
- Network latency
- Inefficient code

**Solutions**:

1. **Monitor resource usage**
   ```bash
   # Docker stats
   docker stats
   
   # Kubernetes resources
   kubectl top pods -n ct-engine-production
   kubectl top nodes
   ```

2. **Check database performance**
   ```bash
   # Analyze slow queries
   psql -h 10.55.236.78 -U postgres -d qTest -c "SELECT * FROM pg_stat_activity WHERE state != 'idle'"
   ```

3. **Enable profiling**
   ```bash
   # Enable SQL query logging (development only)
   export SQLALCHEMY_ECHO=True
   ```

### Memory Issues

**Symptoms**: Out of memory errors

**Possible Causes**:
- Memory leaks
- Insufficient resources
- Large data processing

**Solutions**:

1. **Increase memory limits**
   ```yaml
   # In Kubernetes deployment
   resources:
     limits:
       memory: "2Gi"
   ```

2. **Monitor memory usage**
   ```bash
   # Check memory usage
   docker stats --no-stream
   kubectl top pods -n ct-engine-production --containers
   ```

3. **Restart services**
   ```bash
   # Docker
   docker restart ct-execution
   
   # Kubernetes
   kubectl rollout restart deployment/ct-execution -n ct-engine-production
   ```

## Getting Help

If you cannot resolve your issue using this guide:

1. **Check logs thoroughly**
   ```bash
   # Collect all relevant logs
   docker logs ct-execution > ct-execution.log
   kubectl logs <pod-name> -n ct-engine-production > k8s.log
   ```

2. **Gather diagnostic information**
   ```bash
   # System information
   uname -a
   docker --version
   kubectl version --client
   python --version
   
   # Configuration dump
   python -c "from shared.config_loader import get_config_dict; import json; print(json.dumps(get_config_dict(), indent=2))"
   ```

3. **Contact support**
   - Create issue in repository with:
     - Error messages
     - Logs
     - Configuration
     - Steps to reproduce
   - Contact DevOps team
   - Check internal documentation

## Additional Resources

- [Main Documentation](README.md)
- [Deployment Guide](DEPLOYMENT.md)
- [API Documentation](API.md)
- [Environment Configuration](ENVIRONMENT_CONFIGURATION.md)
