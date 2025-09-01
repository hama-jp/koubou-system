#!/usr/bin/env bash
# 🏭 工房システム Codex CLI - GPU最適化版 (O3推奨設定)
set -euo pipefail

KOUBOU_HOME="$(cd "$(dirname "$0")/.."; pwd)"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.."; pwd)"


# GPU最適化Ollama環境変数 (O3推奨)
export OLLAMA_NUM_GPU=-1
export OLLAMA_GPU_LAYERS=-1
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_DEBUG=0  # 必要時は1に変更

# Ollamaが起動しているか確認（ポーリング方式）
if ! curl -sf http://localhost:11434/v1/models >/dev/null 2>&1; then
    echo "▶ Starting Ollama with full-GPU off-load..."
    nohup ollama serve >> "$KOUBOU_HOME/logs/ollama.log" 2>&1 &
    
    # Ollamaが準備完了まで待機
    echo "⏳ Waiting for Ollama to be ready..."
    until curl -sf http://localhost:11434/v1/models >/dev/null 2>&1; do
        sleep 1
    done
    echo "✅ Ollama is ready"
fi

echo "🏭 Codex (OSS) — GPU mode active"
echo "📁 Project: $PROJECT_ROOT"
echo "🔥 GPU: Full off-load enabled"
echo "📝 Mode: Full-auto execution"
echo ""

# O3推奨の最適化Codex CLI実行 (TTY問題対応版)
# 環境変数でTTYを強制
export CODEX_FORCE_TTY=1
unset CI

exec codex exec \
    --oss \
    -m gpt-oss:20b \
    --dangerously-bypass-approvals-and-sandbox \
    --cd "$PROJECT_ROOT" \
    --skip-git-repo-check \
    "$@"