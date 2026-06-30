#!/bin/bash

# PowerStore CT Engine Deployment Script
# This script handles deployment to different environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to show usage
usage() {
    echo "Usage: $0 <environment> <action>"
    echo ""
    echo "Environments: development, staging, production"
    echo "Actions: build, push, deploy, all"
    echo ""
    echo "Examples:"
    echo "  $0 development build"
    echo "  $0 staging deploy"
    echo "  $0 production all"
    exit 1
}

# Check if environment and action are provided
if [ $# -lt 2 ]; then
    usage
fi

ENVIRONMENT=$1
ACTION=$2

# Validate environment
case $ENVIRONMENT in
    development|staging|production)
        ;;
    *)
        print_error "Invalid environment: $ENVIRONMENT"
        usage
        ;;
esac

# Validate action
case $ACTION in
    build|push|deploy|all)
        ;;
    *)
        print_error "Invalid action: $ACTION"
        usage
        ;;
esac

# Set variables based on environment
case $ENVIRONMENT in
    development)
        REGISTRY="your-registry"
        IMAGE_TAG="development-latest"
        NAMESPACE="ct-engine-dev"
        ;;
    staging)
        REGISTRY="your-registry"
        IMAGE_TAG="staging-latest"
        NAMESPACE="ct-engine-staging"
        ;;
    production)
        REGISTRY="your-registry"
        IMAGE_TAG="production-latest"
        NAMESPACE="ct-engine-production"
        ;;
esac

IMAGE_NAME="${REGISTRY}/ct-engine:${IMAGE_TAG}"
COMMIT_SHA=$(git rev-parse --short HEAD)

print_info "Environment: $ENVIRONMENT"
print_info "Action: $ACTION"
print_info "Image: $IMAGE_NAME"
print_info "Namespace: $NAMESPACE"
print_info "Commit: $COMMIT_SHA"

# Build Docker image
build_image() {
    print_info "Building Docker image for $ENVIRONMENT..."
    
    docker build \
        --build-arg ENV=$ENVIRONMENT \
        -t ct-engine:${ENVIRONMENT} \
        -t ${IMAGE_NAME} \
        -t ${REGISTRY}/ct-engine:${ENVIRONMENT}-${COMMIT_SHA} \
        .
    
    print_info "Docker image built successfully"
}

# Push Docker image
push_image() {
    print_info "Pushing Docker image to registry..."
    
    docker login ${REGISTRY}
    docker push ${IMAGE_NAME}
    docker push ${REGISTRY}/ct-engine:${ENVIRONMENT}-${COMMIT_SHA}
    
    print_info "Docker image pushed successfully"
}

# Deploy to Kubernetes
deploy_k8s() {
    print_info "Deploying to Kubernetes namespace: $NAMESPACE..."
    
    # Create namespace if it doesn't exist
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply Kubernetes manifests
    kubectl apply -k k8s/overlays/$ENVIRONMENT/
    
    # Wait for deployment to complete
    kubectl rollout status deployment/ct-execution -n $NAMESPACE --timeout=5m
    kubectl rollout status deployment/ct-manager -n $NAMESPACE --timeout=5m
    
    print_info "Deployment completed successfully"
    
    # Show deployment status
    print_info "Deployment status:"
    kubectl get pods -n $NAMESPACE
    kubectl get services -n $NAMESPACE
}

# Run security scan
security_scan() {
    print_info "Running security scan on Docker image..."
    
    if command -v docker &> /dev/null; then
        docker scan ${IMAGE_NAME} || print_warning "Docker scan failed or not available"
    fi
    
    if command -v trivy &> /dev/null; then
        trivy image ${IMAGE_NAME} || print_warning "Trivy scan failed or not available"
    fi
}

# Perform action
case $ACTION in
    build)
        build_image
        ;;
    push)
        push_image
        ;;
    deploy)
        deploy_k8s
        ;;
    all)
        build_image
        security_scan
        push_image
        deploy_k8s
        ;;
esac

print_info "Action '$ACTION' completed successfully for environment '$ENVIRONMENT'"
