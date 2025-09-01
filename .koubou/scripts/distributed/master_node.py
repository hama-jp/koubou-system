#!/usr/bin/env python3
"""
マスターノード - 分散ワーカーの中央管理
"""

import os
import sys
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import time

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from distributed.message_queue import get_queue_instance
from common.database import DatabaseManager

logger = logging.getLogger(__name__)


class MasterNode:
    """分散ワーカーの中央管理ノード"""
    
    def __init__(self, config: Dict[str, Any]):
        self.node_id = config.get('node_id', 'master-01')
        self.location = config.get('location', 'local')
        self.queue_type = config.get('queue_type', 'local')
        
        # データベース（オプショナル）
        try:
            self.db = DatabaseManager()
        except Exception as e:
            logger.warning(f"Database not available: {e}")
            self.db = None
        
        # メッセージキュー
        self.mq = get_queue_instance(self.queue_type)
        
        # 登録ノード情報
        self.registered_nodes = {}
        
        # ヘルスチェックスレッド
        self.health_monitor = None
        self.running = False
        
        # タスクルーティング戦略
        self.routing_strategy = config.get('routing_strategy', 'load_balanced')
        
        # 統計情報
        self.stats = {
            'tasks_routed': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'nodes_registered': 0,
            'nodes_active': 0
        }
    
    def start(self) -> bool:
        """マスターノードを起動"""
        try:
            # メッセージキュー接続
            queue_config = {
                'host': os.getenv('MQ_HOST', 'localhost'),
                'port': int(os.getenv('MQ_PORT', '6379'))
            }
            
            if not self.mq.connect(**queue_config):
                logger.error("Failed to connect to message queue")
                return False
            
            # 管理チャンネルを購読（わかりやすい名前も追加）
            self.mq.subscribe('master:register', self._handle_registration)
            self.mq.subscribe('master:heartbeat', self._handle_heartbeat)
            self.mq.subscribe('master:task_complete', self._handle_task_complete)
            
            # 新しいタスク送信チャンネル
            self.mq.subscribe('tasks/submit', self._handle_task_submit)
            
            # ヘルスモニター開始
            self.running = True
            self.health_monitor = threading.Thread(
                target=self._monitor_health,
                daemon=True
            )
            self.health_monitor.start()
            
            logger.info(f"Master node {self.node_id} started at {self.location}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start master node: {e}")
            return False
    
    def stop(self):
        """マスターノードを停止"""
        self.running = False
        if self.health_monitor:
            self.health_monitor.join(timeout=5)
        self.mq.disconnect()
        logger.info("Master node stopped")
    
    def register_node(self, node_info: Dict[str, Any]):
        """リモートノードを登録"""
        node_id = node_info['node_id']
        
        self.registered_nodes[node_id] = {
            'node_id': node_id,
            'location': node_info.get('location', 'unknown'),
            'capacity': node_info.get('capacity', {
                'max_workers': 1,
                'max_memory_gb': 4,
                'has_gpu': False
            }),
            'capabilities': node_info.get('capabilities', ['general']),
            'llm_config': node_info.get('llm_config', {}),
            'status': 'active',
            'last_heartbeat': datetime.now(),
            'current_load': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'average_response_time': 0
        }
        
        self.stats['nodes_registered'] += 1
        self.stats['nodes_active'] += 1
        
        # ノード専用チャンネルを作成
        node_channel = f"node:{node_id}:tasks"
        
        # 登録確認を送信
        self.mq.publish(f"node:{node_id}:control", {
            'type': 'registration_confirmed',
            'master_id': self.node_id,
            'task_channel': node_channel
        })
        
        logger.info(f"Registered node: {node_id} at {node_info.get('location')}")
    
    def assign_task(self, task: Dict[str, Any]) -> bool:
        """タスクを適切なノードに割り当て"""
        try:
            # アクティブなノードを取得
            active_nodes = self._get_active_nodes()
            
            if not active_nodes:
                logger.warning("No active nodes available")
                return False
            
            # 最適なノードを選択
            best_node = self._select_best_node(task, active_nodes)
            
            if not best_node:
                logger.warning("No suitable node found for task")
                return False
            
            # タスクをノードに送信
            node_channel = f"node:{best_node['node_id']}:tasks"
            
            task_message = {
                'task_id': task.get('task_id') or task.get('id'),
                'type': task.get('type', 'general'),
                'prompt': task.get('prompt') or task.get('content', ''),
                'priority': task.get('priority', 5),
                'requirements': task.get('requirements', {}),
                'assigned_by': self.node_id,
                'assigned_to': best_node['node_id'],
                'assigned_at': datetime.now().isoformat()
            }
            
            self.mq.publish(node_channel, task_message)
            
            # ノードの負荷を更新
            best_node['current_load'] += 1
            
            self.stats['tasks_routed'] += 1
            
            logger.info(f"Assigned task {task['id']} to node {best_node['node_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign task: {e}")
            return False
    
    def _select_best_node(self, task: Dict[str, Any], nodes: List[Dict]) -> Optional[Dict]:
        """タスクに最適なノードを選択"""
        
        # タスクタイプに基づくフィルタリング
        task_type = task.get('type', 'general')
        capable_nodes = [
            n for n in nodes 
            if task_type in n.get('capabilities', ['general'])
        ]
        
        if not capable_nodes:
            # 汎用ノードにフォールバック
            capable_nodes = [
                n for n in nodes 
                if 'general' in n.get('capabilities', [])
            ]
        
        if not capable_nodes:
            return None
        
        # ルーティング戦略に基づく選択
        if self.routing_strategy == 'load_balanced':
            # 負荷分散: 最も負荷の低いノード
            return min(capable_nodes, key=lambda n: n['current_load'])
            
        elif self.routing_strategy == 'round_robin':
            # ラウンドロビン
            import random
            return random.choice(capable_nodes)
            
        elif self.routing_strategy == 'geographic':
            # 地理的近接性（簡易版: 同じlocationを優先）
            same_location = [
                n for n in capable_nodes 
                if n['location'] == self.location
            ]
            if same_location:
                return min(same_location, key=lambda n: n['current_load'])
            return min(capable_nodes, key=lambda n: n['current_load'])
            
        elif self.routing_strategy == 'capability_based':
            # 能力ベース: GPUタスクはGPUノードへ
            if task.get('requires_gpu'):
                gpu_nodes = [
                    n for n in capable_nodes 
                    if n['capacity'].get('has_gpu')
                ]
                if gpu_nodes:
                    return min(gpu_nodes, key=lambda n: n['current_load'])
            
            # 高優先度タスクは高性能ノードへ
            if task.get('priority', 5) >= 8:
                high_perf = sorted(
                    capable_nodes,
                    key=lambda n: n['capacity'].get('max_workers', 1),
                    reverse=True
                )
                if high_perf:
                    return high_perf[0]
            
            return min(capable_nodes, key=lambda n: n['current_load'])
        
        # デフォルト: 負荷分散
        return min(capable_nodes, key=lambda n: n['current_load'])
    
    def _get_active_nodes(self) -> List[Dict]:
        """アクティブなノードのリストを取得"""
        active_nodes = []
        timeout_threshold = datetime.now() - timedelta(seconds=60)
        
        for node_id, node_info in self.registered_nodes.items():
            if node_info['status'] == 'active':
                if node_info['last_heartbeat'] > timeout_threshold:
                    active_nodes.append(node_info)
                else:
                    # タイムアウトしたノードを非アクティブに
                    node_info['status'] = 'timeout'
                    self.stats['nodes_active'] -= 1
                    logger.warning(f"Node {node_id} timed out")
        
        return active_nodes
    
    def _handle_registration(self, data: Dict[str, Any]):
        """ノード登録リクエストを処理"""
        logger.info(f"Received registration message: {data}")
        if data.get('type') == 'register':
            self.register_node(data)
        else:
            logger.warning(f"Unknown registration message type: {data.get('type')}")
    
    def _handle_heartbeat(self, data: Dict[str, Any]):
        """ハートビートを処理"""
        node_id = data.get('node_id')
        if node_id in self.registered_nodes:
            node = self.registered_nodes[node_id]
            node['last_heartbeat'] = datetime.now()
            node['current_load'] = data.get('current_load', 0)
            node['status'] = 'active'
            
            # 統計情報を更新
            if 'stats' in data:
                node['tasks_completed'] = data['stats'].get('completed', 0)
                node['tasks_failed'] = data['stats'].get('failed', 0)
    
    def _handle_task_submit(self, data: Dict[str, Any]):
        """クライアントからのタスク送信を処理"""
        task_id = data.get('task_id')
        client_id = data.get('client_id')
        
        logger.info(f"Received task {task_id} from client {client_id}")
        
        # ステータスを通知
        self.mq.publish('tasks/status', {
            'task_id': task_id,
            'status': 'queued',
            'timestamp': datetime.now().isoformat()
        })
        
        # タスクを割り当て
        success = self.assign_task(data)
        
        if success:
            self.mq.publish('tasks/status', {
                'task_id': task_id,
                'status': 'assigned',
                'timestamp': datetime.now().isoformat()
            })
        else:
            self.mq.publish('tasks/result', {
                'task_id': task_id,
                'status': 'failed',
                'error': 'No available workers',
                'timestamp': datetime.now().isoformat()
            })
    
    def _handle_task_complete(self, data: Dict[str, Any]):
        """タスク完了通知を処理"""
        task_id = data.get('task_id')
        node_id = data.get('node_id')
        status = data.get('status')
        
        if node_id in self.registered_nodes:
            node = self.registered_nodes[node_id]
            node['current_load'] = max(0, node['current_load'] - 1)
            
            if status == 'completed':
                self.stats['tasks_completed'] += 1
            else:
                self.stats['tasks_failed'] += 1
        
        # データベースを更新（利用可能な場合）
        if self.db:
            if status == 'completed':
                self.db.update_task_status(task_id, 'completed', data.get('result'))
            else:
                self.db.update_task_status(task_id, 'failed', data.get('error'))
        
        # クライアントに結果を通知
        self.mq.publish('tasks/result', {
            'task_id': task_id,
            'status': status,
            'result': data.get('result'),
            'error': data.get('error'),
            'worker_id': node_id,
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"Task {task_id} {status} by node {node_id}")
    
    def _monitor_health(self):
        """ノードの健全性を監視"""
        while self.running:
            try:
                # 定期的にノード状態をチェック
                active_nodes = self._get_active_nodes()
                
                # 統計情報を更新
                self.stats['nodes_active'] = len(active_nodes)
                
                # ヘルスレポートを発行
                self.mq.publish('master:health', {
                    'master_id': self.node_id,
                    'timestamp': datetime.now().isoformat(),
                    'stats': self.stats,
                    'active_nodes': [n['node_id'] for n in active_nodes]
                })
                
                # 30秒ごとにチェック
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """マスターノードのステータスを取得"""
        active_nodes = self._get_active_nodes()
        
        return {
            'master_id': self.node_id,
            'location': self.location,
            'status': 'running' if self.running else 'stopped',
            'stats': self.stats,
            'nodes': {
                'registered': len(self.registered_nodes),
                'active': len(active_nodes),
                'details': [
                    {
                        'node_id': n['node_id'],
                        'location': n['location'],
                        'status': n['status'],
                        'load': n['current_load'],
                        'capabilities': n['capabilities']
                    }
                    for n in self.registered_nodes.values()
                ]
            }
        }


def main():
    """マスターノード起動"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Master Node for Distributed Workers')
    parser.add_argument('--node-id', default='master-01', help='Master node ID')
    parser.add_argument('--location', default='local', help='Node location')
    parser.add_argument('--queue-type', default='local', choices=['local', 'redis', 'rabbitmq'])
    parser.add_argument('--routing', default='load_balanced', 
                      choices=['load_balanced', 'round_robin', 'geographic', 'capability_based'])
    
    args = parser.parse_args()
    
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # マスターノード設定
    config = {
        'node_id': args.node_id,
        'location': args.location,
        'queue_type': args.queue_type,
        'routing_strategy': args.routing
    }
    
    # マスターノード起動
    master = MasterNode(config)
    
    if master.start():
        logger.info("Master node is running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(10)
                # 定期的にステータスを表示
                status = master.get_status()
                logger.info(f"Status: {json.dumps(status, indent=2)}")
        except KeyboardInterrupt:
            logger.info("Shutting down master node...")
            master.stop()
    else:
        logger.error("Failed to start master node")
        sys.exit(1)


if __name__ == "__main__":
    main()