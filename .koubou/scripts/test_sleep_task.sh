#!/bin/bash
# 長時間実行するテストスクリプト

echo "Starting long-running task simulation..."
echo "This will sleep for 75 seconds to test worker protection"

# 75秒間スリープ（ハートビートタイムアウトより長い）
for i in {1..15}; do
    echo "Progress: $((i*5)) seconds elapsed..."
    sleep 5
done

echo "Task completed successfully after 75 seconds!"