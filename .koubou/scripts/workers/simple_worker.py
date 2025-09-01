#!/usr/bin/env python3
"""
シンプルワーカー - 基本的なタスク処理のみ（LLM無し）
テスト・デバッグ用の安定版ワーカー
"""

import json
import os
import sys
import logging
import time
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# 環境変数から設定を取得
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
WORKER_ID = os.environ.get('WORKER_ID', f"simple_worker_{os.getpid()}")

# 共通モジュールのパスを追加
common_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, common_path)

from common.database import get_db_manager

DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
LOG_DIR = Path(f"{KOUBOU_HOME}/logs/workers")

# データベースマネージャーを初期化
db = get_db_manager(DB_PATH)

# ロガーの設定
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"{WORKER_ID}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SimpleWorker:
    """シンプルなテスト用ワーカー"""
    
    def __init__(self):
        self.worker_id = WORKER_ID
        self.logger = logger
        self.register_worker()
        
    def register_worker(self):
        """ワーカーをデータベースに登録"""
        try:
            # 既存のレコードを削除
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workers WHERE worker_id = ?", (self.worker_id,))
            conn.commit()
            conn.close()
        except:
            pass
        
        if db.register_worker(self.worker_id):
            self.logger.info(f"Simple worker {self.worker_id} registered in DB.")
        else:
            self.logger.error(f"Failed to register worker {self.worker_id}")
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """次のタスクを取得"""
        try:
            pending_tasks = db.get_pending_tasks(limit=1)
            if pending_tasks:
                row = pending_tasks[0]
                task_id = row['task_id']
                
                if db.assign_task_to_worker(task_id, self.worker_id):
                    self.logger.info(f"Picked up task {task_id}")
                    db.update_worker_status(self.worker_id, 'busy', task_id)
                    
                    content_str = row["content"] or '{}'
                    task = {
                        'task_id': task_id,
                        'content': json.loads(content_str)
                    }
                    return task
        except Exception as e:
            self.logger.error(f"Error getting task: {e}")
        return None
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """タスクを処理（シンプル版）"""
        task_content = task.get('content', {})
        prompt = task_content.get('prompt', '')
        
        self.logger.info(f"Processing task {task['task_id']} (simple mode)")
        
        # シンプルな処理結果を返す
        result = {
            'success': True,
            'output': f"Task {task['task_id']} processed successfully by simple worker.\nPrompt: {prompt[:100]}...",
            'error': None
        }
        
        # 処理時間をシミュレート
        time.sleep(2)
        
        return result
    
    def update_task_result(self, task_id: str, result: Dict[str, Any]):
        """タスク結果を更新"""
        try:
            status = 'completed' if result.get('success') else 'failed'
            db.update_task_status(task_id, status, json.dumps(result))
            db.update_worker_stats(self.worker_id, result.get('success', False))
            db.update_worker_status(self.worker_id, 'idle', None)
            self.logger.info(f"Task {task_id} marked as {status}")
        except Exception as e:
            self.logger.error(f"Failed to update task result: {e}")
    
    def run(self):
        """メインループ"""
        self.logger.info(f"🚀 Simple worker {self.worker_id} started")
        
        try:
            heartbeat_counter = 0
            while True:
                task = self.get_next_task()
                if task:
                    result = self.process_task(task)
                    self.update_task_result(task['task_id'], result)
                else:
                    time.sleep(1)
                    heartbeat_counter += 1
                    if heartbeat_counter >= 10:
                        db.update_worker_status(self.worker_id, 'idle', None)
                        heartbeat_counter = 0
        except KeyboardInterrupt:
            self.logger.info("Worker interrupted")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            db.update_worker_status(self.worker_id, 'offline', None)
            self.logger.info(f"Worker {self.worker_id} stopped")

if __name__ == "__main__":
    worker = SimpleWorker()
    worker.run()