#!/usr/bin/env python3
"""
統合テスト - リモートワーカーを含む総合テスト
"""

import os
import sys
import time
import json
import requests
from datetime import datetime

KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
sys.path.insert(0, os.path.join(KOUBOU_HOME, 'scripts'))

from common.database import get_db_manager

def create_test_tasks():
    """テスト用タスクを作成"""
    db = get_db_manager(f"{KOUBOU_HOME}/db/koubou.db")
    
    test_tasks = [
        {
            'task_id': f'integration_test_high_{int(time.time())}',
            'content': json.dumps({
                'type': 'code_generation',
                'prompt': 'Create a Python function that implements the Fibonacci sequence with memoization for optimization'
            }),
            'priority': 9
        },
        {
            'task_id': f'integration_test_med1_{int(time.time())}',
            'content': json.dumps({
                'type': 'translation',
                'prompt': 'Translate to Japanese: "The workshop system efficiently manages distributed AI workers"'
            }),
            'priority': 6
        },
        {
            'task_id': f'integration_test_med2_{int(time.time())}',
            'content': json.dumps({
                'type': 'documentation',
                'prompt': 'Write a brief documentation for a REST API endpoint that returns user profile data'
            }),
            'priority': 5
        },
        {
            'task_id': f'integration_test_low_{int(time.time())}',
            'content': json.dumps({
                'type': 'general',
                'prompt': 'Generate a simple greeting message for morning time'
            }),
            'priority': 2
        }
    ]
    
    created_tasks = []
    for task in test_tasks:
        result = db.create_task(
            task_id=task['task_id'],
            content=task['content'],
            priority=task['priority']
        )
        if result:
            created_tasks.append(task['task_id'])
            print(f"✅ Created task: {task['task_id']} (priority={task['priority']})")
    
    return created_tasks


def monitor_tasks(task_ids, timeout=120):
    """タスクの処理状況を監視"""
    db = get_db_manager(f"{KOUBOU_HOME}/db/koubou.db")
    start_time = time.time()
    completed_tasks = []
    task_results = {}
    
    print("\n📊 Monitoring task processing...")
    print("-" * 60)
    
    while time.time() - start_time < timeout:
        for task_id in task_ids:
            if task_id in completed_tasks:
                continue
            
            with db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT status, assigned_to, result
                    FROM task_master
                    WHERE task_id = ?
                """, (task_id,))
                row = cursor.fetchone()
                
                if row:
                    status, worker, result = row
                    
                    if status == 'completed':
                        completed_tasks.append(task_id)
                        task_results[task_id] = {
                            'worker': worker,
                            'result': result,
                            'time': time.time() - start_time
                        }
                        print(f"✅ {task_id} completed by {worker} ({task_results[task_id]['time']:.1f}s)")
                    elif status == 'in_progress':
                        print(f"⏳ {task_id} in progress by {worker}")
                    elif status == 'pending':
                        print(f"⏸️  {task_id} pending")
        
        if len(completed_tasks) == len(task_ids):
            print("\n🎉 All tasks completed!")
            break
        
        time.sleep(5)
    
    return task_results


def check_api_endpoints():
    """APIエンドポイントの動作確認"""
    print("\n🔍 Checking API endpoints...")
    print("-" * 60)
    
    endpoints = [
        ('MCP Server', 'http://localhost:8765/health'),
        ('Log API - Workers', 'http://localhost:8768/api/workers/status'),
        ('Log API - Logs', 'http://localhost:8768/api/logs/recent?limit=5'),
        ('Log API - Stats', 'http://localhost:8768/api/logs/stats'),
    ]
    
    results = {}
    for name, url in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                results[name] = 'OK'
                print(f"✅ {name}: OK")
                
                # ワーカー情報を表示
                if 'workers' in data:
                    for worker in data['workers']:
                        location_icon = '💻' if worker['location'] == 'local' else '🌐'
                        print(f"   {location_icon} {worker['worker_id']}: {worker['status']} ({worker['location']})")
            else:
                results[name] = f"Error {response.status_code}"
                print(f"❌ {name}: HTTP {response.status_code}")
        except Exception as e:
            results[name] = f"Failed: {e}"
            print(f"❌ {name}: {e}")
    
    return results


def generate_report(task_results, api_results):
    """テスト結果レポートを生成"""
    report = []
    report.append("\n" + "=" * 60)
    report.append("🏭 工房システム統合テストレポート")
    report.append(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 60)
    
    # タスク処理結果
    report.append("\n📋 タスク処理結果:")
    report.append("-" * 40)
    
    total_tasks = len(task_results)
    if total_tasks > 0:
        local_tasks = sum(1 for r in task_results.values() if 'local' in r['worker'])
        remote_tasks = sum(1 for r in task_results.values() if 'remote' in r['worker'])
        avg_time = sum(r['time'] for r in task_results.values()) / total_tasks
        
        report.append(f"  総タスク数: {total_tasks}")
        report.append(f"  ローカル処理: {local_tasks}")
        report.append(f"  リモート処理: {remote_tasks}")
        report.append(f"  平均処理時間: {avg_time:.1f}秒")
        
        report.append("\n  詳細:")
        for task_id, result in task_results.items():
            worker_icon = '💻' if 'local' in result['worker'] else '🌐'
            report.append(f"    {worker_icon} {task_id}")
            report.append(f"       Worker: {result['worker']}")
            report.append(f"       Time: {result['time']:.1f}s")
    else:
        report.append("  ⚠️ タスクが完了しませんでした")
    
    # API状態
    report.append("\n🔌 API状態:")
    report.append("-" * 40)
    for api, status in api_results.items():
        icon = '✅' if status == 'OK' else '❌'
        report.append(f"  {icon} {api}: {status}")
    
    # 総合評価
    report.append("\n🎯 総合評価:")
    report.append("-" * 40)
    
    success_rate = (len(task_results) / 4) * 100 if task_results else 0
    api_health = sum(1 for s in api_results.values() if s == 'OK') / len(api_results) * 100
    
    if success_rate == 100 and api_health == 100:
        report.append("  ✅ 統合テスト成功！")
        report.append("  全システムが正常に動作しています")
    elif success_rate >= 75:
        report.append("  ⚠️ 部分的に成功")
        report.append(f"  タスク成功率: {success_rate:.0f}%")
        report.append(f"  API稼働率: {api_health:.0f}%")
    else:
        report.append("  ❌ テスト失敗")
        report.append(f"  タスク成功率: {success_rate:.0f}%")
        report.append(f"  API稼働率: {api_health:.0f}%")
    
    report.append("\n" + "=" * 60)
    
    return "\n".join(report)


def main():
    """メイン処理"""
    print("🧪 Starting Integration Test...")
    print("=" * 60)
    
    # APIエンドポイント確認
    api_results = check_api_endpoints()
    
    # テストタスク作成
    print("\n📝 Creating test tasks...")
    task_ids = create_test_tasks()
    
    # タスク処理監視
    if task_ids:
        task_results = monitor_tasks(task_ids, timeout=120)
    else:
        print("❌ Failed to create test tasks")
        task_results = {}
    
    # レポート生成
    report = generate_report(task_results, api_results)
    print(report)
    
    # ファイルに保存
    report_file = f"{KOUBOU_HOME}/logs/integration_test_{int(time.time())}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"\n📄 Report saved to: {report_file}")
    
    # ダッシュボードURL表示
    print("\n🖥️ Dashboard URL: http://localhost:8080/")
    print("   View real-time worker status and logs in the dashboard")
    
    return 0 if task_results else 1


if __name__ == '__main__':
    sys.exit(main())