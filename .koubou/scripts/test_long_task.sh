#!/bin/bash
# 長時間タスクのテストスクリプト

echo "=== Long Task Test Script ==="
echo "Testing timeout behavior for gemini-cli tasks"
echo ""

# 環境変数設定
KOUBOU_HOME="${KOUBOU_HOME:-/home/hama/project/koubou-system/.koubou}"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.." && pwd)"

# テスト1: 短いタスク（成功するはず）
echo "[Test 1] Short task (should succeed):"
echo "----------------------------------------"
START_TIME=$(date +%s)
echo "Write a haiku about computers." | timeout 30 $KOUBOU_HOME/scripts/gemini-exec.sh 2>&1
EXIT_CODE=$?
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo ""
echo "Exit code: $EXIT_CODE"
echo "Elapsed time: ${ELAPSED}s"
echo ""

# テスト2: 中程度のタスク（成功するはず）
echo "[Test 2] Medium task (should succeed):"
echo "----------------------------------------"
START_TIME=$(date +%s)
echo "Write a detailed essay about distributed systems with at least 20 key points." | timeout 200 $KOUBOU_HOME/scripts/gemini-exec.sh 2>&1 | head -20
EXIT_CODE=$?
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "... (output truncated)"
echo ""
echo "Exit code: $EXIT_CODE"
echo "Elapsed time: ${ELAPSED}s"
echo ""

# テスト3: gemini-cli直接実行（比較用）
echo "[Test 3] Direct gemini-cli execution:"
echo "----------------------------------------"
cd $PROJECT_ROOT/gemini-cli-local
START_TIME=$(date +%s)
echo "Calculate the factorial of 10 and show the calculation steps." | timeout 30 npm run start 2>/dev/null
EXIT_CODE=$?
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo ""
echo "Exit code: $EXIT_CODE"
echo "Elapsed time: ${ELAPSED}s"
echo ""

# テスト4: タイムアウト値の確認
echo "[Test 4] Timeout configuration check:"
echo "----------------------------------------"
echo -n "gemini-exec.sh timeout: "
grep "^timeout" $KOUBOU_HOME/scripts/gemini-exec.sh | grep -o "[0-9]\+" | head -1
echo -n "local_worker.py timeout: "
grep "self.timeout = " $KOUBOU_HOME/scripts/workers/local_worker.py | grep -o "[0-9]\+" | head -1
echo ""

echo "=== Test Complete ==="