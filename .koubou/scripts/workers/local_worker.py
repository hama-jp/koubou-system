#!/usr/bin/env python3
"""
ローカルワーカー - Gemini CLI (LMStudio) を使用してタスクを処理
"""

import json
import os
import subprocess
import sys
import logging
import time
import sqlite3
import signal
import atexit
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# 環境変数から設定を取得
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')

# 共通モジュールのパスを追加
common_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, common_path)

try:
    from common.database import get_db_manager
    from common.python_executor import PythonExecutor
    from common.task_result_manager import TaskResultManager
    from common.ollama_config import get_ollama_config
    from common.config import get_config
except ImportError as e:
    # フォールバック：絶対パスでインポート
    koubou_scripts_path = os.path.join(KOUBOU_HOME, 'scripts')
    if koubou_scripts_path not in sys.path:
        sys.path.insert(0, koubou_scripts_path)
    from common.database import get_db_manager
    from common.python_executor import PythonExecutor
    from common.task_result_manager import TaskResultManager
    from common.ollama_config import get_ollama_config
    from common.config import get_config
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
LOG_DIR = Path(f"{KOUBOU_HOME}/logs/workers")

# データベースマネージャーを初期化
db = get_db_manager(DB_PATH)

# ロガーの設定
worker_id_for_log = os.environ.get('WORKER_ID', f"gemini_worker_{os.getpid()}")
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"{worker_id_for_log}.log"

# logging設定
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter('%(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, stream_handler]
)

class GeminiLocalWorker:
    """Gemini Repo CLI (ollama + gpt-oss:20b) を使用してタスクを処理するワーカー"""
    
    def __init__(self, model_key: Optional[str] = None):
        # Worker Pool Manager経由での起動を確認
        auth_token = os.environ.get('WORKER_AUTH_TOKEN')
        expected_token = os.environ.get('KOUBOU_HOME', '') + '_POOL_MANAGER'
        
        if auth_token != expected_token:
            self.logger = logging.getLogger(__name__)
            self.logger.error("❌ ワーカーは Worker Pool Manager 経由でのみ起動可能です")
            self.logger.error("使用方法: .koubou/start_system.sh または worker_pool_manager.py を使用してください")
            sys.exit(1)
        
        self.worker_id = os.environ.get('WORKER_ID', f"gemini_worker_{os.getpid()}")
        
        # Ollama設定を読み込み
        self.ollama_config = get_ollama_config()
        
        # モデルキーが環境変数で指定されている場合は優先
        model_key = model_key or os.environ.get('OLLAMA_MODEL_KEY', None)
        
        # モデル設定を取得
        self.model_key = model_key
        self.model = self.ollama_config.get_model_name(model_key)
        self.model_options = self.ollama_config.get_model_options(model_key)
        self.server_host = self.ollama_config.get_server_host()
        
        # max_tokensを環境変数から取得（workers.yamlから渡される）
        self.max_tokens = int(os.environ.get('MAX_TOKENS', '32768'))
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing Gemini worker {self.worker_id}")
        self.logger.info(f"Using model: {self.model} (key: {self.model_key or 'default'})")
        self.logger.info(f"Model options: {self.model_options}")
        self.logger.info(f"Max tokens: {self.max_tokens}")
        self.max_retries = 3
        self.timeout = 600  # 10分に延長（ファイルカウントタスク対応）
        
        # Python実行環境の統一化
        self.python_executor = PythonExecutor(KOUBOU_HOME)
        
        self.register_worker()
        
        # クリーンアップハンドラーを登録
        signal.signal(signal.SIGTERM, self.cleanup_handler)
        signal.signal(signal.SIGINT, self.cleanup_handler)
        atexit.register(self.cleanup)
    
    def register_worker(self):
        """ワーカーをデータベースに登録"""
        # 既存のワーカーレコードをクリーンアップ
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM workers WHERE worker_id = ?", (self.worker_id,))
                conn.commit()
        except Exception as e:
            self.logger.warning(f"Failed to cleanup existing worker record: {e}")
        
        if db.register_worker(self.worker_id):
            self.logger.info(f"Gemini worker {self.worker_id} registered in DB.")
        else:
            self.logger.error(f"Failed to register worker {self.worker_id}")

    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """次のタスクを取得（アトミック）"""
        try:
            # アトミックなタスク取得メソッドを使用
            row = db.acquire_next_task(self.worker_id)
            if row:
                task_id = row['task_id']
                self.logger.info(f"Picked up task {task_id}")
                
                content_str = row["content"] or '{}'
                context_str = '{}'
                
                try:
                    task = {
                        'task_id': task_id,
                        'content': json.loads(content_str),
                        'context': json.loads(context_str)
                    }
                    return task
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON decode error for task {task_id}: {e}. Content: {row.get('content', 'N/A')}")
                    self.fail_task(task_id, {"error": "Invalid JSON format in task content"})
                    return None
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error getting next task: {e}", exc_info=True)
            return None

    def fail_task(self, task_id: str, result: Dict[str, Any]):
        """タスクを失敗としてマーク"""
        self.logger.warning(f"Marking task {task_id} as failed.")
        self.update_task_result(task_id, result)
    
    def check_for_task_notifications(self) -> Optional[str]:
        """Pool Managerからのタスク割り当て通知をチェック"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT task_id FROM worker_notifications
                    WHERE worker_id = ? AND notification_type = 'task_assigned' AND processed = 0
                    ORDER BY created_at ASC LIMIT 1
                """, (self.worker_id,))
                row = cursor.fetchone()
                
                if row:
                    task_id = row['task_id']
                    # 通知を処理済みにマーク
                    cursor.execute("""
                        UPDATE worker_notifications 
                        SET processed = 1 
                        WHERE worker_id = ? AND task_id = ? AND notification_type = 'task_assigned'
                    """, (self.worker_id, task_id))
                    conn.commit()
                    
                    self.logger.info(f"📬 Received task assignment notification: {task_id}")
                    return task_id
                
        except Exception as e:
            self.logger.error(f"Error checking notifications: {e}")
            
        return None
    
    def get_assigned_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """指定されたタスクIDのタスクを取得"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT task_id, content 
                    FROM task_master
                    WHERE task_id = ? AND assigned_to = ? AND status = 'in_progress'
                """, (task_id, self.worker_id))
                row = cursor.fetchone()
                
                if row:
                    content_str = row["content"] or '{}'
                    
                    try:
                        task = {
                            'task_id': task_id,
                            'content': json.loads(content_str),
                            'context': {}
                        }
                        return task
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to decode task content: {e}")
                        return None
                    
        except Exception as e:
            self.logger.error(f"Error retrieving assigned task {task_id}: {e}")
            
        return None

    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """タスクを処理（ファイル操作対応版）"""
        task_content = task.get('content', {})
        task_type = task_content.get('type', 'general')
        prompt = task_content.get('prompt', '')
        
        # ファイル操作パラメータを取得
        input_files = task_content.get('files', [])
        output_file = task_content.get('output_file', None)
        
        # パス検証（セキュリティ強化）
        config = get_config()
        for file_path in input_files:
            is_valid, error_msg = config.validate_file_operation(file_path)
            if not is_valid:
                self.logger.error(f"Invalid file path: {file_path} - {error_msg}")
                return {'success': False, 'output': '', 'error': f'Security validation failed: {error_msg}'}
        
        if output_file:
            is_valid, error_msg = config.validate_file_operation(output_file)
            if not is_valid:
                self.logger.error(f"Invalid output file path: {output_file} - {error_msg}")
                return {'success': False, 'output': '', 'error': f'Security validation failed: {error_msg}'}
        
        self.logger.info(f"Processing task {task['task_id']} of type '{task_type}' with Gemini Repo CLI")
        if input_files:
            self.logger.info(f"Input files: {input_files}")
        if output_file:
            self.logger.info(f"Output file: {output_file}")
        
        if not prompt:
            return {'success': False, 'output': '', 'error': 'Prompt is empty'}

        # LLM処理中ステータスに変更
        db.update_worker_status(self.worker_id, 'processing', task['task_id'])

        # ファイル操作対応版でGemini CLIを実行
        result = self.run_gemini_task_with_files(prompt, input_files, output_file)
        
        # 作業成果物を自動保存（親方確認用）
        task_result = {
            'success': result.get('success', False),
            'output': result.get('output', ''),
            'error': result.get('error', None),
            'files_processed': len(input_files),
            'output_file': output_file,
            'prompt': prompt  # TaskResultManagerで使用
        }
        
        # ファイルに直接保存して親方の負担軽減
        self.logger.info(f"🔄 Starting automatic file save for task {task['task_id']}")
        try:
            self.save_deliverable_files(task['task_id'], task_result, prompt, task_type)
            self.logger.info(f"✅ Automatic file save completed for task {task['task_id']}")
        except Exception as e:
            self.logger.error(f"❌ Failed to save deliverable files for task {task['task_id']}: {e}")
            # スタックトレースも出力
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
        
        return task_result
    
    def run_gemini_task_with_files(self, prompt: str, input_files: list = None, output_file: str = None) -> Dict[str, Any]:
        """ファイル操作対応版 Gemini Repo CLIを使用してタスクを実行（フォールバック無効化）"""
        # 常にgemini-repo-cli直接実行を使用（フォールバック無効化）
        return self.run_gemini_repo_cli_direct(prompt, input_files or [], output_file)
    
    def run_gemini_repo_cli_direct(self, prompt: str, input_files: list, output_file: str = None) -> Dict[str, Any]:
        """gemini-repo-cliを直接実行（ファイル操作機能付き）"""
        import sys
        import os
        
        # gemini_repoモジュールのパスを追加
        project_root = os.path.join(KOUBOU_HOME, "..")
        gemini_repo_cli_path = os.path.join(project_root, "gemini-repo-cli", "src")
        if gemini_repo_cli_path not in sys.path:
            sys.path.insert(0, gemini_repo_cli_path)
            self.logger.info(f"Added gemini-repo-cli path: {gemini_repo_cli_path}")
        
        # virtualenv内のgemini_repoも試す
        venv_path = f"{KOUBOU_HOME}/venv/lib/python3.11/site-packages"
        if venv_path not in sys.path:
            sys.path.insert(0, venv_path)
        
        try:
            # gemini_repoモジュールから直接OllamaAPIをインポート（遅延ロード版）
            from gemini_repo.base_api import BaseRepoAPI
            from gemini_repo.ollama_api import OllamaRepoAPI
            
            # OllamaRepoAPIインスタンスを作成（設定ファイルから取得したモデルを使用）
            api = OllamaRepoAPI(model_name=self.model, host=self.server_host)
            
            # モデルオプションを設定
            if hasattr(api, 'options'):
                # max_tokensをnum_ctxとして設定（Ollamaのパラメータ名）
                api.options['num_ctx'] = self.max_tokens
                
                # その他のモデルオプションも適用
                if self.model_options:
                    api.options.update(self.model_options)
                
                self.logger.info(f"Applied model options: {api.options}")
            
            # ファイル読み込みとコンテキスト構築
            project_root = os.path.join(KOUBOU_HOME, "..")
            repo_name = "koubou-system"
            target_file = output_file or "generated_content.txt"
            
            # 🔧 絶対パス変換：相対パスを project_root 基準の絶対パスに変換
            absolute_input_files = []
            for file_path in input_files:
                if os.path.isabs(file_path):
                    # 既に絶対パスの場合はそのまま使用
                    absolute_input_files.append(file_path)
                else:
                    # 相対パスの場合は project_root を基準に絶対パスに変換
                    absolute_path = os.path.abspath(os.path.join(project_root, file_path))
                    absolute_input_files.append(absolute_path)
            
            self.logger.info(f"Using gemini-repo-cli with files: {input_files}")
            self.logger.info(f"Converted to absolute paths: {absolute_input_files}")
            
            # gemini-repo-cliのgenerate_contentメソッドを呼び出し
            result = api.generate_content(
                repo_name=repo_name,
                file_paths=absolute_input_files,
                target_file_name=target_file,
                prompt=prompt
            )
            
            # 出力ファイルが指定されている場合は書き込み
            if output_file:
                output_path = os.path.join(project_root, output_file)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(result)
                self.logger.info(f"Output written to: {output_file}")
            
            return {
                'success': True,
                'output': result,
                'error': None
            }
            
        except ImportError as e:
            self.logger.error(f"Failed to import gemini_repo modules: {e}")
            # フォールバック無効化：ImportErrorで失敗とする
            return {
                'success': False,
                'output': '',
                'error': f'gemini-repo-cli import failed: {str(e)}'
            }
        except Exception as e:
            self.logger.error(f"Error in run_gemini_repo_cli_direct: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }
    
    def run_gemini_task(self, prompt: str) -> Dict[str, Any]:
        """旧バージョン: 新しいrun_gemini_task_with_filesを使用してください"""
        # 常にファイル操作対応版を使用（空のファイルリストで呼び出し）
        return self.run_gemini_task_with_files(prompt, [], None)
    
    def run_gemini_task_legacy(self, prompt: str) -> Dict[str, Any]:
        """レガシー版: Gemini Repo CLIをシェル経由で実行（非推奨）"""
        gemini_script = f"{KOUBOU_HOME}/scripts/gemini-repo-exec.sh"
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Executing Gemini Repo CLI script: {gemini_script} (attempt {attempt + 1}/{self.max_retries})")
                self.logger.debug(f"Prompt length: {len(prompt)} characters")
                self.logger.debug(f"Timeout set to: {self.timeout} seconds")
                
                # 長時間タスク用にハートビートを送信しながら実行
                import threading
                import signal
                
                # ハートビート送信用のフラグとスレッド
                self.processing = True
                def send_heartbeat():
                    heartbeat_count = 0
                    while self.processing:
                        heartbeat_count += 1
                        db.update_worker_status(self.worker_id, 'processing', None)
                        self.logger.debug(f"Heartbeat #{heartbeat_count} sent")
                        time.sleep(5)  # 5秒ごとにハートビート
                
                heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
                heartbeat_thread.start()
                
                # プロセス開始時刻を記録
                start_time = time.time()
                self.logger.info(f"Starting subprocess at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # サブプロセスを起動
                process = subprocess.Popen(
                    [gemini_script, prompt],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid  # プロセスグループを作成
                )
                
                self.logger.info(f"Subprocess started with PID: {process.pid}")
                
                try:
                    # タイムアウト付きで待機
                    stdout, stderr = process.communicate(timeout=self.timeout)
                    elapsed_time = time.time() - start_time
                    
                    self.logger.info(f"Subprocess completed in {elapsed_time:.2f} seconds")
                    self.logger.debug(f"Return code: {process.returncode}")
                    
                    # ハートビート送信を停止
                    self.processing = False
                    heartbeat_thread.join(timeout=1)
                    
                    if process.returncode == 0:
                        self.logger.info(f"Task completed successfully")
                        return {
                            'success': True,
                            'output': stdout.strip(),
                            'error': None
                        }
                    elif process.returncode == 124:
                        # timeoutコマンドによるタイムアウト
                        self.logger.error(f"Task killed by timeout command in script (exit code 124)")
                        if attempt < self.max_retries - 1:
                            wait_time = 2 ** attempt
                            self.logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            return {
                                'success': False,
                                'output': stdout,
                                'error': f'Script-level timeout (exit code 124): {stderr}'
                            }
                    else:
                        self.logger.error(f"Gemini Repo CLI script failed with code {process.returncode}")
                        self.logger.error(f"stderr: {stderr}")
                        if attempt < self.max_retries - 1:
                            wait_time = 2 ** attempt  # 指数バックオフ
                            self.logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            return {
                                'success': False,
                                'output': stdout,
                                'error': stderr
                            }
                            
                except subprocess.TimeoutExpired:
                    elapsed_time = time.time() - start_time
                    self.logger.error(f"Python subprocess timeout after {elapsed_time:.2f} seconds")
                    
                    # プロセスグループ全体を終了
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        time.sleep(2)  # 終了を待つ
                        if process.poll() is None:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception as e:
                        self.logger.error(f"Failed to kill process group: {e}")
                    
                    # ハートビート送信を停止
                    self.processing = False
                    
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        self.logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        return {'success': False, 'output': '', 'error': f'Python timeout after {elapsed_time:.2f}s'}
                        
            except Exception as e:
                # ハートビート送信を停止
                self.processing = False
                self.logger.exception(f"Unexpected error in run_gemini_task: {e}")
                return {'success': False, 'output': '', 'error': str(e)}
        
        return {'success': False, 'output': '', 'error': 'Max retries exceeded'}

    def update_task_result(self, task_id: str, result: Dict[str, Any]):
        """タスク結果を更新してワーカーをアイドル状態に戻す"""
        try:
            # 本番環境での成果物保存
            try:
                # タスク内容を取得（簡易版）
                task_content = result.get('prompt', f'Task {task_id}')
                
                manager = TaskResultManager()
                saved_files = manager.save_task_deliverable(
                    result, 
                    task_id, 
                    "general",  # task_type
                    task_content,  # task_content
                    5  # priority (default)
                )
                
                self.logger.info(f"📋 Task deliverable saved: {len(saved_files)} files")
                for file_type, file_path in saved_files.items():
                    self.logger.info(f"  {file_type}: {file_path.name}")
                    
            except Exception as e:
                self.logger.warning(f"Failed to save task deliverable: {e}")
            
            # タスク完了をDBに記録（統計も同時に更新）
            success = result.get('success', True)
            db.complete_task_with_stats(
                task_id,
                self.worker_id,
                json.dumps(result),
                success=success
            )
            
            success_indicator = "✅" if result.get('success') else "❌"
            self.logger.info(f"{success_indicator} Task {task_id} completed")
        except sqlite3.Error as e:
            self.logger.error(f"Database error while updating task result: {e}")
    
    def save_deliverable_files(self, task_id: str, task_result: Dict[str, Any], prompt: str, task_type: str):
        """職人の作業成果を実際のファイルとして保存（親方の負担軽減）"""
        self.logger.info(f"📁 save_deliverable_files called for task {task_id}")
        try:
            # 成果物を解析してファイルを生成
            output = task_result.get('output', '')
            self.logger.info(f"📄 Output length: {len(output)} characters")
            if not output:
                self.logger.warning(f"⚠️ No output content for task {task_id}, skipping file save")
                return
                
            # プロジェクトのルートディレクトリを特定
            project_root = self.detect_project_root(prompt)
            if not project_root:
                # デフォルトでワークスペース配下に保存
                project_root = os.getcwd()
                
            self.logger.info(f"💾 Saving deliverables for {task_id} to project: {project_root}")
            
            # コード生成の場合は実際のファイルに保存
            if self.is_code_generation_task(prompt, output):
                self.save_code_files(task_id, output, project_root, prompt)
            
            # ドキュメント生成の場合
            elif self.is_documentation_task(prompt, output):
                self.save_documentation_files(task_id, output, project_root)
            
            # 設定ファイル生成の場合
            elif self.is_config_task(prompt, output):
                self.save_config_files(task_id, output, project_root)
                
        except Exception as e:
            self.logger.error(f"Failed to save deliverable files: {e}")
    
    def detect_project_root(self, prompt: str) -> Optional[str]:
        """プロンプトからプロジェクトルートを推定"""
        import re
        
        # プロンプト内のファイルパス指定を検索
        path_patterns = [
            r'配置先[：:：]\s*([^\n\r]+)',
            r'保存先[：:：]\s*([^\n\r]+)',
            r'ファイル配置[：:：]\s*([^\n\r]+)',
            r'ディレクトリ[：:：]\s*([^\n\r]+)',
            r'フォルダ[：:：]\s*([^\n\r]+)'
        ]
        
        for pattern in path_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                path = match.group(1).strip()
                # パスのクリーンアップ（引用符や余分な文字を削除）
                path = path.strip('"\'`')
                
                # 相対パスを絶対パスに変換
                if not os.path.isabs(path):
                    # まずプロジェクトルートからの相対パスとして解釈
                    project_root = '/home/hama/project/koubou-system'
                    full_path = os.path.join(project_root, path)
                    
                    # ディレクトリが存在するか確認
                    if os.path.exists(full_path):
                        return full_path if os.path.isdir(full_path) else os.path.dirname(full_path)
                    
                    # 親ディレクトリが存在するか確認
                    parent_dir = os.path.dirname(full_path)
                    if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
                        return parent_dir
                    
                    # 現在のディレクトリからの相対パスとして試す
                    current_path = os.path.join(os.getcwd(), path)
                    if os.path.exists(current_path):
                        return current_path if os.path.isdir(current_path) else os.path.dirname(current_path)
                else:
                    # 絶対パスの場合
                    if os.path.exists(path):
                        return path if os.path.isdir(path) else os.path.dirname(path)
                    # 親ディレクトリが存在するか確認
                    parent_dir = os.path.dirname(path)
                    if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
                        return parent_dir
                    
        return None
    
    def is_code_generation_task(self, prompt: str, output: str) -> bool:
        """コード生成タスクかどうか判定"""
        code_keywords = ['実装', 'コード', 'API', 'エンドポイント', 'function', 'class', 'def ', 'import ', '```python', '```javascript', '```html']
        return any(keyword in prompt.lower() or keyword in output.lower() for keyword in code_keywords)
    
    def is_documentation_task(self, prompt: str, output: str) -> bool:
        """ドキュメント生成タスクかどうか判定"""
        doc_keywords = ['README', 'ドキュメント', 'マニュアル', 'ガイド', '説明書', 'API仕様']
        return any(keyword in prompt for keyword in doc_keywords)
    
    def is_config_task(self, prompt: str, output: str) -> bool:
        """設定ファイル生成タスクかどうか判定"""
        config_keywords = ['requirements.txt', 'package.json', '.env', 'config', '設定ファイル']
        return any(keyword in prompt for keyword in config_keywords)
    
    def save_code_files(self, task_id: str, output: str, project_root: str, prompt: str = ""):
        """コードファイルとして保存（改良版: Web開発ファイルに対応）"""
        import re
        from datetime import datetime
        
        self.logger.info(f"🔍 Analyzing output for code files...")
        
        # ファイル構成の指定を検索
        files_to_create = {}
        
        # パターン1: ファイル名セクションで区切られている場合
        # 例: /* ====================== index.html ====================== */
        section_pattern = r'/\*\s*=+\s*([^\s=]+\.\w+)\s*=+\s*\*/'
        sections = re.split(section_pattern, output)
        
        if len(sections) > 1:
            # セクション形式で分割されている
            for i in range(1, len(sections), 2):
                if i+1 < len(sections):
                    filename = sections[i].strip()
                    content = sections[i+1].strip()
                    
                    # コメントやマークダウンの装飾を削除
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```$', '', content)
                    
                    files_to_create[filename] = content
                    self.logger.info(f"📄 Found file section: {filename}")
        
        # パターン2: コードブロックにファイル名が記載されている場合
        if not files_to_create:
            code_blocks = re.findall(r'```(\w+)?\n(.*?)```', output, re.DOTALL)
            
            # 特定のファイル名を持つブロックを探す
            for block_content in code_blocks:
                lang = block_content[0] if isinstance(block_content, tuple) else None
                code = block_content[1] if isinstance(block_content, tuple) else block_content
                
                if not code or not isinstance(code, str):
                    continue
                    
                # ファイル名の推定
                if '<!DOCTYPE html>' in code or '<html' in code:
                    files_to_create['index.html'] = code.strip()
                elif 'body' in code and '{' in code and 'margin' in code:
                    files_to_create['style.css'] = code.strip()
                elif ('function' in code or 'const' in code) and 'document' in code:
                    files_to_create['script.js'] = code.strip()
        
        # パターン3: 通常のコードブロックから推定
        if not files_to_create:
            code_blocks = re.findall(r'```(\w+)?\n(.*?)```', output, re.DOTALL)
            
            for i, (lang, code) in enumerate(code_blocks):
                if not code.strip():
                    continue
                    
                # 言語に応じた拡張子を決定
                ext_map = {
                    'python': '.py', 'javascript': '.js', 'html': '.html', 
                    'css': '.css', 'json': '.json', 'bash': '.sh',
                    'sql': '.sql', 'yaml': '.yml', 'jsx': '.jsx', 
                    'typescript': '.ts', 'tsx': '.tsx'
                }
                
                # ファイル名を推定
                if lang and lang.lower() in ext_map:
                    ext = ext_map[lang.lower()]
                    if ext == '.html':
                        filename = 'index.html'
                    elif ext == '.css':
                        filename = 'style.css'
                    elif ext in ['.js', '.jsx']:
                        filename = 'script.js'
                    elif ext == '.py':
                        filename = 'main.py'
                    else:
                        filename = f"file_{i}{ext}"
                else:
                    # コンテンツから推定
                    if '<!DOCTYPE html>' in code or '<html' in code:
                        filename = 'index.html'
                    elif 'body' in code and '{' in code and '}' in code:
                        filename = 'style.css'
                    elif 'function' in code or 'const' in code or 'let' in code:
                        filename = 'script.js'
                    else:
                        filename = f"output_{i}.txt"
                
                files_to_create[filename] = code.strip()
                self.logger.info(f"📄 Found code block: {filename}")
        
        # ファイルを保存
        if files_to_create:
            # タスクIDを含むサブディレクトリを作成
            task_dir = os.path.join(project_root, f"task_{task_id}")
            os.makedirs(task_dir, exist_ok=True)
            
            for filename, content in files_to_create.items():
                filepath = os.path.join(task_dir, filename)
                
                # ディレクトリが存在しない場合は作成
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                self.logger.info(f"✅ Saved: {filepath}")
            
            # 使い方の説明ファイルも生成
            readme_content = f"""# タスク成果物: {task_id}

## 生成されたファイル
{chr(10).join(f"- {filename}" for filename in files_to_create.keys())}

## 使用方法
1. ブラウザで `index.html` を開く
2. または、HTTPサーバーで提供:
   ```bash
   python -m http.server 8000
   # http://localhost:8000 にアクセス
   ```

## タスク詳細
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            readme_path = os.path.join(task_dir, "README.md")
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            self.logger.info(f"📚 Saved README: {readme_path}")
        else:
            self.logger.warning(f"⚠️ No separate code files detected, analyzing as single output")
            # 単一ファイルとして保存
            filepath = os.path.join(project_root, f"output_{task_id}.txt")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(output)
            self.logger.info(f"📄 Saved as text: {filepath}")
    
    def save_documentation_files(self, task_id: str, output: str, project_root: str):
        """ドキュメントファイルとして保存"""
        filename = "README.md"
        if "API" in output:
            filename = "API_DOCS.md"
        elif "開発者" in output or "developer" in output.lower():
            filename = "DEVELOPER_GUIDE.md"
            
        filepath = os.path.join(project_root, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
            
        self.logger.info(f"📖 Saved documentation: {filepath}")
    
    def save_config_files(self, task_id: str, output: str, project_root: str):
        """設定ファイルとして保存"""
        if 'requirements.txt' in output or ('pip install' in output and any(pkg in output for pkg in ['fastapi', 'flask', 'django'])):
            filepath = os.path.join(project_root, 'requirements.txt')
            # requirements形式で抽出
            lines = []
            for line in output.split('\n'):
                if '==' in line or '>=' in line or line.strip().endswith('.txt'):
                    lines.append(line.strip())
            if lines:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                self.logger.info(f"⚙️ Saved config: {filepath}")

    def cleanup(self):
        """クリーンアップ処理"""
        try:
            db.update_worker_status(self.worker_id, 'offline', None)
            self.logger.info(f"Worker {self.worker_id} cleanup completed")
        except:
            pass
    
    def cleanup_handler(self, signum, frame):
        """シグナルハンドラー"""
        self.cleanup()
        sys.exit(0)

    def run(self):
        """メインループ"""
        self.logger.info(f"🚀 Gemini worker {self.worker_id} started (model: {self.model})")
        
        try:
            heartbeat_counter = 0
            while True:
                # Pool Managerからのタスク割り当て通知をチェック
                assigned_task_id = self.check_for_task_notifications()
                
                if assigned_task_id:
                    # 指定されたタスクを取得して処理
                    task = self.get_assigned_task(assigned_task_id)
                    if task:
                        self.logger.info(f"🔥 Processing assigned task: {assigned_task_id}")
                        result = self.process_task(task)
                        self.update_task_result(task['task_id'], result)
                    else:
                        self.logger.warning(f"Could not retrieve assigned task: {assigned_task_id}")
                else:
                    # 通知がない場合は少し待機
                    time.sleep(1)
                    # 10秒ごとにハートビートを送信
                    heartbeat_counter += 1
                    if heartbeat_counter >= 10:
                        db.update_worker_status(self.worker_id, 'idle', None)
                        heartbeat_counter = 0
        except KeyboardInterrupt:
            self.logger.info("🛑 Worker interrupted by user")
        except Exception as e:
            self.logger.error(f"💥 Unexpected error in worker main loop: {e}")
        finally:
            # ワーカーをオフラインに設定
            db.update_worker_status(self.worker_id, 'offline', None)
            self.logger.info(f"👋 Gemini worker {self.worker_id} stopped")

if __name__ == "__main__":
    worker = GeminiLocalWorker()
    worker.run()