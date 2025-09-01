# Koubou System Documentation

## 📚 Documentation Structure

### 🏗️ [Architecture](./architecture/)
- [System Architecture](./architecture/SYSTEM_ARCHITECTURE.md) - Overall system design and components
- [Dynamic Scaling](./architecture/DYNAMIC_SCALING.md) - Automatic worker pool scaling features

### 📖 [Guides](./guides/)
- [Quick Start](./guides/QUICKSTART.md) - Get started with Koubou System in 5 minutes
- [Installation Guide](./guides/INSTALLATION.md) - Detailed setup instructions
- [Usage Guide](./guides/USAGE.md) - Basic usage instructions

### 🔌 [API Specifications](./api/)
- [MCP Server API](./api/MCP_SERVER_API.md) - Task delegation API
- [Worker API](./api/WORKER_API.md) - Worker management API

### ⚙️ [Operations](./operations/)
- [System Management](./operations/SYSTEM_MANAGEMENT.md) - Startup, shutdown, and monitoring
- [Troubleshooting](./operations/TROUBLESHOOTING.md) - Problem solving guide

### 🚀 [Features](./features/)
- [Task Examples](./features/TASK_EXAMPLES.md) - Real-world usage examples
- [GraphQL Implementation](./features/GRAPHQL_IMPLEMENTATION.md) - GraphQL API features
- [WebSocket Features](./features/WEBSOCKET_FEATURES.md) - Real-time communication
- [Dashboard Preview](./features/DASHBOARD_PREVIEW.md) - Web monitoring interface

### 📊 [Development](./development/)
- [Requirements](./development/01_requirements.md) - System requirements and specifications
- [Design Documents](./development/02_design_v2.md) - Technical design details
- [Implementation Guide](./development/03_implementation_guide_v2.md) - Complete implementation guide
- [Roadmap](./development/ROADMAP.md) - Future development plans
- [Extensibility Roadmap](./development/EXTENSIBILITY_ROADMAP.md) - Extension capabilities

### 📋 [Reports](./reports/)
- [Review Report](./reports/review_report.md) - System review and analysis
- [Improvements](./reports/IMPROVEMENTS.md) - Enhancement documentation

## 🌟 What is Koubou System?

Koubou System is a distributed AI task processing system that enables efficient collaboration between Claude Code (Master Agent) and local LLM workers (Craftsmen). It allows you to delegate computationally expensive tasks to local resources while maintaining high-level control and quality assurance.

## 🎯 Key Features

- **Distributed Processing**: Delegate tasks from Claude Code to local LLM workers
- **Real-time Monitoring**: WebSocket-based dashboard for system oversight
- **Flexible API**: REST and GraphQL interfaces for various use cases
- **Scalable Architecture**: Dynamic worker pool management
- **Quality Assurance**: Master-worker delegation pattern with review cycles

## 🚀 Quick Links

- [Get Started in 5 Minutes](./guides/QUICKSTART.md)
- [System Architecture Overview](./architecture/SYSTEM_ARCHITECTURE.md)
- [API Documentation](./api/MCP_SERVER_API.md)
- [Complete Setup Guide](./COMPLETE_GUIDE.md)

---

*For Japanese documentation, see the parent directory.*