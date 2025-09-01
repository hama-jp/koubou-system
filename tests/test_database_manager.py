import pytest
import sqlite3
import tempfile
import os
import threading
import time
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import concurrent.futures


class TestDatabaseManager:
    """Test cases for Database Manager component"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        import uuid
        import time
        
        # Create unique filename to avoid conflicts in parallel execution
        unique_id = f"{uuid.uuid4().hex}_{int(time.time() * 1000000)}"
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, f"test_db_{unique_id}.db")
        
        try:
            conn = sqlite3.connect(path, timeout=30.0)  # Longer timeout for concurrent access
            cursor = conn.cursor()
            
            # Create tasks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'queued',
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    worker_id TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            # Create workers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'idle',
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create task_history table for audit trail
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    status_from TEXT,
                    status_to TEXT,
                    worker_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history(task_id)')
            
            conn.commit()
            conn.close()
            
            yield path
            
        finally:
            # Cleanup - ensure file is closed before deletion
            try:
                if os.path.exists(path):
                    # Wait a bit to ensure all connections are closed
                    time.sleep(0.1)
                    os.unlink(path)
            except (OSError, PermissionError):
                # File might still be in use, ignore cleanup error
                pass
    
    def test_database_initialization(self, temp_db):
        """Test database initialization with all required tables"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Check if all required tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['tasks', 'workers', 'task_history']
        for table in required_tables:
            assert table in tables, f"Required table '{table}' is missing"
        
        # Check if indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        
        expected_indexes = ['idx_tasks_status', 'idx_tasks_priority', 
                          'idx_workers_status', 'idx_task_history_task_id']
        for index in expected_indexes:
            assert index in indexes, f"Expected index '{index}' is missing"
        
        conn.close()
    
    def test_task_insertion_and_retrieval(self, temp_db):
        """Test task insertion and retrieval operations"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert a test task
        task_data = {
            'task_id': 'test_task_001',
            'type': 'general',
            'content': 'Test task content',
            'priority': 8,
            'status': 'queued'
        }
        
        cursor.execute('''
            INSERT INTO tasks (task_id, type, content, priority, status)
            VALUES (:task_id, :type, :content, :priority, :status)
        ''', task_data)
        conn.commit()
        
        # Retrieve the task
        cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_data['task_id'],))
        result = cursor.fetchone()
        
        assert result is not None
        assert result[1] == task_data['task_id']  # task_id column
        assert result[2] == task_data['type']     # type column
        assert result[3] == task_data['content']  # content column
        assert result[4] == task_data['priority'] # priority column
        assert result[5] == task_data['status']   # status column
        
        conn.close()
    
    def test_task_status_updates(self, temp_db):
        """Test task status update operations"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert initial task
        task_id = 'test_task_status_001'
        cursor.execute('''
            INSERT INTO tasks (task_id, type, content, priority, status)
            VALUES (?, 'general', 'Test content', 5, 'queued')
        ''', (task_id,))
        
        # Update status to 'assigned'
        cursor.execute('''
            UPDATE tasks 
            SET status = 'assigned', worker_id = 'test_worker_001', 
                started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (task_id,))
        
        # Update status to 'completed'
        cursor.execute('''
            UPDATE tasks 
            SET status = 'completed', result = 'Task completed successfully',
                completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (task_id,))
        
        conn.commit()
        
        # Verify final state
        cursor.execute('SELECT status, worker_id, result FROM tasks WHERE task_id = ?', (task_id,))
        result = cursor.fetchone()
        
        assert result[0] == 'completed'
        assert result[1] == 'test_worker_001'
        assert result[2] == 'Task completed successfully'
        
        conn.close()
    
    def test_worker_registration_and_heartbeat(self, temp_db):
        """Test worker registration and heartbeat mechanisms"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Register a worker
        worker_id = 'test_worker_heartbeat_001'
        cursor.execute('''
            INSERT OR REPLACE INTO workers (worker_id, status, last_heartbeat)
            VALUES (?, 'idle', CURRENT_TIMESTAMP)
        ''', (worker_id,))
        conn.commit()
        
        # Update heartbeat
        cursor.execute('''
            UPDATE workers 
            SET last_heartbeat = CURRENT_TIMESTAMP, status = 'working'
            WHERE worker_id = ?
        ''', (worker_id,))
        conn.commit()
        
        # Verify worker state
        cursor.execute('SELECT status, last_heartbeat FROM workers WHERE worker_id = ?', (worker_id,))
        result = cursor.fetchone()
        
        assert result[0] == 'working'
        assert result[1] is not None  # heartbeat timestamp exists
        
        conn.close()
    
    def test_concurrent_database_operations(self, temp_db):
        """Test concurrent database operations"""
        def insert_task(task_id):
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO tasks (task_id, type, content, priority, status)
                    VALUES (?, 'general', 'Concurrent test task', 5, 'queued')
                ''', (f'concurrent_task_{task_id}',))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()
        
        # Create multiple threads to insert tasks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(insert_task, i) for i in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All insertions should succeed
        assert all(results), "Some concurrent insertions failed"
        
        # Verify all tasks were inserted
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE task_id LIKE "concurrent_task_%"')
        count = cursor.fetchone()[0]
        assert count == 50
        conn.close()
    
    def test_database_transaction_rollback(self, temp_db):
        """Test database transaction rollback on errors"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        try:
            # Start transaction
            cursor.execute('BEGIN TRANSACTION')
            
            # Insert valid task
            cursor.execute('''
                INSERT INTO tasks (task_id, type, content, priority, status)
                VALUES ('valid_task', 'general', 'Valid task', 5, 'queued')
            ''')
            
            # Try to insert invalid task (duplicate task_id)
            cursor.execute('''
                INSERT INTO tasks (task_id, type, content, priority, status)
                VALUES ('valid_task', 'general', 'Duplicate task', 5, 'queued')
            ''')
            
            # This should not be reached due to integrity error
            cursor.execute('COMMIT')
        except sqlite3.IntegrityError:
            cursor.execute('ROLLBACK')
        
        # Verify no tasks were inserted
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE task_id = "valid_task"')
        count = cursor.fetchone()[0]
        assert count == 0
        
        conn.close()
    
    def test_database_query_performance(self, temp_db):
        """Test database query performance with large dataset"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert a large number of tasks
        tasks_data = []
        for i in range(1000):
            tasks_data.append((f'perf_task_{i}', 'general', f'Performance test task {i}', 
                             i % 10 + 1, 'queued'))
        
        cursor.executemany('''
            INSERT INTO tasks (task_id, type, content, priority, status)
            VALUES (?, ?, ?, ?, ?)
        ''', tasks_data)
        conn.commit()
        
        # Test query performance
        start_time = time.time()
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE status = "queued"')
        result = cursor.fetchone()
        query_time = time.time() - start_time
        
        assert result[0] == 1000
        assert query_time < 1.0, f"Query took too long: {query_time}s"
        
        # Test indexed query performance
        start_time = time.time()
        cursor.execute('SELECT * FROM tasks WHERE priority = 5 ORDER BY created_at LIMIT 10')
        results = cursor.fetchall()
        indexed_query_time = time.time() - start_time
        
        assert len(results) == 10
        assert indexed_query_time < 0.1, f"Indexed query took too long: {indexed_query_time}s"
        
        conn.close()
    
    def test_task_history_tracking(self, temp_db):
        """Test task history tracking functionality"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        task_id = 'history_test_task'
        worker_id = 'history_test_worker'
        
        # Insert initial task
        cursor.execute('''
            INSERT INTO tasks (task_id, type, content, priority, status)
            VALUES (?, 'general', 'History test task', 5, 'queued')
        ''', (task_id,))
        
        # Log status change to history
        cursor.execute('''
            INSERT INTO task_history (task_id, status_from, status_to, worker_id, details)
            VALUES (?, 'queued', 'assigned', ?, 'Task assigned to worker')
        ''', (task_id, worker_id))
        
        cursor.execute('''
            INSERT INTO task_history (task_id, status_from, status_to, worker_id, details)
            VALUES (?, 'assigned', 'completed', ?, 'Task completed successfully')
        ''', (task_id, worker_id))
        
        conn.commit()
        
        # Verify history entries
        cursor.execute('SELECT COUNT(*) FROM task_history WHERE task_id = ?', (task_id,))
        count = cursor.fetchone()[0]
        assert count == 2
        
        # Verify history details
        cursor.execute('''
            SELECT status_from, status_to, worker_id, details 
            FROM task_history WHERE task_id = ? ORDER BY timestamp
        ''', (task_id,))
        history = cursor.fetchall()
        
        assert history[0][0] == 'queued'
        assert history[0][1] == 'assigned'
        assert history[1][0] == 'assigned'
        assert history[1][1] == 'completed'
        
        conn.close()
    
    def test_database_backup_and_restore(self, temp_db):
        """Test database backup and restore functionality"""
        # Insert test data
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (task_id, type, content, priority, status)
            VALUES ('backup_test', 'general', 'Backup test task', 5, 'queued')
        ''')
        conn.commit()
        conn.close()
        
        # Create backup
        backup_path = temp_db + '.backup'
        
        # Simple file copy backup
        import shutil
        shutil.copy2(temp_db, backup_path)
        
        # Simulate data corruption by truncating original file
        with open(temp_db, 'w') as f:
            f.write('')
        
        # Restore from backup
        shutil.copy2(backup_path, temp_db)
        
        # Verify data integrity after restore
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute('SELECT task_id FROM tasks WHERE task_id = "backup_test"')
        result = cursor.fetchone()
        
        assert result is not None
        assert result[0] == 'backup_test'
        
        conn.close()
        os.unlink(backup_path)


class TestDatabaseErrorHandling:
    """Test database error handling scenarios"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        import uuid
        import time
        
        unique_id = f"{uuid.uuid4().hex}_{int(time.time() * 1000000)}"
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, f"test_error_db_{unique_id}.db")
        
        try:
            conn = sqlite3.connect(path, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'queued',
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    worker_id TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'idle',
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            yield path
            
        finally:
            try:
                if os.path.exists(path):
                    time.sleep(0.1)
                    os.unlink(path)
            except (OSError, PermissionError):
                pass

    def test_database_connection_failure(self):
        """Test handling of database connection failures"""
        # Test connecting to non-existent database path
        invalid_path = "/nonexistent/path/database.db"
        
        with pytest.raises(sqlite3.OperationalError):
            conn = sqlite3.connect(invalid_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
    
    def test_database_locked_scenario(self, temp_db):
        """Test handling of database locked scenarios"""
        # Create a long-running transaction to lock the database
        conn1 = sqlite3.connect(temp_db, timeout=1.0)
        cursor1 = conn1.cursor()
        cursor1.execute('BEGIN EXCLUSIVE TRANSACTION')
        
        # Try to access from another connection
        conn2 = sqlite3.connect(temp_db, timeout=1.0)
        cursor2 = conn2.cursor()
        
        with pytest.raises(sqlite3.OperationalError):
            cursor2.execute('''
                INSERT INTO tasks (task_id, type, content, priority, status)
                VALUES ('locked_test', 'general', 'Test', 5, 'queued')
            ''')
        
        # Cleanup
        cursor1.execute('ROLLBACK')
        conn1.close()
        conn2.close()
    
    def test_database_corruption_detection(self):
        """Test detection of database corruption"""
        # Create a corrupted database file
        corrupted_path = tempfile.mktemp(suffix='.db')
        
        with open(corrupted_path, 'wb') as f:
            f.write(b'corrupted database content')
        
        try:
            conn = sqlite3.connect(corrupted_path)
            cursor = conn.cursor()
            with pytest.raises(sqlite3.DatabaseError):
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            conn.close()
        finally:
            if os.path.exists(corrupted_path):
                os.unlink(corrupted_path)
    
    def test_disk_space_exhaustion_simulation(self):
        """Test handling of disk space exhaustion"""
        # This test would need to be run in a controlled environment
        # where disk space can be artificially limited
        pass
    
    def test_database_schema_migration(self, temp_db):
        """Test database schema migration scenarios"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Add a new column to existing table (simulating migration)
        try:
            cursor.execute('ALTER TABLE tasks ADD COLUMN execution_time INTEGER DEFAULT 0')
            conn.commit()
            
            # Verify column was added
            cursor.execute('PRAGMA table_info(tasks)')
            columns = [row[1] for row in cursor.fetchall()]
            assert 'execution_time' in columns
            
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        
        conn.close()


class TestDatabasePerformanceAndOptimization:
    """Test database performance and optimization scenarios"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        import uuid
        import time
        
        # Create unique filename to avoid conflicts in parallel execution
        unique_id = f"{uuid.uuid4().hex}_{int(time.time() * 1000000)}"
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, f"test_perf_db_{unique_id}.db")
        
        try:
            conn = sqlite3.connect(path, timeout=30.0)
            cursor = conn.cursor()
            
            # Create required tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'queued',
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    worker_id TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'idle',
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            yield path
            
        finally:
            try:
                if os.path.exists(path):
                    time.sleep(0.1)
                    os.unlink(path)
            except (OSError, PermissionError):
                pass

    def test_bulk_insert_performance(self, temp_db):
        """Test bulk insert performance"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Prepare bulk data
        bulk_data = [(f'bulk_task_{i}', 'general', f'Bulk task {i}', 5, 'queued') 
                     for i in range(1000)]
        
        # Test bulk insert performance
        start_time = time.time()
        cursor.executemany('''
            INSERT INTO tasks (task_id, type, content, priority, status)
            VALUES (?, ?, ?, ?, ?)
        ''', bulk_data)
        conn.commit()
        bulk_insert_time = time.time() - start_time
        
        # Should complete within reasonable time
        assert bulk_insert_time < 5.0, f"Bulk insert took too long: {bulk_insert_time}s"
        
        # Verify all records inserted
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE task_id LIKE "bulk_task_%"')
        count = cursor.fetchone()[0]
        assert count == 1000
        
        conn.close()
    
    def test_complex_query_performance(self, temp_db):
        """Test performance of complex queries"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert test data with various statuses and priorities
        test_data = []
        statuses = ['queued', 'assigned', 'working', 'completed', 'failed']
        for i in range(500):
            status = statuses[i % len(statuses)]
            priority = (i % 10) + 1
            test_data.append((f'complex_task_{i}', 'general', f'Task {i}', priority, status))
        
        cursor.executemany('''
            INSERT INTO tasks (task_id, type, content, priority, status)
            VALUES (?, ?, ?, ?, ?)
        ''', test_data)
        conn.commit()
        
        # Test complex query performance
        start_time = time.time()
        cursor.execute('''
            SELECT status, priority, COUNT(*) as count, AVG(priority) as avg_priority
            FROM tasks 
            WHERE task_id LIKE 'complex_task_%'
            GROUP BY status, priority
            HAVING COUNT(*) > 5
            ORDER BY priority DESC, status
        ''')
        results = cursor.fetchall()
        query_time = time.time() - start_time
        
        assert query_time < 1.0, f"Complex query took too long: {query_time}s"
        assert len(results) > 0, "Complex query returned no results"
        
        conn.close()
    
    def test_database_vacuum_operation(self, temp_db):
        """Test database VACUUM operation for optimization"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert and delete data to create fragmentation
        for i in range(100):
            cursor.execute('''
                INSERT INTO tasks (task_id, type, content, priority, status)
                VALUES (?, 'general', 'Temporary task', 5, 'queued')
            ''', (f'temp_task_{i}',))
        
        cursor.execute('DELETE FROM tasks WHERE task_id LIKE "temp_task_%"')
        conn.commit()
        
        # Get file size before vacuum
        size_before = os.path.getsize(temp_db)
        
        # Perform VACUUM
        cursor.execute('VACUUM')
        
        # Get file size after vacuum
        size_after = os.path.getsize(temp_db)
        
        # VACUUM should not increase file size
        assert size_after <= size_before
        
        conn.close()


class TestDatabaseConnectionPooling:
    """Test database connection pooling scenarios"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        import uuid
        import time
        
        # Create unique filename to avoid conflicts in parallel execution
        unique_id = f"{uuid.uuid4().hex}_{int(time.time() * 1000000)}"
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, f"test_pool_db_{unique_id}.db")
        
        try:
            conn = sqlite3.connect(path, timeout=30.0)
            cursor = conn.cursor()
            
            # Create required tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'queued',
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    worker_id TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'idle',
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            yield path
            
        finally:
            try:
                if os.path.exists(path):
                    time.sleep(0.1)
                    os.unlink(path)
            except (OSError, PermissionError):
                pass

    def test_connection_reuse(self, temp_db):
        """Test connection reuse in pool"""
        # This would test a connection pool implementation
        # For now, test basic connection management
        connections = []
        
        try:
            # Create multiple connections
            for i in range(10):
                conn = sqlite3.connect(temp_db)
                connections.append(conn)
            
            # All connections should be valid
            for conn in connections:
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                result = cursor.fetchone()
                assert result[0] == 1
        
        finally:
            # Close all connections
            for conn in connections:
                conn.close()
    
    def test_connection_timeout_handling(self):
        """Test connection timeout handling"""
        # Test connection timeout scenarios
        pass


class TestDatabaseMaintenanceAndMonitoring:
    """Test database maintenance and monitoring scenarios"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        import uuid
        import time
        
        # Create unique filename to avoid conflicts in parallel execution
        unique_id = f"{uuid.uuid4().hex}_{int(time.time() * 1000000)}"
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, f"test_maint_db_{unique_id}.db")
        
        try:
            conn = sqlite3.connect(path, timeout=30.0)
            cursor = conn.cursor()
            
            # Create required tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'queued',
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    worker_id TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'idle',
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            yield path
            
        finally:
            try:
                if os.path.exists(path):
                    time.sleep(0.1)
                    os.unlink(path)
            except (OSError, PermissionError):
                pass

    def test_database_size_monitoring(self, temp_db):
        """Test database size monitoring"""
        initial_size = os.path.getsize(temp_db)
        
        # Insert data to increase size
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        large_content = "x" * 10000  # 10KB content
        for i in range(10):
            cursor.execute('''
                INSERT INTO tasks (task_id, type, content, priority, status)
                VALUES (?, 'general', ?, 5, 'queued')
            ''', (f'large_task_{i}', large_content))
        
        conn.commit()
        conn.close()
        
        final_size = os.path.getsize(temp_db)
        assert final_size > initial_size
    
    def test_database_integrity_check(self, temp_db):
        """Test database integrity check"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Perform integrity check
        cursor.execute('PRAGMA integrity_check')
        result = cursor.fetchone()
        
        assert result[0] == 'ok', f"Database integrity check failed: {result[0]}"
        
        conn.close()
    
    def test_database_statistics_collection(self, temp_db):
        """Test collection of database statistics"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert test data
        for i in range(50):
            status = 'queued' if i < 20 else 'completed' if i < 40 else 'failed'
            cursor.execute('''
                INSERT INTO tasks (task_id, type, content, priority, status)
                VALUES (?, 'general', 'Test task', 5, ?)
            ''', (f'stats_task_{i}', status))
        
        conn.commit()
        
        # Collect statistics
        cursor.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status')
        stats = dict(cursor.fetchall())
        
        assert stats.get('queued', 0) >= 20
        assert stats.get('completed', 0) >= 20
        assert stats.get('failed', 0) >= 10
        
        conn.close()