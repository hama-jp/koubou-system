#!/bin/bash
# 🏭 工房システム停止スクリプト

KOUBOU_HOME="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$KOUBOU_HOME/pids"

echo "🛑 Stopping Koubou System..."

# PIDファイルから各サービスを停止
if [ -d "$PID_DIR" ]; then
    for pidfile in "$PID_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            SERVICE=$(basename "$pidfile" .pid)
            PID=$(cat "$pidfile")
            if kill -0 $PID 2>/dev/null; then
                echo "  Stopping $SERVICE (PID: $PID)..."
                kill $PID
            fi
            rm "$pidfile"
        fi
    done
fi

# プロセス名で残っているプロセスを停止
echo "  Cleaning up remaining processes..."
pkill -f "mcp_server.py" 2>/dev/null || true
pkill -f "local_worker.py" 2>/dev/null || true
pkill -f "enhanced_worker.py" 2>/dev/null || true
pkill -f "websocket_server.py" 2>/dev/null || true
pkill -f "worker_pool_manager.py" 2>/dev/null || true
pkill -f "enhanced_pool_manager.py" 2>/dev/null || true
pkill -f "remote_worker.py" 2>/dev/null || true
pkill -f "graphql_server.py" 2>/dev/null || true
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "worker_log_api.py" 2>/dev/null || true

# Ollamaサービスは他のアプリケーションも使用する可能性があるのでそのまま残す
echo "  Note: Ollama service is kept running for other applications"

echo "✅ System stopped."