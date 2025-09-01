#!/usr/bin/env python3
"""長時間タスクのテスト - ワーカーが正しく保護されるか確認"""

import time
import json
import requests
from datetime import datetime

def create_long_task():
    """65秒かかるタスクを作成（ハートビートタイムアウトより長い）"""
    
    # タスクを作成
    task_data = {
        "type": "general",
        "prompt": "Please count slowly from 1 to 70, pausing for 1 second between each number. This is a test of long-running task handling.",
        "priority": 10,
        "sync": False  # 非同期で実行
    }
    
    print(f"[{datetime.now()}] Creating long-running task...")
    response = requests.post(
        "http://localhost:8765/task/delegate",
        json=task_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        task_id = result.get("task_id")
        print(f"[{datetime.now()}] Task created: {task_id}")
        return task_id
    else:
        print(f"Failed to create task: {response.status_code}")
        print(response.text)
        return None

def monitor_task(task_id):
    """タスクの状態を監視"""
    print(f"\n[{datetime.now()}] Monitoring task {task_id}...")
    print("This will take about 70 seconds. Worker should NOT be killed during this time.")
    print("-" * 60)
    
    start_time = time.time()
    last_status = None
    
    while True:
        elapsed = int(time.time() - start_time)
        
        # タスクステータスを取得
        response = requests.get(f"http://localhost:8765/task/status/{task_id}")
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            if status != last_status:
                print(f"[{elapsed:3d}s] Task status: {status}")
                last_status = status
            
            if status == "completed":
                print(f"\n[{datetime.now()}] Task completed successfully!")
                result = data.get("result", {})
                if result:
                    print(f"Success: {result.get('success')}")
                    if result.get('output'):
                        print(f"Output length: {len(result.get('output'))} chars")
                break
            elif status == "failed":
                print(f"\n[{datetime.now()}] Task failed!")
                print(f"Result: {data.get('result')}")
                break
        
        # ワーカー状態も確認
        if elapsed % 10 == 0:  # 10秒ごとに
            workers_response = requests.get("http://localhost:8765/workers/status")
            if workers_response.status_code == 200:
                workers = workers_response.json().get("workers", [])
                active_workers = [w for w in workers if w.get("status") != "offline"]
                if active_workers:
                    for w in active_workers:
                        print(f"[{elapsed:3d}s] Worker {w['worker_id']}: {w['status']}")
        
        time.sleep(2)
        
        # タイムアウト（3分）
        if elapsed > 180:
            print(f"\n[{datetime.now()}] Test timeout after 3 minutes")
            break

def main():
    print("=" * 60)
    print("Long-running Task Protection Test")
    print("=" * 60)
    print("\nThis test will:")
    print("1. Create a task that takes ~70 seconds")
    print("2. Monitor that the worker is NOT killed during processing")
    print("3. Verify task completes successfully")
    print("\nNOTE: Worker heartbeat timeout is typically 60 seconds")
    print("=" * 60)
    
    # タスクを作成
    task_id = create_long_task()
    if task_id:
        # タスクを監視
        monitor_task(task_id)
    
    print("\nTest completed!")

if __name__ == "__main__":
    main()