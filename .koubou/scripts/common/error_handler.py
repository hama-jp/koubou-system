#!/usr/bin/env python3
"""
エラーハンドリングと自動リカバリーモジュール
"""

import logging
import time
import traceback
from typing import Callable, Any, Optional, Dict
from functools import wraps
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class ErrorRecoveryManager:
    """エラーリカバリー管理"""
    
    def __init__(self):
        self.error_history = []
        self.recovery_strategies = {}
        self.max_retries = 3
        self.retry_delay = 5  # 秒
        
    def register_strategy(self, error_type: type, strategy: Callable):
        """エラータイプごとのリカバリー戦略を登録"""
        self.recovery_strategies[error_type] = strategy
        
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """エラーを処理してリカバリーを試みる"""
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'traceback': traceback.format_exc()
        }
        
        self.error_history.append(error_info)
        
        # リカバリー戦略を探す
        for error_type, strategy in self.recovery_strategies.items():
            if isinstance(error, error_type):
                logger.info(f"Applying recovery strategy for {error_type.__name__}")
                try:
                    return strategy(error, context)
                except Exception as recovery_error:
                    logger.error(f"Recovery strategy failed: {recovery_error}")
                    
        logger.error(f"No recovery strategy found for {type(error).__name__}")
        return False
    
    def get_error_stats(self) -> Dict[str, Any]:
        """エラー統計を取得"""
        if not self.error_history:
            return {'total_errors': 0}
        
        stats = {
            'total_errors': len(self.error_history),
            'by_type': {},
            'recent_errors': self.error_history[-10:]  # 最新10件
        }
        
        for error in self.error_history:
            error_type = error['error_type']
            stats['by_type'][error_type] = stats['by_type'].get(error_type, 0) + 1
        
        return stats


def retry_on_failure(max_retries: int = 3, 
                     delay: float = 1.0, 
                     backoff: float = 2.0,
                     exceptions: tuple = (Exception,)):
    """
    失敗時にリトライするデコレーター
    
    Args:
        max_retries: 最大リトライ回数
        delay: 初回リトライまでの遅延（秒）
        backoff: リトライごとの遅延倍率
        exceptions: リトライ対象の例外タプル
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            current_delay = delay
            
            while retry_count <= max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retry_count += 1
                    
                    if retry_count > max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries} retries")
                        raise
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {retry_count}/{max_retries}): {e}"
                        f" Retrying in {current_delay:.1f}s..."
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator


def circuit_breaker(failure_threshold: int = 5,
                    recovery_timeout: int = 60,
                    expected_exception: type = Exception):
    """
    サーキットブレーカーパターンの実装
    
    Args:
        failure_threshold: 回路を開く失敗回数の閾値
        recovery_timeout: 回路を再度閉じるまでの待機時間（秒）
        expected_exception: 期待される例外タイプ
    """
    def decorator(func: Callable) -> Callable:
        func._failure_count = 0
        func._last_failure_time = None
        func._circuit_open = False
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 回路が開いているかチェック
            if func._circuit_open:
                if func._last_failure_time:
                    time_since_failure = (datetime.now() - func._last_failure_time).total_seconds()
                    if time_since_failure > recovery_timeout:
                        logger.info(f"Circuit breaker: Attempting to close circuit for {func.__name__}")
                        func._circuit_open = False
                        func._failure_count = 0
                    else:
                        raise RuntimeError(f"Circuit breaker is open for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                # 成功したら失敗カウントをリセット
                func._failure_count = 0
                return result
                
            except expected_exception as e:
                func._failure_count += 1
                func._last_failure_time = datetime.now()
                
                if func._failure_count >= failure_threshold:
                    func._circuit_open = True
                    logger.error(
                        f"Circuit breaker: Opening circuit for {func.__name__} "
                        f"after {func._failure_count} failures"
                    )
                
                raise
                
        return wrapper
    return decorator


class TaskRecoveryHandler:
    """タスク処理のリカバリーハンドラー"""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
        self.recovery_manager = ErrorRecoveryManager()
        self._setup_recovery_strategies()
    
    def _setup_recovery_strategies(self):
        """リカバリー戦略を設定"""
        
        # タイムアウトエラーの場合
        def timeout_recovery(error: Exception, context: Dict) -> bool:
            task_id = context.get('task_id')
            if task_id and self.db:
                logger.info(f"Recovering from timeout for task {task_id}")
                # タスクを再キューイング
                self.db.update_task_status(task_id, 'pending')
                return True
            return False
        
        # LLM接続エラーの場合
        def llm_connection_recovery(error: Exception, context: Dict) -> bool:
            logger.info("Attempting to restart LLM connection...")
            # LLMサービスの再起動を試みる
            try:
                import subprocess
                subprocess.run(['ollama', 'serve'], timeout=5, capture_output=True)
                return True
            except:
                return False
        
        # データベースエラーの場合
        def db_recovery(error: Exception, context: Dict) -> bool:
            logger.info("Attempting database recovery...")
            if self.db:
                try:
                    # データベース接続を再確立
                    self.db.reconnect()
                    return True
                except:
                    return False
            return False
        
        self.recovery_manager.register_strategy(TimeoutError, timeout_recovery)
        self.recovery_manager.register_strategy(ConnectionError, llm_connection_recovery)
        self.recovery_manager.register_strategy(sqlite3.OperationalError, db_recovery)
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def process_task_with_recovery(self, task: Dict[str, Any], processor: Callable) -> Any:
        """リカバリー機能付きでタスクを処理"""
        try:
            return processor(task)
        except Exception as e:
            context = {
                'task_id': task.get('id'),
                'task_type': task.get('type'),
                'timestamp': datetime.now().isoformat()
            }
            
            if self.recovery_manager.handle_error(e, context):
                # リカバリー成功後、再試行
                return processor(task)
            else:
                # リカバリー失敗
                raise


class HealthMonitor:
    """システムヘルスモニタリング"""
    
    def __init__(self):
        self.health_checks = {}
        self.check_results = {}
        
    def register_check(self, name: str, check_func: Callable[[], bool]):
        """ヘルスチェック関数を登録"""
        self.health_checks[name] = check_func
    
    def run_checks(self) -> Dict[str, Any]:
        """全ヘルスチェックを実行"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'overall_health': 'healthy',
            'checks': {}
        }
        
        for name, check_func in self.health_checks.items():
            try:
                is_healthy = check_func()
                results['checks'][name] = {
                    'status': 'healthy' if is_healthy else 'unhealthy',
                    'checked_at': datetime.now().isoformat()
                }
                
                if not is_healthy:
                    results['overall_health'] = 'degraded'
                    
            except Exception as e:
                results['checks'][name] = {
                    'status': 'error',
                    'error': str(e),
                    'checked_at': datetime.now().isoformat()
                }
                results['overall_health'] = 'unhealthy'
        
        self.check_results = results
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """最新のヘルスステータスを取得"""
        return self.check_results


# 共通エラークラス
class WorkerError(Exception):
    """ワーカー関連エラー"""
    pass

class TaskError(Exception):
    """タスク処理エラー"""
    pass

class LLMError(Exception):
    """LLM関連エラー"""
    pass


# グローバルインスタンス
error_manager = ErrorRecoveryManager()
health_monitor = HealthMonitor()


def setup_default_health_checks():
    """デフォルトのヘルスチェックを設定"""
    
    # データベースチェック
    def check_database():
        try:
            import sqlite3
            conn = sqlite3.connect('.koubou/db/koubou.db')
            conn.execute('SELECT 1')
            conn.close()
            return True
        except:
            return False
    
    # Redisチェック
    def check_redis():
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            return True
        except:
            return False
    
    # Ollamaチェック
    def check_ollama():
        try:
            import subprocess
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    health_monitor.register_check('database', check_database)
    health_monitor.register_check('redis', check_redis)
    health_monitor.register_check('ollama', check_ollama)


# モジュール初期化時にデフォルトチェックを設定
setup_default_health_checks()


if __name__ == "__main__":
    # テスト実行
    
    # リトライデコレーターのテスト
    @retry_on_failure(max_retries=3, delay=0.5)
    def flaky_function():
        import random
        if random.random() < 0.7:
            raise ConnectionError("Random failure")
        return "Success!"
    
    # サーキットブレーカーのテスト
    @circuit_breaker(failure_threshold=3, recovery_timeout=5)
    def unstable_service():
        raise ConnectionError("Service unavailable")
    
    # ヘルスチェック実行
    print("Running health checks...")
    results = health_monitor.run_checks()
    print(json.dumps(results, indent=2))
    
    # エラー統計
    print("\nError statistics:")
    print(json.dumps(error_manager.get_error_stats(), indent=2))