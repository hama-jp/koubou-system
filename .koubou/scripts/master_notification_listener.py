#!/usr/bin/env python3
"""
親方通知リスナー - 職人からの完了通知を受信
"""

import os
import sys
import json
import logging
import threading
import time
from typing import Dict, Any

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'distributed'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from distributed.message_queue import get_queue_instance
except ImportError:
    # フォールバック: ファイルベースの通知システム
    class LocalQueue:
        def __init__(self):
            self.connected = False
            # 通知ファイルのパス
            koubou_home = os.environ.get('KOUBOU_HOME', '/tmp')
            self.notifications_dir = os.path.join(koubou_home, 'notifications')
            os.makedirs(self.notifications_dir, exist_ok=True)
            self.processed_files = set()
            
        def connect(self, **kwargs):
            self.connected = True
            return True
            
        def subscribe(self, channel, callback):
            self.channel = channel
            self.callback = callback
            return True
            
        def check_for_notifications(self):
            """ファイルベースの通知をチェック"""
            try:
                import glob
                pattern = os.path.join(self.notifications_dir, f"{self.channel}_*.json")
                notification_files = glob.glob(pattern)
                
                for file_path in notification_files:
                    if file_path not in self.processed_files:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                notification = json.load(f)
                            
                            # コールバックを実行
                            self.callback(notification)
                            self.processed_files.add(file_path)
                            
                            # ファイルを削除（処理済み）
                            os.remove(file_path)
                            
                        except Exception as e:
                            logger.error(f"通知ファイル処理エラー {file_path}: {e}")
                            
            except Exception as e:
                logger.error(f"通知チェックエラー: {e}")
    
    def get_queue_instance(queue_type="local"):
        return LocalQueue()

# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MasterNotificationListener:
    """親方通知リスナー"""
    
    def __init__(self):
        self.mq = get_queue_instance("local")
        self.running = False
        self.listener_thread = None
        
    def start_listener(self):
        """通知リスナーを開始"""
        if not self.running:
            # メッセージキューに接続
            if not self.mq.connect():
                logger.error("メッセージキューへの接続に失敗")
                return False
            
            # 通知チャンネルを購読
            self.mq.subscribe('master_notifications', self.on_notification_received)
            
            self.running = True
            
            # バックグラウンドでリスナーを実行
            self.listener_thread = threading.Thread(target=self._listen_loop)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            
            logger.info("親方通知リスナーを開始しました")
            return True
        
        return False
    
    def stop_listener(self):
        """通知リスナーを停止"""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5)
        logger.info("親方通知リスナーを停止しました")
    
    def _listen_loop(self):
        """通知受信ループ"""
        while self.running:
            # ファイルベースの通知をチェック
            if hasattr(self.mq, 'check_for_notifications'):
                self.mq.check_for_notifications()
            time.sleep(1)  # 1秒ごとにファイルをチェック
    
    def on_notification_received(self, notification: Dict[str, Any]):
        """通知受信時の処理"""
        try:
            notification_type = notification.get('type')
            task_id = notification.get('task_id', 'unknown')
            
            if notification_type == 'task_completed':
                self.handle_task_completed(notification)
            elif notification_type == 'task_failed':
                self.handle_task_failed(notification)
            else:
                logger.warning(f"未知の通知タイプ: {notification_type}")
                
        except Exception as e:
            logger.error(f"通知処理エラー: {e}")
    
    def handle_task_completed(self, notification: Dict[str, Any]):
        """タスク完了通知の処理"""
        task_id = notification.get('task_id', '')[:8] + '...'
        summary = notification.get('summary', 'タスク内容不明')
        worker_id = notification.get('worker_id', 'unknown')
        duration = notification.get('duration', '不明')
        
        # コンソールに表示（デスクトップ通知風）
        print("=" * 60)
        print("🎉 【職人完了報告】")
        print(f"📋 タスク ID: {task_id}")
        print(f"👷 担当職人: {worker_id}")
        print(f"💬 作業内容: {summary}")
        print(f"⏱️  実行時間: {duration}")
        print(f"✅ ステータス: 完了")
        print("=" * 60)
        print()
        
        # 必要に応じて他の処理を追加
        # - デスクトップ通知の送信
        # - Slackへの投稿
        # - メール送信など
        
        self._send_desktop_notification(
            "工房システム - タスク完了",
            f"{worker_id} が作業を完了しました\n{summary}"
        )
    
    def handle_task_failed(self, notification: Dict[str, Any]):
        """タスク失敗通知の処理"""
        task_id = notification.get('task_id', '')[:8] + '...'
        summary = notification.get('summary', 'タスク内容不明')
        worker_id = notification.get('worker_id', 'unknown')
        error = notification.get('error', '不明なエラー')
        
        # コンソールに表示（エラー通知風）
        print("=" * 60)
        print("⚠️  【職人エラー報告】")
        print(f"📋 タスク ID: {task_id}")
        print(f"👷 担当職人: {worker_id}")
        print(f"💬 作業内容: {summary}")
        print(f"❌ エラー内容: {error}")
        print(f"🔴 ステータス: 失敗")
        print("=" * 60)
        print()
        
        self._send_desktop_notification(
            "工房システム - タスク失敗",
            f"{worker_id} の作業でエラーが発生\n{error}"
        )
    
    def _send_desktop_notification(self, title: str, message: str):
        """デスクトップ通知を送信（Linux/WSL対応）"""
        try:
            # Linux用のnotify-sendコマンドを試す
            import subprocess
            subprocess.run([
                'notify-send', 
                title, 
                message, 
                '--urgency=normal',
                '--expire-time=5000'
            ], check=False, capture_output=True)
        except:
            # フォールバック: システムベルを鳴らす
            try:
                print('\a')  # ASCII Bell
            except:
                pass

# グローバルインスタンス
_master_listener = None

def get_master_listener():
    """親方リスナーのシングルトンインスタンスを取得"""
    global _master_listener
    if _master_listener is None:
        _master_listener = MasterNotificationListener()
    return _master_listener

def start_notification_system():
    """通知システムを開始"""
    listener = get_master_listener()
    return listener.start_listener()

def stop_notification_system():
    """通知システムを停止"""
    listener = get_master_listener()
    listener.stop_listener()

if __name__ == '__main__':
    """スタンドアローン実行"""
    print("🏭 親方通知システムを開始...")
    
    if start_notification_system():
        try:
            print("通知を待機しています... (Ctrl+C で終了)")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n通知システムを終了します...")
            stop_notification_system()
    else:
        print("通知システムの開始に失敗しました")