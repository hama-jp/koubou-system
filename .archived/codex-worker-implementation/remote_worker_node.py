#!/usr/bin/env python3
"""
リモートワーカーノード - 分散処理実行ノード
"""

import os
import sys
import json
import logging
import subprocess
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from distributed.message_queue import get_queue_instance

logger = logging.getLogger(__name__)


class RemoteWorkerNode:
    """リモートワーカーノード"""
    
    def __init__(self, config: Dict[str, Any]):
        self.node_id = config.get('node_id', f'worker-{uuid.uuid4().hex[:8]}')
        self.location = config.get('location', 'unknown')
        self.queue_type = config.get('queue_type', 'local')
        
        # ノード能力
        self.capacity = config.get('capacity', {
            'max_workers': 2,
            'max_memory_gb': 4,
            'has_gpu': False
        })
        
        # 処理可能なタスクタイプ
        self.capabilities = config.get('capabilities', ['general'])
        
        # LLM設定
        self.llm_config = config.get('llm_config', {
            'type': 'ollama',
            'model': 'gemma2:2b',
            'endpoint': 'http://localhost:11434'
        })
        
        # メッセージキュー
        self.mq = get_queue_instance(self.queue_type)
        
        # ワーカープール
        self.worker_pool = []
        self.max_workers = self.capacity['max_workers']
        self.current_load = 0
        
        # 実行中のタスク
        self.running_tasks = {}
        
        # 統計情報
        self.stats = {
            'tasks_received': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_processing_time': 0
        }
        
        # 制御フラグ
        self.running = False
        self.master_id = None
        self.task_channel = None
        
        # ヘルスチェックスレッド
        self.heartbeat_thread = None
    
    def connect_to_master(self, master_host: str = 'localhost') -> bool:
        """マスターノードに接続"""
        try:
            # メッセージキュー接続
            queue_config = {
                'host': master_host,
                'port': int(os.getenv('MQ_PORT', '6379'))
            }
            
            if not self.mq.connect(**queue_config):
                logger.error("Failed to connect to message queue")
                return False
            
            # 自身の制御チャンネルを購読
            control_channel = f"node:{self.node_id}:control"
            self.mq.subscribe(control_channel, self._handle_control_message)
            
            # マスターに登録
            registration_message = {
                'type': 'register',
                'node_id': self.node_id,
                'location': self.location,
                'capacity': self.capacity,
                'capabilities': self.capabilities,
                'llm_config': self.llm_config,
                'timestamp': datetime.now().isoformat()
            }
            
            self.mq.publish('master:register', registration_message)
            
            logger.info(f"Worker node {self.node_id} connecting to master at {master_host}")
            
            # 登録確認を待つ（最大10秒）
            start_time = time.time()
            while not self.master_id and time.time() - start_time < 10:
                time.sleep(0.5)
            
            if self.master_id:
                logger.info(f"Successfully registered with master {self.master_id}")
                self.running = True
                self._start_heartbeat()
                return True
            else:
                logger.error("Failed to register with master (timeout)")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to master: {e}")
            return False
    
    def disconnect(self):
        """マスターから切断"""
        self.running = False
        
        # ハートビート停止
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        
        # 実行中のタスクを停止
        for task_id in list(self.running_tasks.keys()):
            self._cancel_task(task_id)
        
        # メッセージキュー切断
        self.mq.disconnect()
        
        logger.info(f"Worker node {self.node_id} disconnected")
    
    def _handle_control_message(self, data: Dict[str, Any]):
        """制御メッセージを処理"""
        msg_type = data.get('type')
        
        if msg_type == 'registration_confirmed':
            # 登録確認
            self.master_id = data.get('master_id')
            self.task_channel = data.get('task_channel')
            
            # タスクチャンネルを購読
            if self.task_channel:
                self.mq.subscribe(self.task_channel, self._handle_task)
                logger.info(f"Subscribed to task channel: {self.task_channel}")
        
        elif msg_type == 'shutdown':
            # シャットダウン要求
            logger.info("Received shutdown request from master")
            self.disconnect()
        
        elif msg_type == 'scale':
            # ワーカー数調整
            new_max = data.get('max_workers')
            if new_max:
                self.max_workers = min(new_max, self.capacity['max_workers'])
                logger.info(f"Adjusted max workers to {self.max_workers}")
    
    def _handle_task(self, data: Dict[str, Any]):
        """タスクを処理"""
        task_id = data.get('task_id')
        
        # 負荷チェック
        if self.current_load >= self.max_workers:
            logger.warning(f"Node at capacity, rejecting task {task_id}")
            self._report_task_status(task_id, 'rejected', error='Node at capacity')
            return
        
        # タスク受信
        self.stats['tasks_received'] += 1
        self.current_load += 1
        
        # タスク実行スレッド起動
        thread = threading.Thread(
            target=self._process_task,
            args=(data,),
            daemon=True
        )
        thread.start()
        
        self.running_tasks[task_id] = thread
        logger.info(f"Started processing task {task_id}")
    
    def _process_task(self, task: Dict[str, Any]):
        """タスクを実行"""
        task_id = task.get('task_id')
        start_time = time.time()
        
        try:
            # タスクタイプに応じた処理
            task_type = task.get('type', 'general')
            prompt = task.get('prompt', '')
            
            if task_type == 'code' and 'code' in self.capabilities:
                result = self._execute_code_task(prompt)
            else:
                result = self._execute_general_task(prompt)
            
            # 成功報告
            processing_time = time.time() - start_time
            self.stats['tasks_completed'] += 1
            self.stats['total_processing_time'] += processing_time
            
            self._report_task_status(task_id, 'completed', result=result)
            logger.info(f"Task {task_id} completed in {processing_time:.2f}s")
            
        except Exception as e:
            # 失敗報告
            self.stats['tasks_failed'] += 1
            self._report_task_status(task_id, 'failed', error=str(e))
            logger.error(f"Task {task_id} failed: {e}")
            
        finally:
            # クリーンアップ
            self.current_load = max(0, self.current_load - 1)
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    def _execute_general_task(self, prompt: str) -> str:
        """一般タスクを実行（Ollama直接）"""
        try:
            if self.llm_config['type'] == 'ollama':
                # Ollamaコマンド実行
                cmd = [
                    'ollama', 'run',
                    self.llm_config.get('model', 'gemma2:2b'),
                    prompt
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=True
                )
                
                return result.stdout.strip()
                
            elif self.llm_config['type'] == 'api':
                # API呼び出し（実装例）
                import requests
                
                response = requests.post(
                    self.llm_config['endpoint'],
                    json={'prompt': prompt},
                    timeout=120
                )
                response.raise_for_status()
                
                return response.json().get('result', '')
            
            else:
                raise ValueError(f"Unknown LLM type: {self.llm_config['type']}")
                
        except subprocess.TimeoutExpired:
            raise TimeoutError("Task execution timed out")
        except Exception as e:
            raise RuntimeError(f"Task execution failed: {e}")
    
    def _execute_code_task(self, prompt: str) -> str:
        """コードタスクを実行（Codex CLI経由）"""
        try:
            # Codex CLIスクリプトパス
            codex_script = os.path.expanduser('~/.koubou/scripts/codex-exec.sh')
            
            if not os.path.exists(codex_script):
                # フォールバック: 一般タスクとして実行
                return self._execute_general_task(prompt)
            
            # Codex実行
            result = subprocess.run(
                [codex_script, prompt],
                capture_output=True,
                text=True,
                timeout=180,
                check=True,
                env={
                    **os.environ,
                    'CODEX_UNSAFE_ALLOW_NO_SANDBOX': '1'
                }
            )
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise TimeoutError("Code generation timed out")
        except Exception as e:
            # フォールバック
            logger.warning(f"Codex failed, falling back to general: {e}")
            return self._execute_general_task(prompt)
    
    def _cancel_task(self, task_id: str):
        """タスクをキャンセル"""
        if task_id in self.running_tasks:
            # スレッドの強制終了は推奨されないので、フラグ等で制御する実装が必要
            logger.warning(f"Cancelling task {task_id}")
            self._report_task_status(task_id, 'cancelled')
    
    def _report_task_status(self, task_id: str, status: str, 
                           result: Optional[str] = None, 
                           error: Optional[str] = None):
        """タスクステータスをマスターに報告"""
        report = {
            'task_id': task_id,
            'node_id': self.node_id,
            'status': status,
            'timestamp': datetime.now().isoformat()
        }
        
        if result:
            report['result'] = result
        if error:
            report['error'] = error
        
        self.mq.publish('master:task_complete', report)
    
    def _start_heartbeat(self):
        """ハートビート送信を開始"""
        def send_heartbeat():
            while self.running:
                try:
                    heartbeat = {
                        'node_id': self.node_id,
                        'timestamp': datetime.now().isoformat(),
                        'current_load': self.current_load,
                        'max_workers': self.max_workers,
                        'stats': {
                            'received': self.stats['tasks_received'],
                            'completed': self.stats['tasks_completed'],
                            'failed': self.stats['tasks_failed']
                        }
                    }
                    
                    self.mq.publish('master:heartbeat', heartbeat)
                    
                    # 30秒ごとに送信
                    time.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Failed to send heartbeat: {e}")
        
        self.heartbeat_thread = threading.Thread(
            target=send_heartbeat,
            daemon=True
        )
        self.heartbeat_thread.start()
    
    def get_status(self) -> Dict[str, Any]:
        """ノードステータスを取得"""
        avg_time = 0
        if self.stats['tasks_completed'] > 0:
            avg_time = self.stats['total_processing_time'] / self.stats['tasks_completed']
        
        return {
            'node_id': self.node_id,
            'location': self.location,
            'status': 'running' if self.running else 'stopped',
            'connected_to': self.master_id,
            'load': {
                'current': self.current_load,
                'max': self.max_workers
            },
            'capabilities': self.capabilities,
            'stats': {
                **self.stats,
                'average_processing_time': avg_time
            },
            'llm': self.llm_config
        }


def main():
    """リモートワーカーノード起動"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Remote Worker Node')
    parser.add_argument('--node-id', help='Worker node ID (auto-generated if not specified)')
    parser.add_argument('--location', default='local', help='Node location')
    parser.add_argument('--master', default='localhost', help='Master node host')
    parser.add_argument('--queue-type', default='local', choices=['local', 'redis', 'rabbitmq'])
    parser.add_argument('--max-workers', type=int, default=2, help='Maximum concurrent workers')
    parser.add_argument('--capabilities', nargs='+', default=['general'], 
                      help='Task capabilities (e.g., general code confidential)')
    parser.add_argument('--llm-type', default='ollama', choices=['ollama', 'api'])
    parser.add_argument('--llm-model', default='gemma2:2b', help='LLM model name')
    parser.add_argument('--gpu', action='store_true', help='Node has GPU')
    
    args = parser.parse_args()
    
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # ワーカーノード設定
    config = {
        'node_id': args.node_id,
        'location': args.location,
        'queue_type': args.queue_type,
        'capacity': {
            'max_workers': args.max_workers,
            'max_memory_gb': 4,  # 仮の値
            'has_gpu': args.gpu
        },
        'capabilities': args.capabilities,
        'llm_config': {
            'type': args.llm_type,
            'model': args.llm_model,
            'endpoint': 'http://localhost:11434' if args.llm_type == 'ollama' else None
        }
    }
    
    # ワーカーノード起動
    worker = RemoteWorkerNode(config)
    
    if worker.connect_to_master(args.master):
        logger.info(f"Worker node {worker.node_id} is running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(30)
                # 定期的にステータスを表示
                status = worker.get_status()
                logger.info(f"Status: {json.dumps(status, indent=2)}")
        except KeyboardInterrupt:
            logger.info("Shutting down worker node...")
            worker.disconnect()
    else:
        logger.error("Failed to connect to master")
        sys.exit(1)


if __name__ == "__main__":
    main()