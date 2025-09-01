# MCP Server API Specification

## Overview

The MCP (Model Context Protocol) Server is a RESTful API server that connects Claude Code and the Koubou System.

**Base URL**: `http://localhost:8765`

## Authentication

Authentication is not implemented in the current POC version. We recommend implementing proper authentication mechanisms for production environments.

## Endpoints

### GET /health

System health check

#### Request
```http
GET /health HTTP/1.1
Host: localhost:8765
```

#### Response
```json
{
  "status": "healthy",
  "timestamp": "2025-08-29T12:34:56.789Z"
}
```

#### Status Codes
- `200 OK`: System healthy

---

### POST /task/delegate

Delegate a task

#### Request
```http
POST /task/delegate HTTP/1.1
Host: localhost:8765
Content-Type: application/json

{
  "type": "code",
  "prompt": "Create a Python function to calculate prime numbers",
  "priority": 8,
  "sync": false,
  "files": ["utils.py", "main.py"],
  "options": {
    "timeout": 120,
    "model": "gpt-oss:20b"
  }
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | string | Yes | Task type: `code` or `general` |
| prompt | string | Yes | Task content/instructions |
| priority | integer | No | Priority (1-10), default: 5 |
| sync | boolean | No | Synchronous execution flag, default: false |
| files | array | No | List of related files |
| options | object | No | Additional options |

#### Response (Asynchronous)
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "delegated"
}
```

#### Response (Synchronous)
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "completed",
  "result": {
    "success": true,
    "output": "def is_prime(n):\n    if n <= 1:\n        return False\n    ...",
    "error": null
  }
}
```

#### Status Codes
- `200 OK`: Task delegation successful
- `400 Bad Request`: Invalid request
- `500 Internal Server Error`: Server error

---

### GET /task/{task_id}/status

Get task status

#### Request
```http
GET /task/task_20250829_123456_789012/status HTTP/1.1
Host: localhost:8765
```

#### Response
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "completed",
  "result": {
    "success": true,
    "output": "Task output...",
    "error": null
  },
  "created_at": "2025-08-29T12:34:56",
  "updated_at": "2025-08-29T12:35:12"
}
```

#### Status Values
- `pending`: Waiting for processing
- `in_progress`: Processing
- `completed`: Completed
- `failed`: Failed
- `cancelled`: Cancelled

#### Status Codes
- `200 OK`: Success
- `404 Not Found`: Task not found

---

### GET /tasks

Get task list

#### Request
```http
GET /tasks?status=pending&limit=10 HTTP/1.1
Host: localhost:8765
```

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Status to filter by |
| limit | integer | Maximum number of results (default: 10) |
| offset | integer | Offset |

#### Response
```json
{
  "tasks": [
    {
      "task_id": "task_20250829_123456_789012",
      "status": "completed",
      "created_at": "2025-08-29T12:34:56"
    },
    {
      "task_id": "task_20250829_123457_890123",
      "status": "pending",
      "created_at": "2025-08-29T12:34:57"
    }
  ],
  "total": 42
}
```

---

### DELETE /task/{task_id}

Cancel task (not implemented)

#### Request
```http
DELETE /task/task_20250829_123456_789012 HTTP/1.1
Host: localhost:8765
```

#### Response
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "cancelled"
}
```

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {}
  }
}
```

### Error Codes

| Code | Description |
|------|-------------|
| INVALID_REQUEST | Invalid request |
| TASK_NOT_FOUND | Task not found |
| SERVER_ERROR | Internal server error |
| WORKER_UNAVAILABLE | Worker unavailable |
| TIMEOUT | Timeout |

## Usage Examples

### Python

```python
import requests
import json

class MCPClient:
    def __init__(self, base_url='http://localhost:8765'):
        self.base_url = base_url
    
    def submit_task(self, prompt, task_type='general', sync=False, priority=5):
        response = requests.post(
            f'{self.base_url}/task/delegate',
            json={
                'type': task_type,
                'prompt': prompt,
                'sync': sync,
                'priority': priority
            }
        )
        return response.json()
    
    def get_status(self, task_id):
        response = requests.get(
            f'{self.base_url}/task/{task_id}/status'
        )
        return response.json()
    
    def wait_for_completion(self, task_id, timeout=300):
        import time
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(task_id)
            if status['status'] in ['completed', 'failed']:
                return status
            time.sleep(2)
        raise TimeoutError(f"Task {task_id} timed out")

# Usage example
client = MCPClient()

# Synchronous execution
result = client.submit_task(
    "Write a haiku about programming",
    task_type='general',
    sync=True
)
print(result['result']['output'])

# Asynchronous execution
task = client.submit_task(
    "Create a REST API with Flask",
    task_type='code',
    sync=False,
    priority=8
)
result = client.wait_for_completion(task['task_id'])
print(result['result']['output'])
```

### cURL

```bash
# Health check
curl http://localhost:8765/health

# Submit task (synchronous)
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "type": "general",
    "prompt": "What is recursion?",
    "sync": true
  }'

# Submit task (asynchronous)
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "type": "code",
    "prompt": "Create a binary search function",
    "sync": false,
    "priority": 7
  }'

# Check status
curl http://localhost:8765/task/task_20250829_123456_789012/status

# List tasks
curl "http://localhost:8765/tasks?status=pending&limit=5"
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

class MCPClient {
    constructor(baseURL = 'http://localhost:8765') {
        this.client = axios.create({ baseURL });
    }
    
    async submitTask(prompt, options = {}) {
        const { data } = await this.client.post('/task/delegate', {
            type: options.type || 'general',
            prompt,
            sync: options.sync || false,
            priority: options.priority || 5
        });
        return data;
    }
    
    async getStatus(taskId) {
        const { data } = await this.client.get(`/task/${taskId}/status`);
        return data;
    }
    
    async waitForCompletion(taskId, timeout = 300000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const status = await this.getStatus(taskId);
            if (['completed', 'failed'].includes(status.status)) {
                return status;
            }
            await new Promise(r => setTimeout(r, 2000));
        }
        throw new Error(`Task ${taskId} timed out`);
    }
}

// Usage example
(async () => {
    const client = new MCPClient();
    
    // Synchronous execution
    const result = await client.submitTask(
        'Explain async/await in JavaScript',
        { sync: true }
    );
    console.log(result.result.output);
    
    // Asynchronous execution
    const task = await client.submitTask(
        'Create an Express.js server',
        { type: 'code', priority: 8 }
    );
    const completed = await client.waitForCompletion(task.task_id);
    console.log(completed.result.output);
})();
```

## Rate Limiting

Rate limiting is not implemented in the current POC version. For production environments, we recommend:

- Requests/second: 100
- Concurrent tasks: depends on max_workers configuration
- Task size: maximum 1MB

## WebSocket (Planned)

WebSocket endpoint for real-time updates (not implemented):

```javascript
// Future implementation example
const ws = new WebSocket('ws://localhost:8765/ws');

ws.on('message', (data) => {
    const event = JSON.parse(data);
    switch(event.type) {
        case 'task_started':
            console.log(`Task ${event.task_id} started`);
            break;
        case 'task_completed':
            console.log(`Task ${event.task_id} completed`);
            break;
        case 'worker_spawned':
            console.log(`New worker ${event.worker_id} spawned`);
            break;
    }
});
```

---
Last updated: 2025-08-29
Version: 1.0.0