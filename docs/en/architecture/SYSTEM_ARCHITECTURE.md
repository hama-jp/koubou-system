# Koubou System Architecture Document

## System Overview

The Koubou System is a distributed task processing system designed to delegate complex tasks from Claude Code (Master Agent) to local LLMs (Ollama/Codex CLI) for efficient processing.

## Key Concepts

### 1. Task Delegation Pattern
```
High-cost tasks → Local LLM
Simple decisions → Claude Code
Code generation → Codex CLI → Ollama
General queries → Ollama direct
```

### 2. Asynchronous Processing
- Background parallel processing
- Concurrent execution by multiple workers
- Load balancing through task queuing

### 3. Dynamic Scaling
- Automatic worker count adjustment based on load
- Efficient resource utilization
- Automatic failure recovery

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                   User Interface                     │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                  Claude Code                         │
│            (Primary AI Assistant)                    │
│  ┌────────────────────────────────────────────┐    │
│  │ MCP Client (Model Context Protocol)         │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP/JSON
┌─────────────────────▼───────────────────────────────┐
│                  MCP Server                          │
│                 (Flask API)                          │
│  ┌──────────────────────────────────────────┐      │
│  │ • Task Router                             │      │
│  │ • Queue Manager                           │      │
│  │ • Result Aggregator                       │      │
│  └──────────────────────────────────────────┘      │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                SQLite Database                       │
│  ┌──────────────────────────────────────────┐      │
│  │ Tables:                                    │      │
│  │ • task_master (Task management)            │      │
│  │ • workers (Worker status)                  │      │
│  │ • agents (Agent registration)              │      │
│  │ • system_logs (Logging)                   │      │
│  │ • agent_communications (Communication log) │      │
│  └──────────────────────────────────────────┘      │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│            Worker Pool Manager                       │
│         (Dynamic Scaling Controller)                 │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│   Worker #1   │           │   Worker #N   │
│               │    ...    │               │
└───────┬───────┘           └───────┬───────┘
        │                           │
        ▼                           ▼
┌───────────────────────────────────────────┐
│           Local LLM Layer                  │
│  ┌─────────────┐    ┌──────────────┐     │
│  │   Ollama    │    │  Codex CLI   │     │
│  │ (gpt-oss:20b)│    │  (via Ollama) │     │
│  └─────────────┘    └──────────────┘     │
└───────────────────────────────────────────┘
```

## Directory Structure

```
koubou-system/
├── .koubou/                    # System home directory
│   ├── config/                 # Configuration files
│   │   ├── agent.yaml         # Agent configuration
│   │   ├── codex.toml         # Codex CLI configuration
│   │   └── .env               # Environment variables
│   ├── db/                    # Database
│   │   └── koubou.db         # SQLite database
│   ├── logs/                  # Log files
│   │   ├── agents/           # Agent logs
│   │   ├── workers/          # Worker logs
│   │   └── system/           # System logs
│   ├── scripts/              # Execution scripts
│   │   ├── mcp_server.py     # MCP server
│   │   ├── workers/          # Worker scripts
│   │   │   ├── local_worker.py
│   │   │   └── worker_pool_manager.py
│   │   ├── codex-*.sh        # Codex wrappers
│   │   └── test_*.py         # Test scripts
│   ├── tasks/                # Task files
│   │   ├── pending/          # Pending
│   │   ├── in_progress/      # In progress
│   │   ├── completed/        # Completed
│   │   └── failed/          # Failed
│   └── venv/                 # Python virtual environment
├── scripts/                   # Setup scripts
│   ├── setup_poc.sh          # POC setup
│   └── init_database.sql     # DB initialization SQL
├── DYNAMIC_SCALING.md        # Scaling documentation
├── SYSTEM_ARCHITECTURE.md    # This file
└── README.md                 # Project overview
```

## API Specification

### MCP Server API

#### POST /task/delegate
Delegate a task

**Request:**
```json
{
  "type": "code|general",
  "prompt": "Task description",
  "priority": 1-10,
  "sync": true|false,
  "files": ["file1.py", "file2.py"],
  "options": {
    "timeout": 120,
    "model": "gpt-oss:20b"
  }
}
```

**Response:**
```json
{
  "task_id": "task_20250829_123456",
  "status": "delegated|completed",
  "result": {
    "success": true,
    "output": "Processing result",
    "error": null
  }
}
```

#### GET /task/{task_id}/status
Get task status

**Response:**
```json
{
  "task_id": "task_20250829_123456",
  "status": "pending|in_progress|completed|failed",
  "result": {...},
  "created_at": "2025-08-29T12:34:56",
  "updated_at": "2025-08-29T12:35:00"
}
```

## Database Schema

### task_master Table
| Column | Type | Description |
|--------|------|-------------|
| task_id | TEXT | Task ID (Primary Key) |
| task_type | TEXT | Task type (code/general) |
| status | TEXT | Status |
| priority | INTEGER | Priority (1-10) |
| content | JSON | Task content |
| result | JSON | Execution result |
| assigned_worker_type | TEXT | Assigned worker |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Update time |

### workers Table
| Column | Type | Description |
|--------|------|-------------|
| worker_id | TEXT | Worker ID (Primary Key) |
| worker_type | TEXT | Worker type |
| model_name | TEXT | Model in use |
| status | TEXT | Status (idle/busy/offline) |
| tasks_completed | INTEGER | Completed tasks count |
| tasks_failed | INTEGER | Failed tasks count |
| last_heartbeat | TIMESTAMP | Last heartbeat |

## Environment Variables

```bash
# Required
KOUBOU_HOME=/path/to/.koubou
OPENAI_API_BASE=http://192.168.11.29:1234/v1

# Optional
WORKER_ID=worker_001
OLLAMA_NUM_GPU=999
OLLAMA_GPU_LAYERS=999
CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
```

## Security Considerations

1. **Sandboxed Execution**
   - Codex CLI operates in `danger-full-access` mode
   - Proper permission restrictions recommended for production

2. **Network Isolation**
   - Currently local network only
   - Proper firewall configuration recommended for production

3. **Authentication & Authorization**
   - Currently no authentication
   - API authentication implementation recommended for production

4. **Data Protection**
   - SQLite is a single file
   - Regular backups recommended

## Performance Metrics

### Processing Capacity
- Concurrent processable tasks: depends on max_workers setting (default 5)
- Task processing time:
  - General tasks: 5-30 seconds
  - Code tasks: 10-120 seconds

### Resource Usage
- Memory: ~2-4GB per worker (depends on model size)
- CPU: 1-2 cores per worker
- GPU: Used during model loading (shareable)

## Operations Guide

### Daily Operations

```bash
# System startup
.koubou/start_system.sh

# Status check
curl http://localhost:8765/health

# Log monitoring
tail -f .koubou/logs/worker_pool.log

# System shutdown
.koubou/stop_system.sh
```

### Backup

```bash
# Database backup
sqlite3 .koubou/db/koubou.db ".backup backup.db"

# Configuration files backup
tar -czf koubou_config_backup.tar.gz .koubou/config/
```

### Incident Response

```bash
# Worker restart
pkill -f local_worker.py
python .koubou/scripts/workers/worker_pool_manager.py

# Database repair
sqlite3 .koubou/db/koubou.db "VACUUM;"
sqlite3 .koubou/db/koubou.db "REINDEX;"

# Log cleanup
find .koubou/logs -name "*.log" -mtime +7 -delete
```

## Limitations and Future Plans

### Current Limitations
- SQLite concurrent write limitations
- Local network only support
- Single-node execution only

### Future Enhancement Plans
- PostgreSQL/MySQL support
- Distributed worker support
- Kubernetes support
- Web management interface
- Metrics dashboard (Grafana)
- Message queue (Redis/RabbitMQ) integration

## License and Contributions

This project is developed as a POC (Proof of Concept).
Please conduct appropriate security reviews and testing before production use.

---
Last updated: 2025-08-29
Version: 1.0.0