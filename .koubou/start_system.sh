#!/bin/bash
# 🏭 工房システム - 統合起動スクリプト

set -e

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 設定
KOUBOU_HOME="${KOUBOU_HOME:-$(cd "$(dirname "$0")" && pwd)}"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.." && pwd)"
GEMINI_CLI_PATH="$PROJECT_ROOT/gemini-cli-local"

# ワーカータイプ設定（local, simple）
# local: 実際に動作するワーカー（gemini-repo-cli統合・ファイル保存機能付き）
# simple: モックワーカー（テスト用・実際の処理はしない）
export KOUBOU_WORKER_TYPE="${KOUBOU_WORKER_TYPE:-local}"

# PIDファイルディレクトリ
PID_DIR="$KOUBOU_HOME/pids"
mkdir -p "$PID_DIR"

# ログディレクトリ
LOG_DIR="$KOUBOU_HOME/logs"
mkdir -p "$LOG_DIR"

echo -e "${CYAN}🏭 工房システム 起動開始${NC}"
echo -e "${BLUE}KOUBOU_HOME: $KOUBOU_HOME${NC}"
echo -e "${BLUE}PROJECT_ROOT: $PROJECT_ROOT${NC}"
echo -e "${BLUE}GEMINI_CLI_PATH: $GEMINI_CLI_PATH${NC}"
echo -e "${BLUE}WORKER_TYPE: $KOUBOU_WORKER_TYPE${NC}"
echo ""

# 環境変数をエクスポート
export KOUBOU_HOME
export LOCAL_LLM_ENDPOINT="http://192.168.11.29:1234/v1"
export LOCAL_LLM_MODEL="gpt-oss-20b@f16"

# 前提条件チェック
echo -e "${YELLOW}📋 前提条件チェック中...${NC}"

# Ollamaの動作確認と起動
if ! command -v ollama > /dev/null 2>&1; then
    echo -e "${RED}❌ Ollamaがインストールされていません${NC}"
    echo "Ollamaをインストールしてください: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

if ! curl -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ Ollama APIが応答しません。起動中...${NC}"
    # Ollamaサービスをバックグラウンドで起動
    nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    OLLAMA_PID=$!
    echo $OLLAMA_PID > "$PID_DIR/ollama.pid"
    
    # 起動待ち
    for i in {1..10}; do
        if curl -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Ollama API 起動完了 (PID: $OLLAMA_PID)${NC}"
            break
        fi
        sleep 1
    done
    
    if ! curl -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
        echo -e "${RED}❌ Ollama APIが起動できません${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Ollama API 既に稼働中${NC}"
fi

# モデルの確認
if ! ollama list | grep -q "gpt-oss:20b"; then
    echo -e "${RED}❌ gpt-oss:20b モデルが見つかりません${NC}"
    echo "モデルをダウンロードしてください: ollama pull gpt-oss:20b"
    exit 1
fi
echo -e "${GREEN}✅ Ollama モデル (gpt-oss:20b) 確認${NC}"

# Gemini Repo CLIの確認（uvを使用）
PYTHONPATH="$PROJECT_ROOT/gemini-repo-cli/src:$PYTHONPATH"
export PYTHONPATH
if ! uv run python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT/gemini-repo-cli/src'); import gemini_repo" 2>/dev/null; then
    echo -e "${RED}❌ Gemini Repo CLI モジュールが見つかりません${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Gemini Repo CLI 準備完了 (Ollama + gpt-oss:20b)${NC}"


cd "$PROJECT_ROOT"

# 古いプロセスの終了
echo -e "${YELLOW}🛑 既存プロセスの終了中...${NC}"
pkill -f "mcp_server.py" 2>/dev/null || true
pkill -f "local_worker.py" 2>/dev/null || true
pkill -f "enhanced_worker.py" 2>/dev/null || true
pkill -f "websocket_server.py" 2>/dev/null || true
pkill -f "worker_pool_manager.py" 2>/dev/null || true
pkill -f "enhanced_pool_manager.py" 2>/dev/null || true
pkill -f "graphql_server.py" 2>/dev/null || true
pkill -f "dashboard_server.py" 2>/dev/null || true
sleep 2

# Python環境をuvで統一
echo -e "${YELLOW}🐍 Python環境 (uv) 準備中...${NC}"
cd "$PROJECT_ROOT"
if ! command -v uv &> /dev/null; then
    echo -e "${RED}❌ uv が見つかりません。uvをインストールしてください。${NC}"
    exit 1
fi

# uv環境で必要な依存関係をインストール
uv sync --quiet || {
    echo -e "${RED}❌ uv sync に失敗しました${NC}"
    exit 1
}
echo -e "${GREEN}✅ Python環境 (uv) 準備完了${NC}"

# 1. MCP Server 起動
echo -e "${PURPLE}🚀 MCP Server 起動中...${NC}"
cd "$KOUBOU_HOME/scripts"
nohup uv run python mcp_server.py > "$LOG_DIR/mcp_server.log" 2>&1 &
MCP_PID=$!
echo $MCP_PID > "$PID_DIR/mcp_server.pid"
echo -e "${GREEN}✅ MCP Server started (PID: $MCP_PID, Port: 8765)${NC}"

# 2. Worker Pool Manager 起動
echo -e "${PURPLE}🚀 Worker Pool Manager 起動中...${NC}"
cd "$KOUBOU_HOME/scripts/workers"
nohup uv run python enhanced_pool_manager.py > "$LOG_DIR/worker_pool_manager.log" 2>&1 &
MANAGER_PID=$!
echo $MANAGER_PID > "$PID_DIR/enhanced_pool_manager.pid"
echo -e "${GREEN}✅ Worker Pool Manager started (PID: $MANAGER_PID)${NC}"

# 3. WebSocket Server 起動
echo -e "${PURPLE}🚀 WebSocket Server 起動中...${NC}"
cd "$KOUBOU_HOME/scripts"
nohup uv run python websocket_server.py > "$LOG_DIR/websocket_server.log" 2>&1 &
WS_PID=$!
echo $WS_PID > "$PID_DIR/websocket_server.pid"
echo -e "${GREEN}✅ WebSocket Server started (PID: $WS_PID, Port: 8766)${NC}"

# 4. GraphQL API Server 起動
if [ -f "$KOUBOU_HOME/scripts/graphql_server.py" ]; then
    echo -e "${PURPLE}🚀 GraphQL API Server 起動中...${NC}"
    # GraphQL用依存関係をインストール
    cd "$KOUBOU_HOME"
    uv pip install ariadne flask-cors > /dev/null 2>&1 || echo -e "${YELLOW}⚠️ GraphQL dependencies already installed${NC}"
    cd "$KOUBOU_HOME/scripts"
    nohup uv run python graphql_server.py > "$LOG_DIR/graphql_server.log" 2>&1 &
    GQL_PID=$!
    echo $GQL_PID > "$PID_DIR/graphql_server.pid"
    echo -e "${GREEN}✅ GraphQL API Server started (PID: $GQL_PID, Port: 8767)${NC}"
fi

# 5. Web Dashboard 起動
echo -e "${PURPLE}🚀 Web Dashboard 起動中...${NC}"
cd "$KOUBOU_HOME/dashboard"
nohup python3 -m http.server 8080 > "$LOG_DIR/dashboard.log" 2>&1 &
DASH_PID=$!
echo $DASH_PID > "$PID_DIR/dashboard.pid"
echo -e "${GREEN}✅ Web Dashboard started (PID: $DASH_PID, Port: 8080)${NC}"

# 6. Worker Log API 起動（通常モードでも起動）
if [[ "$1" != "--background" && "$1" != "-b" ]]; then
    echo -e "${PURPLE}🚀 Worker Log API 起動中...${NC}"
    cd "$KOUBOU_HOME/scripts/api"
    nohup uv run python worker_log_api.py > "$LOG_DIR/worker_log_api.log" 2>&1 &
    LOG_API_PID=$!
    echo $LOG_API_PID > "$PID_DIR/worker_log_api.pid"
    echo -e "${GREEN}✅ Worker Log API started (PID: $LOG_API_PID, Port: 8768)${NC}"
fi

# サービス起動完了待ち
echo -e "${YELLOW}⏳ サービス起動完了待ち...${NC}"
sleep 5

# ヘルスチェック
echo -e "${YELLOW}🔍 ヘルスチェック中...${NC}"

# MCP Server
if curl -s http://localhost:8765/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ MCP Server 正常稼働${NC}"
else
    echo -e "${RED}❌ MCP Server 異常${NC}"
fi

# WebSocket Server
if curl -s http://localhost:8766/health 2>/dev/null | grep -q "healthy"; then
    echo -e "${GREEN}✅ WebSocket Server 正常稼働${NC}"
else
    echo -e "${YELLOW}⚠️  WebSocket Server ヘルスチェック未対応${NC}"
fi

echo ""
echo -e "${CYAN}🎉 工房システム 起動完了！${NC}"
echo ""
echo -e "${BLUE}📊 サービス情報:${NC}"
echo -e "${GREEN}  • MCP Server: http://localhost:8765${NC}"
echo -e "${GREEN}  • WebSocket Server: ws://localhost:8766${NC}"
if [ ! -z "$GQL_PID" ]; then
    echo -e "${GREEN}  • GraphQL API: http://localhost:8767${NC}"
fi
echo -e "${GREEN}  • Web Dashboard: http://localhost:8080${NC}"
echo -e "${GREEN}  • Worker Log API: http://localhost:8768${NC}"
echo ""
echo -e "${BLUE}🔧 設定情報:${NC}"
echo -e "${GREEN}  • ワーカータイプ: $KOUBOU_WORKER_TYPE${NC}"
echo -e "${GREEN}  • Ollama エンドポイント: http://localhost:11434/v1${NC}"
echo -e "${GREEN}  • Ollama モデル: gpt-oss:20b${NC}"
echo -e "${GREEN}  • Gemini Repo CLI: gemini-repo-cli (Ollama + gpt-oss:20b)${NC}"
echo ""
echo -e "${YELLOW}📝 ログファイル:${NC}"
echo -e "  • MCP Server: $LOG_DIR/mcp_server.log"
echo -e "  • Worker Manager: $LOG_DIR/worker_pool_manager.log"
echo -e "  • WebSocket: $LOG_DIR/websocket_server.log"
echo ""
echo -e "${PURPLE}💡 使用方法:${NC}"
echo -e "  curl -X POST http://localhost:8765/task/delegate -H \"Content-Type: application/json\" \\"
echo -e "    -d '{\"prompt\":\"Hello from Gemini Repo CLI!\",\"sync\":true}'"
echo ""
echo -e "${RED}停止方法: Ctrl+C または .koubou/stop_system.sh${NC}"

# Ctrl+C ハンドリング
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 システム停止中...${NC}"
    
    # 各プロセスを終了
    [ ! -z "$MCP_PID" ] && kill $MCP_PID 2>/dev/null || true
    [ ! -z "$MANAGER_PID" ] && kill $MANAGER_PID 2>/dev/null || true
    [ ! -z "$WS_PID" ] && kill $WS_PID 2>/dev/null || true
    [ ! -z "$GQL_PID" ] && kill $GQL_PID 2>/dev/null || true
    [ ! -z "$DASH_PID" ] && kill $DASH_PID 2>/dev/null || true
    [ ! -z "$LOG_API_PID" ] && kill $LOG_API_PID 2>/dev/null || true
    
    # PIDファイルを削除
    rm -f "$PID_DIR"/*.pid
    
    echo -e "${GREEN}✅ 工房システム 停止完了${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# バックグラウンドモードのチェック
if [[ "$1" == "--background" || "$1" == "-b" ]]; then
    echo -e "${CYAN}🔄 システムをバックグラウンドで起動しました${NC}"
    echo -e "${YELLOW}停止コマンド: .koubou/stop_system.sh${NC}"
    
    # Worker Log APIも起動
    echo -e "${PURPLE}🚀 Worker Log API 起動中...${NC}"
    cd "$KOUBOU_HOME/scripts/api"
    nohup uv run python worker_log_api.py > "$LOG_DIR/worker_log_api.log" 2>&1 &
    LOG_API_PID=$!
    echo $LOG_API_PID > "$PID_DIR/worker_log_api.pid"
    echo -e "${GREEN}✅ Worker Log API started (PID: $LOG_API_PID, Port: 8768)${NC}"
    
    exit 0
fi

# フォアグラウンドで待機
echo -e "${CYAN}🔄 システム稼働中... (Ctrl+C で停止)${NC}"
while true; do
    sleep 10
    
    # プロセス生存チェック
    if ! kill -0 $MCP_PID 2>/dev/null; then
        echo -e "${RED}❌ MCP Server が停止しました${NC}"
        cleanup
    fi
done