#!/usr/bin/env python3
"""
ワーカープールマネージャー - 動的にワーカーを管理
"""

import json
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import signal
import sys
import logging

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common.database import get_db_manager
from pool_manager_api import PoolManagerAPI

KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
LOG_DIR = Path(f"{KOUBOU_HOME}/logs/workers")

# DatabaseManagerインスタンスを取得
db = get_db_manager(DB_PATH)

# ロガーの設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ワーカータイプの選択（環境変数または設定ファイルから）
WORKER_TYPE = os.environ.get('KOUBOU_WORKER_TYPE', 'local')  # デフォルトはlocal（実動作版）
WORKER_SCRIPTS = {
    'local': f"{KOUBOU_HOME}/scripts/workers/local_worker.py",        # 基本ワーカー（gemini-repo-cli統合・自動保存機能付き）
    'simple': f"{KOUBOU_HOME}/scripts/workers/simple_worker.py",      # シンプルワーカー（テスト用・モック）
}
# simple workerはモックなので、デフォルトはlocalを使用
WORKER_SCRIPT = WORKER_SCRIPTS.get(WORKER_TYPE, WORKER_SCRIPTS['local'])

# データベースマネージャーを初期化
db = get_db_manager(DB_PATH)

class WorkerPoolManager:
    """複数のワーカーを動的に管理"""
    
    def __init__(self, min_workers=1, max_workers=5, max_active_tasks=2):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.max_active_tasks = max_active_tasks  # 🚦 新機能：アクティブタスク数の上限
        self.workers = {}  # worker_id: process
        self.worker_stats = {}  # worker_id: stats
        self.running = True
        self.lock = threading.Lock()
        
        # ログディレクトリ作成
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # ワーカータイプをログに記録
        print(f"🎯 Worker Pool Manager Started")
        print(f"Configuration: min={min_workers}, max={max_workers} workers, max_active_tasks={max_active_tasks}")
        print(f"Worker Type: {WORKER_TYPE} ({WORKER_SCRIPT})")
        
        # シグナルハンドラー設定
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """終了シグナルを処理"""
        print("\nShutting down worker pool...")
        self.running = False
        self.shutdown_all_workers()
        sys.exit(0)
    
    def get_pending_task_count(self) -> int:
        """保留中のタスク数を取得"""
        stats = db.get_task_statistics()
        return stats.get('pending', 0)
    
    def get_active_worker_count(self) -> int:
        """アクティブなワーカー数を取得（データベース内の全アクティブワーカー）"""
        try:
            workers = db.get_active_workers(timeout_seconds=60)
            return len(workers)
        except Exception as e:
            print(f"Error getting active worker count: {e}")
            # フォールバック: 自分が管理するワーカーのみ
            with self.lock:
                return len([w for w in self.workers.values() if w.poll() is None])
    
    def get_active_task_count(self) -> int:
        """アクティブなタスク数を取得（進行中のタスク数）"""
        try:
            stats = db.get_task_statistics()
            return stats.get('in_progress', 0) + stats.get('processing', 0)
        except Exception as e:
            print(f"Error getting active task count: {e}")
            return 0
    
    def spawn_worker(self, worker_id: Optional[str] = None) -> str:
        """新しいワーカーを起動"""
        if worker_id is None:
            worker_id = f"worker_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:17]}"
        
        print(f"🚀 Spawning new worker: {worker_id}")
        
        # 環境変数を設定
        env = os.environ.copy()
        env['WORKER_ID'] = worker_id
        env['KOUBOU_HOME'] = KOUBOU_HOME
        env['WORKER_AUTH_TOKEN'] = f"{KOUBOU_HOME}_POOL_MANAGER"  # 認証トークン
        
        # ログファイル
        log_file = LOG_DIR / f"{worker_id}.log"
        
        # ワーカープロセスを起動（venv Pythonを使用）
        python_executable = f"{KOUBOU_HOME}/venv/bin/python"
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                [python_executable, WORKER_SCRIPT],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT
            )
        
        with self.lock:
            self.workers[worker_id] = process
            self.worker_stats[worker_id] = {
                'started_at': datetime.now(),
                'tasks_processed': 0,
                'status': 'running'
            }
        
        # DBにワーカーを登録
        self._register_worker(worker_id)
        
        return worker_id
    
    def _register_worker(self, worker_id: str):
        """ワーカーをデータベースに登録"""
        db.register_worker(worker_id)
    
    def shutdown_worker(self, worker_id: str):
        """ワーカーを停止"""
        with self.lock:
            if worker_id in self.workers:
                process = self.workers[worker_id]
                if process.poll() is None:
                    print(f"🛑 Shutting down worker: {worker_id}")
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                
                del self.workers[worker_id]
                self.worker_stats[worker_id]['status'] = 'stopped'
                self.worker_stats[worker_id]['stopped_at'] = datetime.now()
        
        # DBのステータスを更新
        db.update_worker_status(worker_id, 'offline')
    
    def shutdown_all_workers(self):
        """すべてのワーカーを停止"""
        worker_ids = list(self.workers.keys())
        for worker_id in worker_ids:
            self.shutdown_worker(worker_id)
    
    def scale_workers(self):
        """🚦 タスクキュー機能付きワーカー数調整"""
        pending_tasks = self.get_pending_task_count()
        active_tasks = self.get_active_task_count()
        active_workers = self.get_active_worker_count()
        
        print(f"📊 Status: {pending_tasks} pending tasks, {active_tasks} active tasks, {active_workers} active workers")
        print(f"🚦 Queue limit: {self.max_active_tasks} max active tasks")
        
        # 🚦 キュー制御：アクティブタスク数が上限に達している場合はワーカー起動を制限
        if active_tasks >= self.max_active_tasks:
            print(f"⏸️ Task queue full ({active_tasks}/{self.max_active_tasks}), waiting for tasks to complete")
            return
        
        # スケールアップの判定（キュー制限内で）
        # タスクがあるのにワーカーがいない場合は即座に起動
        if pending_tasks > 0 and active_workers == 0:
            print(f"⚡ No workers available, spawning worker for {pending_tasks} pending tasks")
            self.spawn_worker()
        # キューに余裕があり、待機タスクがある場合にワーカー追加
        elif pending_tasks > 0 and active_tasks < self.max_active_tasks and active_workers < self.max_workers:
            # キューの空き分だけタスクを処理可能
            available_slots = self.max_active_tasks - active_tasks
            workers_needed = min(pending_tasks, available_slots, self.max_workers - active_workers)
            
            if workers_needed > 0:
                print(f"📈 Queue scaling: adding {workers_needed} workers (available slots: {available_slots})")
                for _ in range(workers_needed):
                    self.spawn_worker()
        
        # スケールダウンの判定
        elif pending_tasks == 0 and active_workers > self.min_workers:
            # タスクがない場合は余分なワーカーを削減
            workers_to_remove = active_workers - self.min_workers
            idle_workers = self.get_idle_workers()
            
            if workers_to_remove > 0 and idle_workers:
                print(f"📉 Scaling down: removing {min(workers_to_remove, len(idle_workers))} idle workers")
                for worker_id in idle_workers[:workers_to_remove]:
                    self.shutdown_worker(worker_id)
    
    def get_idle_workers(self) -> List[str]:
        """アイドル状態のワーカーを取得"""
        workers = db.get_active_workers(timeout_seconds=30)
        return [w['worker_id'] for w in workers if w['status'] == 'idle']
    
    def cleanup_dead_workers(self):
        """停止したワーカーをクリーンアップ"""
        with self.lock:
            dead_workers = []
            for worker_id, process in self.workers.items():
                if process.poll() is not None:
                    dead_workers.append(worker_id)
            
            for worker_id in dead_workers:
                print(f"☠️ Cleaning up dead worker: {worker_id}")
                # プロセスを確実に終了
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                    except:
                        pass
                
                # データベースからも削除
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE workers SET status = 'offline' WHERE worker_id = ?", (worker_id,))
                        conn.commit()
                except Exception as e:
                    logger.error(f"Failed to update worker status to offline: {e}", exc_info=True)
                
                del self.workers[worker_id]
                self.worker_stats[worker_id]['status'] = 'crashed'
    
    def print_stats(self):
        """統計情報を表示"""
        print("\n" + "="*50)
        print("Worker Pool Statistics")
        print("="*50)
        
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # ワーカー統計
                cursor.execute("""
                    SELECT worker_id, status, tasks_completed, tasks_failed, last_heartbeat
                    FROM workers
                    WHERE last_heartbeat > datetime('now', '-5 minutes')
                    ORDER BY worker_id
                """)
                
                workers = cursor.fetchall()
                if workers:
                    print("\nActive Workers:")
                    for w in workers:
                        success_rate = 0
                        if w[2] + w[3] > 0:
                            success_rate = (w[2] / (w[2] + w[3])) * 100
                        print(f"  • {w[0]}: {w[1]} | Tasks: {w[2]} completed, {w[3]} failed ({success_rate:.1f}% success)")
                
                # タスク統計
                cursor.execute("""
                    SELECT status, COUNT(*) FROM task_master
                    GROUP BY status
                """)
                
                task_stats = cursor.fetchall()
                if task_stats:
                    print("\nTask Statistics:")
                    for stat in task_stats:
                        print(f"  • {stat[0]}: {stat[1]} tasks")
        except Exception as e:
            logger.error(f"Failed to print stats: {e}", exc_info=True)
            print(f"Error retrieving statistics: {e}")
        print("="*50 + "\n")
    
    def run(self):
        """メインループ"""
        print("🎯 Worker Pool Manager Started")
        print(f"Configuration: min={self.min_workers}, max={self.max_workers} workers")
        
        # APIサーバーを起動（監視用と制御用を分離）
        self.api = PoolManagerAPI(self)
        self.api.start_servers()
        
        # 初期ワーカーを起動（min_workersが0の場合はタスク待機）
        if self.min_workers > 0:
            print(f"🚀 Starting {self.min_workers} initial workers")
            for i in range(self.min_workers):
                self.spawn_worker()
        else:
            print("⏳ Starting with 0 workers, will spawn on demand when tasks arrive")
        
        last_stats_time = time.time()
        
        while self.running:
            try:
                # ワーカー数を調整
                self.scale_workers()
                
                # 死んだワーカーをクリーンアップ
                self.cleanup_dead_workers()
                
                # 定期的に統計を表示
                if time.time() - last_stats_time > 30:
                    self.print_stats()
                    last_stats_time = time.time()
                
                # 待機
                time.sleep(5)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(5)
        
        # 終了処理
        self.shutdown_all_workers()
        print("Worker Pool Manager stopped")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Worker Pool Manager")
    parser.add_argument("--min", type=int, default=1, help="Minimum number of workers")
    parser.add_argument("--max", type=int, default=3, help="Maximum number of workers (default: 3 for stability)")
    parser.add_argument("--max-active-tasks", type=int, default=2, help="Maximum number of active tasks (default: 2)")
    args = parser.parse_args()
    
    # 警告を表示
    if args.max > 4:
        print(f"⚠️  Warning: Running with {args.max} max workers may cause LLM server overload")
        print("   Recommended max workers: 3-4 for stable operation")
    
    manager = WorkerPoolManager(min_workers=args.min, max_workers=args.max, max_active_tasks=args.max_active_tasks)
    manager.run()