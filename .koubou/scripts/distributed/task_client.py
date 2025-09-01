#!/usr/bin/env python3
"""
タスククライアント - 分散ワーカーシステムへのタスク送信
わかりやすい信号名で通信フローを実装
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from distributed.message_queue import get_queue_instance


class TaskClient:
    """タスク送信クライアント"""
    
    def __init__(self, queue_type: str = 'redis'):
        self.queue_type = queue_type
        self.mq = get_queue_instance(queue_type)
        self.client_id = f"client-{uuid.uuid4().hex[:8]}"
        
        # わかりやすいチャンネル名
        self.channels = {
            # タスク関連
            'task_submit': 'tasks/submit',           # タスク送信
            'task_status': 'tasks/status',           # ステータス更新
            'task_result': 'tasks/result',           # 結果通知
            
            # ワーカー管理
            'worker_available': 'workers/available',  # 利用可能ワーカー
            'worker_busy': 'workers/busy',           # ビジー状態
            'worker_idle': 'workers/idle',           # アイドル状態
            
            # システム管理
            'system_health': 'system/health',        # ヘルスチェック
            'system_metrics': 'system/metrics',      # メトリクス
            'system_alert': 'system/alert',          # アラート
        }
        
        self.pending_tasks = {}  # 送信済みタスクの追跡
    
    def connect(self) -> bool:
        """メッセージキューに接続"""
        try:
            if not self.mq.connect(host='localhost', port=6379):
                print("❌ Failed to connect to message queue")
                return False
            
            # 結果チャンネルを購読
            self.mq.subscribe(self.channels['task_result'], self._handle_result)
            self.mq.subscribe(self.channels['task_status'], self._handle_status)
            
            print(f"✅ Client {self.client_id} connected")
            return True
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def submit_task(self, 
                   task_type: str, 
                   prompt: str, 
                   priority: int = 5,
                   requirements: Optional[Dict] = None) -> str:
        """タスクを送信"""
        task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        task_message = {
            'task_id': task_id,
            'client_id': self.client_id,
            'type': task_type,
            'prompt': prompt,
            'priority': priority,
            'requirements': requirements or {},
            'submitted_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        # タスクを送信
        self.mq.publish(self.channels['task_submit'], task_message)
        
        # ペンディングリストに追加
        self.pending_tasks[task_id] = {
            'status': 'submitted',
            'submitted_at': datetime.now(),
            'result': None
        }
        
        print(f"📤 Task submitted: {task_id}")
        print(f"   Type: {task_type}")
        print(f"   Priority: {priority}")
        
        return task_id
    
    def _handle_status(self, data: Dict[str, Any]):
        """ステータス更新を処理"""
        task_id = data.get('task_id')
        status = data.get('status')
        
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id]['status'] = status
            
            # ステータスアイコン
            icons = {
                'queued': '⏳',
                'assigned': '👷',
                'processing': '⚙️',
                'completed': '✅',
                'failed': '❌'
            }
            icon = icons.get(status, '❓')
            
            print(f"{icon} Task {task_id}: {status}")
            
            if 'worker_id' in data:
                print(f"   Assigned to: {data['worker_id']}")
    
    def _handle_result(self, data: Dict[str, Any]):
        """タスク結果を処理"""
        task_id = data.get('task_id')
        status = data.get('status')
        
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id]['status'] = status
            self.pending_tasks[task_id]['completed_at'] = datetime.now()
            
            if status == 'completed':
                result = data.get('result', '')
                self.pending_tasks[task_id]['result'] = result
                
                print(f"\n✅ Task {task_id} completed!")
                print(f"Result:\n{'-'*60}")
                print(result[:500])  # 最初の500文字を表示
                if len(result) > 500:
                    print(f"... (truncated, total {len(result)} chars)")
                print(f"{'-'*60}\n")
                
            elif status == 'failed':
                error = data.get('error', 'Unknown error')
                print(f"\n❌ Task {task_id} failed!")
                print(f"Error: {error}\n")
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """タスクステータスを取得"""
        return self.pending_tasks.get(task_id)
    
    def list_tasks(self):
        """全タスクをリスト表示"""
        print("\n📋 Task List")
        print("=" * 70)
        
        for task_id, info in self.pending_tasks.items():
            status = info['status']
            submitted = info['submitted_at'].strftime('%H:%M:%S')
            
            # ステータスに応じた表示
            if status == 'completed':
                completed = info.get('completed_at')
                if completed:
                    duration = (completed - info['submitted_at']).total_seconds()
                    print(f"✅ {task_id} | {submitted} | Completed in {duration:.1f}s")
                else:
                    print(f"✅ {task_id} | {submitted} | Completed")
            elif status == 'failed':
                print(f"❌ {task_id} | {submitted} | Failed")
            else:
                print(f"⏳ {task_id} | {submitted} | {status}")
        
        print("=" * 70)
    
    def wait_for_task(self, task_id: str, timeout: int = 60) -> bool:
        """タスク完了を待つ"""
        start_time = time.time()
        
        print(f"⏳ Waiting for task {task_id}...")
        
        while time.time() - start_time < timeout:
            task = self.pending_tasks.get(task_id)
            if task:
                if task['status'] in ['completed', 'failed']:
                    return task['status'] == 'completed'
            time.sleep(1)
        
        print(f"⏰ Task {task_id} timed out after {timeout}s")
        return False
    
    def disconnect(self):
        """切断"""
        self.mq.disconnect()
        print(f"👋 Client {self.client_id} disconnected")


def interactive_mode():
    """対話モード"""
    client = TaskClient('redis')
    
    if not client.connect():
        print("Failed to connect to distributed system")
        return
    
    print("\n🚀 Distributed Task Client")
    print("=" * 60)
    print("Commands:")
    print("  submit <type> <prompt> - Submit a task")
    print("  list                   - List all tasks")
    print("  status <task_id>       - Get task status")
    print("  wait <task_id>         - Wait for task completion")
    print("  quit                   - Exit")
    print("=" * 60)
    
    try:
        while True:
            cmd = input("\n> ").strip()
            
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=2)
            command = parts[0].lower()
            
            if command == 'quit':
                break
            
            elif command == 'submit':
                if len(parts) < 3:
                    print("Usage: submit <type> <prompt>")
                    print("Types: general, code, documentation")
                    continue
                
                task_type = parts[1]
                prompt = parts[2]
                
                # 優先度を聞く
                priority_str = input("Priority (1-10, default 5): ").strip()
                priority = int(priority_str) if priority_str.isdigit() else 5
                
                task_id = client.submit_task(task_type, prompt, priority)
                
            elif command == 'list':
                client.list_tasks()
            
            elif command == 'status':
                if len(parts) < 2:
                    print("Usage: status <task_id>")
                    continue
                
                task_id = parts[1]
                status = client.get_task_status(task_id)
                if status:
                    print(f"Task {task_id}: {status}")
                else:
                    print(f"Task {task_id} not found")
            
            elif command == 'wait':
                if len(parts) < 2:
                    print("Usage: wait <task_id>")
                    continue
                
                task_id = parts[1]
                success = client.wait_for_task(task_id, timeout=120)
                
            else:
                print(f"Unknown command: {command}")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        client.disconnect()


def demo_mode():
    """デモモード - 自動でタスクを送信"""
    client = TaskClient('redis')
    
    if not client.connect():
        return
    
    print("\n🎯 Demo Mode - Submitting test tasks")
    print("=" * 60)
    
    # テストタスクを送信
    test_tasks = [
        ("general", "What is Python decorators?", 5),
        ("code", "Write a function to calculate fibonacci numbers", 8),
        ("documentation", "Explain REST API best practices", 3),
        ("general", "What are the benefits of microservices?", 4),
        ("code", "Create a simple web server in Python", 9),
    ]
    
    task_ids = []
    
    for task_type, prompt, priority in test_tasks:
        task_id = client.submit_task(task_type, prompt, priority)
        task_ids.append(task_id)
        time.sleep(0.5)
    
    print(f"\n📊 Submitted {len(task_ids)} tasks")
    
    # 全タスクの完了を待つ
    print("\n⏳ Waiting for all tasks to complete...")
    
    for _ in range(60):  # 最大60秒待つ
        time.sleep(2)
        client.list_tasks()
        
        # 全タスク完了チェック
        all_done = True
        for task_id in task_ids:
            task = client.get_task_status(task_id)
            if task and task['status'] not in ['completed', 'failed']:
                all_done = False
                break
        
        if all_done:
            print("\n✅ All tasks completed!")
            break
    
    # 最終結果
    print("\n📊 Final Results:")
    client.list_tasks()
    
    client.disconnect()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'demo':
        demo_mode()
    else:
        interactive_mode()