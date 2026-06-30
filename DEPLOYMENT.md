# Deployment Guide

This guide provides detailed instructions for deploying the PowerStore CT Engine to different environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Deployment](#development-deployment)
- [Staging Deployment](#staging-deployment)
- [Production Deployment](#production-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Rollback Procedures](#rollback-procedures)
- [Monitoring and Logging](#monitoring-and-logging)

## Prerequisites

### Required Tools

- Docker 20.10+
- kubectl (for Kubernetes deployment)
- Access to Docker registry
- PostgreSQL database
- Jenkins server
- Vault (for production secrets)

### Required Access

- Docker registry push/pull access
- Kubernetes cluster access
- Database credentials
- Jenkins credentials
- Vault access (production)

## Development Deployment

### Local Development Setup

#### 1. Environment Setup

```bash
# Clone repository
git clone https://github.com/Tanmay71710/powerstore_CT_engine.git
cd powerstore_CT_engine

# Copy environment template
cp .env.example .env

# Edit environment file
nano .env
```

#### 2. Configure .env File

```bash
# Environment Configuration
ENVIRONMENT=development
APP_NAME=execution
APP_PORT=5000

# Database Configuration
DATABASE_HOST=10.55.236.78
DATABASE_PORT=5432
DATABASE_NAME=qTest
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres

# Jenkins Configuration
JENKINS_URL=https://osj-ngm-03-prd.cec.delllabs.net
JENKINS_USERNAME=svc_prdsysqafw
JENKINS_PASSWORD=your-dev-password

# Application Configuration
SECRET_KEY=development-secret-key
```

#### 3. Build and Run

```bash
# Build Docker image
docker build --build-arg ENV=development -t ct-engine:dev .

# Run execution engine
docker run -d \
  --name ct-execution \
  -e APP_NAME=execution \
  -e ENVIRONMENT=development \
  -p 5000:5000 \
  --env-file .env \
  ct-engine:dev

# Run manager engine
docker run -d \
  --name ct-manager \
  -e APP_NAME=manager \
  -e ENVIRONMENT=development \
  -p 5002:5002 \
  --env-file .env \
  ct-engine:dev

# Run monitor engine
docker run -d \
  --name ct-monitor \
  -e APP_NAME=monitor \
  -e ENVIRONMENT=development \
  --env-file .env \
  ct-engine:dev
```

#### 4. Verify Deployment

```bash
# Check container status
docker ps

# Check logs
docker logs ct-execution
docker logs ct-manager
docker logs ct-monitor

# Test health endpoints
curl http://localhost:5000/health
curl http://localhost:5002/health
```

## Staging Deployment

### Prerequisites

- Staging Kubernetes cluster access
- Staging database credentials
- Staging Jenkins credentials
- Docker registry access

### Deployment Steps

#### 1. Build Docker Image

```bash
# Build with staging configuration
docker build \
  --build-arg ENV=staging \
  -t ct-engine:staging \
  -t your-registry/ct-engine:staging-latest \
  -t your-registry/ct-engine:staging-$(git rev-parse --short HEAD) .
```

#### 2. Push to Registry

```bash
# Login to registry
docker login your-registry

# Push images
docker push your-registry/ct-engine:staging-latest
docker push your-registry/ct-engine:staging-$(git rev-parse --short HEAD)
```

#### 3. Configure Kubernetes Secrets

```bash
# Create namespace
kubectl create namespace ct-engine-staging

# Create database secret
kubectl create secret generic ct-db-secret \
  --from-literal=DATABASE_HOST=10.55.236.78 \
  --from-literal=DATABASE_PORT=5432 \
  --from-literal=DATABASE_NAME=qTest \
  --from-literal=DATABASE_USER=postgres \
  --from-literal=DATABASE_PASSWORD=your-staging-db-password \
  -n ct-engine-staging

# Create Jenkins secret
kubectl create secret generic ct-jenkins-secret \
  --from-literal=JENKINS_URL=https://osj-ngm-03-prd.cec.delllabs.net \
  --from-literal=JENKINS_USERNAME=svc_prdsysqafw \
  --from-literal=JENKINS_PASSWORD=your-staging-jenkins-password \
  -n ct-engine-staging

# Create application secret
kubectl create secret generic ct-app-secret \
  --from-literal=SECRET_KEY=your-staging-secret-key \
  -n ct-engine-staging
```

#### 4. Deploy to Kubernetes

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/staging/ -n ct-engine-staging

# Verify deployment
kubectl get pods -n ct-engine-staging
kubectl get services -n ct-engine-staging
```

#### 5. Verify Deployment

```bash
# Check pod status
kubectl describe pod <pod-name> -n ct-engine-staging

# Check logs
kubectl logs <pod-name> -n ct-engine-staging

# Port forward for local testing
kubectl port-forward svc/ct-execution 5000:5000 -n ct-engine-staging

# Test health endpoint
curl http://localhost:5000/health
```

## Production Deployment

### Prerequisites

- Production Kubernetes cluster access
- Production database credentials
- Production Jenkins credentials
- Vault access for secrets
- Approval from production team

### Pre-Deployment Checklist

- [ ] All tests passing in staging
- [ ] Security scan completed and passed
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Rollback plan documented
- [ ] Monitoring and alerting configured
- [ ] Backup plan in place

### Deployment Steps

#### 1. Build Production Image

```bash
# Build with production configuration
docker build \
  --build-arg ENV=production \
  -t ct-engine:production \
  -t your-registry/ct-engine:production-latest \
  -t your-registry/ct-engine:production-$(git rev-parse --short HEAD) .
```

#### 2. Security Scan

```bash
# Run security scan
docker scan ct-engine:production

# Scan for vulnerabilities
trivy image ct-engine:production
```

#### 3. Push to Registry

```bash
# Login to registry
docker login your-registry

# Push images
docker push your-registry/ct-engine:production-latest
docker push your-registry/ct-engine:production-$(git rev-parse --short HEAD)
```

#### 4. Configure Production Secrets

```bash
# Create namespace
kubectl create namespace ct-engine-production

# Retrieve secrets from Vault
vault kv get -field=DATABASE_PASSWORD secret/ct-engine/production
vault kv get -field=JENKINS_PASSWORD secret/ct-engine/production
vault kv get -field=SECRET_KEY secret/ct-engine/production

# Create Kubernetes secrets from Vault
kubectl create secret generic ct-db-secret \
  --from-literal=DATABASE_HOST=10.55.236.78 \
  --from-literal=DATABASE_PORT=5432 \
  --from-literal=DATABASE_NAME=qTest \
  --from-literal=DATABASE_USER=postgres \
  --from-literal=DATABASE_PASSWORD=$(vault kv get -field=DATABASE_PASSWORD secret/ct-engine/production) \
  -n ct-engine-production

kubectl create secret generic ct-jenkins-secret \
  --from-literal=JENKINS_URL=https://osj-ngm-03-prd.cec.delllabs.net \
  --from-literal=JENKINS_USERNAME=svc_prdsysqafw \
  --from-literal=JENKINS_PASSWORD=$(vault kv get -field=JENKINS_PASSWORD secret/ct-engine/production) \
  -n ct-engine-production

kubectl create secret generic ct-app-secret \
  --from-literal=SECRET_KEY=$(vault kv get -field=SECRET_KEY secret/ct-engine/production) \
  -n ct-engine-production
```

#### 5. Deploy to Production

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/production/ -n ct-engine-production

# Verify deployment
kubectl get pods -n ct-engine-production
kubectl get services -n ct-engine-production
```

#### 6. Post-Deployment Verification

```bash
# Check pod status
kubectl describe pod <pod-name> -n ct-engine-production

# Check logs
kubectl logs <pod-name> -n ct-engine-production

# Test health endpoints
kubectl exec -it <pod-name> -n ct-engine-production -- curl http://localhost:5000/health

# Run smoke tests
python -m pytest tests/smoke_tests.py -v
```

## Kubernetes Deployment

### Kubernetes Manifests Structure

```
k8s/
├── base/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── overlays/
│   ├── development/
│   │   └── kustomization.yaml
│   ├── staging/
│   │   └── kustomization.yaml
│   └── production/
│       └── kustomization.yaml
```

### Example Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ct-execution
  namespace: ct-engine-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ct-execution
  template:
    metadata:
      labels:
        app: ct-execution
        environment: production
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: ct-execution
        image: your-registry/ct-engine:production-latest
        ports:
        - containerPort: 5000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: APP_NAME
          value: "execution"
        - name: DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ct-db-secret
              key: DATABASE_PASSWORD
        - name: JENKINS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ct-jenkins-secret
              key: JENKINS_PASSWORD
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: ct-app-secret
              key: SECRET_KEY
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Rollback Procedures

### Docker Rollback

```bash
# Stop current containers
docker stop ct-execution ct-manager ct-monitor

# Start previous version
docker run -d \
  --name ct-execution \
  -e APP_NAME=execution \
  -e ENVIRONMENT=production \
  -p 5000:5000 \
  --env-file .env \
  your-registry/ct-engine:production-previous-version
```

### Kubernetes Rollback

```bash
# Check rollout history
kubectl rollout history deployment/ct-execution -n ct-engine-production

# Rollback to previous version
kubectl rollout undo deployment/ct-execution -n ct-engine-production

# Rollback to specific revision
kubectl rollout undo deployment/ct-execution --to-revision=2 -n ct-engine-production

# Verify rollback
kubectl get pods -n ct-engine-production
kubectl rollout status deployment/ct-execution -n ct-engine-production
```

## Monitoring and Logging

### Container Logs

```bash
# Docker logs
docker logs -f ct-execution

# Kubernetes logs
kubectl logs -f <pod-name> -n ct-engine-production
kubectl logs -f deployment/ct-execution -n ct-engine-production
```

### Health Checks

```bash
# Docker health check
docker exec ct-execution curl http://localhost:5000/health

# Kubernetes health check
kubectl exec -it <pod-name> -n ct-engine-production -- curl http://localhost:5000/health
```

### Monitoring Metrics

The application exposes metrics at `/metrics` endpoint (if configured):

```bash
# Get metrics
curl http://localhost:5000/metrics
```

## Troubleshooting

### Common Deployment Issues

#### Image Pull Errors

```bash
# Check registry access
docker pull your-registry/ct-engine:production-latest

# Check image exists
docker images | grep ct-engine
```

#### Pod Not Starting

```bash
# Describe pod for details
kubectl describe pod <pod-name> -n ct-engine-production

# Check events
kubectl get events -n ct-engine-production --sort-by='.lastTimestamp'
```

#### Database Connection Issues

```bash
# Test database connectivity
kubectl exec -it <pod-name> -n ct-engine-production -- psql -h 10.55.236.78 -U postgres -d qTest

# Check database secret
kubectl get secret ct-db-secret -n ct-engine-production -o yaml
```

## Support

For deployment issues:
- Check logs: `kubectl logs <pod-name> -n ct-engine-production`
- Review this documentation
- Contact DevOps team
- Create issue in repository
