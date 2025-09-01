#!/usr/bin/env python3
"""
MCP-分散システムブリッジ
MCPサーバーと分散ワーカーシステムを統合
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import threading
import uuid

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS
from distributed.message_queue import get_queue_instance

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

class MCPDistributedBridge:
    """MCPサーバーと分散システムのブリッジ"""
    
    def __init__(self, queue_type: str = 'redis'):
        self.queue_type = queue_type
        self.mq = None
        self.connected = False
        self.pending_tasks = {}
        
        # 結果受信用スレッド
        self.result_listener = None
        
    def start(self) -> bool:
        """ブリッジを開始"""
        try:
            # メッセージキューに接続
            self.mq = get_queue_instance(self.queue_type)
            
            if self.queue_type == 'redis':
                if not self.mq.connect(host='localhost', port=6379):
                    logger.error("Failed to connect to Redis")
                    return False
            else:
                if not self.mq.connect():
                    logger.error("Failed to connect to message queue")
                    return False
            
            # 結果チャンネルを購読
            self.mq.subscribe('tasks/result', self._handle_task_result)
            self.mq.subscribe('tasks/status', self._handle_task_status)
            
            self.connected = True
            logger.info("MCP-Distributed bridge started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start bridge: {e}")
            return False
    
    def submit_task(self, task_data: Dict[str, Any]) -> str:
        """分散システムにタスクを送信"""
        if not self.connected:
            raise RuntimeError("Bridge not connected")
        
        # タスクID生成
        task_id = f"mcp-task-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        # タスクメッセージ作成
        task_message = {
            'task_id': task_id,
            'client_id': 'mcp-server',
            'type': task_data.get('type', 'general'),
            'prompt': task_data.get('prompt', ''),
            'priority': task_data.get('priority', 5),
            'requirements': task_data.get('requirements', {}),
            'submitted_at': datetime.now().isoformat(),
            'source': 'mcp'
        }
        
        # キューに送信
        self.mq.publish('tasks/submit', task_message)
        
        # ペンディングリストに追加
        self.pending_tasks[task_id] = {
            'status': 'submitted',
            'submitted_at': datetime.now(),
            'original_request': task_data,
            'result': None
        }
        
        logger.info(f"Task {task_id} submitted to distributed system")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """タスクステータスを取得"""
        if task_id in self.pending_tasks:
            return self.pending_tasks[task_id]
        return None
    
    def _handle_task_result(self, data: Dict[str, Any]):
        """タスク結果を処理"""
        task_id = data.get('task_id')
        
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id]['status'] = data.get('status')
            self.pending_tasks[task_id]['result'] = data.get('result')
            self.pending_tasks[task_id]['error'] = data.get('error')
            self.pending_tasks[task_id]['completed_at'] = datetime.now()
            self.pending_tasks[task_id]['worker_id'] = data.get('worker_id')
            
            logger.info(f"Task {task_id} completed with status: {data.get('status')}")
    
    def _handle_task_status(self, data: Dict[str, Any]):
        """タスクステータス更新を処理"""
        task_id = data.get('task_id')
        
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id]['status'] = data.get('status')
            self.pending_tasks[task_id]['last_update'] = datetime.now()
            
            logger.debug(f"Task {task_id} status updated: {data.get('status')}")
    
    def stop(self):
        """ブリッジを停止"""
        if self.mq:
            self.mq.disconnect()
        self.connected = False
        logger.info("MCP-Distributed bridge stopped")


# グローバルブリッジインスタンス
bridge = MCPDistributedBridge()

@app.route('/health', methods=['GET'])
def health_check():
    """ヘルスチェック"""
    return jsonify({
        'status': 'healthy' if bridge.connected else 'disconnected',
        'timestamp': datetime.now().isoformat(),
        'queue_type': bridge.queue_type,
        'pending_tasks': len(bridge.pending_tasks)
    })

@app.route('/task/submit', methods=['POST'])
def submit_task():
    """タスクを分散システムに送信"""
    try:
        data = request.json
        
        if not data or 'prompt' not in data:
            return jsonify({'error': 'Missing prompt'}), 400
        
        # タスクを送信
        task_id = bridge.submit_task(data)
        
        return jsonify({
            'task_id': task_id,
            'status': 'submitted',
            'message': 'Task submitted to distributed system'
        })
        
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """タスクステータスを取得"""
    task = bridge.get_task_status(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # レスポンス作成
    response = {
        'task_id': task_id,
        'status': task.get('status', 'unknown'),
        'submitted_at': task.get('submitted_at', '').isoformat() if task.get('submitted_at') else None,
        'completed_at': task.get('completed_at', '').isoformat() if task.get('completed_at') else None,
        'worker_id': task.get('worker_id')
    }
    
    # 結果がある場合は追加
    if task.get('result'):
        response['result'] = task['result']
    if task.get('error'):
        response['error'] = task['error']
    
    return jsonify(response)

@app.route('/task/<task_id>/result', methods=['GET'])
def get_task_result(task_id):
    """タスク結果を取得"""
    task = bridge.get_task_status(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if task.get('status') not in ['completed', 'failed']:
        return jsonify({
            'error': 'Task not completed',
            'status': task.get('status')
        }), 202
    
    return jsonify({
        'task_id': task_id,
        'status': task['status'],
        'result': task.get('result'),
        'error': task.get('error'),
        'worker_id': task.get('worker_id'),
        'processing_time': (
            (task['completed_at'] - task['submitted_at']).total_seconds()
            if task.get('completed_at') and task.get('submitted_at')
            else None
        )
    })

@app.route('/system/stats', methods=['GET'])
def get_system_stats():
    """システム統計を取得"""
    stats = {
        'total_tasks': len(bridge.pending_tasks),
        'by_status': {},
        'average_processing_time': 0,
        'success_rate': 0
    }
    
    # ステータス別集計
    completed_count = 0
    total_time = 0
    
    for task in bridge.pending_tasks.values():
        status = task.get('status', 'unknown')
        stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
        
        if status == 'completed':
            completed_count += 1
            if task.get('completed_at') and task.get('submitted_at'):
                total_time += (task['completed_at'] - task['submitted_at']).total_seconds()
    
    # 平均処理時間と成功率
    if completed_count > 0:
        stats['average_processing_time'] = total_time / completed_count
        stats['success_rate'] = (completed_count / len(bridge.pending_tasks)) * 100
    
    return jsonify(stats)

@app.route('/worker/scale', methods=['POST'])
def scale_workers():
    """ワーカー数を調整（分散システムに指示）"""
    data = request.json
    
    if not data or 'workers' not in data:
        return jsonify({'error': 'Missing workers parameter'}), 400
    
    # スケーリング指示を送信
    bridge.mq.publish('system/scale', {
        'action': 'scale',
        'target_workers': data['workers'],
        'timestamp': datetime.now().isoformat()
    })
    
    return jsonify({
        'status': 'scaling',
        'target_workers': data['workers']
    })

def main():
    """メインエントリーポイント"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MCP-Distributed Bridge Server')
    parser.add_argument('--port', type=int, default=8768, help='Server port')
    parser.add_argument('--queue', default='redis', choices=['local', 'redis', 'rabbitmq'])
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # ブリッジ設定
    bridge.queue_type = args.queue
    
    # ブリッジ起動
    if not bridge.start():
        logger.error("Failed to start bridge")
        sys.exit(1)
    
    # Flaskサーバー起動
    try:
        logger.info(f"Starting MCP-Distributed Bridge on port {args.port}")
        app.run(
            host='0.0.0.0',
            port=args.port,
            debug=args.debug,
            use_reloader=False
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        bridge.stop()

if __name__ == '__main__':
    main()