# Dynamic Worker Scaling System

## Overview

The **Koubou System**’s Dynamic Worker Scaling System automatically adjusts the number of workers (artisan agents) according to task load. When tasks increase, new workers are launched; when tasks decrease, unnecessary workers are stopped, achieving efficient resource utilization.

## Architecture

```
┌─────────────────┐
│  Claude Code    │
│ (Main Agent) │
└────────┬────────┘
         │ Task delegation
         ▼
┌─────────────────┐
│   MCP Server    │
│   (Flask API)   │
└────────┬────────┘
         │ Task registration
         ▼
┌─────────────────┐      ┌──────────────┐
│   Task Queue    │◀────▶│   Database   │
│   (SQLite)      │      │   (SQLite)   │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────────────────────┐
│    Worker Pool Manager          │
│  (Dynamic Scaling Controller)    │
└────────┬────────────────────────┘
         │ Management & Monitoring
         ▼
┌──────────────────────────────────────┐
│          Worker Pool                 │
│  ┌──────────┐  ┌──────────┐        │
│  │ Worker 1 │  │ Worker 2 │  ...   │
│  └──────────┘  └──────────┘        │
│       ▼              ▼              │
│  [ Ollama / Codex CLI ]             │
└──────────────────────────────────────┘
```

## Component Details

### 1. Worker Pool Manager (`worker_pool_manager.py`)

**Primary Functions:**
- Lifecycle management of workers (start, stop, monitor)
- Automatic scaling based on load
- Health checks and crash recovery
- Collection and display of statistics

**Configuration Parameters:**
```python
min_workers = 1    # Minimum number of workers
max_workers = 5    # Maximum number of workers
scale_up_threshold = 2    # Threshold for adding a worker (pending_tasks / active_workers)
idle_timeout = 30  # Idle timeout in seconds
```

### 2. Local Worker (`local_worker.py`)

**Functions:**
- Fetch tasks from the task queue
- Dispatch processing based on task type:
  - `code`: Process via Codex CLI
  - `general`: Process directly via Ollama
- Update the database with results
- Send heartbeats

**Environment Variables:**
```bash
WORKER_ID=worker_20250829_123456  # Worker identifier
KOUBOU_HOME=/path/to/.koubou      # Koubou home directory
```

### 3. MCP Server (`mcp_server.py`)

**Endpoints:**

| Endpoint                | Method | Description           |
|-------------------------|--------|-----------------------|
| `/health`               | GET    | Health check          |
| `/task/delegate`        | POST   | Task delegation       |
| `/task/<id>/status`     | GET    | Get task status       |
| `/tasks`                | GET    | List all tasks        |

**Sample Task Delegation Request:**
```json
{
  "type": "code",
  "prompt": "Create a Python function...",
  "priority": 8,
  "sync": false
}
```

## Scaling Algorithm

### Scale‑Up Condition
```python
if pending_tasks > active_workers * 2 and active_workers < max_workers:
    # Launch a new worker
    spawn_worker()
```

### Scale‑Down Condition
```python
if pending_tasks == 0 and active_workers > min_workers:
    # Shut down idle workers
    shutdown_idle_workers()
```

### Worker Selection Strategy
1. **Task Retrieval**: Process tasks with the highest priority and oldest creation time first.
2. **Worker Assignment**: Prefer idle workers for assignment.
3. **Load Balancing**: Each worker independently pulls tasks (pull‑based).

## Usage

### System Startup

```bash
# Start all components
.koubou/start_system.sh

# Custom configuration
python .koubou/scripts/workers/worker_pool_manager.py --min 2 --max 10
```

### Load Testing

```bash
# Interactive load test
python .koubou/scripts/load_test.py

# Programmatic usage
import requests

# Submit a task
response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'code',
    'prompt': 'Write a function...',
    'priority': 8,
    'sync': False
})

task_id = response.json()['task_id']

# Check status
status = requests.get(f'http://localhost:8765/task/{task_id}/status')
print(status.json())
```

### System Shutdown

```bash
# Graceful shutdown
.koubou/stop_system.sh

# Emergency shutdown
pkill -f "worker_pool_manager"
pkill -f "local_worker"
```

## Monitoring

### Log Files
```
.koubou/logs/
├── mcp_server.log      # MCP server logs
├── worker_pool.log     # Pool manager logs
├── ollama.log          # Ollama server logs
└── workers/
    ├── worker_001.log  # Individual worker logs
    └── worker_002.log
```

### Database Statistics
```sql
-- View active workers
SELECT worker_id, status, tasks_completed, tasks_failed 
FROM workers 
WHERE last_heartbeat > datetime('now', '-1 minute');

-- Task statistics
SELECT status, COUNT(*) as count 
FROM task_master 
GROUP BY status;

-- Average processing time
SELECT AVG(julianday(updated_at) - julianday(created_at)) * 24 * 60 as avg_minutes
FROM task_master 
WHERE status = 'completed';
```

### Real‑Time Statistics

The Worker Pool Manager prints statistics every 30 seconds:

```
====================================================
Worker Pool Statistics
====================================================

Active Workers:
  • worker_001: busy | Tasks: 5 completed, 0 failed (100.0% success)
  • worker_002: idle | Tasks: 3 completed, 1 failed (75.0% success)
  • worker_003: busy | Tasks: 2 completed, 0 failed (100.0% success)

Task Statistics:
  • pending: 8 tasks
  • in_progress: 3 tasks
  • completed: 45 tasks
  • failed: 2 tasks
====================================================
```

## Performance Optimization

### Recommended Settings

| Task Characteristic | `min_workers` | `max_workers` | Notes                     |
|---------------------|---------------|---------------|---------------------------|
| Light & High‑Frequency | 2 | 8 | Focus on responsiveness |
| Heavy & Low‑Frequency  | 1 | 3 | Focus on resource efficiency |
| Burst‑Type            | 1 | 10 | Handle sudden load spikes |
| Steady Load           | 3 | 5 | Focus on stability |

### Tuning Points

1. **Ollama Memory Usage**
   - Each worker runs an independent Ollama instance.
   - Monitor GPU memory (model size × number of workers).

2. **Database Connections**
   - SQLite limits concurrent writes.
   - Consider migrating to PostgreSQL if needed.

3. **Task Timeout**
   - Code tasks: 120 s
   - General tasks: 60 s
   - Long tasks should be split.

## Troubleshooting

### Worker Fails to Start
```bash
# Check Ollama server
curl http://localhost:11434/api/tags

# Verify database
sqlite3 .koubou/db/koubou.db "SELECT * FROM workers;"

# Inspect logs
tail -f .koubou/logs/worker_pool.log
```

### Task Not Being Processed
```bash
# Check pending tasks
sqlite3 .koubou/db/koubou.db "SELECT * FROM task_master WHERE status='pending';"

# Verify worker status
curl http://localhost:8765/tasks
```

### Memory Exhaustion
```bash
# Limit number of workers
python .koubou/scripts/workers/worker_pool_manager.py --max 3

# Switch to a lighter model
# Edit `self.model` in local_worker.py
```

## Future Enhancements

1. **Priority‑Based Queuing**
   - Current: FIFO
   - Plan: Implement priority queue

2. **Distributed Worker Support**
   - Current: Local only
   - Plan: Support remote workers

3. **WebSocket Real‑Time Notifications**
   - Current: Polling
   - Plan: Push notifications

4. **Metrics Collection**
   - Integrate Prometheus/Grafana for detailed performance analysis

5. **Enhanced Fault Recovery**
   - Retry mechanism for tasks
   - Automatic worker recovery

## Summary

The Dynamic Worker Scaling System enables the Koubou System to automatically adjust resources based on workload, efficiently processing tasks with minimal resource usage. Starting with a minimal footprint and scaling up as needed preserves a balance between cost and performance.