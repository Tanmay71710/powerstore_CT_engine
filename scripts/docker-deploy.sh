#!/bin/bash

# Docker Deployment Script for PowerStore CT Engine
# This script handles Docker-based deployment for local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
    echo "Usage: $0 <environment> <service> <action>"
    echo ""
    echo "Environments: development, staging, production"
    echo "Services: execution, manager, monitor, all"
    echo "Actions: build, run, stop, restart, logs"
    echo ""
    echo "Examples:"
    echo "  $0 development execution build"
    echo "  $0 development all run"
    echo "  $0 development execution logs"
    echo "  $0 development all stop"
    exit 1
}

# Check arguments
if [ $# -lt 3 ]; then
    usage
fi

ENVIRONMENT=$1
SERVICE=$2
ACTION=$3

# Validate environment
case $ENVIRONMENT in
    development|staging|production)
        ;;
    *)
        print_error "Invalid environment: $ENVIRONMENT"
        usage
        ;;
esac

# Validate service
case $SERVICE in
    execution|manager|monitor|all)
        ;;
    *)
        print_error "Invalid service: $SERVICE"
        usage
        ;;
esac

# Set port based on service
get_port() {
    case $1 in
        execution) echo "5000" ;;
        manager) echo "5002" ;;
        monitor) echo "5003" ;;
    esac
}

# Build Docker image
build_image() {
    print_info "Building Docker image for $ENVIRONMENT..."
    docker build --build-arg ENV=$ENVIRONMENT -t ct-engine:$ENVIRONMENT .
    print_info "Build completed successfully"
}

# Run Docker container
run_container() {
    local service=$1
    local port=$(get_port $service)
    local container_name="ct-${service}-${ENVIRONMENT}"
    
    print_info "Running $service container on port $port..."
    
    # Stop existing container if running
    if docker ps -a | grep -q $container_name; then
        print_warning "Container $container_name already exists, stopping it..."
        docker stop $container_name
        docker rm $container_name
    fi
    
    # Run new container
    docker run -d \
        --name $container_name \
        -e APP_NAME=$service \
        -e ENVIRONMENT=$ENVIRONMENT \
        -p $port:$port \
        --env-file .env \
        ct-engine:$ENVIRONMENT
    
    print_info "Container $container_name started successfully"
}

# Stop Docker container
stop_container() {
    local service=$1
    local container_name="ct-${service}-${ENVIRONMENT}"
    
    print_info "Stopping $service container..."
    
    if docker ps | grep -q $container_name; then
        docker stop $container_name
        print_info "Container $container_name stopped successfully"
    else
        print_warning "Container $container_name is not running"
    fi
}

# Restart Docker container
restart_container() {
    local service=$1
    stop_container $service
    sleep 2
    run_container $service
}

# Show container logs
show_logs() {
    local service=$1
    local container_name="ct-${service}-${ENVIRONMENT}"
    
    print_info "Showing logs for $service container..."
    
    if docker ps | grep -q $container_name; then
        docker logs -f $container_name
    else
        print_error "Container $container_name is not running"
        exit 1
    fi
}

# Perform action
case $ACTION in
    build)
        build_image
        ;;
    run)
        build_image
        if [ "$SERVICE" = "all" ]; then
            run_container "execution"
            run_container "manager"
            run_container "monitor"
        else
            run_container $SERVICE
        fi
        ;;
    stop)
        if [ "$SERVICE" = "all" ]; then
            stop_container "execution"
            stop_container "manager"
            stop_container "monitor"
        else
            stop_container $SERVICE
        fi
        ;;
    restart)
        if [ "$SERVICE" = "all" ]; then
            restart_container "execution"
            restart_container "manager"
            restart_container "monitor"
        else
            restart_container $SERVICE
        fi
        ;;
    logs)
        if [ "$SERVICE" = "all" ]; then
            print_error "Cannot show logs for all services at once"
            exit 1
        else
            show_logs $SERVICE
        fi
        ;;
    *)
        print_error "Invalid action: $ACTION"
        usage
        ;;
esac

print_info "Action '$ACTION' completed successfully"
