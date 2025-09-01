#!/usr/bin/env python3
"""
GraphQL API サーバー - 柔軟なクエリインターフェース
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.database import get_db_manager

from flask import Flask
from flask_cors import CORS

# GraphQL imports
try:
    from ariadne import QueryType, MutationType, SubscriptionType, make_executable_schema
    from ariadne.asgi import GraphQL
    from ariadne.explorer import ExplorerGraphiQL
except ImportError:
    print("Error: ariadne not installed")
    print("Install with: uv pip install ariadne flask-cors")
    sys.exit(1)

# 設定
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"

# データベースマネージャー
db = get_db_manager(DB_PATH)

# GraphQL スキーマ定義
type_defs = """
    scalar DateTime
    scalar JSON

    type Task {
        id: String!
        content: JSON!
        status: TaskStatus!
        priority: Int!
        result: JSON
        createdBy: String
        assignedTo: String
        createdAt: DateTime!
        updatedAt: DateTime!
    }

    type Worker {
        id: String!
        status: WorkerStatus!
        currentTask: String
        tasksCompleted: Int!
        tasksFailed: Int!
        lastHeartbeat: DateTime!
        createdAt: DateTime!
    }

    type TaskStatistics {
        pending: Int!
        inProgress: Int!
        completed: Int!
        failed: Int!
        total: Int!
    }

    type WorkerStatistics {
        totalWorkers: Int!
        busyWorkers: Int!
        idleWorkers: Int!
        totalCompleted: Int!
        totalFailed: Int!
        successRate: Float!
    }

    type SystemStatus {
        status: String!
        timestamp: DateTime!
        taskStats: TaskStatistics!
        workerStats: WorkerStatistics!
        version: String!
    }

    type TaskSubmissionResult {
        success: Boolean!
        taskId: String
        message: String
        task: Task
    }

    type WorkerActionResult {
        success: Boolean!
        workerId: String
        message: String
        worker: Worker
    }

    enum TaskStatus {
        PENDING
        IN_PROGRESS
        COMPLETED
        FAILED
        CANCELLED
        ARCHIVED_OLD_SYSTEM
    }

    enum WorkerStatus {
        IDLE
        BUSY
        OFFLINE
    }

    enum TaskType {
        CODE
        GENERAL
    }

    input TaskInput {
        type: TaskType!
        prompt: String!
        priority: Int
        files: [String!]
        options: JSON
        sync: Boolean
    }

    input TaskFilter {
        status: TaskStatus
        createdBy: String
        assignedTo: String
        minPriority: Int
        maxPriority: Int
    }

    input WorkerFilter {
        status: WorkerStatus
        minTasksCompleted: Int
    }

    type Query {
        # System queries
        systemStatus: SystemStatus!
        health: String!
        
        # Task queries
        task(id: String!): Task
        tasks(filter: TaskFilter, limit: Int = 10, offset: Int = 0): [Task!]!
        taskStatistics: TaskStatistics!
        pendingTasks(limit: Int = 10): [Task!]!
        
        # Worker queries
        worker(id: String!): Worker
        workers(filter: WorkerFilter, activeOnly: Boolean = true): [Worker!]!
        workerStatistics: WorkerStatistics!
        activeWorkers: [Worker!]!
    }

    type Mutation {
        # Task mutations
        submitTask(input: TaskInput!): TaskSubmissionResult!
        cancelTask(id: String!): TaskSubmissionResult!
        retryTask(id: String!): TaskSubmissionResult!
        updateTaskPriority(id: String!, priority: Int!): TaskSubmissionResult!
        
        # Worker mutations
        spawnWorker(count: Int = 1): WorkerActionResult!
        terminateWorker(id: String!): WorkerActionResult!
        scaleWorkers(targetCount: Int!): WorkerActionResult!
        
        # System mutations
        clearCompletedTasks(olderThanHours: Int = 24): Int!
        cleanupDeadWorkers: Int!
    }

    type Subscription {
        # Real-time subscriptions
        taskUpdated(id: String): Task!
        workerUpdated(id: String): Worker!
        systemStatusChanged: SystemStatus!
    }
"""

# Query resolvers
query = QueryType()

@query.field("systemStatus")
def resolve_system_status(_, info):
    """システムステータスを取得"""
    task_stats = db.get_task_statistics()
    worker_stats = db.get_worker_statistics()
    
    # 統計を整形
    task_statistics = {
        'pending': task_stats.get('pending', 0),
        'inProgress': task_stats.get('in_progress', 0),
        'completed': task_stats.get('completed', 0),
        'failed': task_stats.get('failed', 0),
        'total': sum(task_stats.values())
    }
    
    total_completed = worker_stats.get('total_completed') or 0
    total_failed = worker_stats.get('total_failed') or 0
    total_tasks = total_completed + total_failed
    
    worker_statistics = {
        'totalWorkers': worker_stats.get('total_workers') or 0,
        'busyWorkers': worker_stats.get('busy_workers') or 0,
        'idleWorkers': worker_stats.get('idle_workers') or 0,
        'totalCompleted': total_completed,
        'totalFailed': total_failed,
        'successRate': (total_completed / total_tasks * 100) if total_tasks > 0 else 0
    }
    
    return {
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'taskStats': task_statistics,
        'workerStats': worker_statistics,
        'version': '2.0.0'
    }

@query.field("health")
def resolve_health(_, info):
    """ヘルスチェック"""
    return "healthy"

@query.field("task")
def resolve_task(_, info, id):
    """特定のタスクを取得"""
    task = db.get_task(id)
    if task:
        return format_task(task)
    return None

@query.field("tasks")
def resolve_tasks(_, info, filter=None, limit=10, offset=0):
    """タスク一覧を取得"""
    # フィルタリングロジックは簡略化
    with db.get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM task_master"
        conditions = []
        params = []
        
        if filter:
            if filter.get('status'):
                status_map = {
                    'PENDING': 'pending',
                    'IN_PROGRESS': 'in_progress',
                    'COMPLETED': 'completed',
                    'FAILED': 'failed',
                    'CANCELLED': 'cancelled'
                }
                conditions.append("status = ?")
                params.append(status_map.get(filter['status'], 'pending'))
            
            if filter.get('createdBy'):
                conditions.append("created_by = ?")
                params.append(filter['createdBy'])
            
            if filter.get('assignedTo'):
                conditions.append("assigned_to = ?")
                params.append(filter['assignedTo'])
            
            if filter.get('minPriority'):
                conditions.append("priority >= ?")
                params.append(filter['minPriority'])
            
            if filter.get('maxPriority'):
                conditions.append("priority <= ?")
                params.append(filter['maxPriority'])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += f" ORDER BY priority DESC, created_at DESC LIMIT {limit} OFFSET {offset}"
        
        cursor.execute(query, params)
        tasks = cursor.fetchall()
        
        return [format_task(dict(task)) for task in tasks]

@query.field("taskStatistics")
def resolve_task_statistics(_, info):
    """タスク統計を取得"""
    stats = db.get_task_statistics()
    return {
        'pending': stats.get('pending', 0),
        'inProgress': stats.get('in_progress', 0),
        'completed': stats.get('completed', 0),
        'failed': stats.get('failed', 0),
        'total': sum(stats.values())
    }

@query.field("pendingTasks")
def resolve_pending_tasks(_, info, limit=10):
    """保留中のタスクを取得"""
    tasks = db.get_pending_tasks(limit)
    return [format_task(task) for task in tasks]

@query.field("worker")
def resolve_worker(_, info, id):
    """特定のワーカーを取得"""
    workers = db.get_active_workers(timeout_seconds=120)
    for worker in workers:
        if worker['worker_id'] == id:
            return format_worker(worker)
    return None

@query.field("workers")
def resolve_workers(_, info, filter=None, activeOnly=True):
    """ワーカー一覧を取得"""
    timeout = 60 if activeOnly else 3600
    workers = db.get_active_workers(timeout_seconds=timeout)
    
    if filter:
        filtered = []
        for worker in workers:
            if filter.get('status'):
                status_map = {
                    'IDLE': 'idle',
                    'BUSY': 'busy',
                    'OFFLINE': 'offline'
                }
                if worker['status'] != status_map.get(filter['status']):
                    continue
            
            if filter.get('minTasksCompleted'):
                if worker['tasks_completed'] < filter['minTasksCompleted']:
                    continue
            
            filtered.append(worker)
        workers = filtered
    
    return [format_worker(worker) for worker in workers]

@query.field("workerStatistics")
def resolve_worker_statistics(_, info):
    """ワーカー統計を取得"""
    stats = db.get_worker_statistics()
    total_completed = stats.get('total_completed', 0)
    total_failed = stats.get('total_failed', 0)
    total_tasks = total_completed + total_failed
    
    return {
        'totalWorkers': stats.get('total_workers', 0),
        'busyWorkers': stats.get('busy_workers', 0),
        'idleWorkers': stats.get('idle_workers', 0),
        'totalCompleted': total_completed,
        'totalFailed': total_failed,
        'successRate': (total_completed / total_tasks * 100) if total_tasks > 0 else 0
    }

@query.field("activeWorkers")
def resolve_active_workers(_, info):
    """アクティブなワーカーを取得"""
    workers = db.get_active_workers(timeout_seconds=60)
    return [format_worker(worker) for worker in workers]

# Mutation resolvers
mutation = MutationType()

@mutation.field("submitTask")
def resolve_submit_task(_, info, input):
    """タスクを送信"""
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    task_content = {
        'type': input['type'].lower(),
        'prompt': input['prompt'],
        'files': input.get('files', []),
        'options': input.get('options', {})
    }
    
    priority = input.get('priority', 5)
    
    success = db.create_task(
        task_id=task_id,
        content=json.dumps(task_content),
        priority=priority,
        created_by='graphql_client'
    )
    
    if success:
        task = db.get_task(task_id)
        return {
            'success': True,
            'taskId': task_id,
            'message': 'Task submitted successfully',
            'task': format_task(task) if task else None
        }
    else:
        return {
            'success': False,
            'taskId': None,
            'message': 'Failed to submit task',
            'task': None
        }

@mutation.field("cancelTask")
def resolve_cancel_task(_, info, id):
    """タスクをキャンセル"""
    success = db.update_task_status(id, 'cancelled')
    task = db.get_task(id) if success else None
    
    return {
        'success': success,
        'taskId': id,
        'message': 'Task cancelled' if success else 'Failed to cancel task',
        'task': format_task(task) if task else None
    }

@mutation.field("retryTask")
def resolve_retry_task(_, info, id):
    """タスクを再試行"""
    task = db.get_task(id)
    if not task:
        return {
            'success': False,
            'taskId': id,
            'message': 'Task not found',
            'task': None
        }
    
    # 新しいタスクIDで再作成
    new_task_id = f"retry_{id}_{datetime.now().strftime('%H%M%S')}"
    success = db.create_task(
        task_id=new_task_id,
        content=task['content'],
        priority=task['priority'],
        created_by='graphql_retry'
    )
    
    if success:
        new_task = db.get_task(new_task_id)
        return {
            'success': True,
            'taskId': new_task_id,
            'message': f'Task retried with new ID: {new_task_id}',
            'task': format_task(new_task) if new_task else None
        }
    
    return {
        'success': False,
        'taskId': None,
        'message': 'Failed to retry task',
        'task': None
    }

@mutation.field("updateTaskPriority")
def resolve_update_task_priority(_, info, id, priority):
    """タスクの優先度を更新"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE task_master 
            SET priority = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        """, (priority, id))
        conn.commit()
        success = cursor.rowcount > 0
    
    task = db.get_task(id) if success else None
    
    return {
        'success': success,
        'taskId': id,
        'message': f'Priority updated to {priority}' if success else 'Failed to update priority',
        'task': format_task(task) if task else None
    }

@mutation.field("spawnWorker")
def resolve_spawn_worker(_, info, count=1):
    """ワーカーを起動"""
    # 実際のワーカー起動はWorker Pool Managerが行うため、ここではシミュレート
    return {
        'success': True,
        'workerId': f"worker_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        'message': f'Request to spawn {count} worker(s) sent',
        'worker': None
    }

@mutation.field("terminateWorker")
def resolve_terminate_worker(_, info, id):
    """ワーカーを停止"""
    success = db.update_worker_status(id, 'offline')
    
    return {
        'success': success,
        'workerId': id,
        'message': 'Worker terminated' if success else 'Failed to terminate worker',
        'worker': None
    }

@mutation.field("scaleWorkers")
def resolve_scale_workers(_, info, targetCount):
    """ワーカー数を調整"""
    return {
        'success': True,
        'workerId': None,
        'message': f'Request to scale to {targetCount} workers sent',
        'worker': None
    }

@mutation.field("clearCompletedTasks")
def resolve_clear_completed_tasks(_, info, olderThanHours=24):
    """完了タスクをクリア"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM task_master 
            WHERE status IN ('completed', 'failed', 'cancelled')
            AND updated_at < datetime('now', '-' || ? || ' hours')
        """, (olderThanHours,))
        conn.commit()
        deleted = cursor.rowcount
    
    return deleted

@mutation.field("cleanupDeadWorkers")
def resolve_cleanup_dead_workers(_, info):
    """デッドワーカーをクリーンアップ"""
    deleted = db.cleanup_dead_workers(timeout_seconds=60)
    return deleted

# Helper functions
def format_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """タスクデータをGraphQL形式に変換"""
    if not task:
        return None
    
    # contentをJSONとしてパース
    content = task.get('content', '{}')
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except:
            content = {'raw': content}
    
    # resultをJSONとしてパース
    result = task.get('result')
    if result and isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            result = {'raw': result}
    
    return {
        'id': task['task_id'],
        'content': content,
        'status': task['status'].upper().replace('_', '_'),
        'priority': task.get('priority', 5),
        'result': result,
        'createdBy': task.get('created_by'),
        'assignedTo': task.get('assigned_to'),
        'createdAt': task.get('created_at'),
        'updatedAt': task.get('updated_at')
    }

def format_worker(worker: Dict[str, Any]) -> Dict[str, Any]:
    """ワーカーデータをGraphQL形式に変換"""
    if not worker:
        return None
    
    return {
        'id': worker['worker_id'],
        'status': worker['status'].upper(),
        'currentTask': worker.get('current_task'),
        'tasksCompleted': worker.get('tasks_completed', 0),
        'tasksFailed': worker.get('tasks_failed', 0),
        'lastHeartbeat': worker.get('last_heartbeat'),
        'createdAt': worker.get('created_at')
    }

# Create schema
schema = make_executable_schema(type_defs, query, mutation)

# Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# GraphQL playground
explorer_html = ExplorerGraphiQL().html(None)

@app.route("/graphql", methods=["GET"])
def graphql_playground():
    """GraphQL Playground UI"""
    return explorer_html, 200

@app.route("/graphql", methods=["POST"])
def graphql_server():
    """GraphQL API endpoint"""
    from ariadne import graphql_sync
    from flask import request, jsonify
    
    data = request.get_json()
    success, result = graphql_sync(
        schema,
        data,
        context_value=request,
        debug=app.debug
    )
    
    status_code = 200 if success else 400
    return jsonify(result), status_code

if __name__ == "__main__":
    print("🚀 Starting GraphQL Server")
    print("📊 GraphQL Playground: http://localhost:8767/graphql")
    print("🔌 GraphQL Endpoint: http://localhost:8767/graphql")
    print("")
    print("Example query:")
    print("  { systemStatus { status taskStats { pending completed } } }")
    print("")
    app.run(host="0.0.0.0", port=8767, debug=True)