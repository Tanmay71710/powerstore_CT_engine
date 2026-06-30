# API Documentation

This document provides comprehensive API documentation for the PowerStore CT Engine.

## Table of Contents

- [Base URLs](#base-urls)
- [Authentication](#authentication)
- [Common Headers](#common-headers)
- [Error Responses](#error-responses)
- [Execution Engine API](#execution-engine-api)
- [Manager Engine API](#manager-engine-api)
- [Monitor Engine API](#monitor-engine-api)

## Base URLs

The API base URLs vary by environment:

| Environment | Base URL |
|------------|----------|
| Development | http://localhost:5000 |
| Staging | http://staging-api.dell.com:5000 |
| Production | http://prod-api.dell.com:5000 |

## Authentication

Currently, the framework uses LDAP authentication for certain endpoints. Configure LDAP settings in your environment configuration.

### LDAP Configuration

```python
LDAP_URL = "ldaps://amer.dell.com:3269"
LDAP_BASE_DN = "DC=dell,DC=com"
LDAP_USE_SSL = True
```

## Common Headers

### Request Headers

```
Content-Type: application/json
Accept: application/json
Authorization: Bearer <token> (if required)
```

### Response Headers

```
Content-Type: application/json
X-Environment: development|staging|production
X-Request-ID: <uuid>
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "error": "Bad Request",
  "message": "Invalid request parameters",
  "details": {}
}
```

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "message": "Authentication required",
  "details": {}
}
```

### 404 Not Found
```json
{
  "error": "Not Found",
  "message": "Resource not found",
  "details": {}
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred",
  "details": {}
}
```

## Execution Engine API

The Execution Engine handles test execution and monitoring.

### Health Check

Check if the service is running.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "4.0.0",
  "timestamp": "2024-06-30T10:00:00Z"
}
```

**Example**:
```bash
curl http://localhost:5000/health
```

### Create Test Set

Create a new test set configuration.

**Endpoint**: `POST /test_sets`

**Request Body**:
```json
{
  "name": "my_test_set",
  "description": "Test set for validation",
  "qaenv": "/home/trqa-dev",
  "xpool_groups": "QA-TestRunner,FRAMEWORK",
  "xpool_reservation_limit": 5,
  "filter": {
    "dev_test": "False",
    "pr_tester": "False"
  },
  "jenkins_server": "https://osj-ngm-03-prd.cec.delllabs.net"
}
```

**Response**:
```json
{
  "id": 1,
  "name": "my_test_set",
  "status": "created",
  "created_at": "2024-06-30T10:00:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:5000/test_sets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_test_set",
    "description": "Test set for validation",
    "qaenv": "/home/trqa-dev",
    "xpool_groups": "QA-TestRunner,FRAMEWORK"
  }'
```

### Get Test Set

Retrieve details of a specific test set.

**Endpoint**: `GET /test_sets/{id}`

**Parameters**:
- `id` (path): Test set ID

**Response**:
```json
{
  "id": 1,
  "name": "my_test_set",
  "description": "Test set for validation",
  "qaenv": "/home/trqa-dev",
  "xpool_groups": "QA-TestRunner,FRAMEWORK",
  "xpool_reservation_limit": 5,
  "filter": {
    "dev_test": "False",
    "pr_tester": "False"
  },
  "jenkins_server": "https://osj-ngm-03-prd.cec.delllabs.net",
  "created_at": "2024-06-30T10:00:00Z",
  "updated_at": "2024-06-30T10:00:00Z"
}
```

**Example**:
```bash
curl http://localhost:5000/test_sets/1
```

### List Test Sets

List all test sets with optional filtering.

**Endpoint**: `GET /test_sets`

**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 10)
- `status` (optional): Filter by status

**Response**:
```json
{
  "test_sets": [
    {
      "id": 1,
      "name": "my_test_set",
      "status": "active"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 10
}
```

**Example**:
```bash
curl http://localhost:5000/test_sets?page=1&per_page=10
```

### Start Test Execution

Start execution of a test set.

**Endpoint**: `POST /test_execution`

**Request Body**:
```json
{
  "test_set_name": "my_test_set",
  "test_set_id": 1,
  "parameters": {
    "environment": "development",
    "priority": "high"
  }
}
```

**Response**:
```json
{
  "execution_id": 123,
  "test_set_name": "my_test_set",
  "status": "started",
  "started_at": "2024-06-30T10:00:00Z",
  "jenkins_job": "Trident/test_executer",
  "jenkins_build_number": 456
}
```

**Example**:
```bash
curl -X POST http://localhost:5000/test_execution \
  -H "Content-Type: application/json" \
  -d '{
    "test_set_name": "my_test_set",
    "test_set_id": 1,
    "parameters": {
      "environment": "development",
      "priority": "high"
    }
  }'
```

### Get Test Execution Status

Get the status of a test execution.

**Endpoint**: `GET /test_execution/{id}`

**Parameters**:
- `id` (path): Test execution ID

**Response**:
```json
{
  "execution_id": 123,
  "test_set_name": "my_test_set",
  "status": "running",
  "started_at": "2024-06-30T10:00:00Z",
  "updated_at": "2024-06-30T10:30:00Z",
  "jenkins_job": "Trident/test_executer",
  "jenkins_build_number": 456,
  "jenkins_build_status": "RUNNING",
  "progress": {
    "total": 100,
    "completed": 45,
    "failed": 2,
    "passed": 43
  }
}
```

**Example**:
```bash
curl http://localhost:5000/test_execution/123
```

### List Test Executions

List all test executions with optional filtering.

**Endpoint**: `GET /test_executions`

**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 10)
- `status` (optional): Filter by status
- `test_set_name` (optional): Filter by test set name

**Response**:
```json
{
  "executions": [
    {
      "execution_id": 123,
      "test_set_name": "my_test_set",
      "status": "running",
      "started_at": "2024-06-30T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 10
}
```

**Example**:
```bash
curl http://localhost:5000/test_executions?status=running&page=1
```

### Cancel Test Execution

Cancel a running test execution.

**Endpoint**: `DELETE /test_execution/{id}`

**Parameters**:
- `id` (path): Test execution ID

**Response**:
```json
{
  "execution_id": 123,
  "status": "cancelled",
  "cancelled_at": "2024-06-30T11:00:00Z",
  "message": "Test execution cancelled successfully"
}
```

**Example**:
```bash
curl -X DELETE http://localhost:5000/test_execution/123
```

## Manager Engine API

The Manager Engine manages test sets, configurations, and cluster operations.

### Health Check

Check if the manager service is running.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "4.0.0",
  "timestamp": "2024-06-30T10:00:00Z"
}
```

**Example**:
```bash
curl http://localhost:5002/health
```

### List Clusters

List all available clusters.

**Endpoint**: `GET /clusters`

**Query Parameters**:
- `status` (optional): Filter by status (available, leased, maintenance)
- `environment` (optional): Filter by environment

**Response**:
```json
{
  "clusters": [
    {
      "id": "cluster-001",
      "name": "Test Cluster 1",
      "status": "available",
      "environment": "development",
      "capacity": {
        "cpu": "16",
        "memory": "64GB",
        "storage": "1TB"
      }
    }
  ],
  "total": 1
}
```

**Example**:
```bash
curl http://localhost:5002/clusters?status=available
```

### Get Cluster Details

Get detailed information about a specific cluster.

**Endpoint**: `GET /clusters/{id}`

**Parameters**:
- `id` (path): Cluster ID

**Response**:
```json
{
  "id": "cluster-001",
  "name": "Test Cluster 1",
  "status": "available",
  "environment": "development",
  "capacity": {
    "cpu": "16",
    "memory": "64GB",
    "storage": "1TB"
  },
  "labels": {
    "team": "QA",
    "project": "PowerStore"
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Example**:
```bash
curl http://localhost:5002/clusters/cluster-001
```

### Lease Cluster

Lease a cluster for test execution.

**Endpoint**: `POST /clusters/{id}/lease`

**Parameters**:
- `id` (path): Cluster ID

**Request Body**:
```json
{
  "test_execution_id": 123,
  "duration_hours": 24,
  "purpose": "Test execution",
  "requested_by": "user@example.com"
}
```

**Response**:
```json
{
  "cluster_id": "cluster-001",
  "lease_id": "lease-001",
  "status": "leased",
  "leased_at": "2024-06-30T10:00:00Z",
  "expires_at": "2024-07-01T10:00:00Z",
  "test_execution_id": 123
}
```

**Example**:
```bash
curl -X POST http://localhost:5002/clusters/cluster-001/lease \
  -H "Content-Type: application/json" \
  -d '{
    "test_execution_id": 123,
    "duration_hours": 24,
    "purpose": "Test execution",
    "requested_by": "user@example.com"
  }'
```

### Release Cluster

Release a leased cluster.

**Endpoint**: `DELETE /clusters/{id}/lease`

**Parameters**:
- `id` (path): Cluster ID

**Response**:
```json
{
  "cluster_id": "cluster-001",
  "lease_id": "lease-001",
  "status": "released",
  "released_at": "2024-06-30T11:00:00Z",
  "message": "Cluster released successfully"
}
```

**Example**:
```bash
curl -X DELETE http://localhost:5002/clusters/cluster-001/lease
```

### Get Cluster Leases

Get all leases for a cluster.

**Endpoint**: `GET /clusters/{id}/leases`

**Parameters**:
- `id` (path): Cluster ID

**Response**:
```json
{
  "cluster_id": "cluster-001",
  "leases": [
    {
      "lease_id": "lease-001",
      "test_execution_id": 123,
      "status": "active",
      "leased_at": "2024-06-30T10:00:00Z",
      "expires_at": "2024-07-01T10:00:00Z"
    }
  ]
}
```

**Example**:
```bash
curl http://localhost:5002/clusters/cluster-001/leases
```

## Monitor Engine API

The Monitor Engine monitors cluster health and test execution status.

### Health Check

Check if the monitor service is running.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "4.0.0",
  "timestamp": "2024-06-30T10:00:00Z"
}
```

**Example**:
```bash
curl http://localhost:5003/health
```

### Get Cluster Status

Get health status of all clusters.

**Endpoint**: `GET /clusters/status`

**Response**:
```json
{
  "clusters": [
    {
      "id": "cluster-001",
      "name": "Test Cluster 1",
      "health": "healthy",
      "status": "available",
      "metrics": {
        "cpu_usage": "45%",
        "memory_usage": "60%",
        "disk_usage": "30%"
      },
      "last_checked": "2024-06-30T10:00:00Z"
    }
  ],
  "total_clusters": 1,
  "healthy_clusters": 1,
  "unhealthy_clusters": 0
}
```

**Example**:
```bash
curl http://localhost:5003/clusters/status
```

### Get Active Test Executions

Get all currently active test executions.

**Endpoint**: `GET /test_executions/active`

**Response**:
```json
{
  "active_executions": [
    {
      "execution_id": 123,
      "test_set_name": "my_test_set",
      "status": "running",
      "started_at": "2024-06-30T10:00:00Z",
      "cluster_id": "cluster-001",
      "progress": {
        "total": 100,
        "completed": 45,
        "failed": 2,
        "passed": 43
      }
    }
  ],
  "total_active": 1
}
```

**Example**:
```bash
curl http://localhost:5003/test_executions/active
```

### Get System Metrics

Get system-wide metrics and statistics.

**Endpoint**: `GET /metrics`

**Response**:
```json
{
  "system": {
    "uptime": "72h 30m",
    "version": "4.0.0",
    "environment": "development"
  },
  "performance": {
    "cpu_usage": "35%",
    "memory_usage": "55%",
    "disk_usage": "25%"
  },
  "executions": {
    "total_today": 10,
    "active": 1,
    "completed": 8,
    "failed": 1
  },
  "clusters": {
    "total": 5,
    "available": 3,
    "leased": 2,
    "maintenance": 0
  }
}
```

**Example**:
```bash
curl http://localhost:5003/metrics
```

### Get Alerts

Get system alerts and notifications.

**Endpoint**: `GET /alerts`

**Query Parameters**:
- `severity` (optional): Filter by severity (info, warning, error, critical)
- `since` (optional): Get alerts since timestamp

**Response**:
```json
{
  "alerts": [
    {
      "id": "alert-001",
      "severity": "warning",
      "message": "Cluster memory usage high",
      "cluster_id": "cluster-001",
      "created_at": "2024-06-30T10:00:00Z",
      "resolved": false
    }
  ],
  "total": 1,
  "unresolved": 1
}
```

**Example**:
```bash
curl http://localhost:5003/alerts?severity=warning
```

## WebSocket Support

The framework supports WebSocket connections for real-time updates.

### Test Execution Updates

Connect to receive real-time updates for test execution.

**Endpoint**: `WS /ws/test_execution/{id}`

**Parameters**:
- `id` (path): Test execution ID

**Message Format**:
```json
{
  "type": "progress_update",
  "execution_id": 123,
  "data": {
    "completed": 46,
    "failed": 2,
    "passed": 44,
    "current_test": "test_case_046"
  }
}
```

**Example**:
```javascript
const ws = new WebSocket('ws://localhost:5000/ws/test_execution/123');

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

## Rate Limiting

API endpoints may be rate-limited based on your configuration.

**Rate Limit Headers**:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1625097600
```

**Rate Limit Exceeded Response**:
```json
{
  "error": "Rate Limit Exceeded",
  "message": "Too many requests",
  "details": {
    "limit": 1000,
    "remaining": 0,
    "reset_at": "2024-06-30T11:00:00Z"
  }
}
```

## SDK and Client Libraries

### Python Client

```python
from powerstore_ct_engine import Client

# Initialize client
client = Client(
    base_url="http://localhost:5000",
    environment="development"
)

# Create test set
test_set = client.create_test_set(
    name="my_test_set",
    description="Test set for validation"
)

# Start execution
execution = client.start_execution(
    test_set_name="my_test_set",
    parameters={"environment": "development"}
)

# Get status
status = client.get_execution_status(execution.execution_id)
```

### cURL Examples

See individual endpoint examples above.

## Testing APIs

### Using Swagger UI

The framework includes Swagger UI for interactive API testing:

- Development: http://localhost:5000/swagger
- Staging: http://staging-api.dell.com:5000/swagger
- Production: http://prod-api.dell.com:5000/swagger

### Using Postman

Import the API collection and configure environment variables for each environment.

## Support

For API-related issues:
- Check API documentation
- Test with Swagger UI
- Review error responses
- Contact API team
- Create issue in repository
