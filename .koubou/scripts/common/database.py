#!/usr/bin/env python3
"""
データベース操作共通モジュール
全コンポーネントで使用するデータベース操作を一元化
"""

import sqlite3
import json
import os
import time
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager
import threading
import logging
import queue

# ロガー設定
logger = logging.getLogger(__name__)

class ConnectionPool:
    """SQLite接続プール"""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self._initialize_pool(pool_size)
    
    def _initialize_pool(self, pool_size: int):
        """コネクションプールを初期化"""
        for _ in range(pool_size):
            conn = self._create_connection()
            self.pool.put(conn)
    
    def _create_connection(self):
        """新しいデータベース接続を作成"""
        conn = sqlite3.connect(
            self.db_path, 
            timeout=30.0, 
            check_same_thread=False,
            isolation_level=None  # autocommit mode for WAL
        )
        conn.row_factory = sqlite3.Row
        
        # WALモードとパフォーマンス設定（推奨値）
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=60000")  # 60秒に延長
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")  # テンポラリデータをメモリに
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        conn.execute("PRAGMA wal_autocheckpoint=1000")  # WAL checkpointを調整
        conn.execute("PRAGMA optimize")  # クエリプランナー最適化
        
        return conn
    
    @contextmanager
    def get_connection(self):
        """プールから接続を取得"""
        conn = None
        temp_conn = False
        try:
            try:
                conn = self.pool.get(timeout=10)  # 10秒でタイムアウト
            except queue.Empty:
                # プールが空の場合、一時的な接続を作成
                logger.warning("Connection pool exhausted, creating temporary connection")
                conn = self._create_connection()
                temp_conn = True
            
            # 接続の健全性をチェック
            try:
                conn.execute("SELECT 1").fetchone()
            except sqlite3.Error:
                # 壊れた接続を検出、新しい接続を作成
                logger.warning("Detected broken connection, creating new one")
                try:
                    conn.close()
                except:
                    pass
                conn = self._create_connection()
                temp_conn = True
            
            yield conn
            
        except Exception as e:
            logger.error(f"Database connection error: {e}", exc_info=True)
            if conn:
                # エラー時はロールバックを試行
                try:
                    conn.rollback()
                except:
                    pass
                # 問題のある接続は破棄
                if not temp_conn:
                    try:
                        conn.close()
                    except:
                        pass
                    conn = None  # プールに戻さない
            raise
        finally:
            if conn:
                try:
                    if temp_conn:
                        # 一時接続は閉じる
                        conn.close()
                    else:
                        # 正常な接続のみプールに戻す
                        self.pool.put_nowait(conn)
                except queue.Full:
                    # プールが満杯の場合は接続を閉じる
                    conn.close()
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    try:
                        conn.close()
                    except:
                        pass

class DatabaseManager:
    """データベース操作を管理するクラス"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初期化
        
        Args:
            db_path: データベースファイルのパス
        """
        self.db_path = db_path or os.environ.get('KOUBOU_DB', '.koubou/db/koubou.db')
        self._connection_pool = ConnectionPool(self.db_path, pool_size=10)
        self._ensure_database()
    
    def _ensure_database(self):
        """データベースとテーブルが存在することを確認"""
        with self.get_connection() as conn:
            # WALモードに変更してコンカレンシーを向上
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            cursor = conn.cursor()
            
            # タスクマスターテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_master (
                    task_id TEXT PRIMARY KEY,
                    content TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 5,
                    result TEXT,
                    created_by TEXT,
                    assigned_to TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # ワーカーテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'idle',
                    current_task TEXT,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_failed INTEGER DEFAULT 0,
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # インデックス作成
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task_master(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_priority ON task_master(priority DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_worker_status ON workers(status)")
            
            conn.commit()
    
    def get_connection(self):
        """
        データベース接続を取得（コンテキストマネージャー）
        
        Yields:
            sqlite3.Connection: データベース接続
        """
        return self._connection_pool.get_connection()
    
    # ========== タスク関連操作 ==========
    
    def create_task(self, task_id: str, content: str, priority: int = 5, 
                   created_by: str = 'system') -> bool:
        """
        新しいタスクを作成
        
        Args:
            task_id: タスクID
            content: タスク内容（JSON文字列）
            priority: 優先度（1-10）
            created_by: 作成者
        
        Returns:
            bool: 成功した場合True
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    # WALモードでは明示的なトランザクション開始
                    cursor.execute("BEGIN IMMEDIATE")
                    try:
                        cursor.execute("""
                            INSERT INTO task_master (task_id, content, priority, created_by)
                            VALUES (?, ?, ?, ?)
                        """, (task_id, content, priority, created_by))
                        cursor.execute("COMMIT")
                        return True
                    except Exception as inner_e:
                        cursor.execute("ROLLBACK")
                        raise inner_e
                        
            except sqlite3.IntegrityError:
                logger.warning(f"Task {task_id} already exists")
                return False
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Database locked on attempt {attempt + 1}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to create task after {attempt + 1} attempts: {e}", exc_info=True)
                    return False
            except Exception as e:
                logger.error(f"Failed to create task: {e}", exc_info=True)
                return False
        
        return False
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        タスク情報を取得
        
        Args:
            task_id: タスクID
        
        Returns:
            タスク情報の辞書、存在しない場合None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM task_master WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_task_status(self, task_id: str, status: str, 
                          result: Optional[str] = None) -> bool:
        """
        タスクのステータスを更新
        
        Args:
            task_id: タスクID
            status: 新しいステータス
            result: 実行結果（オプション）
        
        Returns:
            bool: 成功した場合True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if result is not None:
                    cursor.execute("""
                        UPDATE task_master 
                        SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ?
                    """, (status, result, task_id))
                else:
                    cursor.execute("""
                        UPDATE task_master 
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ?
                    """, (status, task_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            return False
    
    def complete_task(self, task_id: str, result: str) -> bool:
        """
        タスクを完了状態にする
        
        Args:
            task_id: タスクID
            result: 実行結果
        
        Returns:
            bool: 成功した場合True
        """
        return self.update_task_status(task_id, 'completed', result)
    
    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        処理待ちタスクを取得（優先度順）
        
        Args:
            limit: 取得する最大件数
        
        Returns:
            タスクのリスト
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM task_master 
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def assign_task_to_worker(self, task_id: str, worker_id: str) -> bool:
        """
        タスクをワーカーに割り当て
        
        Args:
            task_id: タスクID
            worker_id: ワーカーID
        
        Returns:
            bool: 成功した場合True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE task_master 
                    SET status = 'in_progress', assigned_to = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = ? AND status = 'pending'
                """, (worker_id, task_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to assign task: {e}")
            return False
    
    def get_task_statistics(self) -> Dict[str, int]:
        """
        タスクの統計情報を取得
        
        Returns:
            ステータスごとのタスク数
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM task_master
                GROUP BY status
            """)
            return {row['status']: row['count'] for row in cursor.fetchall()}
    
    # ========== ワーカー関連操作 ==========
    
    def register_worker(self, worker_id: str) -> bool:
        """
        新しいワーカーを登録
        
        Args:
            worker_id: ワーカーID
        
        Returns:
            bool: 成功した場合True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO workers (worker_id, status)
                    VALUES (?, 'idle')
                """, (worker_id,))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # 既に存在する場合は再登録
            return self.update_worker_status(worker_id, 'idle')
        except Exception as e:
            logger.error(f"Failed to register worker: {e}")
            return False
    
    def update_worker_status(self, worker_id: str, status: str, 
                           current_task: Optional[str] = None) -> bool:
        """
        ワーカーのステータスを更新
        
        Args:
            worker_id: ワーカーID
            status: 新しいステータス
            current_task: 現在処理中のタスクID（オプション）
        
        Returns:
            bool: 成功した場合True
        """
        for attempt in range(3):  # 3回リトライ
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE workers 
                        SET status = ?, current_task = ?, last_heartbeat = CURRENT_TIMESTAMP
                        WHERE worker_id = ?
                    """, (status, current_task, worker_id))
                    conn.commit()
                    return cursor.rowcount > 0
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # 指数バックオフ
                    continue
                logger.error(f"Failed to update worker status after {attempt + 1} attempts: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to update worker status: {e}")
                return False
    
    def update_worker_heartbeat(self, worker_id: str) -> bool:
        """
        ワーカーのハートビートを更新
        
        Args:
            worker_id: ワーカーID
        
        Returns:
            bool: 成功した場合True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE workers 
                    SET last_heartbeat = CURRENT_TIMESTAMP
                    WHERE worker_id = ?
                """, (worker_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update worker heartbeat: {e}")
            return False
    
    def increment_worker_stats(self, worker_id: str, success: bool) -> bool:
        """
        ワーカーの統計情報を更新
        
        Args:
            worker_id: ワーカーID
            success: タスクが成功した場合True
        
        Returns:
            bool: 更新に成功した場合True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if success:
                    cursor.execute("""
                        UPDATE workers 
                        SET tasks_completed = tasks_completed + 1,
                            status = 'idle',
                            current_task = NULL,
                            last_heartbeat = CURRENT_TIMESTAMP
                        WHERE worker_id = ?
                    """, (worker_id,))
                else:
                    cursor.execute("""
                        UPDATE workers 
                        SET tasks_failed = tasks_failed + 1,
                            status = 'idle',
                            current_task = NULL,
                            last_heartbeat = CURRENT_TIMESTAMP
                        WHERE worker_id = ?
                    """, (worker_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update worker stats: {e}")
            return False
    
    def increment_worker_completed_tasks(self, worker_id: str) -> bool:
        """
        ワーカーの完了タスク数をインクリメント
        
        Args:
            worker_id: ワーカーID
        
        Returns:
            bool: 成功した場合True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE workers 
                    SET tasks_completed = tasks_completed + 1,
                        last_heartbeat = CURRENT_TIMESTAMP
                    WHERE worker_id = ?
                """, (worker_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to increment completed tasks: {e}")
            return False
    
    def increment_worker_failed_tasks(self, worker_id: str) -> bool:
        """
        ワーカーの失敗タスク数をインクリメント
        
        Args:
            worker_id: ワーカーID
        
        Returns:
            bool: 成功した場合True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE workers 
                    SET tasks_failed = tasks_failed + 1,
                        last_heartbeat = CURRENT_TIMESTAMP
                    WHERE worker_id = ?
                """, (worker_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to increment failed tasks: {e}")
            return False
    
    def get_active_workers(self, timeout_seconds: int = 60) -> List[Dict[str, Any]]:
        """
        アクティブなワーカーのリストを取得
        
        Args:
            timeout_seconds: ハートビートのタイムアウト秒数
        
        Returns:
            アクティブなワーカーのリスト
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM workers
                WHERE last_heartbeat > datetime('now', '-' || ? || ' seconds')
            """, (timeout_seconds,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """
        現在実行中のタスクの詳細情報を取得
        
        Returns:
            実行中タスクの詳細リスト
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    tm.task_id,
                    tm.content,
                    tm.status,
                    tm.priority,
                    tm.result,
                    tm.assigned_to,
                    tm.created_at,
                    tm.updated_at,
                    w.status as worker_status
                FROM task_master tm
                LEFT JOIN workers w ON tm.assigned_to = w.worker_id
                WHERE tm.status IN ('in_progress', 'processing')
                ORDER BY tm.priority DESC, tm.created_at ASC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_dead_workers(self, timeout_seconds: int = 60) -> int:
        """
        デッドワーカーをクリーンアップ
        
        Args:
            timeout_seconds: ハートビートのタイムアウト秒数
        
        Returns:
            削除されたワーカー数
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # タイムアウトしたワーカーのタスクを解放
                cursor.execute("""
                    UPDATE task_master
                    SET status = 'pending', assigned_to = NULL
                    WHERE assigned_to IN (
                        SELECT worker_id FROM workers
                        WHERE last_heartbeat <= datetime('now', '-' || ? || ' seconds')
                    ) AND status = 'in_progress'
                """, (timeout_seconds,))
                
                # デッドワーカーを削除
                cursor.execute("""
                    DELETE FROM workers
                    WHERE last_heartbeat <= datetime('now', '-' || ? || ' seconds')
                """, (timeout_seconds,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} dead workers")
                
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup dead workers: {e}")
            return 0
    
    def get_worker_statistics(self) -> Dict[str, Any]:
        """
        ワーカーの統計情報を取得
        
        Returns:
            ワーカー統計の辞書
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 全体統計
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_workers,
                    SUM(CASE WHEN status = 'busy' THEN 1 ELSE 0 END) as busy_workers,
                    SUM(CASE WHEN status = 'idle' THEN 1 ELSE 0 END) as idle_workers,
                    SUM(tasks_completed) as total_completed,
                    SUM(tasks_failed) as total_failed
                FROM workers
                WHERE last_heartbeat > datetime('now', '-60 seconds')
            """)
            
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def get_all_workers(self) -> List[Dict[str, Any]]:
        """
        全ワーカー情報を取得
        
        Returns:
            全ワーカーのリスト
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    worker_id,
                    status,
                    current_task,
                    tasks_completed,
                    tasks_failed,
                    last_heartbeat,
                    created_at
                FROM workers
                ORDER BY last_heartbeat DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def acquire_next_task(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        次の保留中タスクをアトミックに取得し、ワーカーに割り当てる
        
        Args:
            worker_id: タスクを取得するワーカーのID
        
        Returns:
            取得したタスクの情報、またはNone
        """
        for attempt in range(3):  # リトライ処理
            try:
                with self.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")  # 即時ロックを確保
                    cursor = conn.cursor()
                    
                    # 優先度が最も高い保留中タスクを取得
                    cursor.execute("""
                        SELECT task_id, content, priority, created_at
                        FROM task_master
                        WHERE status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                    """)
                    
                    row = cursor.fetchone()
                    if not row:
                        conn.rollback()
                        return None
                    
                    task_id = row[0]
                    
                    # タスクをワーカーに割り当て
                    cursor.execute("""
                        UPDATE task_master
                        SET status = 'in_progress',
                            assigned_to = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ? AND status = 'pending'
                    """, (worker_id, task_id))
                    
                    if cursor.rowcount == 0:
                        # 別のワーカーが既に取得した
                        conn.rollback()
                        continue
                    
                    # ワーカーステータスも更新
                    cursor.execute("""
                        UPDATE workers
                        SET status = 'busy',
                            current_task = ?,
                            last_heartbeat = CURRENT_TIMESTAMP
                        WHERE worker_id = ?
                    """, (task_id, worker_id))
                    
                    conn.commit()
                    
                    return {
                        'task_id': task_id,
                        'content': row[1],
                        'priority': row[2],
                        'created_at': row[3]
                    }
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    import time
                    time.sleep(0.1 * (attempt + 1))
                    continue
                logger.error(f"Failed to acquire task after {attempt + 1} attempts: {e}", exc_info=True)
                return None
            except Exception as e:
                logger.error(f"Failed to acquire task: {e}", exc_info=True)
                return None
        
        return None
    
    def complete_task_with_stats(self, task_id: str, worker_id: str, result: str, success: bool = True) -> bool:
        """
        タスクを完了し、ワーカー統計を単一トランザクションで更新
        
        Args:
            task_id: 完了するタスクのID
            worker_id: タスクを完了したワーカーのID
            result: タスクの結果
            success: タスクが成功した場合True
        
        Returns:
            bool: 成功した場合True
        """
        for attempt in range(3):
            try:
                with self.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    cursor = conn.cursor()
                    
                    # タスクを完了状態に更新
                    status = 'completed' if success else 'failed'
                    cursor.execute("""
                        UPDATE task_master
                        SET status = ?,
                            result = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_id = ? AND assigned_to = ?
                    """, (status, result, task_id, worker_id))
                    
                    if cursor.rowcount == 0:
                        conn.rollback()
                        logger.error(f"Task {task_id} not found or not assigned to worker {worker_id}")
                        return False
                    
                    # ワーカー統計を更新
                    if success:
                        cursor.execute("""
                            UPDATE workers
                            SET tasks_completed = tasks_completed + 1,
                                status = 'idle',
                                current_task = NULL,
                                last_heartbeat = CURRENT_TIMESTAMP
                            WHERE worker_id = ?
                        """, (worker_id,))
                    else:
                        cursor.execute("""
                            UPDATE workers
                            SET tasks_failed = tasks_failed + 1,
                                status = 'idle',
                                current_task = NULL,
                                last_heartbeat = CURRENT_TIMESTAMP
                            WHERE worker_id = ?
                        """, (worker_id,))
                    
                    conn.commit()
                    return True
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    import time
                    time.sleep(0.1 * (attempt + 1))
                    continue
                logger.error(f"Failed to complete task after {attempt + 1} attempts: {e}", exc_info=True)
                return False
            except Exception as e:
                logger.error(f"Failed to complete task: {e}", exc_info=True)
                return False
        
        return False
    
    def get_task_summary(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        タスクリストにサマリー情報を追加
        
        Args:
            tasks: タスク情報のリスト
        
        Returns:
            サマリー情報を追加したタスクリスト
        """
        import json
        
        for task in tasks:
            try:
                content_data = json.loads(task.get('content', '{}'))
                summary = content_data.get('prompt', '')[:100]
                if len(content_data.get('prompt', '')) > 100:
                    summary += '...'
                task['summary'] = summary
                task['type'] = content_data.get('type', 'general')
            except:
                content = task.get('content', '')
                task['summary'] = content[:100] + ('...' if len(content) > 100 else '')
                task['type'] = 'general'
        
        return tasks

# シングルトンインスタンス
_db_manager: Optional[DatabaseManager] = None

def get_db_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """
    データベースマネージャーのシングルトンインスタンスを取得
    
    Args:
        db_path: データベースパス（初回のみ有効）
    
    Returns:
        DatabaseManager: データベースマネージャーインスタンス
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager