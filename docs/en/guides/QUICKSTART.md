# Koubou System Quick Start Guide

## 🚀 Get Started with Koubou System in 5 Minutes

This guide explains how to quickly set up and verify the operation of the AI agent collaboration system "Koubou System".

---

## 📋 Prerequisites

Please ensure the following software is installed:

- **Linux/WSL2 environment** (Ubuntu 20.04 or later recommended)
- **Python 3.8 or higher**
- **SQLite3**
- **LMStudio** (for gpt-oss-20b model)
- **Claude Code** (for Master Agent)

### Required Package Installation

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip sqlite3 jq inotify-tools

# Python packages
pip3 install requests pyyaml flask
```

---

## 🛠️ Setup (3 Steps)

### Step 1: Repository Clone and Initial Setup

```bash
# Clone repository (or extract)
cd ~
git clone https://github.com/your-repo/koubou-system.git
cd koubou-system

# Grant execution permission to setup script
chmod +x scripts/setup_all.sh

# Run complete setup
./scripts/setup_all.sh
```

The setup script automatically performs:
- ✅ Directory structure creation
- ✅ Database initialization
- ✅ Configuration file placement
- ✅ Required script copying

### Step 2: LMStudio Preparation

1. **Launch LMStudio**
2. **Load gpt-oss-20b model**
3. **Start in server mode** (port 1234)

```bash
# Verify LMStudio connection
/var/koubou/scripts/check_lmstudio.sh
```

On success, you'll see:
```
✓ Successfully connected to LMStudio
✓ gpt-oss-20b model is available
```

### Step 3: System Startup

```bash
# Start the system
cd /var/koubou/scripts
./start_system.sh
```

Startup message:
```
===================================
Koubou System v2.0 Starting
===================================
Master Agent: claude-code
Starting local craftsmen...
  Worker #1 started (PID: 12345)
  Worker #2 started (PID: 12346)
System startup complete
```

---

## 🎯 Verification

### Method 1: Direct Command Line Testing

```bash
# Create test task
sqlite3 /var/koubou/db/koubou.db << EOF
INSERT INTO task_master (task_id, content, task_type, priority, status)
VALUES ('test_001', 'Write a Python hello world program', 'code_generation', 5, 'pending');
EOF

# Check task status (wait a few seconds)
sqlite3 /var/koubou/db/koubou.db "SELECT task_id, status FROM task_master WHERE task_id = 'test_001';"

# Check completed task results
cat /var/koubou/tasks/completed/test_001.json | jq -r '.content'
```

### Method 2: Using Claude Code

You can use the following MCP tools in Claude Code:

1. **Delegate Task**
```
Use the koubou_delegate_task tool to delegate
"Create a Python function to calculate factorial" 
task.
```

2. **Check Status**
```
Use koubou_get_task_status tool to check
the status of the returned task_id.
```

3. **List Tasks**
```
Use koubou_list_tasks tool to check
the current task list.
```

---

## 📊 System Monitoring

### Real-time Log Monitoring

```bash
# Monitor worker logs
tail -f /var/koubou/logs/workers/worker_1.log

# Monitor system monitor logs
tail -f /var/koubou/logs/system/monitor.log
```

### Database Status Check

```bash
# Worker status
sqlite3 -header -column /var/koubou/db/koubou.db \
  "SELECT worker_id, status, model_name FROM workers;"

# Task statistics
sqlite3 -header -column /var/koubou/db/koubou.db \
  "SELECT status, COUNT(*) as count FROM task_master GROUP BY status;"
```

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. Cannot Connect to LMStudio
```bash
# Check port
netstat -tln | grep 1234

# Solutions
- Verify LMStudio is running
- Verify model is loaded
- Check firewall settings
```

#### 2. Workers Not Processing Tasks
```bash
# Check worker processes
ps aux | grep local_worker

# Check database
sqlite3 /var/koubou/db/koubou.db "SELECT * FROM workers;"

# Solutions
- Check worker logs for errors
- Verify database permissions (chmod 666)
```

#### 3. Permission Errors
```bash
# Fix permissions
sudo chown -R $USER:$USER /var/koubou
chmod 755 /var/koubou
chmod 666 /var/koubou/db/koubou.db
```

---

## 🛑 System Shutdown

```bash
# Stop system with Ctrl+C
# Or from another terminal
pkill -f start_system.sh
pkill -f local_worker.py

# Complete cleanup
sqlite3 /var/koubou/db/koubou.db "UPDATE workers SET status = 'offline';"
```

---

## 📚 Next Steps

### Once You've Mastered the Basics

1. **Configuration Customization**
   - Edit `/var/koubou/config/agent.yaml`
   - Adjust worker count and priority rules

2. **Advanced Features**
   - Parallel processing of multiple tasks
   - Utilizing task priorities
   - Adding custom task types

3. **System Extensions**
   - Adding new agent adapters
   - Integrating cloud LLM workers
   - Enabling web dashboard

### Detailed Documentation

- [Requirements Document](01_requirements.md) - Detailed system requirements
- [Design Document](02_design_v2.md) - Architecture and design details
- [Implementation Guide](03_implementation_guide_v2.md) - Complete implementation guide

---

## 💡 Tips & Tricks

### Performance Optimization
```bash
# Increase worker count
# Edit /var/koubou/config/agent.yaml
workers:
  local:
    max_concurrent: 5  # Increase from 3 to 5
```

### Debug Mode
```bash
# Enable debug with environment variable
export KOUBOU_LOG_LEVEL=DEBUG
./start_system.sh
```

### Backup
```bash
# Database backup
cp /var/koubou/db/koubou.db /var/koubou/db/koubou.db.backup

# Complete backup
tar -czf koubou-backup-$(date +%Y%m%d).tar.gz /var/koubou
```

---

## 🆘 Support

If issues persist:

1. **Check log files**
   - All logs under `/var/koubou/logs/`
   
2. **Generate system status report**
   ```bash
   /var/koubou/scripts/system_report.sh > report.txt
   ```

3. **Create Issue**
   - Create an Issue in the GitHub repository
   - Attach `report.txt`

---

## 📜 License

This project is released under the MIT License.

---

## 🎉 Ready!

You've now completed the basic setup of the Koubou System.
Your AI agents and craftsmen are ready to efficiently process your tasks!

Happy Coding with AI Agents! 🤖✨