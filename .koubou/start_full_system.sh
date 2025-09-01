#!/bin/bash
# 工房システム完全起動スクリプト（全機能統合版）

set -e

echo "======================================"
echo "🏭 工房システム完全版を起動します"
echo "======================================"

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 環境変数設定
export KOUBOU_HOME="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$KOUBOU_HOME/scripts:$PYTHONPATH"
export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# PIDファイル保存先
PID_DIR="$KOUBOU_HOME/pids"
mkdir -p "$PID_DIR"

# ログディレクトリ
LOG_DIR="$KOUBOU_HOME/logs"
mkdir -p "$LOG_DIR"

# プロセスID保存
PIDS=()

# 終了処理
cleanup() {
    echo -e "\n${YELLOW}🛑 システムを停止中...${NC}"
    
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "  Stopped process $pid"
        fi
    done
    
    # PIDファイルクリーンアップ
    rm -f "$PID_DIR"/*.pid
    
    echo -e "${GREEN}✅ システム停止完了${NC}"
    exit 0
}

trap cleanup INT TERM EXIT

# ヘルスチェック関数
check_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=0
    
    echo -n "  Waiting for $service (port $port)..."
    
    while [ $attempt -lt $max_attempts ]; do
        if nc -z localhost "$port" 2>/dev/null; then
            echo -e " ${GREEN}OK${NC}"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
        echo -n "."
    done
    
    echo -e " ${RED}FAILED${NC}"
    return 1
}

# 1. 前提条件チェック
echo -e "\n${BLUE}📋 前提条件をチェック中...${NC}"

# Python仮想環境
if [ ! -f "$KOUBOU_HOME/venv/bin/python" ]; then
    echo -e "${RED}❌ Python仮想環境が見つかりません${NC}"
    echo "  setup_poc_v2.sh を実行してください"
    exit 1
fi

# データベース
if [ ! -f "$KOUBOU_HOME/db/koubou.db" ]; then
    echo -e "${YELLOW}⚠️ データベースが見つかりません。作成中...${NC}"
    cat "$KOUBOU_HOME/../scripts/init_database.sql" | sqlite3 "$KOUBOU_HOME/db/koubou.db"
fi

# Redis（オプション）
USE_DISTRIBUTED=false
if redis-cli ping &>/dev/null; then
    echo -e "${GREEN}✓ Redis稼働中 - 分散機能を有効化${NC}"
    USE_DISTRIBUTED=true
else
    echo -e "${YELLOW}! Redis未起動 - ローカルモードで実行${NC}"
fi

# Ollama（オプション）
if command -v ollama &>/dev/null && ollama list &>/dev/null; then
    echo -e "${GREEN}✓ Ollama利用可能${NC}"
else
    echo -e "${YELLOW}! Ollama未起動 - LLM機能制限あり${NC}"
fi

# 2. コアサービス起動
echo -e "\n${BLUE}🚀 コアサービスを起動中...${NC}"

# MCPサーバー
echo -n "📡 MCPサーバー起動..."
"$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/mcp_server.py" \
    > "$LOG_DIR/mcp_server.log" 2>&1 &
MCP_PID=$!
PIDS+=($MCP_PID)
echo $MCP_PID > "$PID_DIR/mcp_server.pid"
echo -e " ${GREEN}OK${NC} (PID: $MCP_PID)"

# ワーカープールマネージャー
echo -n "👷 ワーカープール起動..."
"$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/workers/worker_pool_manager.py" \
    --min 1 --max 3 \
    > "$LOG_DIR/worker_pool.log" 2>&1 &
WORKER_PID=$!
PIDS+=($WORKER_PID)
echo $WORKER_PID > "$PID_DIR/worker_pool.pid"
echo -e " ${GREEN}OK${NC} (PID: $WORKER_PID)"

# 3. リアルタイム通信サービス
echo -e "\n${BLUE}🔌 リアルタイム通信サービスを起動中...${NC}"

# WebSocketサーバー
if [ -f "$KOUBOU_HOME/scripts/websocket_server.py" ]; then
    echo -n "🔌 WebSocketサーバー起動..."
    "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/websocket_server.py" \
        > "$LOG_DIR/websocket.log" 2>&1 &
    WS_PID=$!
    PIDS+=($WS_PID)
    echo $WS_PID > "$PID_DIR/websocket.pid"
    echo -e " ${GREEN}OK${NC} (PID: $WS_PID)"
fi

# GraphQLサーバー
if [ -f "$KOUBOU_HOME/scripts/graphql_server.py" ]; then
    echo -n "📊 GraphQLサーバー起動..."
    "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/graphql_server.py" \
        > "$LOG_DIR/graphql.log" 2>&1 &
    GQL_PID=$!
    PIDS+=($GQL_PID)
    echo $GQL_PID > "$PID_DIR/graphql.pid"
    echo -e " ${GREEN}OK${NC} (PID: $GQL_PID)"
fi

# 4. 分散システム（Redisが利用可能な場合）
if [ "$USE_DISTRIBUTED" = true ]; then
    echo -e "\n${BLUE}🌐 分散システムを起動中...${NC}"
    
    # マスターノード
    echo -n "🎯 マスターノード起動..."
    "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/distributed/master_node.py" \
        --node-id master-01 --queue-type redis \
        > "$LOG_DIR/master_node.log" 2>&1 &
    MASTER_PID=$!
    PIDS+=($MASTER_PID)
    echo $MASTER_PID > "$PID_DIR/master_node.pid"
    echo -e " ${GREEN}OK${NC} (PID: $MASTER_PID)"
    
    sleep 2
    
    # ワーカーノード
    echo -n "👷 分散ワーカーノード起動..."
    "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/distributed/remote_worker_node.py" \
        --node-id worker-01 --queue-type redis \
        --capabilities general code --max-workers 2 \
        > "$LOG_DIR/distributed_worker.log" 2>&1 &
    DIST_WORKER_PID=$!
    PIDS+=($DIST_WORKER_PID)
    echo $DIST_WORKER_PID > "$PID_DIR/distributed_worker.pid"
    echo -e " ${GREEN}OK${NC} (PID: $DIST_WORKER_PID)"
    
    # MCP-分散ブリッジ
    if [ -f "$KOUBOU_HOME/scripts/mcp_distributed_bridge.py" ]; then
        echo -n "🌉 MCP-分散ブリッジ起動..."
        "$KOUBOU_HOME/venv/bin/python" "$KOUBOU_HOME/scripts/mcp_distributed_bridge.py" \
            --queue redis \
            > "$LOG_DIR/mcp_bridge.log" 2>&1 &
        BRIDGE_PID=$!
        PIDS+=($BRIDGE_PID)
        echo $BRIDGE_PID > "$PID_DIR/mcp_bridge.pid"
        echo -e " ${GREEN}OK${NC} (PID: $BRIDGE_PID)"
    fi
fi

# 5. サービス確認
echo -e "\n${BLUE}🔍 サービス起動を確認中...${NC}"

check_service "MCP API" 8765
check_service "WebSocket" 8766
check_service "GraphQL" 8767

if [ "$USE_DISTRIBUTED" = true ]; then
    check_service "MCP-Bridge" 8768
fi

# 6. システム情報表示
echo -e "\n${GREEN}======================================"
echo "✅ 工房システム起動完了！"
echo "======================================"
echo ""
echo "📍 エンドポイント:"
echo "  MCP API:     http://localhost:8765"
echo "  WebSocket:   ws://localhost:8766"
echo "  GraphQL:     http://localhost:8767/graphql"
if [ "$USE_DISTRIBUTED" = true ]; then
    echo "  MCP Bridge:  http://localhost:8768"
fi
echo ""
echo "📊 管理ツール:"
echo "  ダッシュボード: http://localhost:8765/dashboard"
echo "  ヘルスチェック: http://localhost:8765/health"
echo "  システム統計:   http://localhost:8765/stats"
echo ""
echo "📝 ログファイル:"
echo "  $LOG_DIR/"
echo ""
echo "🛑 停止方法: Ctrl+C"
echo "======================================"
echo ""

# 7. モニタリングループ
monitor_services() {
    while true; do
        sleep 60
        
        # ヘルスチェック
        if ! curl -s http://localhost:8765/health > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️ MCPサーバーが応答しません${NC}"
        fi
        
        # プロセスチェック
        for pid in "${PIDS[@]}"; do
            if ! kill -0 "$pid" 2>/dev/null; then
                echo -e "${RED}❌ プロセス $pid が停止しました${NC}"
            fi
        done
    done
}

# バックグラウンドでモニタリング
monitor_services &
MONITOR_PID=$!

# メインプロセスを維持
echo "システム監視中... (60秒ごとにヘルスチェック)"
wait $MONITOR_PID