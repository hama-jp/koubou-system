# Installation Guide

## Prerequisites

### Mandatory Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended) / macOS / WSL2  
- **Python**: 3.9 or newer  
- **Memory**: Minimum 4 GB, recommended 8 GB or more  
- **Disk Space**: At least 10 GB of free space  

### Required Software
```bash
# Verification commands
python3 --version   # Python 3.9+
sqlite3 --version   # SQLite 3.x
npm --version       # Node.js/npm (for Codex CLI)
```

## Installation Steps

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/koubou-system.git
cd koubou-system
```

### 2. Install uv
```bash
# If uv is not present
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
```

### 3. Install Ollama
```bash
# Linux/WSL
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Start the server
ollama serve
```

### 4. Download the Model
```bash
# Download the gpt-oss:20b model (≈13 GB)
ollama pull gpt-oss:20b

# Verify
ollama list
```

### 5. Install Codex CLI
```bash
# Install via npm
npm install -g @openai/codex

# Verify
codex --version
```

### 6. Set Up the Koubou System
```bash
# Run the POC setup script
chmod +x scripts/setup_poc.sh
./scripts/setup_poc.sh
```
The setup script performs the following:
- Creates the `.koubou/` directory structure  
- Sets up a Python virtual environment (using uv)  
- Installs required Python packages  
- Initializes the SQLite database  
- Generates configuration files  

## Configuration

### 1. LMStudio Settings (Ollama Alternative)
Edit `.koubou/config/agent.yaml`:
```yaml
workers:
  local:
    endpoint: "http://192.168.11.29:1234/v1"  # LMStudio endpoint
    model: "gpt-oss-20b@f16"                  # Model identifier
```

### 2. Environment Variables
Edit `.koubou/config/.env`:
```bash
KOUBOU_HOME=/path/to/koubou-system/.koubou
LMSTUDIO_ENDPOINT=http://localhost:1234/v1
OLLAMA_NUM_GPU=999  # Max GPU usage
```

### 3. Codex CLI Settings
Edit `.koubou/config/codex.toml`:
```toml
model = "gpt-oss:20b"
sandbox_mode = "workspace-write"
approval_policy = "never"
```

## Verification

### 1. Basic Test
```bash
# MCP server test
source .koubou/venv/bin/activate
python .koubou/scripts/test_integration.py
```

### 2. Codex CLI Test
```bash
# Verify connection to Ollama
.koubou/scripts/test-codex.sh

# Run a simple task
.koubou/scripts/codex-ollama.sh exec "Write a hello world in Python"
```

### 3. End‑to‑End System Test
```bash
# Start the system
.koubou/start_system.sh

# In a separate terminal, run a load test
python .koubou/scripts/load_test.py

# Stop the system
.koubou/stop_system.sh
```

## Troubleshooting

### Ollama Does Not Start
```bash
# Check service status
systemctl status ollama

# Start manually
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Codex CLI Cannot Write
```bash
# Set the unsafe environment variable
export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1

# Run in dangerous mode
codex --dangerously-bypass-approvals-and-sandbox
```

### Database Errors
```bash
# Repair the database
sqlite3 .koubou/db/koubou.db "VACUUM;"
sqlite3 .koubou/db/koubou.db "REINDEX;"

# Re‑initialize
rm .koubou/db/koubou.db
sqlite3 .koubou/db/koubou.db < scripts/init_database.sql
```

### Insufficient Memory
```bash
# Limit the number of workers
python .koubou/scripts/workers/worker_pool_manager.py --max 2

# Switch to a lighter model
ollama pull gemma2:2b
# Update agent.yaml with the new model
```

## Uninstall

### Complete Removal
```bash
# Remove the Koubou System
./cleanup.sh

# Delete Ollama models
ollama rm gpt-oss:20b

# Uninstall Codex CLI
npm uninstall -g @openai/codex
```

### Partial Removal
```bash
# Delete only data (preserve configuration)
rm -rf .koubou/db/* .koubou/logs/* .koubou/tasks/*

# Delete only logs
rm -rf .koubou/logs/*
```

## Next Steps

- [User Guide](./USAGE.md) – Learn the basic usage  
- [API Specification](../api/MCP_SERVER_API.md) – Review API details  
- [System Management](../operations/SYSTEM_MANAGEMENT.md) – Learn operational procedures  

---
Last updated: 2025‑08‑29  
Version: 1.0.0
