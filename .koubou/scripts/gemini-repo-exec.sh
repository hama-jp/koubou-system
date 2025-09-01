#!/bin/bash
# Gemini Repo CLI wrapper for worker execution
# ollama + gpt-oss:20b 経由で実行

set -e

# 環境変数設定
KOUBOU_HOME="${KOUBOU_HOME:-/home/hama/project/koubou-system/.koubou}"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.." && pwd)"

# プロンプトの取得（引数またはstdin）- シェルインジェクション対策
if [ -n "$1" ]; then
    PROMPT="$1"
elif [ ! -t 0 ]; then
    # stdinから読み取り（サイズ制限付き）
    PROMPT=$(head -c 10000 | cat)
else
    echo "Error: No prompt provided" >&2
    echo "Usage: $0 'prompt' or echo 'prompt' | $0" >&2
    exit 1
fi

if [ -z "$PROMPT" ]; then
    echo "Error: Empty prompt" >&2
    exit 1
fi

# プロンプトの安全性チェック（基本的な検証）
if [ ${#PROMPT} -gt 10000 ]; then
    echo "Error: Prompt too long (max 10000 characters)" >&2
    exit 1
fi

# 作業ディレクトリを設定
cd "$PROJECT_ROOT"

# Ollamaの動作確認
if ! curl -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
    echo "Error: Ollama API is not responding at http://localhost:11434" >&2
    exit 1
fi

# gemini-repo-cli を実行
# タイムアウトを600秒（10分）に設定（ワーカーのタイムアウトと一致）
timeout 600 "$KOUBOU_HOME/venv/bin/python" -m gemini_repo.cli \
    --provider ollama \
    --ollama-model gpt-oss:20b \
    koubou-system \
    "generated_content.txt" \
    "$PROMPT" 2>/dev/null || {
    EXIT_CODE=$?
    echo "Error: Gemini Repo CLI execution failed or timed out (exit code: $EXIT_CODE)" >&2
    exit $EXIT_CODE
}