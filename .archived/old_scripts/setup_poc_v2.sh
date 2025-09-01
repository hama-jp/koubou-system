#!/bin/bash
# 工房システム POC セットアップスクリプト (プロジェクトディレクトリ内完結版)
# Version: 2.1.0 - 完全版（全機能対応）
# Usage: ./setup_poc_v2.sh

set -e

echo "========================================="
echo "工房システム POC セットアップ v2.1.0"
echo "========================================="

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 成功/失敗表示
success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}!${NC} $1"
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 1. 環境確認
echo -e "\n${BLUE}環境確認中...${NC}"

# OS確認
if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "darwin"* ]]; then
    success "対応OS: $OSTYPE"
else
    warning "未テストのOS: $OSTYPE"
fi

# 必須コマンドチェック
check_required_commands() {
    local missing_commands=()
    
    # Python3
    if ! command -v python3 &> /dev/null; then
        missing_commands+=("python3")
    else
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        success "Python3 インストール済み ($PYTHON_VERSION)"
    fi
    
    # uv (Astralの高速Pythonパッケージマネージャー)
    if ! command -v uv &> /dev/null; then
        missing_commands+=("uv")
    else
        UV_VERSION=$(uv --version | cut -d' ' -f2)
        success "uv インストール済み ($UV_VERSION)"
    fi
    
    # SQLite3
    if ! command -v sqlite3 &> /dev/null; then
        missing_commands+=("sqlite3")
    else
        SQLITE_VERSION=$(sqlite3 --version | cut -d' ' -f1)
        success "SQLite3 インストール済み ($SQLITE_VERSION)"
    fi
    
    # npm/node チェック（Codex CLI用）
    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        success "npm インストール済み ($NPM_VERSION)"
    else
        warning "npmがインストールされていません（Codex CLI使用時に必要）"
    fi
    
    # Redis チェック（分散システム用）
    if command -v redis-cli &> /dev/null; then
        REDIS_VERSION=$(redis-cli --version | cut -d' ' -f2)
        success "Redis インストール済み ($REDIS_VERSION)"
        
        # Redis動作確認
        if redis-cli ping &> /dev/null; then
            success "Redisサーバー稼働中"
        else
            warning "Redisサーバーが起動していません"
            info "分散機能を使用する場合は 'redis-server' を起動してください"
        fi
    else
        warning "Redisがインストールされていません（分散機能使用時に必要）"
    fi
    
    # Ollama チェック
    if command -v ollama &> /dev/null; then
        OLLAMA_VERSION=$(ollama --version | head -n1)
        success "Ollama インストール済み"
        
        # モデルの確認
        if ollama list 2>/dev/null | grep -q "gpt-oss:20b"; then
            success "gpt-oss:20b モデル利用可能"
        elif ollama list 2>/dev/null | grep -q "gemma2:2b"; then
            success "gemma2:2b モデル利用可能"
        else
            warning "推奨LLMモデルが見つかりません"
            info "後で 'ollama pull gemma2:2b' を実行してください"
        fi
    else
        warning "Ollamaがインストールされていません"
        info "ローカルLLM機能を使用する場合は後でインストールしてください"
    fi
    
    # Codex CLI チェック
    if command -v codex &> /dev/null; then
        CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
        success "Codex CLI インストール済み ($CODEX_VERSION)"
    else
        warning "Codex CLIがインストールされていません"
        info "コード生成機能を使用する場合は後でインストールしてください"
    fi
    
    # 必須コマンド不足チェック
    if [ ${#missing_commands[@]} -ne 0 ]; then
        error "必須コマンドが不足しています: ${missing_commands[*]}"
    fi
}

check_required_commands

# 2. ディレクトリ構造作成
echo -e "\n${BLUE}ディレクトリ構造を作成中...${NC}"

# .koubouディレクトリ作成
mkdir -p .koubou/{scripts,config,db,logs,venv}
mkdir -p .koubou/scripts/{workers,common,distributed}
mkdir -p .koubou/logs/{workers,system}
mkdir -p .koubou/dashboard
mkdir -p .koubou/config/distributed

success "ディレクトリ構造作成完了"

# 3. Python仮想環境セットアップ
echo -e "\n${BLUE}Python仮想環境をセットアップ中...${NC}"

cd .koubou

# 仮想環境作成（uvを使用）
if [ ! -f venv/bin/python ]; then
    uv venv venv
    success "仮想環境作成完了"
else
    success "仮想環境は既に存在します"
fi

# pyproject.toml作成
cat > pyproject.toml << 'EOF'
[project]
name = "koubou-system"
version = "2.1.0"
dependencies = [
    # 基本依存関係
    "requests>=2.31.0",
    "pyyaml>=6.0.1",
    "flask>=3.0.0",
    "flask-cors>=4.0.0",
    "python-dotenv>=1.0.0",
    "psutil>=5.9.0",
    
    # 非同期処理
    "asyncio>=3.4.3",
    
    # リアルタイム通信
    "websockets>=12.0",
    
    # GraphQL
    "ariadne>=0.21.0",
    "graphql-core>=3.2.0",
    
    # 分散システム
    "redis>=6.0.0",        # Redis通信
    
    # ユーティリティ
    "click>=8.1.0",        # CLI
    "rich>=13.0.0",        # リッチテキスト出力
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.7.0",
    "flake8>=6.1.0",
    "mypy>=1.5.0",
]

monitoring = [
    "prometheus-client>=0.17.0",
]

distributed = [
    "pika>=1.3.0",         # RabbitMQ
    "celery>=5.3.0",       # タスクキュー（代替）
]
EOF

success "pyproject.toml作成完了"

# 依存関係インストール
echo -e "\n${BLUE}依存関係をインストール中...${NC}"
uv pip install --python venv/bin/python -r pyproject.toml 2>/dev/null || {
    # pyproject.tomlからの直接インストールが失敗した場合
    uv pip install --python venv/bin/python \
        requests pyyaml flask flask-cors python-dotenv psutil \
        websockets ariadne graphql-core redis click rich
}

# 開発ツールインストール（オプション）
if [ "$1" == "--dev" ]; then
    info "開発ツールをインストール中..."
    uv pip install --python venv/bin/python \
        pytest pytest-asyncio black flake8 mypy
fi

success "依存関係インストール完了"

# 4. データベース初期化
echo -e "\n${BLUE}データベースを初期化中...${NC}"

# SQLファイル作成
cat > ../scripts/init_database.sql << 'EOF'
-- 工房システムデータベース初期化スクリプト

-- タスクテーブル
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'general',
    content TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'pending',
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system'
);

-- ワーカーテーブル
CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'idle',
    current_task TEXT,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    capabilities TEXT DEFAULT 'general'
);

-- タスク履歴テーブル
CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    worker_id TEXT,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- メトリクステーブル
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    labels TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
EOF

# データベース初期化
cat ../scripts/init_database.sql | sqlite3 db/koubou.db
success "データベース初期化完了"

# 5. 起動スクリプト作成
echo -e "\n${BLUE}起動スクリプトを作成中...${NC}"

# システム起動スクリプト
cat > start_system.sh << 'EOF'
#!/bin/bash
# 工房システム起動スクリプト

echo "🏭 工房システムを起動します..."

# 環境変数設定
export KOUBOU_HOME="$(pwd)"
export PYTHONPATH="$KOUBOU_HOME/scripts:$PYTHONPATH"
export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1

# MCPサーバー起動
echo "📡 MCPサーバーを起動中..."
$KOUBOU_HOME/venv/bin/python scripts/mcp_server.py &
MCP_PID=$!
echo "MCPサーバー起動 (PID: $MCP_PID)"

# ワーカープール起動
echo "👷 ワーカープールを起動中..."
$KOUBOU_HOME/venv/bin/python scripts/workers/worker_pool_manager.py &
WORKER_PID=$!
echo "ワーカープール起動 (PID: $WORKER_PID)"

# WebSocketサーバー起動（オプション）
if [ -f scripts/websocket_server.py ]; then
    echo "🔌 WebSocketサーバーを起動中..."
    $KOUBOU_HOME/venv/bin/python scripts/websocket_server.py &
    WS_PID=$!
    echo "WebSocketサーバー起動 (PID: $WS_PID)"
fi

# GraphQLサーバー起動（オプション）
if [ -f scripts/graphql_server.py ]; then
    echo "📊 GraphQLサーバーを起動中..."
    $KOUBOU_HOME/venv/bin/python scripts/graphql_server.py &
    GQL_PID=$!
    echo "GraphQLサーバー起動 (PID: $GQL_PID)"
fi

echo ""
echo "✅ システム起動完了！"
echo "MCP API: http://localhost:8765"
echo "WebSocket: ws://localhost:8766"
echo "GraphQL: http://localhost:8767/graphql"
echo ""
echo "停止するには Ctrl+C を押してください"

# 終了処理
trap "echo '🛑 システムを停止中...'; kill $MCP_PID $WORKER_PID $WS_PID $GQL_PID 2>/dev/null; exit" INT TERM

# プロセス監視
wait
EOF

chmod +x start_system.sh
success "起動スクリプト作成完了"

# 6. 分散システム起動スクリプト（オプション）
cat > start_distributed.sh << 'EOF'
#!/bin/bash
# 分散ワーカーシステム起動スクリプト

echo "🌐 分散ワーカーシステムを起動します..."

# Redis確認
if ! redis-cli ping &> /dev/null; then
    echo "❌ Redisが起動していません"
    echo "redis-server を起動してください"
    exit 1
fi

# マスターノード起動
echo "🎯 マスターノードを起動中..."
$KOUBOU_HOME/venv/bin/python scripts/distributed/master_node.py \
    --node-id master-01 \
    --queue-type redis &
MASTER_PID=$!

sleep 2

# ワーカーノード起動
echo "👷 ワーカーノードを起動中..."
$KOUBOU_HOME/venv/bin/python scripts/distributed/remote_worker_node.py \
    --node-id worker-01 \
    --queue-type redis \
    --capabilities general code &
WORKER1_PID=$!

echo ""
echo "✅ 分散システム起動完了！"
echo ""
echo "タスク送信: venv/bin/python scripts/distributed/task_client.py"
echo ""

trap "echo '🛑 分散システムを停止中...'; kill $MASTER_PID $WORKER1_PID 2>/dev/null; exit" INT TERM
wait
EOF

chmod +x start_distributed.sh
success "分散システム起動スクリプト作成完了"

cd ..

# 7. 完了メッセージ
echo ""
echo "========================================="
echo -e "${GREEN}✅ セットアップ完了！${NC}"
echo "========================================="
echo ""
echo "📁 作成されたディレクトリ:"
echo "   .koubou/         - システムホームディレクトリ"
echo "   .koubou/scripts/ - スクリプト"
echo "   .koubou/config/  - 設定ファイル"
echo "   .koubou/db/      - データベース"
echo "   .koubou/logs/    - ログファイル"
echo "   .koubou/venv/    - Python仮想環境"
echo ""
echo "🚀 システム起動方法:"
echo "   基本システム: .koubou/start_system.sh"
echo "   分散システム: .koubou/start_distributed.sh"
echo ""
echo "📝 次のステップ:"
echo "   1. scripts/ディレクトリにシステムファイルをコピー"
echo "   2. 必要に応じてOllamaモデルをダウンロード"
echo "   3. Redisサーバーを起動（分散機能使用時）"
echo ""
echo "詳細は docs/README.md を参照してください"