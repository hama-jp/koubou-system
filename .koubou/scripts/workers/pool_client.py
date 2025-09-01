#!/usr/bin/env python3
"""Worker Pool Manager クライアント - 監視と制御"""

import json
import socket
import sys
import os
from pathlib import Path

KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
MONITOR_SOCKET = f"{KOUBOU_HOME}/worker_pool_monitor.sock"
CONTROL_SOCKET = f"{KOUBOU_HOME}/worker_pool_control.sock"

class PoolClient:
    """Worker Pool Managerのクライアント"""
    
    @staticmethod
    def send_monitor_command(command, **kwargs):
        """監視用コマンドを送信（読み取り専用）"""
        return PoolClient._send_command(MONITOR_SOCKET, command, **kwargs)
    
    @staticmethod
    def send_control_command(command, auth_token=None, **kwargs):
        """制御用コマンドを送信（要認証）"""
        if auth_token is None:
            auth_token = os.environ.get('POOL_CONTROL_TOKEN', 'default_token')
        
        return PoolClient._send_command(
            CONTROL_SOCKET, 
            command, 
            auth_token=auth_token,
            **kwargs
        )
    
    @staticmethod
    def _send_command(socket_path, command, **kwargs):
        """コマンドを送信"""
        try:
            # UNIXソケットに接続
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(socket_path)
            
            # リクエストを作成
            request = {'command': command}
            request.update(kwargs)
            
            # 送信
            client.send(json.dumps(request).encode())
            
            # 応答を受信
            response = client.recv(4096).decode()
            client.close()
            
            return json.loads(response)
        except FileNotFoundError:
            return {'success': False, 'error': 'Worker Pool Manager not running'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

# コマンドライン使用例
def main():
    if len(sys.argv) < 2:
        print("Usage: pool_client.py <command> [options]")
        print("\nMonitor commands (read-only):")
        print("  status        - Get worker pool status")
        print("  stats         - Get worker statistics")
        print("  idle          - List idle workers")
        print("  health        - Health check")
        print("\nControl commands (requires auth):")
        print("  spawn         - Spawn a new worker")
        print("  shutdown <id> - Shutdown specific worker")
        print("  scale <min> <max> - Set scaling parameters")
        print("  force-scale   - Force immediate scaling")
        print("  restart <id>  - Restart specific worker")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # 監視コマンド
    if command == "status":
        result = PoolClient.send_monitor_command('get_status')
    elif command == "stats":
        result = PoolClient.send_monitor_command('get_worker_stats')
    elif command == "idle":
        result = PoolClient.send_monitor_command('get_idle_workers')
    elif command == "health":
        result = PoolClient.send_monitor_command('health_check')
    
    # 制御コマンド
    elif command == "spawn":
        result = PoolClient.send_control_command('spawn_worker')
    elif command == "shutdown":
        if len(sys.argv) < 3:
            print("Error: worker_id required")
            sys.exit(1)
        result = PoolClient.send_control_command('shutdown_worker', worker_id=sys.argv[2])
    elif command == "scale":
        if len(sys.argv) < 4:
            print("Error: min and max workers required")
            sys.exit(1)
        result = PoolClient.send_control_command(
            'scale',
            min_workers=int(sys.argv[2]),
            max_workers=int(sys.argv[3])
        )
    elif command == "force-scale":
        result = PoolClient.send_control_command('force_scale')
    elif command == "restart":
        if len(sys.argv) < 3:
            print("Error: worker_id required")
            sys.exit(1)
        result = PoolClient.send_control_command('restart_worker', worker_id=sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    # 結果を表示
    if result.get('success'):
        print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()