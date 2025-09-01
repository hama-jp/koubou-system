#!/usr/bin/env python3
"""
負荷テスト - 複数タスクを投入してワーカープールの動作を確認
"""

import argparse
import json
import requests
import time
import random
import threading
from datetime import datetime

MCP_SERVER = "http://localhost:8765"

# テスト用のタスク
SAMPLE_TASKS = [
    {
        "type": "general",
        "prompt": "Write a haiku about programming",
        "priority": random.randint(1, 10)
    },
    {
        "type": "general", 
        "prompt": "Explain recursion in simple terms",
        "priority": random.randint(1, 10)
    },
    {
        "type": "general",
        "prompt": "What are the benefits of unit testing?",
        "priority": random.randint(1, 10)
    },
    {
        "type": "code",
        "prompt": "Write a Python function to calculate fibonacci numbers",
        "priority": random.randint(5, 10)
    },
    {
        "type": "general",
        "prompt": "List 5 design patterns in software engineering",
        "priority": random.randint(1, 10)
    },
    {
        "type": "code",
        "prompt": "Create a simple Python decorator that measures execution time",
        "priority": random.randint(5, 10)
    },
    {
        "type": "general",
        "prompt": "Explain the difference between TCP and UDP",
        "priority": random.randint(1, 10)
    },
    {
        "type": "general",
        "prompt": "What is the CAP theorem?",
        "priority": random.randint(1, 10)
    }
]

def submit_task(task_data):
    """タスクを送信"""
    try:
        # 非同期モードで送信（ワーカーが処理）
        task_data["sync"] = False
        
        response = requests.post(f"{MCP_SERVER}/task/delegate", json=task_data)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Task submitted: {data['task_id']} - {task_data['prompt'][:50]}...")
            return data['task_id']
        else:
            print(f"✗ Failed to submit task: {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ Error submitting task: {e}")
        return None

def check_task_status(task_id):
    """タスクのステータスを確認"""
    try:
        response = requests.get(f"{MCP_SERVER}/task/{task_id}/status")
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def monitor_tasks(task_ids):
    """タスクの完了を監視"""
    print("\n📊 Monitoring task completion...")
    
    completed = set()
    start_time = time.time()
    
    while len(completed) < len(task_ids):
        time.sleep(2)
        
        for task_id in task_ids:
            if task_id not in completed:
                status = check_task_status(task_id)
                if status and status.get('status') in ['completed', 'failed']:
                    completed.add(task_id)
                    elapsed = time.time() - start_time
                    print(f"  • {task_id}: {status['status']} ({elapsed:.1f}s)")
        
        # タイムアウト（5分）
        if time.time() - start_time > 300:
            print("⚠️ Timeout waiting for tasks to complete")
            break
    
    elapsed_total = time.time() - start_time
    print(f"\n✅ {len(completed)}/{len(task_ids)} tasks completed in {elapsed_total:.1f} seconds")

def burst_test(num_tasks=20):
    """バーストテスト - 一度に大量のタスクを投入"""
    print(f"\n🚀 Burst Test: Submitting {num_tasks} tasks...")
    
    task_ids = []
    for i in range(num_tasks):
        # ランダムにタスクを選択
        task = random.choice(SAMPLE_TASKS).copy()
        task['priority'] = random.randint(1, 10)
        
        task_id = submit_task(task)
        if task_id:
            task_ids.append(task_id)
        
        # 少し間隔を空ける
        time.sleep(0.1)
    
    print(f"Submitted {len(task_ids)} tasks")
    return task_ids

def gradual_test(duration=30, rate=2):
    """段階的テスト - 一定のレートでタスクを投入"""
    print(f"\n📈 Gradual Test: Submitting {rate} tasks/sec for {duration} seconds...")
    
    task_ids = []
    start_time = time.time()
    
    while time.time() - start_time < duration:
        for _ in range(rate):
            task = random.choice(SAMPLE_TASKS).copy()
            task['priority'] = random.randint(1, 10)
            
            task_id = submit_task(task)
            if task_id:
                task_ids.append(task_id)
        
        time.sleep(1)
    
    print(f"Submitted {len(task_ids)} tasks over {duration} seconds")
    return task_ids

def show_system_stats():
    """システム統計を表示"""
    try:
        response = requests.get(f"{MCP_SERVER}/tasks")
        if response.status_code == 200:
            data = response.json()
            tasks = data.get('tasks', [])
            
            # ステータス別に集計
            stats = {}
            for task in tasks:
                status = task.get('status', 'unknown')
                stats[status] = stats.get(status, 0) + 1
            
            print("\n📊 System Statistics:")
            print("="*40)
            for status, count in stats.items():
                print(f"  {status}: {count} tasks")
            print(f"  Total: {len(tasks)} tasks")
            print("="*40)
    except Exception as e:
        print(f"Failed to get system stats: {e}")

def main():
    """メイン実行"""
    parser = argparse.ArgumentParser(description="工房システム 負荷テストスクリプト")
    parser.add_argument("test_type", nargs='?', default="burst", choices=["burst", "gradual", "heavy", "custom"], help="実行するテストの種類")
    parser.add_argument("-n", "--num_tasks", type=int, default=20, help="カスタムテストで投入するタスク数")
    parser.add_argument("-d", "--duration", type=int, default=30, help="段階的テストの実行時間（秒）")
    parser.add_argument("-r", "--rate", type=int, default=2, help="段階的テストの秒間タスク投入数")

    args = parser.parse_args()

    print("="*50)
    print("工房システム 負荷テスト")
    print("="*50)
    
    # システム状態を確認
    try:
        response = requests.get(f"{MCP_SERVER}/health")
        if response.status_code != 200:
            print("❌ MCP Server is not running!")
            return
    except:
        print("❌ Cannot connect to MCP Server at", MCP_SERVER)
        return
    
    print("✅ MCP Server is running")
    
    task_ids = []
    if args.test_type == "burst":
        task_ids = burst_test(20)
    elif args.test_type == "gradual":
        task_ids = gradual_test(args.duration, args.rate)
    elif args.test_type == "heavy":
        task_ids = burst_test(50)
    elif args.test_type == "custom":
        task_ids = burst_test(args.num_tasks)
    
    if task_ids:
        monitor_tasks(task_ids)
        # 最終統計を表示
        show_system_stats()

if __name__ == "__main__":
    main()
