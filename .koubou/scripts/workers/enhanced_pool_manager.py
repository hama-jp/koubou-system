#!/usr/bin/env python3
"""
拡張版ワーカープールマネージャー - リモートワーカー対応
"""

import json
import os
import sys
import subprocess
import threading
import time
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# 既存のWorkerPoolManagerをインポート
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from worker_pool_manager import WorkerPoolManager, KOUBOU_HOME, LOG_DIR

# データベースマネージャーのインポート
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common.database import get_db_manager

logger = logging.getLogger(__name__)


class TaskRouter:
    """優先度ベースのタスクルーティング"""
    
    def __init__(self, routing_policy: dict):
        self.policy = routing_policy
        self.strategy = routing_policy.get('strategy', 'priority_based')
        self.rules = routing_policy.get('rules', [])
        logger.info(f"TaskRouter initialized with strategy: {self.strategy}")
    
    def route_task(self, task: dict, available_workers: list) -> Optional[str]:
        """
        タスクを最適なワーカーにルーティング
        
        Args:
            task: タスク情報（priority, preferred_worker含む）
            available_workers: 利用可能なワーカーリスト
            
        Returns:
            選択されたworker_id または None
        """
        if not available_workers:
            return None
        
        # 🚀 preferred_workerの優先処理を追加
        preferred_worker = task.get('preferred_worker')
        if preferred_worker:
            # preferred_workerが利用可能かチェック
            preferred_available = [w for w in available_workers if w['worker_id'] == preferred_worker]
            if preferred_available:
                logger.info(f"Task {task.get('task_id')} routed to preferred worker {preferred_worker}")
                return preferred_worker
            else:
                logger.warning(f"Preferred worker {preferred_worker} not available, using fallback")
        
        priority = task.get('priority', 5)
        
        # 🔧 localがビジー時のremote即座委託ロジック
        local_workers = [w for w in available_workers if w.get('location', 'local') == 'local']
        remote_workers = [w for w in available_workers if w.get('location', 'local') != 'local']
        
        # localワーカーがすべてビジー（または存在しない）場合、remoteに即座委託
        local_idle = [w for w in local_workers if w.get('status') == 'idle']
        if not local_idle and remote_workers:
            best_remote = self._select_best_worker(remote_workers, task)
            if best_remote:
                logger.info(f"Task {task.get('task_id')} routed to remote worker {best_remote} (local busy)")
                return best_remote
        
        # 優先度ベースのルール適用
        for rule in self.rules:
            priority_range = rule.get('priority_range', [1, 10])
            if priority_range[0] <= priority <= priority_range[1]:
                preferred_types = rule.get('preferred_workers', [])
                
                # 優先ワーカータイプから選択
                for worker_type in preferred_types:
                    candidates = [
                        w for w in available_workers 
                        if self._match_worker_type(w, worker_type)
                    ]
                    
                    if candidates:
                        # パフォーマンスファクターで重み付け選択
                        selected = self._select_best_worker(candidates, task)
                        if selected:
                            logger.info(f"Task {task.get('task_id')} routed to {selected} (priority: {priority})")
                            return selected
                
                # フォールバック設定確認
                if rule.get('fallback_to_local', False) and not candidates:
                    local_workers = [w for w in available_workers if w.get('location', 'local') == 'local']
                    if local_workers:
                        return self._select_best_worker(local_workers, task)
        
        # デフォルト: 最初の利用可能なワーカー
        default_worker = available_workers[0]['worker_id'] if available_workers else None
        if default_worker:
            logger.info(f"Task {task.get('task_id')} routed to {default_worker} (default)")
        return default_worker
    
    def _match_worker_type(self, worker: dict, worker_type: str) -> bool:
        """ワーカータイプのマッチング"""
        if worker_type == 'local':
            return worker.get('location', 'local') == 'local'
        elif worker_type == 'remote':
            return worker.get('location', 'local') != 'local'
        return True
    
    def _select_best_worker(self, candidates: list, task: dict) -> Optional[str]:
        """候補から最適なワーカーを選択"""
        if not candidates:
            return None
            
        # スコア計算
        scores = []
        for worker in candidates:
            score = self._calculate_worker_score(worker, task)
            scores.append((worker['worker_id'], score))
        
        # 最高スコアのワーカーを選択
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0] if scores else None
    
    def _calculate_worker_score(self, worker: dict, task: dict) -> float:
        """ワーカーのスコア計算"""
        score = 0.0
        
        # パフォーマンスファクター
        score += worker.get('performance_factor', 1.0) * 100
        
        # 現在の負荷（アイドル優先）
        if worker.get('status') == 'idle':
            score += 50
        elif worker.get('status') == 'busy':
            score -= 30
        
        # 成功率
        total_tasks = worker.get('tasks_completed', 0) + worker.get('tasks_failed', 0)
        if total_tasks > 0:
            success_rate = worker.get('tasks_completed', 0) / total_tasks
            score += success_rate * 30
        
        return score


class EnhancedWorkerPoolManager(WorkerPoolManager):
    """拡張版ワーカープールマネージャー"""
    
    def __init__(self, config_file: str = None):
        # 設定ファイルの読み込み
        self.config = self.load_config(config_file)
        
        # プール設定
        pool_config = self.config.get('pool', {})
        super().__init__(
            min_workers=pool_config.get('min_workers', 1),
            max_workers=pool_config.get('max_workers', 5),
            max_active_tasks=pool_config.get('max_active_tasks', 3)
        )
        
        # リモートワーカーの管理
        self.remote_workers = {}
        
        # タスクルーター
        routing_policy = self.config.get('routing_policy', {})
        self.task_router = TaskRouter(routing_policy)
        
        # データベースマネージャー
        self.db = get_db_manager(f"{KOUBOU_HOME}/db/koubou.db")
        
        logger.info("🚀 Enhanced Worker Pool Manager initialized")
    
    def load_config(self, config_file: str = None) -> dict:
        """設定ファイルの読み込み"""
        if config_file is None:
            config_file = f"{KOUBOU_HOME}/config/workers.yaml"
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"✅ Loaded configuration from {config_file}")
                return config
        else:
            logger.warning(f"⚠️ Config file not found: {config_file}, using defaults")
            return {}
    
    def initialize_workers(self):
        """ローカル・リモートワーカーの初期化"""
        # ローカルワーカーの起動
        local_configs = self.config.get('workers', {}).get('local_workers', [])
        for config in local_configs[:self.min_workers]:  # 最小数だけ起動
            self.start_local_worker(config)
        
        # リモートワーカーの起動
        remote_configs = self.config.get('workers', {}).get('remote_workers', [])
        for config in remote_configs:
            self.start_remote_worker(config)
    
    def start_local_worker(self, config: dict):
        """ローカルワーカーの起動"""
        worker_id = config['worker_id']
        
        # 既存のstart_workerメソッドを使用
        env = os.environ.copy()
        env['WORKER_ID'] = worker_id
        env['WORKER_AUTH_TOKEN'] = f"{KOUBOU_HOME}_POOL_MANAGER"
        
        # max_tokensを環境変数として渡す
        env['MAX_TOKENS'] = str(config.get('max_tokens', 32768))
        
        # ローカルワーカースクリプト
        worker_script = f"{KOUBOU_HOME}/scripts/workers/local_worker.py"
        cmd = [sys.executable, worker_script]
        
        log_file = LOG_DIR / f"{worker_id}.log"
        
        try:
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env
                )
            
            self.workers[worker_id] = process
            
            # データベースに登録
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO workers 
                    (worker_id, status, location, performance_factor, last_heartbeat)
                    VALUES (?, 'idle', 'local', ?, datetime('now'))
                """, (worker_id, config.get('performance_factor', 1.0)))
            
            logger.info(f"💻 Started local worker: {worker_id}")
            
        except Exception as e:
            logger.error(f"Failed to start local worker {worker_id}: {e}")
    
    def start_remote_worker(self, config: dict):
        """リモートワーカーの起動"""
        worker_id = config['worker_id']
        
        # リモートワーカースクリプトの起動
        worker_script = f"{KOUBOU_HOME}/scripts/workers/remote_worker.py"
        
        # 設定をJSON文字列として渡す
        config_json = json.dumps(config)
        
        cmd = [
            sys.executable, worker_script,
            '--worker-id', worker_id,
            '--config', config_json
        ]
        
        # 環境変数設定
        env = os.environ.copy()
        env['WORKER_AUTH_TOKEN'] = f"{KOUBOU_HOME}_POOL_MANAGER"
        env['KOUBOU_HOME'] = KOUBOU_HOME
        
        # max_tokensを環境変数として渡す
        env['MAX_TOKENS'] = str(config.get('max_tokens', 16384))
        
        # ログファイルのパス
        log_file = LOG_DIR / f"{worker_id}.log"
        
        try:
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env
                )
            
            self.remote_workers[worker_id] = process
            
            # データベースに登録
            endpoint_url = f"http://{config.get('remote_host')}:{config.get('remote_port', 11434)}"
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO workers 
                    (worker_id, status, location, performance_factor, endpoint_url, last_heartbeat)
                    VALUES (?, 'idle', 'remote', ?, ?, datetime('now'))
                """, (worker_id, config.get('performance_factor', 0.5), endpoint_url))
            
            logger.info(f"🌐 Started remote worker: {worker_id} @ {endpoint_url}")
            
        except Exception as e:
            logger.error(f"Failed to start remote worker {worker_id}: {e}")
    
    def get_available_workers(self) -> List[Dict]:
        """利用可能なワーカーのリストを取得"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT worker_id, status, location, performance_factor,
                           tasks_completed, tasks_failed
                    FROM workers
                    WHERE status = 'idle'
                      AND datetime('now', '-60 seconds') <= last_heartbeat
                """)
                workers = cursor.fetchall()
                
                # Rowオブジェクトを辞書に変換
                result = []
                for row in workers:
                    result.append({
                        'worker_id': row[0],
                        'status': row[1],
                        'location': row[2],
                        'performance_factor': row[3],
                        'tasks_completed': row[4],
                        'tasks_failed': row[5]
                    })
                return result
            
        except Exception as e:
            logger.error(f"Error getting available workers: {e}")
            return []
    
    def assign_task_to_worker(self, task: dict):
        """タスクをワーカーに割り当て"""
        # 利用可能なワーカーを取得
        available_workers = self.get_available_workers()
        
        if not available_workers:
            logger.warning("No available workers for task assignment")
            return None
        
        # ルーティング
        selected_worker_id = self.task_router.route_task(task, available_workers)
        
        if selected_worker_id:
            # ワーカーのステータスを更新
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE workers 
                    SET status = 'busy', current_task = ?
                    WHERE worker_id = ?
                """, (task.get('task_id'), selected_worker_id))
                
                # タスクをワーカーに割り当て
                conn.execute("""
                    UPDATE task_master 
                    SET status = 'in_progress', assigned_to = ?
                    WHERE task_id = ?
                """, (selected_worker_id, task.get('task_id')))
            
            # ワーカーに直接通知
            self.notify_worker_task_assignment(selected_worker_id, task)
            
            logger.info(f"✅ Task {task.get('task_id')} assigned to {selected_worker_id}")
            return selected_worker_id
        
        return None
    
    def notify_worker_task_assignment(self, worker_id: str, task: dict):
        """ワーカーにタスク割り当てを直接通知"""
        try:
            # データベースに通知フラグを設定
            with self.db.get_connection() as conn:
                # worker_notificationsテーブルが存在しない場合は作成
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS worker_notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        worker_id TEXT NOT NULL,
                        notification_type TEXT NOT NULL,
                        task_id TEXT,
                        message TEXT,
                        processed INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 通知レコードを挿入
                conn.execute("""
                    INSERT INTO worker_notifications 
                    (worker_id, notification_type, task_id, message)
                    VALUES (?, 'task_assigned', ?, ?)
                """, (
                    worker_id,
                    task.get('task_id'),
                    f"Task {task.get('task_id')} assigned - process immediately"
                ))
                
            logger.info(f"📬 Notified worker {worker_id} of task assignment: {task.get('task_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to notify worker {worker_id}: {e}")
            return False
    
    def monitor_loop(self):
        """監視ループ（親クラスのメソッドをオーバーライド）"""
        logger.info("🔄 Starting enhanced monitoring loop")
        
        while self.running:
            try:
                # 保留中のタスクを処理
                with self.db.get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT task_id, 'general' as type, priority, content
                        FROM task_master
                        WHERE status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 10
                    """)
                    pending_tasks = cursor.fetchall()
                
                for row in pending_tasks:
                    task = {
                        'task_id': row[0],
                        'type': row[1],
                        'priority': row[2],
                        'content': row[3]
                    }
                    self.assign_task_to_worker(task)
                
                # ヘルスチェック
                self.check_worker_health()
                
                # パフォーマンス調整
                if self.config.get('performance', {}).get('auto_adjust_performance', False):
                    self.adjust_performance_factors()
                
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(10)
    
    def check_worker_health(self):
        """ワーカーのヘルスチェック"""
        # タイムアウトしたワーカーを検出
        timeout_seconds = self.config.get('health_check', {}).get('timeout', 60)
        
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE workers 
                SET status = 'offline'
                WHERE datetime('now', '-{} seconds') > last_heartbeat
                  AND status != 'offline'
            """.format(timeout_seconds))
    
    def adjust_performance_factors(self):
        """パフォーマンスファクターの自動調整"""
        # TODO: 実装予定
        pass
    
    def shutdown_all_workers(self):
        """すべてのワーカーを停止"""
        # ローカルワーカーの停止
        for worker_id, process in self.workers.items():
            if process.poll() is None:
                logger.info(f"Stopping local worker {worker_id}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except:
                    process.kill()
        
        # リモートワーカーの停止
        for worker_id, process in self.remote_workers.items():
            if process.poll() is None:
                logger.info(f"Stopping remote worker {worker_id}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except:
                    process.kill()


def main():
    """メインエントリーポイント"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Worker Pool Manager')
    parser.add_argument('--config', type=str, help='Configuration file path')
    parser.add_argument('--test-mode', action='store_true', help='Run in test mode')
    
    args = parser.parse_args()
    
    # マネージャーの作成
    manager = EnhancedWorkerPoolManager(config_file=args.config)
    
    if args.test_mode:
        logger.info("🧪 Running in test mode")
        
        # ワーカーの初期化
        manager.initialize_workers()
        
        # 利用可能なワーカーの確認
        time.sleep(3)  # ワーカー起動を待つ
        workers = manager.get_available_workers()
        logger.info(f"Available workers: {len(workers)}")
        for w in workers:
            logger.info(f"  - {w['worker_id']}: location={w['location']}, performance={w['performance_factor']}")
        
        # テストタスクのルーティング
        test_tasks = [
            {'task_id': 'test_001', 'priority': 9, 'type': 'general'},
            {'task_id': 'test_002', 'priority': 5, 'type': 'general'},
            {'task_id': 'test_003', 'priority': 2, 'type': 'general'},
        ]
        
        for task in test_tasks:
            selected = manager.task_router.route_task(task, workers)
            logger.info(f"Task {task['task_id']} (priority={task['priority']}) -> {selected}")
        
        # 停止
        manager.shutdown_all_workers()
        
    else:
        # 通常モード
        logger.info("🚀 Starting Enhanced Worker Pool Manager")
        
        # ワーカーの初期化
        manager.initialize_workers()
        
        # 監視ループの開始
        monitor_thread = threading.Thread(target=manager.monitor_loop)
        monitor_thread.start()
        
        try:
            monitor_thread.join()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            manager.running = False
            manager.shutdown_all_workers()


if __name__ == "__main__":
    main()