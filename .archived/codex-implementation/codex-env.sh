#!/bin/bash
# Codex CLI environment wrapper for Koubou System

# プロジェクト設定
export KOUBOU_HOME="$(cd "$(dirname "$0")/.." && pwd)"
export PROJECT_ROOT="$(cd "$KOUBOU_HOME/.." && pwd)"

# LMStudio設定を環境変数で設定
export OPENAI_API_BASE="http://192.168.11.29:1234/v1"
export OPENAI_API_KEY="not-needed"

# 作業ディレクトリを設定
cd "$PROJECT_ROOT"

echo "🤖 Codex CLI for Koubou System"
echo "📁 Project: $PROJECT_ROOT"
echo "🔗 LMStudio: $OPENAI_API_BASE"
echo "🧠 Model: gpt-oss-20b@f16"
echo ""

# Codex CLIを起動
exec codex \
    --model "gpt-oss-20b@f16" \
    --full-auto \
    -C "$PROJECT_ROOT" \
    "$@"