#!/bin/bash
# Codex CLI exec wrapper for Ollama with proper flag placement

# プロジェクトルート設定
KOUBOU_HOME="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.." && pwd)"

# 作業ディレクトリを設定
cd "$PROJECT_ROOT"

# Ollamaが起動しているか確認
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Starting Ollama..."
    OLLAMA_NUM_GPU=999 OLLAMA_GPU_LAYERS=999 ollama serve > "$KOUBOU_HOME/logs/ollama.log" 2>&1 &
    sleep 3
fi

echo "🤖 Codex CLI exec with Ollama (gpt-oss:20b)"
echo "📁 Project: $PROJECT_ROOT"
echo ""

# execコマンドの後にフラグを配置（重要！）  
# Linux環境でLandlockが無い場合の対応
export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1

exec codex exec \
    --oss \
    --model "gpt-oss:20b" \
    --sandbox danger-full-access \
    -c "approval_policy=\"never\"" \
    -c "trust_level=\"trusted\"" \
    "$@"