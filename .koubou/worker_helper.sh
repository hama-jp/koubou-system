#!/bin/bash
# ワーカー起動ヘルパースクリプト

set -e

WORKER_ID="${1:-test_worker_1}"
KOUBOU_HOME="${KOUBOU_HOME:-/home/hama/project/koubou-system/.koubou}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "🏭 ワーカー起動ヘルパー"
echo "WORKER_ID: $WORKER_ID"
echo "KOUBOU_HOME: $KOUBOU_HOME"
echo "PROJECT_ROOT: $PROJECT_ROOT"

# プロジェクトルートに移動
cd "$PROJECT_ROOT"

echo "📍 現在位置: $(pwd)"
echo "🔍 ワーカースクリプト確認..."

if [ -f ".koubou/scripts/workers/local_worker.py" ]; then
    echo "✅ ワーカースクリプト見つかりました: .koubou/scripts/workers/local_worker.py"
    echo "🚀 ワーカー起動中..."
    
    # 環境変数設定してuv runで起動
    export WORKER_ID="$WORKER_ID"
    export KOUBOU_HOME="$KOUBOU_HOME"
    
    uv run .koubou/scripts/workers/local_worker.py "$@"
else
    echo "❌ ワーカースクリプトが見つかりません: .koubou/scripts/workers/local_worker.py"
    echo "📂 利用可能なスクリプト:"
    find .koubou/scripts -name "*.py" | grep worker | head -5
    exit 1
fi