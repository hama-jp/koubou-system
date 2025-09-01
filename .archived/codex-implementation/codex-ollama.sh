#!/bin/bash
# Codex CLI wrapper for Ollama with gpt-oss:20b

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

echo "🤖 Codex CLI with Ollama (gpt-oss:20b)"
echo "📁 Project: $PROJECT_ROOT"
echo ""

# Codex CLIを実行（--ossフラグでOllamaを使用）
exec codex \
    --oss \
    --model "gpt-oss:20b" \
    --sandbox workspace-write \
    --ask-for-approval never \
    --trusted-workspace \
    -C "$PROJECT_ROOT" \
    "$@"