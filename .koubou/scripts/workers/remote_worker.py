#!/usr/bin/env python3
"""
リモートワーカー - LAN上のOllamaサーバーを使用する職人
LocalWorkerを継承し、gemini-repo-cli経由でリモートOllamaにアクセス
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, Optional

# LocalWorkerのインポート
from local_worker import GeminiLocalWorker, KOUBOU_HOME

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RemoteWorker(GeminiLocalWorker):
    """
    リモートOllamaサーバーを使用するワーカー
    LocalWorkerを継承し、gemini-repo-cli経由でアクセス
    """
    
    def __init__(self, worker_id: str, worker_config: dict):
        """
        リモートワーカーの初期化
        
        Args:
            worker_id: ワーカー識別子
            worker_config: ワーカー設定
        """
        # 環境変数を設定してから親クラスを初期化
        os.environ['WORKER_ID'] = worker_id
        # 注意: WORKER_AUTH_TOKENは必ずPool Managerから設定される必要がある
        
        # 基本設定を継承（model_keyは使わない）
        # 親クラスのコンストラクタで認証チェックが行われる
        super().__init__()
        
        # リモート特有の設定
        self.remote_host = worker_config.get('remote_host', 'localhost')
        self.remote_port = worker_config.get('remote_port', 11434)
        self.performance_factor = worker_config.get('performance_factor', 0.5)
        self.network_timeout = worker_config.get('network_timeout', 300)
        
        # gemini-repo-cli用の設定を更新
        self.server_host = f"http://{self.remote_host}:{self.remote_port}"
        
        # ワーカー識別情報
        self.worker_location = 'remote'
        self.endpoint_url = self.server_host
        
        logger.info(f"🌐 Remote worker initialized: {worker_id}")
        logger.info(f"   Endpoint: {self.server_host}")
        logger.info(f"   Model: {self.model}")
        logger.info(f"   Performance Factor: {self.performance_factor}")
    
    def health_check(self) -> bool:
        """リモートサーバーのヘルスチェック"""
        try:
            import requests
            response = requests.get(
                f"{self.server_host}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"✅ Health check passed for {self.worker_id}")
                return True
            else:
                logger.warning(f"⚠️ Health check failed for {self.worker_id}: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Health check error for {self.worker_id}: {e}")
            return False
    
    def run_gemini_repo_cli_direct(self, prompt: str, input_files: list, output_file: str = None) -> Dict[str, Any]:
        """
        リモートOllama向けにカスタマイズされたgemini-repo-cli実行
        """
        import sys
        import os
        import threading
        
        # gemini_repoモジュールのパスを追加
        project_root = os.path.join(KOUBOU_HOME, "..")
        gemini_repo_cli_path = os.path.join(project_root, "gemini-repo-cli", "src")
        if gemini_repo_cli_path not in sys.path:
            sys.path.insert(0, gemini_repo_cli_path)
        
        try:
            from gemini_repo.ollama_api import OllamaRepoAPI
            
            # リモートOllamaサーバーへの接続
            api = OllamaRepoAPI(
                model_name=self.model,
                host=self.server_host
            )
            
            # ネットワーク遅延を考慮した設定
            if hasattr(api, 'options'):
                model_options = {
                    **self.model_options,
                    'num_predict': 4096,  # レスポンスサイズ制限
                    'num_ctx': 8192,      # コンテキストサイズ
                }
                api.options.update(model_options)
                logger.info(f"Applied model options for remote: {model_options}")
            
            # ファイル読み込みとコンテキスト構築
            project_root = os.path.join(KOUBOU_HOME, "..")
            repo_name = "koubou-system"
            target_file = output_file or "generated_content.txt"
            
            # 絶対パス変換
            absolute_input_files = []
            for file_path in input_files:
                if os.path.isabs(file_path):
                    absolute_input_files.append(file_path)
                else:
                    absolute_path = os.path.abspath(os.path.join(project_root, file_path))
                    absolute_input_files.append(absolute_path)
            
            logger.info(f"🌐 Calling remote Ollama via gemini-repo-cli")
            logger.info(f"   Files: {input_files}")
            
            # 🔥 ハートビート送信を開始
            processing = True
            heartbeat_count = 0
            
            def send_heartbeat():
                nonlocal heartbeat_count, processing
                while processing:
                    try:
                        heartbeat_count += 1
                        # データベース経由でハートビート送信
                        # LocalWorkerと同様にグローバルdbを使用
                        from local_worker import db
                        with db.get_connection() as conn:
                            conn.execute("""
                                UPDATE workers 
                                SET last_heartbeat = datetime('now'), status = 'busy'
                                WHERE worker_id = ?
                            """, (self.worker_id,))
                        logger.debug(f"💓 Remote heartbeat #{heartbeat_count} sent")
                        time.sleep(15)  # 15秒間隔でハートビート送信
                    except Exception as e:
                        logger.error(f"Heartbeat error: {e}")
                        time.sleep(15)  # エラー時も15秒待機
            
            # ハートビートスレッド開始
            heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
            heartbeat_thread.start()
            
            try:
                # タイムアウト付きで実行
                start_time = time.time()
                result = api.generate_content(
                    repo_name=repo_name,
                    file_paths=absolute_input_files,
                    target_file_name=target_file,
                    prompt=prompt
                )
                elapsed = time.time() - start_time
                
                logger.info(f"✅ Remote response received in {elapsed:.2f}s")
                
                # 出力ファイルが指定されている場合は書き込み
                if output_file:
                    output_path = os.path.join(project_root, output_file)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(result)
                    logger.info(f"Output written to: {output_file}")
                
                return {
                    'success': True,
                    'output': result,
                    'error': None,
                    'execution_time': elapsed,
                    'worker_location': self.worker_location
                }
                
            finally:
                # ハートビート送信を停止
                processing = False
                heartbeat_thread.join(timeout=2)
                logger.info(f"💓 Heartbeat stopped after {heartbeat_count} beats")
            
        except Exception as e:
            logger.error(f"❌ Remote worker error: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'worker_location': self.worker_location
            }
    
    def register_with_manager(self):
        """ワーカープールマネージャーに登録"""
        try:
            # データベースに登録
            self.db.execute("""
                INSERT OR REPLACE INTO workers 
                (worker_id, status, last_heartbeat, location, performance_factor, endpoint_url)
                VALUES (?, 'idle', datetime('now'), ?, ?, ?)
            """, (self.worker_id, self.worker_location, self.performance_factor, self.endpoint_url))
            
            logger.info(f"📋 Remote worker {self.worker_id} registered with manager")
            
        except Exception as e:
            logger.error(f"Failed to register remote worker: {e}")


def main():
    """メインエントリーポイント"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Remote Worker for Koubou System')
    parser.add_argument('--worker-id', required=True, help='Worker ID')
    parser.add_argument('--config', type=str, help='Worker configuration (JSON)')
    parser.add_argument('--remote-host', default='192.168.11.6', help='Remote Ollama host')
    parser.add_argument('--remote-port', default=11434, type=int, help='Remote Ollama port')
    parser.add_argument('--test-mode', action='store_true', help='Run in test mode')
    
    args = parser.parse_args()
    
    # 設定の準備
    if args.config:
        worker_config = json.loads(args.config)
    else:
        worker_config = {
            'remote_host': args.remote_host,
            'remote_port': args.remote_port,
            'model': 'gpt-oss:20b',
            'performance_factor': 0.5,
            'network_timeout': 300
        }
    
    # ワーカーの作成
    worker = RemoteWorker(args.worker_id, worker_config)
    
    # テストモードの場合
    if args.test_mode:
        logger.info("🧪 Running in test mode")
        
        # ヘルスチェック
        if worker.health_check():
            logger.info("✅ Health check passed")
            
            # テストタスク実行
            test_result = worker.run_gemini_repo_cli_direct(
                prompt="Write a simple hello world function in Python",
                input_files=[],
                output_file=None
            )
            
            if test_result['success']:
                logger.info("✅ Test task succeeded")
                logger.info(f"   Execution time: {test_result.get('execution_time', 'N/A')}s")
                logger.info(f"   Output preview: {test_result['output'][:200]}...")
            else:
                logger.error(f"❌ Test task failed: {test_result['error']}")
        else:
            logger.error("❌ Health check failed")
        
        return
    
    # 通常モード: ワーカーとして動作
    worker.register_with_manager()
    
    logger.info(f"🚀 Remote worker {args.worker_id} started")
    logger.info(f"   Listening for tasks...")
    
    # タスク処理ループ
    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info(f"Shutting down remote worker {args.worker_id}")
    except Exception as e:
        logger.error(f"Remote worker error: {e}")


if __name__ == "__main__":
    main()