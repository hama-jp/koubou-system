#!/usr/bin/env python3
"""
リモートワーカー統合テスト
実際にタスクを投入してローカル・リモートワーカーで処理をテスト
"""

import os
import sys
import time
import json
import sqlite3
import logging

# プロジェクトのパスを追加
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
sys.path.insert(0, os.path.join(KOUBOU_HOME, 'scripts'))

from common.database import get_db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_tasks(db_manager):
    """テスト用タスクを作成"""
    test_tasks = [
        {
            'task_id': f'test_high_{int(time.time())}',
            'content': 'Write a Python function to calculate factorial',
            'priority': 9,
            'type': 'code_generation'
        },
        {
            'task_id': f'test_medium_{int(time.time())}',
            'content': 'Translate this to Japanese: "Hello World"',
            'priority': 5,
            'type': 'translation'
        },
        {
            'task_id': f'test_low_{int(time.time())}',
            'content': 'Generate a simple greeting message',
            'priority': 2,
            'type': 'general'
        }
    ]
    
    created_tasks = []
    for task in test_tasks:
        result = db_manager.create_task(
            task_id=task['task_id'],
            content=json.dumps({'type': task['type'], 'prompt': task['content']}),
            priority=task['priority']
        )
        if result:
            created_tasks.append(task['task_id'])
            logger.info(f"✅ Created task: {task['task_id']} (priority={task['priority']})")
    
    return created_tasks


def monitor_tasks(db_manager, task_ids, timeout=60):
    """タスクの処理状況を監視"""
    start_time = time.time()
    completed_tasks = []
    
    while time.time() - start_time < timeout:
        for task_id in task_ids:
            if task_id in completed_tasks:
                continue
                
            with db_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT status, assigned_to, result
                    FROM task_master
                    WHERE task_id = ?
                """, (task_id,))
                row = cursor.fetchone()
                
                if row and row[0] == 'completed':
                    completed_tasks.append(task_id)
                    logger.info(f"✅ Task {task_id} completed by {row[1]}")
                    if row[2]:
                        result = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                        logger.info(f"   Result preview: {str(result)[:100]}...")
                elif row and row[0] == 'in_progress':
                    logger.info(f"⏳ Task {task_id} in progress by {row[1]}")
        
        if len(completed_tasks) == len(task_ids):
            logger.info("🎉 All tasks completed!")
            break
        
        time.sleep(5)
    
    return completed_tasks


def check_worker_status(db_manager):
    """ワーカーの状態を確認"""
    with db_manager.get_connection() as conn:
        cursor = conn.execute("""
            SELECT worker_id, location, status, performance_factor,
                   tasks_completed, tasks_failed
            FROM workers
            WHERE datetime('now', '-120 seconds') <= last_heartbeat
               OR status = 'idle'
            ORDER BY location, worker_id
        """)
        workers = cursor.fetchall()
    
    logger.info("\n📊 Worker Status:")
    logger.info("-" * 60)
    for worker in workers:
        location_icon = "💻" if worker[1] == 'local' else "🌐"
        logger.info(f"{location_icon} {worker[0]}")
        logger.info(f"   Location: {worker[1]}, Status: {worker[2]}")
        logger.info(f"   Performance: {worker[3]:.2f}x")
        logger.info(f"   Tasks: {worker[4]} completed, {worker[5]} failed")
    logger.info("-" * 60)


def main():
    """メインテスト処理"""
    logger.info("🧪 Starting Remote Worker Integration Test")
    logger.info("=" * 60)
    
    # データベース接続
    db_path = f"{KOUBOU_HOME}/db/koubou.db"
    db_manager = get_db_manager(db_path)
    
    # ワーカー状態確認
    check_worker_status(db_manager)
    
    # テストタスク作成
    logger.info("\n📝 Creating test tasks...")
    task_ids = create_test_tasks(db_manager)
    
    if not task_ids:
        logger.error("❌ Failed to create test tasks")
        return 1
    
    logger.info(f"Created {len(task_ids)} test tasks")
    
    # タスク処理を監視
    logger.info("\n🔄 Monitoring task processing...")
    completed = monitor_tasks(db_manager, task_ids, timeout=120)
    
    # 結果サマリー
    logger.info("\n📈 Test Summary:")
    logger.info("-" * 60)
    logger.info(f"Total tasks: {len(task_ids)}")
    logger.info(f"Completed: {len(completed)}")
    logger.info(f"Success rate: {len(completed) / len(task_ids) * 100:.1f}%")
    
    # 最終的なワーカー状態
    check_worker_status(db_manager)
    
    if len(completed) == len(task_ids):
        logger.info("\n✅ Integration test PASSED!")
        return 0
    else:
        logger.info("\n⚠️ Integration test INCOMPLETE")
        return 1


if __name__ == "__main__":
    sys.exit(main())