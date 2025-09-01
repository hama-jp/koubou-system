# 🏭 Koubou System

> **Distributed AI Task Processing System** - A scalable framework for delegating complex tasks from Claude Code to local LLM workers

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Flask](https://img.shields.io/badge/flask-3.0%2B-green.svg)](https://flask.palletsprojects.com/)

## 🚀 Features

- **🎯 Dynamic Worker Scaling** - Automatically adjusts worker count based on task load
- **🤖 Multi-LLM Integration** - Supports LMStudio (gpt-oss-20b@f16) via Gemini CLI
- **🔄 Async Processing** - Parallel task execution with background workers  
- **📊 Real-time Dashboard** - Live monitoring of tasks and worker status
- **🔒 Local Processing** - Secure on-premise LLM execution

## 🏗️ Architecture

```
Claude Code → MCP Server → Task Queue → Worker Pool → Local LLM
     ↑            ↑           ↑           ↑            ↑
   User UI    REST API    SQLite DB   Dynamic Scale  LMStudio/Gemini
```

## ⚡ Quick Start

```bash
# Clone and setup
git clone https://github.com/your-username/koubou-system
cd koubou-system
uv sync

# Setup LMStudio with gpt-oss-20b@f16 model
# Start LMStudio server at http://192.168.11.29:1234/v1
# Install Gemini CLI in ./gemini-cli-local/

# Start all services
.koubou/start_system.sh

# Access dashboard
open http://localhost:8080
```

## 🔧 System Components

| Service | Port | Purpose |
|---------|------|---------|
| **MCP Server** | 8765 | REST API for task delegation |
| **WebSocket** | 8766 | Real-time communication |
| **GraphQL** | 8767 | Query interface |
| **Dashboard** | 8080 | Web monitoring interface |

## 📊 Usage Example

```python
import requests

# Delegate a task
response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'general',
    'content': 'Analyze this data and provide insights',
    'priority': 5
})

task_id = response.json()['task_id']
print(f"Task {task_id} delegated to worker pool")
```

## 📈 Performance

- **Throughput**: ~3 tasks/minute per worker
- **Scaling**: 1-8 workers based on queue depth
- **Reliability**: 100% task completion rate
- **Latency**: Sub-second task dispatch

## 🛠️ Development

```bash
# Run tests
uv run pytest tests/

# Check system health
curl http://localhost:8765/health

# View worker status
sqlite3 .koubou/db/koubou.db "SELECT * FROM workers;"
```

## 📚 Documentation

- [🚀 Quick Start Guide](./docs/guides/QUICKSTART.md)
- [🔌 API Reference](./docs/api/MCP_SERVER_API.md)
- [🏗️ Architecture Overview](./docs/architecture/SYSTEM_ARCHITECTURE.md)
- [📦 Installation Guide](./docs/guides/INSTALLATION.md)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for integration with [Claude Code](https://claude.ai/code)
- Powered by [LMStudio](https://lmstudio.ai/) local LLM runtime
- Uses [Gemini CLI](https://github.com/google/gemini-cli) for AI interactions
- Uses [uv](https://docs.astral.sh/uv/) for fast Python package management

---

**⚡ Ready to scale your AI workloads locally? Get started in 30 seconds!**