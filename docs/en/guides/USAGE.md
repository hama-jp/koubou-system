# User Guide

## Basic Usage

### Starting the System

```bash
# Start all components
.koubou/start_system.sh

# Starting components individually
# 1. Ollama
ollama serve

# 2. MCP server
source .koubou/venv/bin/activate
python .koubou/scripts/mcp_server.py

# 3. Worker pool
python .koubou/scripts/workers/worker_pool_manager.py
```

### First Task

#### 1. Simple Question (Synchronous Mode)

```python
import requests

response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'general',
    'prompt': 'What is Python?',
    'sync': True  # Wait for result
})

print(response.json()['result']['output'])
```

#### 2. Code Generation (Asynchronous Mode)

```python
# Task submission
response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'code',
    'prompt': 'Create a Python function to calculate factorial',
    'sync': False,  # Background processing
    'priority': 8
})

task_id = response.json()['task_id']

# Status check
import time
while True:
    status = requests.get(f'http://localhost:8765/task/{task_id}/status')
    if status.json()['status'] in ['completed', 'failed']:
        print(status.json()['result'])
        break
    time.sleep(2)
```

## Using Codex CLI

### Interactive Mode

```bash
# Using Ollama
.koubou/scripts/codex-ollama.sh

# Prompt examples
> Create a REST API with Flask
> Add error handling to the current code
> Refactor this function for better performance
```

### Command-line Mode

```bash
# Create file
.koubou/scripts/codex-exec.sh "Create a Python script that reads CSV files"

# Modify existing file
.koubou/scripts/codex-exec.sh "Add type hints to all functions in utils.py"

# Test creation
.koubou/scripts/codex-exec.sh "Write unit tests for calculator.py using pytest"
```

## Task Management

### Retrieve Task List

```bash
# Via curl
curl http://localhost:8765/tasks | jq

# Via Python
import requests
response = requests.get('http://localhost:8765/tasks')
for task in response.json()['tasks']:
    print(f"{task['task_id']}: {task['status']}")
```

### Setting Task Priority

Priority ranges from 1 (low) to 10 (high):

```python
# High priority task
high_priority = {
    'type': 'code',
    'prompt': 'Fix critical bug in production',
    'priority': 10,
    'sync': False
}

# Low priority task
low_priority = {
    'type': 'general',
    'prompt': 'Generate documentation',
    'priority': 3,
    'sync': False
}
```

## Load Testing

### Burst Test

```bash
# Inject 20 tasks at once
python .koubou/scripts/load_test.py
# Select option 1
```

### Continuous Load Test

```python
import requests
import time
import random

# Send 1 task per second for 10 minutes
end_time = time.time() + 600
while time.time() < end_time:
    requests.post('http://localhost:8765/task/delegate', json={
        'type': random.choice(['general', 'code']),
        'prompt': f'Test task {time.time()}',
        'priority': random.randint(1, 10),
        'sync': False
    })
    time.sleep(1)
```

## Monitoring

### Check System Status

```bash
# Health check
curl http://localhost:8765/health

# Worker status (via database)
sqlite3 .koubou/db/koubou.db "
SELECT worker_id, status, tasks_completed, tasks_failed 
FROM workers 
WHERE last_heartbeat > datetime('now', '-1 minute');"

# Task statistics
sqlite3 .koubou/db/koubou.db "
SELECT status, COUNT(*) 
FROM task_master 
GROUP BY status;"
```

### Log Review

```bash
# MCP server log
tail -f .koubou/logs/mcp_server.log

# Worker pool log
tail -f .koubou/logs/worker_pool.log

# Specific worker log
tail -f .koubou/logs/workers/worker_*.log

# Extract only errors
grep ERROR .koubou/logs/*.log
```

## Practical Usage Examples

### 1. Project Refactoring

```bash
# Execute in project directory
cd my_project

# Request code improvement
.koubou/scripts/codex-exec.sh "
Refactor all Python files in this directory:
1. Add type hints
2. Improve error handling
3. Add docstrings
4. Follow PEP 8
"
```

### 2. Test Suite Creation

```python
# Submit tasks via API
import requests

tasks = [
    "Create unit tests for models.py",
    "Create integration tests for api.py",
    "Create end-to-end tests for the application",
    "Generate test data fixtures"
]

for task in tasks:
    requests.post('http://localhost:8765/task/delegate', json={
        'type': 'code',
        'prompt': task,
        'priority': 7,
        'sync': False
    })
```

### 3. Documentation Generation

```bash
# Batch processing
for file in *.py; do
    .koubou/scripts/codex-exec.sh "
    Generate comprehensive documentation for $file including:
    - Module overview
    - Function descriptions
    - Usage examples
    - Parameter explanations
    "
done
```

## Tips & Tricks

### Performance Optimization

1. Proper Priority Settings  
   - Emergency tasks: 8-10  
   - Normal tasks: 4-7  
   - Background: 1-3  

2. Splitting Tasks  
   - Split large tasks into smaller ones  
   - Identify parts that can be processed in parallel  

3. Model Selection  
   - Simple tasks: lightweight models  
   - Complex tasks: large models  

### Error Handling

```python
def submit_task_with_retry(task_data, max_retries=3):
    for i in range(max_retries):
        try:
            response = requests.post(
                'http://localhost:8765/task/delegate',
                json=task_data,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            time.sleep(2 ** i)  # Exponential backoff
    return None
```

### Custom Workflow

```python
class TaskPipeline:
    def __init__(self):
        self.base_url = 'http://localhost:8765'
    
    def create_and_test(self, module_name):
        # Task submission
        code_task = self.submit_task({
            'type': 'code',
            'prompt': f'Create {module_name}.py with basic functionality',
            'priority': 8,
            'sync': True
        })
        
        # Test creation
        test_task = self.submit_task({
            'type': 'code',
            'prompt': f'Create test_{module_name}.py with pytest',
            'priority': 7,
            'sync': True
        })
        
        # Documentation generation
        doc_task = self.submit_task({
            'type': 'general',
            'prompt': f'Generate README for {module_name}',
            'priority': 5,
            'sync': True
        })
        
        return code_task, test_task, doc_task
    
    def submit_task(self, task_data):
        response = requests.post(
            f'{self.base_url}/task/delegate',
            json=task_data
        )
        return response.json()
```

## Next Steps

- [API Specification](../api/MCP_SERVER_API.md) - API details
- [Troubleshooting](../operations/TROUBLESHOOTING.md) - Problem solving
- [Performance Tuning](../operations/PERFORMANCE.md) - Optimization

---
Last updated: 2025-08-29  
Version: 1.0.0