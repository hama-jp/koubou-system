#!/bin/bash

# 🏭 工房システム統合起動スクリプト
# リモートワーカー対応版

KOUBOU_HOME="$(cd "$(dirname "$0")" && pwd)"
export KOUBOU_HOME

echo "🏭 Starting Koubou Integrated System..."
echo "=================================="

# ログディレクトリ作成
mkdir -p "$KOUBOU_HOME/logs/workers"
mkdir -p "$KOUBOU_HOME/logs/api"
mkdir -p "$KOUBOU_HOME/dashboard"

# 1. Enhanced Worker Pool Manager起動
echo "🔧 Starting Enhanced Worker Pool Manager..."
cd "$KOUBOU_HOME/.."
uv run python "$KOUBOU_HOME/scripts/workers/enhanced_pool_manager.py" > "$KOUBOU_HOME/logs/pool_manager.log" 2>&1 &
POOL_PID=$!
echo "  Pool Manager PID: $POOL_PID"

# 少し待つ
sleep 3

# 2. Worker Log API起動
echo "📡 Starting Worker Log API..."
uv run python "$KOUBOU_HOME/scripts/api/worker_log_api.py" > "$KOUBOU_HOME/logs/api/log_api.log" 2>&1 &
API_PID=$!
echo "  Log API PID: $API_PID (port 8768)"

# 3. Dashboard HTTP Server起動
echo "🖥️ Starting Dashboard..."
cd "$KOUBOU_HOME/dashboard"
python3 -m http.server 8080 > /dev/null 2>&1 &
DASH_PID=$!
echo "  Dashboard PID: $DASH_PID (port 8080)"

# 4. MCP Server起動（必要に応じて）
echo "🔌 Starting MCP Server..."
cd "$KOUBOU_HOME/.."
uv run python "$KOUBOU_HOME/scripts/api/mcp_server.py" > "$KOUBOU_HOME/logs/api/mcp_server.log" 2>&1 &
MCP_PID=$!
echo "  MCP Server PID: $MCP_PID (port 8765)"

echo ""
echo "✅ System Started Successfully!"
echo "=================================="
echo ""
echo "📊 Access Points:"
echo "  Dashboard: http://localhost:8080/"
echo "  Log API:   http://localhost:8768/api/logs/recent"
echo "  MCP API:   http://localhost:8765/health"
echo ""
echo "📋 Process PIDs:"
echo "  Pool Manager: $POOL_PID"
echo "  Log API:      $API_PID"
echo "  Dashboard:    $DASH_PID"
echo "  MCP Server:   $MCP_PID"
echo ""
echo "💡 Tips:"
echo "  - View logs: tail -f $KOUBOU_HOME/logs/*.log"
echo "  - Stop system: kill $POOL_PID $API_PID $DASH_PID $MCP_PID"
echo "  - Or use: $KOUBOU_HOME/stop_system.sh"
echo ""

# PIDファイルに保存
echo "$POOL_PID" > "$KOUBOU_HOME/pool_manager.pid"
echo "$API_PID" > "$KOUBOU_HOME/log_api.pid"
echo "$DASH_PID" > "$KOUBOU_HOME/dashboard.pid"
echo "$MCP_PID" > "$KOUBOU_HOME/mcp_server.pid"

# プロセス監視（オプション）
echo "Press Ctrl+C to stop all services..."
trap "echo 'Stopping...'; kill $POOL_PID $API_PID $DASH_PID $MCP_PID 2>/dev/null; exit" INT

# 待機
wait