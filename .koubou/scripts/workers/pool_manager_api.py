#!/usr/bin/env python3
"""Worker Pool Manager API - 監視用と制御用を分離したAPI"""

import json
import os
import socket
import threading
from pathlib import Path
from enum import Enum

KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
MONITOR_SOCKET = f"{KOUBOU_HOME}/worker_pool_monitor.sock"  # 監視用（読み取り専用）
CONTROL_SOCKET = f"{KOUBOU_HOME}/worker_pool_control.sock"  # 制御用（要認証）

class APIType(Enum):
    MONITOR = "monitor"  # 監視用（読み取り専用）
    CONTROL = "control"  # 制御用（変更操作）

class PoolManagerAPI:
    """Worker Pool ManagerのAPIサーバー"""
    
    def __init__(self, manager):
        self.manager = manager
        self.monitor_socket_path = Path(MONITOR_SOCKET)
        self.control_socket_path = Path(CONTROL_SOCKET)
        self.running = True
        self.control_token = os.environ.get('POOL_CONTROL_TOKEN', 'default_token')
        
    def start_servers(self):
        """監視用と制御用の両方のサーバーを起動"""
        # 監視用サーバー（認証不要）
        self._start_server(self.monitor_socket_path, APIType.MONITOR)
        
        # 制御用サーバー（認証必要）
        self._start_server(self.control_socket_path, APIType.CONTROL)
        
        print(f"📡 Monitor API listening on {self.monitor_socket_path}")
        print(f"🔐 Control API listening on {self.control_socket_path}")
    
    def _start_server(self, socket_path, api_type):
        """指定されたソケットでサーバーを起動"""
        # 既存のソケットファイルを削除
        if socket_path.exists():
            socket_path.unlink()
        
        # UNIXソケットを作成
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        server.listen(5)
        
        # サーバースレッドを開始
        thread = threading.Thread(
            target=self._accept_connections, 
            args=(server, api_type),
            daemon=True
        )
        thread.start()
    
    def _accept_connections(self, server, api_type):
        """接続を受け付ける"""
        while self.running:
            try:
                client, _ = server.accept()
                threading.Thread(
                    target=self._handle_client, 
                    args=(client, api_type),
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection on {api_type.value}: {e}")
    
    def _handle_client(self, client, api_type):
        """クライアントリクエストを処理"""
        try:
            data = client.recv(1024).decode()
            request = json.loads(data)
            
            # 制御APIの場合は認証チェック
            if api_type == APIType.CONTROL:
                token = request.get('auth_token')
                if token != self.control_token:
                    response = {'success': False, 'error': 'Authentication failed'}
                    client.send(json.dumps(response).encode())
                    return
            
            command = request.get('command')
            
            if api_type == APIType.MONITOR:
                response = self._handle_monitor_command(command, request)
            else:  # APIType.CONTROL
                response = self._handle_control_command(command, request)
            
            client.send(json.dumps(response).encode())
        except Exception as e:
            error_response = {'success': False, 'error': str(e)}
            client.send(json.dumps(error_response).encode())
        finally:
            client.close()
    
    def _handle_monitor_command(self, command, request):
        """監視用コマンドを処理（読み取り専用）"""
        if command == 'get_status':
            return {
                'success': True,
                'active_workers': self.manager.get_active_worker_count(),
                'pending_tasks': self.manager.get_pending_task_count(),
                'workers': list(self.manager.workers.keys()),
                'min_workers': self.manager.min_workers,
                'max_workers': self.manager.max_workers
            }
        
        elif command == 'get_worker_stats':
            return {
                'success': True,
                'worker_stats': self.manager.worker_stats
            }
        
        elif command == 'get_idle_workers':
            return {
                'success': True,
                'idle_workers': self.manager.get_idle_workers()
            }
        
        elif command == 'health_check':
            return {
                'success': True,
                'status': 'healthy',
                'running': self.manager.running
            }
        
        else:
            return {'success': False, 'error': f'Unknown monitor command: {command}'}
    
    def _handle_control_command(self, command, request):
        """制御用コマンドを処理（変更操作）"""
        if command == 'spawn_worker':
            worker_id = request.get('worker_id')
            new_id = self.manager.spawn_worker(worker_id)
            return {'success': True, 'worker_id': new_id}
        
        elif command == 'shutdown_worker':
            worker_id = request.get('worker_id')
            if worker_id not in self.manager.workers:
                return {'success': False, 'error': f'Worker {worker_id} not found'}
            self.manager.shutdown_worker(worker_id)
            return {'success': True, 'message': f'Worker {worker_id} shutdown initiated'}
        
        elif command == 'scale':
            min_workers = request.get('min_workers', self.manager.min_workers)
            max_workers = request.get('max_workers', self.manager.max_workers)
            
            if min_workers < 0 or max_workers < min_workers:
                return {'success': False, 'error': 'Invalid scaling parameters'}
            
            self.manager.min_workers = min_workers
            self.manager.max_workers = max_workers
            self.manager.scale_workers()
            return {
                'success': True, 
                'message': f'Scaling parameters updated: min={min_workers}, max={max_workers}'
            }
        
        elif command == 'force_scale':
            # 強制的にスケーリングを実行
            self.manager.scale_workers()
            return {'success': True, 'message': 'Forced scaling executed'}
        
        elif command == 'shutdown_all':
            self.manager.shutdown_all_workers()
            return {'success': True, 'message': 'All workers shutdown initiated'}
        
        elif command == 'restart_worker':
            worker_id = request.get('worker_id')
            if worker_id in self.manager.workers:
                self.manager.shutdown_worker(worker_id)
                new_id = self.manager.spawn_worker()
                return {'success': True, 'old_worker': worker_id, 'new_worker': new_id}
            else:
                return {'success': False, 'error': f'Worker {worker_id} not found'}
        
        else:
            return {'success': False, 'error': f'Unknown control command: {command}'}
    
    def stop_servers(self):
        """すべてのサーバーを停止"""
        self.running = False
        
        # ソケットファイルをクリーンアップ
        for socket_path in [self.monitor_socket_path, self.control_socket_path]:
            if socket_path.exists():
                socket_path.unlink()