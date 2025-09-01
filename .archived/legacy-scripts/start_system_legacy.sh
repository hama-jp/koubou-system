#!/bin/bash
# 工房システム起動スクリプト v3.0 - GraphQL API対応

KOUBOU_HOME="$(cd "$(dirname "$0")" && pwd)"
export KOUBOU_HOME
source "$KOUBOU_HOME/config/.env"

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo "======================================"
echo "     工房システム 起動"
echo "======================================"

# Ollamaサーバー確認
echo -n "1. Checking Ollama server... "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}Starting...${NC}"
    OLLAMA_NUM_GPU=999 OLLAMA_GPU_LAYERS=999 ollama serve > "$KOUBOU_HOME/logs/ollama.log" 2>&1 &
    sleep 3
fi

# Python環境をアクティベート
source "$KOUBOU_HOME/venv/bin/activate"

# MCPサーバー起動
echo -n "2. Starting MCP server... "
# ポートが使用中の場合はプロセスを停止
if lsof -ti:8765 > /dev/null 2>&1; then
    echo -n "(stopping existing process) "
    lsof -ti:8765 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

"$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/mcp_server.py" > "$KOUBOU_HOME/logs/mcp_server.log" 2>&1 &
MCP_PID=$!
sleep 3  # より安定した起動を待つ

if kill -0 $MCP_PID 2>/dev/null && curl -s http://localhost:8765/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} (PID: $MCP_PID)"
else
    echo -e "${RED}Failed${NC}"
    echo "Check logs: $KOUBOU_HOME/logs/mcp_server.log"
    exit 1
fi

# ワーカープールマネージャー起動
echo -n "3. Starting Worker Pool Manager... "
"$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/workers/worker_pool_manager.py" --min 1 --max 3 > "$KOUBOU_HOME/logs/worker_pool.log" 2>&1 &
POOL_PID=$!
sleep 2

if kill -0 $POOL_PID 2>/dev/null; then
    echo -e "${GREEN}✓${NC} (PID: $POOL_PID)"
else
    echo -e "${RED}Failed${NC}"
    kill $MCP_PID
    exit 1
fi

# WebSocketサーバー起動
WS_PID=""
echo -n "4. Starting WebSocket server... "
if "$KOUBOU_HOME/venv/bin/python" -c "import websockets" 2>/dev/null; then
    # ポートが使用中の場合はプロセスを停止
    if lsof -ti:8766 > /dev/null 2>&1; then
        lsof -ti:8766 | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
    
    "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/websocket_server.py" > "$KOUBOU_HOME/logs/websocket.log" 2>&1 &
    WS_PID=$!
    sleep 3  # より安定した起動を待つ
    
    if kill -0 $WS_PID 2>/dev/null; then
        echo -e "${GREEN}✓${NC} (PID: $WS_PID)"
    else
        echo -e "${YELLOW}Failed${NC}"
        echo "Check logs: $KOUBOU_HOME/logs/websocket.log"
        WS_PID=""
    fi
else
    echo -e "${YELLOW}Skipped${NC} (websockets not installed)"
    echo "   Install with: uv pip install websockets"
fi

# GraphQL APIサーバー起動
GQL_PID=""
echo -n "5. Starting GraphQL API server... "
if "$KOUBOU_HOME/venv/bin/python" -c "import ariadne" 2>/dev/null; then
    "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/graphql_server.py" > "$KOUBOU_HOME/logs/graphql.log" 2>&1 &
    GQL_PID=$!
    sleep 2
    
    if kill -0 $GQL_PID 2>/dev/null; then
        echo -e "${GREEN}✓${NC} (PID: $GQL_PID)"
    else
        echo -e "${YELLOW}Failed${NC}"
        echo "   Check if ariadne is installed: uv pip install ariadne flask-cors"
        GQL_PID=""
    fi
else
    echo -e "${YELLOW}Skipped${NC} (ariadne not installed)"
    echo "   Install with: uv pip install ariadne flask-cors"
fi

# Webダッシュボード起動
DASH_PID=""
echo -n "6. Starting Web Dashboard... "
if [ -f "$KOUBOU_HOME/dashboard/index.html" ]; then
    # ポートが使用中の場合はプロセスを停止
    if lsof -ti:8080 > /dev/null 2>&1; then
        lsof -ti:8080 | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
    
    cd "$KOUBOU_HOME/dashboard"
    python3 -m http.server 8080 > "$KOUBOU_HOME/logs/dashboard.log" 2>&1 &
    DASH_PID=$!
    cd - > /dev/null
    sleep 2  # より安定した起動を待つ
    
    if kill -0 $DASH_PID 2>/dev/null && curl -s -I http://localhost:8080 > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} (PID: $DASH_PID)"
    else
        echo -e "${YELLOW}Failed${NC}"
        echo "Check logs: $KOUBOU_HOME/logs/dashboard.log"
        DASH_PID=""
    fi
else
    echo -e "${YELLOW}Skipped${NC} (dashboard not found)"
fi

# 親方通知リスナー起動
NOTIF_PID=""
echo -n "7. Starting Master Notification Listener... "
if [ -f "$KOUBOU_HOME/scripts/master_notification_listener.py" ]; then
    "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/master_notification_listener.py" > "$KOUBOU_HOME/logs/master_notifications.log" 2>&1 &
    NOTIF_PID=$!
    sleep 2
    
    if kill -0 $NOTIF_PID 2>/dev/null; then
        echo -e "${GREEN}✓${NC} (PID: $NOTIF_PID)"
    else
        echo -e "${YELLOW}Failed${NC}"
        echo "   Check logs: $KOUBOU_HOME/logs/master_notifications.log"
        NOTIF_PID=""
    fi
else
    echo -e "${YELLOW}Skipped${NC} (notification listener not found)"
fi

# PIDファイルを保存
echo $MCP_PID > "$KOUBOU_HOME/mcp.pid"
echo $POOL_PID > "$KOUBOU_HOME/pool.pid"
[ ! -z "$WS_PID" ] && echo $WS_PID > "$KOUBOU_HOME/websocket.pid"
[ ! -z "$GQL_PID" ] && echo $GQL_PID > "$KOUBOU_HOME/graphql.pid"
[ ! -z "$DASH_PID" ] && echo $DASH_PID > "$KOUBOU_HOME/dashboard.pid"
[ ! -z "$NOTIF_PID" ] && echo $NOTIF_PID > "$KOUBOU_HOME/notifications.pid"

echo ""
echo "======================================"
echo -e "${GREEN}システム起動完了!${NC}"
echo "======================================"
echo ""
echo "Services:"
echo "  • MCP Server:    http://localhost:8765 (PID: $MCP_PID)"
echo "  • Worker Pool:   1-3 workers (PID: $POOL_PID)"
[ ! -z "$WS_PID" ] && echo "  • WebSocket:     ws://localhost:8766 (PID: $WS_PID)"
[ ! -z "$GQL_PID" ] && echo "  • GraphQL API:   http://localhost:8767/graphql (PID: $GQL_PID)"
[ ! -z "$DASH_PID" ] && echo "  • Dashboard:     http://localhost:8080 (PID: $DASH_PID)"
echo "  • Logs:          $KOUBOU_HOME/logs/"
echo ""
echo "Quick Access:"
[ ! -z "$DASH_PID" ] && echo -e "  ${BLUE}📊 Dashboard:${NC}     http://localhost:8080"
[ ! -z "$GQL_PID" ] && echo -e "  ${MAGENTA}🎮 GraphQL IDE:${NC}   http://localhost:8767/graphql"
echo ""
echo "Test Commands:"
echo "  • Health Check:  curl http://localhost:8765/health"
[ ! -z "$WS_PID" ] && echo "  • WebSocket:     $KOUBOU_HOME/venv/bin/python $KOUBOU_HOME/scripts/test_websocket.py"
[ ! -z "$GQL_PID" ] && echo "  • GraphQL:       $KOUBOU_HOME/venv/bin/python $KOUBOU_HOME/scripts/test_graphql.py"
echo "  • Load Test:     $KOUBOU_HOME/venv/bin/python $KOUBOU_HOME/scripts/load_test.py"
echo "  • Worker Test:   WORKER_ID=test_worker .koubou/venv/bin/python .koubou/scripts/workers/local_worker.py"
echo "  • Quick Task:    curl -X POST http://localhost:8765/task/delegate -H 'Content-Type: application/json' -d '{\"type\":\"general\",\"prompt\":\"Hello\",\"sync\":false}'"
echo ""
echo "Press Ctrl+C to stop all services"

# シグナルハンドリング
trap 'echo "Stopping..."; kill $MCP_PID $POOL_PID $WS_PID $GQL_PID $DASH_PID 2>/dev/null; exit' INT TERM

# プロセス監視
while true; do
    if ! kill -0 $MCP_PID 2>/dev/null; then
        echo -e "${RED}MCP Server stopped${NC}"
        kill $POOL_PID $WS_PID $GQL_PID $DASH_PID 2>/dev/null
        exit 1
    fi
    if ! kill -0 $POOL_PID 2>/dev/null; then
        echo -e "${RED}Worker Pool stopped${NC}"
        kill $MCP_PID $WS_PID $GQL_PID $DASH_PID 2>/dev/null
        exit 1
    fi
    sleep 5
done