#!/bin/bash
# Codex CLI wrapper for LMStudio API (OpenAI compatible)

# プロジェクトルート設定
KOUBOU_HOME="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.." && pwd)"
CONFIG_FILE="$KOUBOU_HOME/config/codex-lmstudio.toml"

# 作業ディレクトリを設定
cd "$PROJECT_ROOT"

# LMStudioが起動しているか確認
if ! curl -s http://192.168.11.29:1234/v1/models > /dev/null 2>&1; then
    echo "⚠️  LMStudio API is not responding at http://192.168.11.29:1234/v1"
    echo "Please ensure LMStudio is running and the API server is enabled."
    exit 1
fi

echo "🤖 Codex CLI with LMStudio (gpt-oss-20b@f16)"
echo "📁 Project: $PROJECT_ROOT"
echo "🌐 API: http://192.168.11.29:1234/v1"
echo "📋 Config: $CONFIG_FILE"
echo ""

# 環境変数を設定
export OPENAI_API_KEY="not-needed"
export OPENAI_BASE_URL="http://192.168.11.29:1234/v1"
export CODEX_CONFIG="$CONFIG_FILE"

# Codex CLIを実行（GPT-4モデルとして偽装）
exec codex \
    --config "openai.base_url=\"http://192.168.11.29:1234/v1\"" \
    --config "openai.api_key=\"lm-studio\"" \
    --model "gpt-4o" \
    --sandbox workspace-write \
    --ask-for-approval on-failure \
    -C "$PROJECT_ROOT" \
    "$@"