#!/usr/bin/env python3
"""
WebSocketサーバー - リアルタイム通知システム
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Set, Dict, Any
import websockets
from websockets.asyncio.server import ServerConnection

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.database import get_db_manager

# 設定
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
WS_HOST = "0.0.0.0"
WS_PORT = 8766

# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# データベースマネージャー
db = get_db_manager(DB_PATH)

class WebSocketManager:
    """WebSocket接続を管理"""
    
    def __init__(self):
        self.clients: Set[ServerConnection] = set()
        self.subscriptions: Dict[str, Set[ServerConnection]] = {
            'task': set(),
            'worker': set(),
            'system': set()
        }
    
    async def register(self, websocket: ServerConnection):
        """クライアントを登録"""
        self.clients.add(websocket)
        logger.info(f"Client {websocket.remote_address} connected")
        
        # 接続時に現在の状態を送信
        await self.send_initial_state(websocket)
    
    async def unregister(self, websocket: ServerConnection):
        """クライアントを登録解除"""
        self.clients.discard(websocket)
        for subscribers in self.subscriptions.values():
            subscribers.discard(websocket)
        logger.info(f"Client {websocket.remote_address} disconnected")
    
    async def send_initial_state(self, websocket: ServerConnection):
        """初期状態を送信"""
        try:
            # タスク統計
            task_stats = db.get_task_statistics()
            # ワーカー統計
            worker_stats = db.get_worker_statistics()
            
            # 現在のアクティブワーカーも送信
            active_workers = []
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT worker_id, status, current_task FROM workers WHERE status <> 'offline'")
                for worker in cursor.fetchall():
                    active_workers.append({
                        'worker_id': worker['worker_id'],
                        'status': worker['status'],
                        'current_task': worker['current_task']
                    })
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching active workers: {e}")
                active_workers = []
            
            # 現在実行中のタスク詳細も送信
            active_tasks = []
            for task in db.get_active_tasks():
                try:
                    content_data = json.loads(task.get('content', '{}'))
                    task_summary = content_data.get('prompt', '')[:100] + ('...' if len(content_data.get('prompt', '')) > 100 else '')
                except:
                    task_summary = task.get('content', '')[:100] + ('...' if len(task.get('content', '')) > 100 else '')
                
                active_tasks.append({
                    'task_id': task['task_id'],
                    'summary': task_summary,
                    'type': content_data.get('type', 'general') if 'content_data' in locals() else 'general',
                    'status': task['status'],
                    'assigned_to': task['assigned_to'],
                    'priority': task['priority'],
                    'created_at': task['created_at']
                })
            
            initial_state = {
                'type': 'initial_state',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'tasks': task_stats,
                    'workers': worker_stats,
                    'active_workers': active_workers,
                    'active_tasks': active_tasks
                }
            }
            
            await websocket.send(json.dumps(initial_state))
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
    
    async def subscribe(self, websocket: ServerConnection, channel: str):
        """チャンネルに購読"""
        if channel in self.subscriptions:
            self.subscriptions[channel].add(websocket)
            logger.info(f"Client subscribed to {channel}")
            
            # 購読確認を送信
            await websocket.send(json.dumps({
                'type': 'subscribed',
                'channel': channel,
                'timestamp': datetime.now().isoformat()
            }))
    
    async def unsubscribe(self, websocket: ServerConnection, channel: str):
        """チャンネルから購読解除"""
        if channel in self.subscriptions:
            self.subscriptions[channel].discard(websocket)
            logger.info(f"Client unsubscribed from {channel}")
    
    async def broadcast(self, message: Dict[str, Any], channel: str = None):
        """メッセージをブロードキャスト"""
        message['timestamp'] = datetime.now().isoformat()
        message_json = json.dumps(message)
        
        if channel and channel in self.subscriptions:
            # 特定チャンネルの購読者に送信
            subscribers = self.subscriptions[channel].copy()
        else:
            # 全クライアントに送信
            subscribers = self.clients.copy()
        
        if subscribers:
            # 非同期で全クライアントに送信
            await asyncio.gather(
                *[client.send(message_json) for client in subscribers],
                return_exceptions=True
            )
    
    async def notify_task_update(self, task_id: str, status: str, details: Dict[str, Any] = None):
        """タスク更新を通知"""
        message = {
            'type': 'task_update',
            'task_id': task_id,
            'status': status,
            'details': details or {}
        }
        await self.broadcast(message, 'task')
    
    async def notify_worker_update(self, worker_id: str, status: str, details: Dict[str, Any] = None):
        """ワーカー更新を通知"""
        message = {
            'type': 'worker_update',
            'worker_id': worker_id,
            'status': status,
            'details': details or {}
        }
        await self.broadcast(message, 'worker')
    
    async def notify_system_event(self, event: str, details: Dict[str, Any] = None):
        """システムイベントを通知"""
        message = {
            'type': 'system_event',
            'event': event,
            'details': details or {}
        }
        await self.broadcast(message, 'system')

# グローバルマネージャー
ws_manager = WebSocketManager()

async def handle_client(websocket):
    """クライアント接続を処理"""
    await ws_manager.register(websocket)
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get('command')
                
                if command == 'subscribe':
                    channel = data.get('channel')
                    if channel:
                        await ws_manager.subscribe(websocket, channel)
                
                elif command == 'unsubscribe':
                    channel = data.get('channel')
                    if channel:
                        await ws_manager.unsubscribe(websocket, channel)
                
                elif command == 'ping':
                    await websocket.send(json.dumps({
                        'type': 'pong',
                        'timestamp': datetime.now().isoformat()
                    }))
                
                elif command == 'get_stats':
                    # 現在の統計を送信
                    stats = {
                        'type': 'stats',
                        'data': {
                            'tasks': db.get_task_statistics(),
                            'workers': db.get_worker_statistics()
                        }
                    }
                    await websocket.send(json.dumps(stats))
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {message}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await ws_manager.unregister(websocket)

async def monitor_database():
    """データベースを監視して変更を通知"""
    last_check = datetime.now()
    last_tasks = {}
    last_workers = {}
    
    while True:
        try:
            # タスクの変更を確認
            current_tasks = {}
            for task in db.get_pending_tasks(limit=100):
                current_tasks[task['task_id']] = task['status']
            
            # 新規または更新されたタスク
            for task_id, status in current_tasks.items():
                if task_id not in last_tasks or last_tasks[task_id] != status:
                    await ws_manager.notify_task_update(task_id, status)
            
            # ワーカーの変更を確認
            current_workers = {}
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT worker_id, status, current_task FROM workers WHERE status <> 'offline'")
                for worker in cursor.fetchall():
                    current_workers[worker['worker_id']] = worker['status']
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching workers in monitor: {e}")
                current_workers = {}
            
            # 新規または更新されたワーカー
            for worker_id, status in current_workers.items():
                if worker_id not in last_workers or last_workers[worker_id] != status:
                    await ws_manager.notify_worker_update(worker_id, status)
            
            # デッドワーカーの通知
            for worker_id in last_workers:
                if worker_id not in current_workers:
                    await ws_manager.notify_worker_update(worker_id, 'offline')
            
            last_tasks = current_tasks
            last_workers = current_workers
            
        except Exception as e:
            logger.error(f"Error in database monitor: {e}")
        
        await asyncio.sleep(2)  # 2秒ごとに確認

async def periodic_stats():
    """定期的に統計情報をブロードキャスト"""
    while True:
        try:
            stats = {
                'type': 'periodic_stats',
                'data': {
                    'tasks': db.get_task_statistics(),
                    'workers': db.get_worker_statistics(),
                    'active_connections': len(ws_manager.clients)
                }
            }
            await ws_manager.broadcast(stats)
        except Exception as e:
            logger.error(f"Error broadcasting stats: {e}")
        
        await asyncio.sleep(5)  # 5秒ごと

async def main():
    """メイン関数"""
    logger.info(f"Starting WebSocket server on {WS_HOST}:{WS_PORT}")
    
    # WebSocketサーバーを起動
    server = await websockets.serve(handle_client, WS_HOST, WS_PORT)
    
    # バックグラウンドタスクを起動
    monitor_task = asyncio.create_task(monitor_database())
    stats_task = asyncio.create_task(periodic_stats())
    
    logger.info(f"WebSocket server is running at ws://{WS_HOST}:{WS_PORT}")
    
    try:
        await asyncio.Future()  # 永続実行
    except KeyboardInterrupt:
        logger.info("Shutting down WebSocket server...")
    finally:
        monitor_task.cancel()
        stats_task.cancel()
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("WebSocket server stopped")