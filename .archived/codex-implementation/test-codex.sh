#!/bin/bash
# Codex CLI connection test script

echo "Testing Codex CLI with LMStudio..."
echo "=================================="

# LMStudio接続確認
echo -n "1. Checking LMStudio connection... "
if curl -s http://192.168.11.29:1234/v1/models > /dev/null 2>&1; then
    echo "✓"
else
    echo "✗"
    echo "Error: Cannot connect to LMStudio at http://192.168.11.29:1234"
    exit 1
fi

# Codex CLIの存在確認
echo -n "2. Checking Codex CLI... "
if command -v codex > /dev/null 2>&1; then
    echo "✓ ($(codex --version))"
else
    echo "✗"
    echo "Error: Codex CLI not found"
    exit 1
fi

# 簡単なテストを実行
echo "3. Running simple test..."
echo ""

# テストコマンド（ファイル一覧表示）
.koubou/scripts/codex-local.sh "List the files in the current directory" --sandbox read-only