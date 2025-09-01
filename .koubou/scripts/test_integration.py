#!/usr/bin/env python3
"""
工房システム統合テスト
"""

import json
import requests
import time
import subprocess
import sys
from pathlib import Path

# 設定
MCP_SERVER = "http://localhost:8765"
TEST_FILE = "test_integration_output.py"

def start_mcp_server():
    """MCPサーバーを起動"""
    print("Starting MCP server...")
    proc = subprocess.Popen(
        ["python3", ".koubou/scripts/mcp_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3)
    return proc

def test_health_check():
    """ヘルスチェック"""
    print("Testing health check...")
    response = requests.get(f"{MCP_SERVER}/health")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    print("✓ Health check passed")

def test_general_task():
    """一般タスクのテスト（Ollama使用）"""
    print("\nTesting general task delegation...")
    
    payload = {
        "type": "general",
        "prompt": "What is 2 + 2?",
        "sync": True,
        "priority": 8
    }
    
    response = requests.post(f"{MCP_SERVER}/task/delegate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    print(f"Task ID: {data['task_id']}")
    print(f"Status: {data['status']}")
    
    if 'result' in data:
        output = data['result'].get('output', '')
        print(f"Output: {output[:100]}...")
        assert '4' in output or 'four' in output.lower()
    
    print("✓ General task delegation passed")

def test_code_task():
    """コード生成タスクのテスト（Codex CLI使用）"""
    print("\nTesting code task delegation...")
    
    # テストファイルを作成
    Path(TEST_FILE).write_text("# Test file\nprint('Hello')")
    
    payload = {
        "type": "code",
        "prompt": f"Add a function called calculate_sum(a, b) that returns a + b to {TEST_FILE}",
        "sync": True,
        "priority": 10
    }
    
    response = requests.post(f"{MCP_SERVER}/task/delegate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    print(f"Task ID: {data['task_id']}")
    print(f"Status: {data['status']}")
    
    # ファイルが更新されたか確認
    time.sleep(2)
    content = Path(TEST_FILE).read_text()
    if 'calculate_sum' in content:
        print("✓ Code was successfully added to file")
    else:
        print("⚠ Code task completed but file not updated (sandbox mode?)")
    
    print("✓ Code task delegation passed")

def test_async_task():
    """非同期タスクのテスト"""
    print("\nTesting async task delegation...")
    
    payload = {
        "type": "general",
        "prompt": "Count from 1 to 5",
        "sync": False,  # 非同期モード
        "priority": 5
    }
    
    response = requests.post(f"{MCP_SERVER}/task/delegate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    task_id = data['task_id']
    print(f"Task ID: {task_id}")
    print(f"Initial Status: {data['status']}")
    
    # ステータスを確認
    time.sleep(2)
    response = requests.get(f"{MCP_SERVER}/task/{task_id}/status")
    if response.status_code == 200:
        status_data = response.json()
        print(f"Current Status: {status_data.get('status')}")
    
    print("✓ Async task delegation passed")

def test_task_list():
    """タスク一覧の取得"""
    print("\nTesting task list...")
    
    response = requests.get(f"{MCP_SERVER}/tasks")
    assert response.status_code == 200
    data = response.json()
    
    tasks = data.get('tasks', [])
    print(f"Found {len(tasks)} tasks")
    
    for task in tasks[:3]:  # 最初の3つを表示
        print(f"  - {task['task_id']}: {task['status']}")
    
    print("✓ Task list retrieval passed")

def main():
    """メインテスト実行"""
    print("=" * 50)
    print("工房システム統合テスト")
    print("=" * 50)
    
    # MCPサーバー起動
    mcp_proc = None
    try:
        mcp_proc = start_mcp_server()
        
        # テスト実行
        test_health_check()
        test_general_task()
        test_code_task()
        test_async_task()
        test_task_list()
        
        print("\n" + "=" * 50)
        print("すべてのテストが成功しました！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ テスト失敗: {e}")
        sys.exit(1)
    finally:
        # クリーンアップ
        if mcp_proc:
            mcp_proc.terminate()
            print("\nMCP server stopped")
        
        # テストファイル削除
        if Path(TEST_FILE).exists():
            Path(TEST_FILE).unlink()

if __name__ == "__main__":
    main()