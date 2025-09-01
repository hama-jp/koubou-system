#!/usr/bin/env python3
"""
ローカルワーカー - Ollamaを使用してタスクを処理
"""

import json
import os
import subprocess
import sys
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common.database import get_db_manager

# 環境変数から設定を取得
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
LOG_DIR = Path(f"{KOUBOU_HOME}/logs/workers")

# データベースマネージャーを初期化
db = get_db_manager(DB_PATH)

# ロガーの設定
worker_id_for_log = os.environ.get('WORKER_ID', f"worker_{os.getpid()}")
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"{worker_id_for_log}.log"

# logging設定
# ファイルハンドラ：詳細なデバッグ情報
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# ストリームハンドラ（コンソール出力）：重要な情報のみ
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter('%(message)s'))

# ルートロガーにハンドラを追加
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        file_handler,
        stream_handler
    ]
)

class LocalWorker:
    """Ollamaを使用してタスクを処理するワーカー"""
    
    def __init__(self):
        self.worker_id = os.environ.get('WORKER_ID', f"worker_{os.getpid()}")
        self.model = "gpt-oss:20b"
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing worker {self.worker_id}")
        self.max_retries = 3  # リトライ回数
        self.timeout = 120  # タイムアウト秒数（増加）
        self.register_worker()
    
    def register_worker(self):
        """ワーカーをデータベースに登録"""
        if db.register_worker(self.worker_id):
            self.logger.info(f"Worker {self.worker_id} registered in DB.")
        else:
            self.logger.error(f"Failed to register worker {self.worker_id}")

    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """次のタスクを取得"""
        try:
            pending_tasks = db.get_pending_tasks(limit=1)
            if pending_tasks:
                row = pending_tasks[0]
                task_id = row['task_id']
                
                # タスクをワーカーに割り当て
                if db.assign_task_to_worker(task_id, self.worker_id):
                    self.logger.info(f"Picked up task {task_id}")
                    # ワーカーステータスを更新
                    db.update_worker_status(self.worker_id, 'busy', task_id)
                    
                    content_str = row["content"] or '{}'
                    context_str = row.get("context", '{}')
                    
                    task = {
                        'task_id': task_id,
                        'content': json.loads(content_str),
                        'context': json.loads(context_str)
                    }
                    return task
                else:
                    return None
        except sqlite3.Error as e:
            self.logger.error(f"Database error while getting task: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for task {task_id}: {e}. Content: {row.get('content', 'N/A')}")
            if task_id:
                self.fail_task(task_id, {"error": "Invalid JSON format in task content"})
        return None

    def fail_task(self, task_id: str, result: Dict[str, Any]):
        """タスクを失敗としてマーク"""
        self.logger.warning(f"Marking task {task_id} as failed.")
        self.update_task_result(task_id, result)

    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """タスクを処理"""
        task_content = task.get('content', {})
        task_type = task_content.get('type', 'general')
        prompt = task_content.get('prompt', '')
        self.logger.info(f"Processing task {task['task_id']} of type '{task_type}'")
        
        if not prompt:
            return {'success': False, 'output': '', 'error': 'Prompt is empty'}

        # LLM処理中ステータスに変更
        db.update_worker_status(self.worker_id, 'processing', task['task_id'])

        if task_type == 'code':
            result = self.run_codex_task(prompt)
        else:
            result = self.run_ollama_task(prompt)
        
        return {
            'success': result.get('success', False),
            'output': result.get('output', ''),
            'error': result.get('error', None)
        }
    
    def run_codex_task(self, prompt: str) -> Dict[str, Any]:
        """Codex CLIを使用してタスクを実行（リトライ付き）"""
        codex_script = f"{KOUBOU_HOME}/scripts/codex-exec.sh"
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Executing codex script: {codex_script} (attempt {attempt + 1}/{self.max_retries})")
                result = subprocess.run(
                    [codex_script, prompt],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False
                )
                if result.returncode == 0:
                    return {
                        'success': True,
                        'output': result.stdout,
                        'error': None
                    }
                else:
                    self.logger.error(f"Codex script failed with stderr: {result.stderr}")
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt  # 指数バックオフ
                        self.logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        return {
                            'success': False,
                            'output': result.stdout,
                            'error': result.stderr
                        }
            except subprocess.TimeoutExpired:
                self.logger.error(f"Codex task timed out (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return {'success': False, 'output': '', 'error': 'Task timeout after retries'}
            except Exception as e:
                self.logger.exception("An unexpected error occurred in run_codex_task")
                return {'success': False, 'output': '', 'error': str(e)}
        
        return {'success': False, 'output': '', 'error': 'Max retries exceeded'}

    def run_ollama_task(self, prompt: str) -> Dict[str, Any]:
        """Ollamaを直接使用してタスクを実行（リトライ付き）"""
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Running general task with model {self.model} (attempt {attempt + 1}/{self.max_retries})")
                result = subprocess.run(
                    ["ollama", "run", self.model, prompt],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False
                )
                if result.stdout:
                    return {'success': True, 'output': result.stdout, 'error': None}
                elif attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 指数バックオフ
                    self.logger.info(f"Empty response, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return {'success': False, 'output': '', 'error': 'Empty response after retries'}
            except subprocess.TimeoutExpired:
                self.logger.error(f"Ollama task timed out (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return {'success': False, 'output': '', 'error': 'Task timeout after retries'}
            except Exception as e:
                self.logger.exception("An unexpected error occurred in run_ollama_task")
                return {'success': False, 'output': '', 'error': str(e)}
        
        return {'success': False, 'output': '', 'error': 'Max retries exceeded'}

    def update_task_result(self, task_id: str, result: Dict[str, Any]):
        """タスク結果を更新"""
        status = 'completed' if result.get('success') else 'failed'
        
        # タスクステータスを更新
        if db.update_task_status(task_id, status, json.dumps(result)):
            self.logger.info(f"Updated task {task_id} to {status}")
            
            # 親方への通知を送信
            self.send_completion_notification(task_id, status, result)
        else:
            self.logger.error(f"Failed to update task {task_id}")
        
        # ワーカー統計を更新
        db.increment_worker_stats(self.worker_id, result.get('success', False))

    def send_completion_notification(self, task_id: str, status: str, result: Dict[str, Any]):
        """タスク完了通知を送信"""
        try:
            from common.notification_hooks import get_notification_hook
            
            # タスク詳細を取得
            task_details = db.get_task(task_id)
            if not task_details:
                self.logger.warning(f"Cannot find task details for {task_id}")
                return
            
            # 通知フックを取得
            hook = get_notification_hook()
            
            # 成功・失敗に応じて通知を送信
            if status == 'completed':
                hook.notify_task_completed(task_id, task_details)
            else:
                error_info = result.get('error', '不明なエラー')
                hook.notify_task_failed(task_id, task_details, error_info)
                
        except Exception as e:
            self.logger.error(f"Failed to send completion notification: {e}")

    def run(self):
        """メインループ"""
        self.logger.info(f"Local Worker {self.worker_id} started.")
        
        while True:
            try:
                # アイドル状態に設定
                db.update_worker_status(self.worker_id, 'idle')
                
                task = self.get_next_task()
                
                if task:
                    # タスク処理中に設定
                    db.update_worker_status(self.worker_id, 'working', task['task_id'])
                    self.logger.info(f"Starting to process task {task['task_id']}")
                    
                    result = self.process_task(task)
                    self.update_task_result(task['task_id'], result)
                    self.logger.info(f"Finished task {task['task_id']}")
                else:
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                self.logger.info("Shutdown signal received. Exiting...")
                break
            except Exception:
                self.logger.exception("An unexpected error occurred in the main loop.")
                time.sleep(5)

if __name__ == "__main__":
    worker = LocalWorker()
    worker.run()
