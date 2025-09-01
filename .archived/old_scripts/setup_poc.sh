#!/bin/bash
# 工房システム POC セットアップスクリプト (プロジェクトディレクトリ内完結版)
# Version: 2.0.0 - 改善版
# Usage: ./setup_poc.sh

set -e

echo "========================================="
echo "工房システム POC セットアップ v2.0.0"
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

# プロジェクトルートディレクトリを取得
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KOUBOU_HOME="$PROJECT_ROOT/.koubou"

echo "プロジェクトディレクトリ: $PROJECT_ROOT"
echo "工房ホーム: $KOUBOU_HOME"
echo ""

# 前提条件チェック
check_prerequisites() {
    echo "前提条件をチェック中..."
    
    # Python チェック
    if command -v python3 &> /dev/null; then
        PY_VERSION=$(python3 --version | awk '{print $2}')
        success "Python3 インストール済み ($PY_VERSION)"
    else
        error "Python3がインストールされていません。"
    fi
    
    # uv チェック
    if command -v uv &> /dev/null; then
        UV_VERSION=$(uv --version | awk '{print $2}')
        success "uv インストール済み ($UV_VERSION)"
    else
        warning "uvがインストールされていません。インストールします..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
        # .bashrcに追加
        if ! grep -q "cargo/bin" ~/.bashrc; then
            echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
            info "~/.bashrcにPATHを追加しました"
        fi
        success "uvをインストールしました"
    fi
    
    # SQLite3チェック
    if command -v sqlite3 &> /dev/null; then
        SQLITE_VERSION=$(sqlite3 --version | awk '{print $1}')
        success "SQLite3 インストール済み ($SQLITE_VERSION)"
    else
        error "SQLite3がインストールされていません。手動でインストールしてください。"
    fi
    
    # npm/node チェック（Codex CLI用）
    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        success "npm インストール済み ($NPM_VERSION)"
    else
        warning "npmがインストールされていません（Codex CLI使用時に必要）"
    fi
    
    # Ollama チェック
    if command -v ollama &> /dev/null; then
        OLLAMA_VERSION=$(ollama --version | head -n1)
        success "Ollama インストール済み"
        # モデルの確認
        if ollama list | grep -q "gpt-oss:20b"; then
            success "gpt-oss:20b モデル利用可能"
        else
            warning "gpt-oss:20b モデルが見つかりません"
            info "後で 'ollama pull gpt-oss:20b' を実行してください"
        fi
    else
        warning "Ollamaがインストールされていません"
        info "Codex CLI統合を使用する場合は後でインストールしてください"
    fi
    
    # Codex CLI チェック
    if command -v codex &> /dev/null; then
        CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
        success "Codex CLI インストール済み ($CODEX_VERSION)"
    else
        warning "Codex CLIがインストールされていません"
        info "後で 'npm install -g @openai/codex' を実行してください"
    fi
    
    # jqチェック (オプション)
    if command -v jq &> /dev/null; then
        success "jq インストール済み"
    else
        warning "jqがインストールされていません（オプション）"
    fi
}

# ディレクトリ構造作成
create_directories() {
    echo ""
    echo "ディレクトリ構造を作成中..."
    
    # .koubouディレクトリとサブディレクトリ作成
    mkdir -p "$KOUBOU_HOME"/{config,tasks,logs,db,tmp,scripts,venv}
    mkdir -p "$KOUBOU_HOME"/tasks/{pending,in_progress,completed,failed}
    mkdir -p "$KOUBOU_HOME"/logs/{agents,workers,system}
    mkdir -p "$KOUBOU_HOME"/scripts/{adapters,workers,common,tests}
    
    # 権限設定 (プロジェクト内なのでsudo不要)
    chmod 755 "$KOUBOU_HOME"
    chmod 700 "$KOUBOU_HOME"/config
    
    success "ディレクトリ構造を作成しました"
}

# Python仮想環境とパッケージセットアップ
setup_python_env() {
    echo ""
    echo "Python環境をセットアップ中..."
    
    cd "$PROJECT_ROOT"
    
    # pyproject.tomlを作成（依存関係を更新）
    cat > pyproject.toml << 'EOF'
[project]
name = "koubou-system"
version = "2.0.0"
description = "工房システム POC - 動的スケーリング対応版"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.31.0",
    "pyyaml>=6.0.1",
    "flask>=3.0.0",
    "flask-cors>=4.0.0",
    "python-dotenv>=1.0.0",
    "psutil>=5.9.0",
    "asyncio>=3.4.3",
    "websockets>=12.0",
    "ariadne>=0.21.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "mypy>=1.7.0",
]

[tool.uv]
dev-dependencies = []
EOF
    
    # uv で仮想環境作成とパッケージインストール
    info "Python仮想環境を作成中..."
    uv venv "$KOUBOU_HOME/venv"
    
    info "依存パッケージをインストール中..."
    source "$KOUBOU_HOME/venv/bin/activate"
    uv pip install -e .
    
    # 開発ツールもインストール（オプション）
    read -p "開発ツール（pytest, black等）もインストールしますか? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        uv pip install -e ".[dev]"
        success "開発ツールをインストールしました"
    fi
    
    success "Python環境をセットアップしました"
}

# データベース初期化
init_database() {
    echo ""
    echo "データベースを初期化中..."
    
    DB_PATH="$KOUBOU_HOME/db/koubou.db"
    
    # 既存のDBがある場合はバックアップ
    if [ -f "$DB_PATH" ]; then
        BACKUP_PATH="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$DB_PATH" "$BACKUP_PATH"
        warning "既存のデータベースをバックアップしました: $BACKUP_PATH"
    fi
    
    # SQLスクリプトを実行（catでパイプすることでエラーを回避）
    if [ -f "$PROJECT_ROOT/scripts/init_database.sql" ]; then
        cat "$PROJECT_ROOT/scripts/init_database.sql" | sqlite3 "$DB_PATH"
        success "データベースを初期化しました"
    else
        warning "init_database.sqlが見つかりません。基本テーブルのみ作成します"
        # 基本的なテーブル構造を作成
        sqlite3 "$DB_PATH" << 'SQL'
-- タスクマスターテーブル
CREATE TABLE IF NOT EXISTS task_master (
    task_id TEXT PRIMARY KEY,
    content TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    result TEXT,
    created_by TEXT,
    assigned_to TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ワーカーテーブル
CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'idle',
    current_task TEXT,
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_task_status ON task_master(status);
CREATE INDEX IF NOT EXISTS idx_task_priority ON task_master(priority DESC);
CREATE INDEX IF NOT EXISTS idx_worker_status ON workers(status);
SQL
        success "基本テーブルを作成しました"
    fi
}

# 設定ファイル作成
create_configs() {
    echo ""
    echo "設定ファイルを作成中..."
    
    # Ollamaの設定を確認
    OLLAMA_ENDPOINT="http://localhost:11434"
    if command -v ollama &> /dev/null; then
        info "Ollamaエンドポイント: $OLLAMA_ENDPOINT"
    fi
    
    # agent.yaml - Ollama設定を含む
    cat > "$KOUBOU_HOME/config/agent.yaml" << EOF
# 工房システム エージェント設定
system:
  name: "koubou-poc"
  version: "2.0.0"
  base_path: "$KOUBOU_HOME"
  
database:
  type: "sqlite"
  path: "$KOUBOU_HOME/db/koubou.db"
  
logging:
  level: "INFO"
  path: "$KOUBOU_HOME/logs"
  
workers:
  ollama:
    enabled: true
    model: "gpt-oss:20b"
    endpoint: "$OLLAMA_ENDPOINT"
    max_concurrent: 3
  
  # LMStudio設定（オプション）
  lmstudio:
    enabled: false
    model: "gpt-oss-20b@f16"
    endpoint: "http://192.168.11.29:1234/v1"
    max_concurrent: 3
    
mcp:
  enabled: true
  server_path: "$KOUBOU_HOME/scripts/mcp_server.py"
  port: 8765
  
worker_pool:
  min_workers: 1
  max_workers: 8
  scale_up_threshold: 2    # pending_tasks > active_workers * threshold
  scale_down_threshold: 0.5 # pending_tasks < active_workers * threshold
  heartbeat_interval: 30
EOF
    
    # .env
    cat > "$KOUBOU_HOME/config/.env" << EOF
# 工房システム環境変数
KOUBOU_HOME=$KOUBOU_HOME
KOUBOU_DB=$KOUBOU_HOME/db/koubou.db
KOUBOU_LOG_DIR=$KOUBOU_HOME/logs
PYTHONPATH=$PROJECT_ROOT:$KOUBOU_HOME/scripts

# Ollama設定
OLLAMA_HOST=0.0.0.0
OLLAMA_NUM_GPU=999
OLLAMA_MODELS_PATH=$KOUBOU_HOME/models

# Codex CLI設定（Linux環境用）
CODEX_UNSAFE_ALLOW_NO_SANDBOX=1

# LMStudio設定（オプション）
LMSTUDIO_ENDPOINT=http://192.168.11.29:1234/v1
EOF
    
    chmod 600 "$KOUBOU_HOME/config/.env"
    
    # Codex設定ファイル
    cat > "$KOUBOU_HOME/config/codex.toml" << 'EOF'
# Codex CLI設定
model = "gpt-oss:20b"
api_base = "http://localhost:11434"
sandbox_mode = "off"
approval_policy = "never"

[options]
temperature = 0.7
max_tokens = 4000
stop = ["```", "\n\n\n"]
EOF
    
    # Claude MCP設定
    cat > "$KOUBOU_HOME/config/claude_mcp_config.json" << EOF
{
  "mcpServers": {
    "koubou": {
      "command": "$KOUBOU_HOME/venv/bin/python",
      "args": ["$KOUBOU_HOME/scripts/mcp_server.py"],
      "env": {
        "KOUBOU_HOME": "$KOUBOU_HOME",
        "PYTHONPATH": "$PROJECT_ROOT"
      }
    }
  }
}
EOF
    
    success "設定ファイルを作成しました"
}

# スクリプト作成
create_scripts() {
    echo ""
    echo "実行スクリプトを作成中..."
    
    # システム起動スクリプト
    cat > "$KOUBOU_HOME/start_system.sh" << 'EOF'
#!/bin/bash
# 工房システム起動スクリプト

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config/.env"
source "$SCRIPT_DIR/venv/bin/activate"

echo "🏭 工房システムを起動中..."

# Ollamaチェック
if command -v ollama &> /dev/null; then
    echo -n "Ollamaサーバーの状態を確認中... "
    if ! pgrep -x "ollama" > /dev/null; then
        echo "起動していません"
        echo "Ollamaサーバーを起動中..."
        ollama serve > "$KOUBOU_LOG_DIR/ollama.log" 2>&1 &
        OLLAMA_PID=$!
        sleep 3
        echo "Ollama起動 (PID: $OLLAMA_PID)"
    else
        echo "既に起動中"
    fi
fi

# MCPサーバー起動
echo "MCPサーバーを起動中..."
python "$SCRIPT_DIR/scripts/mcp_server.py" > "$KOUBOU_LOG_DIR/mcp_server.log" 2>&1 &
MCP_PID=$!
sleep 2

# ワーカープール起動
echo "ワーカープールマネージャーを起動中..."
python "$SCRIPT_DIR/scripts/workers/worker_pool_manager.py" > "$KOUBOU_LOG_DIR/worker_pool.log" 2>&1 &
POOL_PID=$!

echo ""
echo "✅ 工房システムが起動しました"
echo "  MCPサーバー: http://localhost:8765"
echo "  プロセスID: MCP=$MCP_PID, Pool=$POOL_PID"
echo ""
echo "停止: $SCRIPT_DIR/stop_system.sh"
echo "ログ: tail -f $KOUBOU_LOG_DIR/*.log"

# PIDファイル作成
echo "$MCP_PID" > "$SCRIPT_DIR/tmp/mcp.pid"
echo "$POOL_PID" > "$SCRIPT_DIR/tmp/pool.pid"
[ ! -z "$OLLAMA_PID" ] && echo "$OLLAMA_PID" > "$SCRIPT_DIR/tmp/ollama.pid"
EOF
    chmod +x "$KOUBOU_HOME/start_system.sh"
    
    # システム停止スクリプト
    cat > "$KOUBOU_HOME/stop_system.sh" << 'EOF'
#!/bin/bash
# 工房システム停止スクリプト

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🛑 工房システムを停止中..."

# PIDファイルから停止
for pidfile in "$SCRIPT_DIR"/tmp/*.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        NAME=$(basename "$pidfile" .pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo "  $NAME (PID: $PID) を停止..."
            kill "$PID"
        fi
        rm "$pidfile"
    fi
done

# 残っているワーカーも停止
pkill -f "local_worker.py"

echo "✅ 工房システムを停止しました"
EOF
    chmod +x "$KOUBOU_HOME/stop_system.sh"
    
    # Codex実行スクリプト（Ollama用）
    cat > "$KOUBOU_HOME/scripts/codex-ollama.sh" << 'EOF'
#!/bin/bash
# Codex CLI with Ollama

export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config/codex.toml"

# Ollamaが起動しているか確認
if ! pgrep -x "ollama" > /dev/null; then
    echo "⚠️  Ollamaが起動していません。起動してください: ollama serve"
    exit 1
fi

# Codex実行
exec codex \
    --provider ollama \
    --model gpt-oss:20b \
    --api-base http://localhost:11434 \
    --dangerously-run-without-sandbox \
    --no-ask-for-approval \
    --trusted-workspace \
    "$@"
EOF
    chmod +x "$KOUBOU_HOME/scripts/codex-ollama.sh"
    
    # Codexタスク実行スクリプト
    cat > "$KOUBOU_HOME/scripts/codex-exec.sh" << 'EOF'
#!/bin/bash
# Execute task with Codex

if [ $# -eq 0 ]; then
    echo "Usage: $0 \"task description\""
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1

# タスクを実行
"$SCRIPT_DIR/codex-ollama.sh" exec "$1"
EOF
    chmod +x "$KOUBOU_HOME/scripts/codex-exec.sh"
    
    success "実行スクリプトを作成しました"
}

# テストスクリプト作成
create_test_scripts() {
    echo ""
    echo "テストスクリプトを作成中..."
    
    # 統合テスト
    cat > "$KOUBOU_HOME/scripts/test_integration.py" << 'EOF'
#!/usr/bin/env python3
"""工房システム統合テスト"""

import requests
import time
import json
import sys

BASE_URL = "http://localhost:8765"

def test_health():
    """ヘルスチェック"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ ヘルスチェック: OK")
            return True
    except:
        pass
    print("✗ ヘルスチェック: 失敗（MCPサーバーが起動していません）")
    return False

def test_task_submission():
    """タスク送信テスト"""
    task_data = {
        "type": "general",
        "prompt": "What is 2+2?",
        "sync": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/task/delegate", json=task_data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ タスク送信: OK (task_id: {result.get('task_id', 'N/A')})")
            return True
    except Exception as e:
        print(f"✗ タスク送信: 失敗 ({e})")
    return False

if __name__ == "__main__":
    print("🧪 工房システム統合テスト")
    print("-" * 40)
    
    # ヘルスチェック
    if not test_health():
        print("\nMCPサーバーを起動してください:")
        print("  .koubou/start_system.sh")
        sys.exit(1)
    
    # タスク送信
    test_task_submission()
    
    print("\n✅ テスト完了")
EOF
    chmod +x "$KOUBOU_HOME/scripts/test_integration.py"
    
    # 負荷テスト
    cat > "$KOUBOU_HOME/scripts/load_test.py" << 'EOF'
#!/usr/bin/env python3
"""負荷テストツール"""

import requests
import time
import random
import threading
from datetime import datetime

BASE_URL = "http://localhost:8765"

def submit_task(task_num, task_type="general"):
    """タスクを送信"""
    prompts = [
        "Write a Python function to calculate factorial",
        "Explain the concept of recursion",
        "Create a REST API endpoint",
        "What is machine learning?",
        "Debug this code snippet",
    ]
    
    task_data = {
        "type": task_type,
        "prompt": f"Task #{task_num}: {random.choice(prompts)}",
        "priority": random.randint(1, 10),
        "sync": False
    }
    
    try:
        start = time.time()
        response = requests.post(f"{BASE_URL}/task/delegate", json=task_data, timeout=10)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            task_id = response.json().get("task_id")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Task #{task_num} submitted: {task_id} ({elapsed:.2f}s)")
            return task_id
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Task #{task_num} failed: {e}")
    return None

def burst_test(num_tasks=20):
    """バーストテスト"""
    print(f"\n🚀 バーストテスト: {num_tasks}個のタスクを一度に送信")
    
    threads = []
    for i in range(num_tasks):
        t = threading.Thread(target=submit_task, args=(i+1,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    print("✅ バーストテスト完了")

def continuous_test(duration=60, rate=2):
    """継続的負荷テスト"""
    print(f"\n⏱️  継続テスト: {duration}秒間、毎秒{rate}タスク")
    
    start_time = time.time()
    task_count = 0
    
    while time.time() - start_time < duration:
        for _ in range(rate):
            threading.Thread(target=submit_task, args=(task_count+1,)).start()
            task_count += 1
        time.sleep(1)
    
    print(f"✅ 継続テスト完了: {task_count}タスク送信")

if __name__ == "__main__":
    print("🧪 工房システム負荷テスト")
    print("=" * 50)
    
    print("\nテストモード選択:")
    print("1. バーストテスト（20タスク）")
    print("2. 継続的負荷テスト（60秒）")
    print("3. カスタムテスト")
    
    choice = input("\n選択 (1-3): ")
    
    if choice == "1":
        burst_test(20)
    elif choice == "2":
        continuous_test(60, 2)
    elif choice == "3":
        num = int(input("タスク数: "))
        burst_test(num)
    else:
        print("無効な選択")
EOF
    chmod +x "$KOUBOU_HOME/scripts/load_test.py"
    
    success "テストスクリプトを作成しました"
}

# クリーンアップスクリプト作成
create_cleanup_script() {
    echo ""
    echo "クリーンアップスクリプトを作成中..."
    
    cat > "$PROJECT_ROOT/cleanup.sh" << 'EOF'
#!/bin/bash
# 工房システム クリーンアップスクリプト

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
KOUBOU_HOME="$PROJECT_ROOT/.koubou"

echo "🧹 工房システムをクリーンアップします"
echo "削除対象: $KOUBOU_HOME"
echo ""
echo "警告: この操作は取り消せません！"
read -p "続行しますか? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "キャンセルしました"
    exit 0
fi

echo ""
echo "クリーンアップ中..."

# プロセス停止
if [ -f "$KOUBOU_HOME/stop_system.sh" ]; then
    "$KOUBOU_HOME/stop_system.sh" 2>/dev/null
fi

# .koubouディレクトリを削除
if [ -d "$KOUBOU_HOME" ]; then
    rm -rf "$KOUBOU_HOME"
    echo "✓ .koubouディレクトリを削除しました"
fi

# pyproject.tomlを削除（オプション）
if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
    read -p "pyproject.tomlも削除しますか? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm "$PROJECT_ROOT/pyproject.toml"
        echo "✓ pyproject.tomlを削除しました"
    fi
fi

# 生成されたファイルの削除（オプション）
if ls "$PROJECT_ROOT"/*.py 2>/dev/null | grep -q "todo_cli\|test_"; then
    read -p "生成されたPythonファイル（todo_cli.py等）も削除しますか? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$PROJECT_ROOT"/todo_cli.py "$PROJECT_ROOT"/test_*.py
        echo "✓ 生成されたファイルを削除しました"
    fi
fi

echo ""
echo "✅ クリーンアップ完了"
EOF
    
    chmod +x "$PROJECT_ROOT/cleanup.sh"
    success "クリーンアップスクリプトを作成しました"
}

# 最終確認とヒント
final_check() {
    echo ""
    echo "========================================="
    echo "セットアップ完了! 🎉"
    echo "========================================="
    echo ""
    echo "📁 セットアップ内容:"
    echo "  • プロジェクト: $PROJECT_ROOT"
    echo "  • 工房ホーム: $KOUBOU_HOME"
    echo "  • データベース: $KOUBOU_HOME/db/koubou.db"
    echo "  • Python環境: $KOUBOU_HOME/venv"
    echo "  • ログ: $KOUBOU_HOME/logs/"
    echo ""
    echo "🚀 クイックスタート:"
    echo "  1. Ollamaを起動: ollama serve"
    echo "  2. モデル取得: ollama pull gpt-oss:20b"
    echo "  3. システム起動: $KOUBOU_HOME/start_system.sh"
    echo "  4. テスト実行: python $KOUBOU_HOME/scripts/test_integration.py"
    echo ""
    echo "📝 Codex CLI使用例:"
    echo "  • 対話モード: $KOUBOU_HOME/scripts/codex-ollama.sh"
    echo "  • タスク実行: $KOUBOU_HOME/scripts/codex-exec.sh \"タスク内容\""
    echo ""
    echo "🧪 負荷テスト:"
    echo "  python $KOUBOU_HOME/scripts/load_test.py"
    echo ""
    echo "🧹 クリーンアップ:"
    echo "  $PROJECT_ROOT/cleanup.sh"
    echo ""
    echo "📚 ドキュメント:"
    echo "  $PROJECT_ROOT/docs/README.md"
    echo ""
    
    # 次のステップを提案
    if ! command -v ollama &> /dev/null; then
        warning "Ollamaがインストールされていません"
        echo "  インストール: curl -fsSL https://ollama.com/install.sh | sh"
    fi
    
    if ! command -v codex &> /dev/null; then
        warning "Codex CLIがインストールされていません"
        echo "  インストール: npm install -g @openai/codex"
    fi
    
    echo ""
    info "詳細は docs/guides/QUICKSTART.md を参照してください"
}

# メイン処理
main() {
    check_prerequisites
    create_directories
    setup_python_env
    init_database
    create_configs
    create_scripts
    create_test_scripts
    create_cleanup_script
    
    # 既存のスクリプトをコピー（存在する場合）
    if [ -f "$PROJECT_ROOT/.koubou/scripts/mcp_server.py" ]; then
        info "既存のMCPサーバースクリプトを保持"
    fi
    
    if [ -f "$PROJECT_ROOT/.koubou/scripts/workers/worker_pool_manager.py" ]; then
        info "既存のワーカープールマネージャーを保持"
    fi
    
    if [ -f "$PROJECT_ROOT/.koubou/scripts/workers/local_worker.py" ]; then
        info "既存のローカルワーカーを保持"
    fi
    
    final_check
}

# 実行確認
echo "このスクリプトは以下の処理を行います:"
echo "  • $PROJECT_ROOT/.koubou ディレクトリの作成"
echo "  • Python仮想環境の作成 (uv使用)"
echo "  • 必要なパッケージのインストール"
echo "  • データベースの初期化"
echo "  • 設定ファイルとスクリプトの生成"
echo ""
read -p "続行しますか? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    main
else
    echo "キャンセルしました"
    exit 0
fi