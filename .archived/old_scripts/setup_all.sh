#!/bin/bash
# 工房システム 完全セットアップスクリプト
# Usage: ./setup_all.sh

set -e

echo "========================================="
echo "工房システム v2.0 セットアップ"
echo "========================================="

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# 前提条件チェック
check_prerequisites() {
    echo ""
    echo "前提条件をチェック中..."
    
    # Python3チェック
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        success "Python3 インストール済み ($PYTHON_VERSION)"
    else
        error "Python3がインストールされていません"
    fi
    
    # SQLite3チェック
    if command -v sqlite3 &> /dev/null; then
        success "SQLite3 インストール済み"
    else
        error "SQLite3がインストールされていません"
    fi
    
    # jqチェック
    if command -v jq &> /dev/null; then
        success "jq インストール済み"
    else
        warning "jqがインストールされていません。インストールを推奨します。"
        echo "  sudo apt-get install jq  # Ubuntu/Debian"
        echo "  brew install jq          # macOS"
    fi
    
    # inotify-toolsチェック (Linux only)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v inotifywait &> /dev/null; then
            success "inotify-tools インストール済み"
        else
            warning "inotify-toolsがインストールされていません"
            echo "  sudo apt-get install inotify-tools"
        fi
    fi
}

# ディレクトリ構造作成
create_directories() {
    echo ""
    echo "ディレクトリ構造を作成中..."
    
    # ベースディレクトリ
    BASE_DIR="/var/koubou"
    
    # sudoが必要な場合
    if [ ! -w "/var" ]; then
        warning "管理者権限が必要です"
        sudo mkdir -p $BASE_DIR
        sudo chown -R $USER:$USER $BASE_DIR
    else
        mkdir -p $BASE_DIR
    fi
    
    # サブディレクトリ作成
    mkdir -p $BASE_DIR/{config,tasks,logs,db,tmp,scripts}
    mkdir -p $BASE_DIR/tasks/{pending,in_progress,completed,failed}
    mkdir -p $BASE_DIR/logs/{agents,workers,system}
    mkdir -p $BASE_DIR/scripts/{adapters,workers,common}
    
    # 権限設定
    chmod 755 $BASE_DIR
    chmod 700 $BASE_DIR/config
    
    success "ディレクトリ構造を作成しました"
}

# データベース初期化
init_database() {
    echo ""
    echo "データベースを初期化中..."
    
    DB_PATH="/var/koubou/db/koubou.db"
    
    # 既存のDBがある場合はバックアップ
    if [ -f "$DB_PATH" ]; then
        BACKUP_PATH="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        cp $DB_PATH $BACKUP_PATH
        warning "既存のデータベースをバックアップしました: $BACKUP_PATH"
    fi
    
    # SQLスクリプトを実行
    sqlite3 $DB_PATH < scripts/init_database.sql
    
    success "データベースを初期化しました"
}

# 設定ファイル作成
create_configs() {
    echo ""
    echo "設定ファイルを作成中..."
    
    # agent.yaml
    cp scripts/configs/agent.yaml /var/koubou/config/
    
    # .env
    if [ ! -f "/var/koubou/config/.env" ]; then
        cp scripts/configs/env.template /var/koubou/config/.env
        chmod 600 /var/koubou/config/.env
        warning ".envファイルを作成しました。必要に応じて編集してください:"
        echo "  /var/koubou/config/.env"
    else
        success ".envファイルは既に存在します"
    fi
    
    # Claude MCP設定
    cp scripts/configs/claude_mcp_config.json /var/koubou/config/
    
    success "設定ファイルを作成しました"
}

# スクリプトのコピー
copy_scripts() {
    echo ""
    echo "スクリプトをコピー中..."
    
    # 実行可能にして適切な場所にコピー
    cp scripts/workers/local_worker.py /var/koubou/scripts/workers/
    cp scripts/adapters/agent_adapter.py /var/koubou/scripts/adapters/
    cp scripts/mcp_server.py /var/koubou/scripts/
    cp scripts/system_monitor.py /var/koubou/scripts/
    cp scripts/start_system.sh /var/koubou/scripts/
    cp scripts/check_lmstudio.sh /var/koubou/scripts/
    
    # 実行権限付与
    chmod +x /var/koubou/scripts/*.sh
    chmod +x /var/koubou/scripts/*.py
    chmod +x /var/koubou/scripts/workers/*.py
    
    success "スクリプトをコピーしました"
}

# Pythonパッケージインストール
install_python_packages() {
    echo ""
    echo "Pythonパッケージをインストール中..."
    
    # 必要なパッケージ
    PACKAGES="requests pyyaml flask"
    
    for package in $PACKAGES; do
        if python3 -c "import $package" 2>/dev/null; then
            success "$package は既にインストール済み"
        else
            pip3 install $package --user
            success "$package をインストールしました"
        fi
    done
}

# LMStudioチェック
check_lmstudio() {
    echo ""
    echo "LMStudioの接続を確認中..."
    
    if /var/koubou/scripts/check_lmstudio.sh 2>/dev/null; then
        success "LMStudioに接続できました"
    else
        warning "LMStudioに接続できません"
        echo "  1. LMStudioを起動してください"
        echo "  2. gpt-oss-20bモデルをロードしてください"
        echo "  3. ポート1234でサーバーが起動していることを確認してください"
    fi
}

# 最終確認
final_check() {
    echo ""
    echo "========================================="
    echo "セットアップ完了!"
    echo "========================================="
    echo ""
    echo "次のステップ:"
    echo "1. LMStudioでgpt-oss-20bモデルを起動"
    echo "2. システムを起動:"
    echo "   cd /var/koubou/scripts"
    echo "   ./start_system.sh"
    echo ""
    echo "3. Claude Codeで以下のMCPツールが使用可能:"
    echo "   - koubou_delegate_task"
    echo "   - koubou_get_task_status"
    echo "   - koubou_list_tasks"
    echo "   - koubou_get_worker_status"
    echo ""
}

# メイン処理
main() {
    check_prerequisites
    create_directories
    init_database
    create_configs
    copy_scripts
    install_python_packages
    check_lmstudio
    final_check
}

# 実行
main