#!/usr/bin/env python3
"""
通知フックシステム - タスク完了時の親方への通知
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Callable, List
from datetime import datetime

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'distributed'))

try:
    from distributed.message_queue import get_queue_instance
except ImportError:
    # フォールバック: ファイルベースの通知システム
    import tempfile
    
    class LocalQueue:
        def __init__(self):
            self.connected = False
            # 通知ファイルのパス
            koubou_home = os.environ.get('KOUBOU_HOME', '/tmp')
            self.notifications_dir = os.path.join(koubou_home, 'notifications')
            os.makedirs(self.notifications_dir, exist_ok=True)
            
        def connect(self, **kwargs):
            self.connected = True
            return True
            
        def publish(self, channel, message):
            try:
                # ファイルベースの通知
                notification_file = os.path.join(
                    self.notifications_dir,
                    f"{channel}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
                )
                
                # メッセージにタイムスタンプを追加
                message['timestamp'] = datetime.now().isoformat()
                message['channel'] = channel
                
                # ファイルに書き込み
                with open(notification_file, 'w', encoding='utf-8') as f:
                    json.dump(message, f, ensure_ascii=False, indent=2)
                
                print(f"[NOTIFICATION] {channel}: {message.get('type', 'unknown')} - {notification_file}")
                return True
            except Exception as e:
                print(f"[NOTIFICATION ERROR] {e}")
                return False
    
    def get_queue_instance(queue_type="local"):
        return LocalQueue()

logger = logging.getLogger(__name__)

class NotificationHook:
    """職人→親方の通知フックシステム"""
    
    def __init__(self):
        self.mq = get_queue_instance("local")  # LocalQueueを使用
        self.connected = False
        self.hooks: Dict[str, List[Callable]] = {
            'task_completed': [],
            'task_failed': [],
            'worker_status': []
        }
        
    def connect(self):
        """メッセージキューに接続"""
        if not self.connected:
            self.connected = self.mq.connect()
            if self.connected:
                logger.info("通知フックシステムが接続されました")
            else:
                logger.error("通知フックシステムの接続に失敗")
        return self.connected
    
    def register_hook(self, event_type: str, callback: Callable):
        """フックを登録"""
        if event_type in self.hooks:
            self.hooks[event_type].append(callback)
            logger.info(f"フック登録: {event_type}")
        else:
            logger.warning(f"未知のイベントタイプ: {event_type}")
    
    def notify_task_completed(self, task_id: str, task_details: Dict[str, Any]):
        """タスク完了通知を送信"""
        self.connect()
        
        # タスクの内容を要約
        summary = self._create_task_summary(task_details)
        
        notification = {
            'type': 'task_completed',
            'task_id': task_id,
            'summary': summary,
            'completed_at': datetime.now().isoformat(),
            'worker_id': task_details.get('assigned_to', 'unknown'),
            'priority': task_details.get('priority', 5),
            'duration': self._calculate_duration(task_details),
            'success': task_details.get('status') == 'completed'
        }
        
        # メッセージキューに発行
        success = self.mq.publish('master_notifications', notification)
        
        # 登録されたフックを実行
        for hook in self.hooks['task_completed']:
            try:
                hook(notification)
            except Exception as e:
                logger.error(f"フック実行エラー: {e}")
        
        if success:
            logger.info(f"タスク完了通知を送信: {task_id} - {summary}")
        
        return success
    
    def notify_task_failed(self, task_id: str, task_details: Dict[str, Any], error_info: str):
        """タスク失敗通知を送信"""
        self.connect()
        
        summary = self._create_task_summary(task_details)
        
        notification = {
            'type': 'task_failed',
            'task_id': task_id,
            'summary': summary,
            'failed_at': datetime.now().isoformat(),
            'worker_id': task_details.get('assigned_to', 'unknown'),
            'priority': task_details.get('priority', 5),
            'error': error_info,
            'success': False
        }
        
        success = self.mq.publish('master_notifications', notification)
        
        # 登録されたフックを実行
        for hook in self.hooks['task_failed']:
            try:
                hook(notification)
            except Exception as e:
                logger.error(f"フック実行エラー: {e}")
        
        if success:
            logger.warning(f"タスク失敗通知を送信: {task_id} - {error_info}")
        
        return success
    
    def _create_task_summary(self, task_details: Dict[str, Any]) -> str:
        """タスクの内容から要約を作成"""
        try:
            content = task_details.get('content', '')
            if isinstance(content, str):
                content_obj = json.loads(content)
            else:
                content_obj = content
            
            prompt = content_obj.get('prompt', content_obj.get('content', ''))
            
            # 要約作成（最初の50文字 + ...）
            if len(prompt) > 50:
                summary = prompt[:50] + '...'
            else:
                summary = prompt
            
            return summary
        except:
            return 'タスク内容不明'
    
    def _calculate_duration(self, task_details: Dict[str, Any]) -> str:
        """タスク実行時間を計算"""
        try:
            created_at = task_details.get('created_at')
            updated_at = task_details.get('updated_at')
            
            if created_at and updated_at:
                from datetime import datetime
                start = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                end = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                duration = end - start
                
                total_seconds = duration.total_seconds()
                if total_seconds < 60:
                    return f"{total_seconds:.1f}秒"
                elif total_seconds < 3600:
                    minutes = total_seconds / 60
                    return f"{minutes:.1f}分"
                else:
                    hours = total_seconds / 3600
                    return f"{hours:.1f}時間"
            
            return "不明"
        except:
            return "不明"

# デフォルトの通知フックを作成
def default_console_hook(notification: Dict[str, Any]):
    """コンソールに通知を表示するデフォルトフック"""
    task_id = notification['task_id'][:8] + '...'
    summary = notification['summary']
    worker_id = notification['worker_id']
    
    if notification['type'] == 'task_completed':
        duration = notification.get('duration', '不明')
        print(f"🎉 【職人完了報告】 {worker_id} がタスクを完了しました")
        print(f"   📋 タスク: {task_id}")  
        print(f"   💬 内容: {summary}")
        print(f"   ⏱️  実行時間: {duration}")
        print()
    elif notification['type'] == 'task_failed':
        error = notification.get('error', '不明')
        print(f"⚠️  【職人エラー報告】 {worker_id} のタスクが失敗しました")
        print(f"   📋 タスク: {task_id}")
        print(f"   💬 内容: {summary}")
        print(f"   ❌ エラー: {error}")
        print()

# グローバルインスタンス
_notification_hook = None

def get_notification_hook():
    """通知フックのシングルトンインスタンスを取得"""
    global _notification_hook
    if _notification_hook is None:
        _notification_hook = NotificationHook()
        # デフォルトフックを登録
        _notification_hook.register_hook('task_completed', default_console_hook)
        _notification_hook.register_hook('task_failed', default_console_hook)
    return _notification_hook