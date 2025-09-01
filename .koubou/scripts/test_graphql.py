#!/usr/bin/env python3
"""
GraphQL API テストクライアント
"""

import requests
import json
from datetime import datetime

# GraphQL エンドポイント
GRAPHQL_URL = "http://localhost:8767/graphql"

def execute_query(query, variables=None):
    """GraphQLクエリを実行"""
    response = requests.post(
        GRAPHQL_URL,
        json={'query': query, 'variables': variables or {}},
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None

def test_system_status():
    """システムステータスを取得"""
    query = """
    query GetSystemStatus {
        systemStatus {
            status
            timestamp
            version
            taskStats {
                pending
                inProgress
                completed
                failed
                total
            }
            workerStats {
                totalWorkers
                busyWorkers
                idleWorkers
                totalCompleted
                totalFailed
                successRate
            }
        }
    }
    """
    
    print("📊 System Status Query:")
    print("-" * 50)
    result = execute_query(query)
    if result and 'data' in result:
        status = result['data']['systemStatus']
        print(f"Status: {status['status']}")
        print(f"Version: {status['version']}")
        print(f"Timestamp: {status['timestamp']}")
        print(f"\nTask Statistics:")
        for key, value in status['taskStats'].items():
            print(f"  {key}: {value}")
        print(f"\nWorker Statistics:")
        for key, value in status['workerStats'].items():
            print(f"  {key}: {value}")
    print()

def test_submit_task():
    """タスクを送信"""
    mutation = """
    mutation SubmitTask($input: TaskInput!) {
        submitTask(input: $input) {
            success
            taskId
            message
            task {
                id
                status
                priority
                createdAt
            }
        }
    }
    """
    
    variables = {
        "input": {
            "type": "GENERAL",
            "prompt": "Test task from GraphQL",
            "priority": 7
        }
    }
    
    print("📝 Submit Task Mutation:")
    print("-" * 50)
    result = execute_query(mutation, variables)
    if result and 'data' in result:
        submission = result['data']['submitTask']
        print(f"Success: {submission['success']}")
        print(f"Task ID: {submission['taskId']}")
        print(f"Message: {submission['message']}")
        if submission['task']:
            print(f"Task Status: {submission['task']['status']}")
            print(f"Task Priority: {submission['task']['priority']}")
    print()

def test_get_tasks():
    """タスク一覧を取得"""
    query = """
    query GetTasks($filter: TaskFilter, $limit: Int) {
        tasks(filter: $filter, limit: $limit) {
            id
            status
            priority
            createdBy
            createdAt
        }
    }
    """
    
    variables = {
        "filter": {
            "status": "PENDING"
        },
        "limit": 5
    }
    
    print("📋 Get Tasks Query:")
    print("-" * 50)
    result = execute_query(query)
    if result and 'data' in result:
        tasks = result['data']['tasks']
        print(f"Found {len(tasks)} tasks:")
        for task in tasks:
            print(f"  • {task['id']}: {task['status']} (Priority: {task['priority']})")
    print()

def test_get_workers():
    """ワーカー一覧を取得"""
    query = """
    query GetWorkers {
        workers {
            id
            status
            currentTask
            tasksCompleted
            tasksFailed
            lastHeartbeat
        }
    }
    """
    
    print("👷 Get Workers Query:")
    print("-" * 50)
    result = execute_query(query)
    if result and 'data' in result:
        workers = result['data']['workers']
        print(f"Found {len(workers)} workers:")
        for worker in workers:
            print(f"  • {worker['id']}: {worker['status']}")
            print(f"    Completed: {worker['tasksCompleted']}, Failed: {worker['tasksFailed']}")
    print()

def test_task_statistics():
    """タスク統計を取得"""
    query = """
    query GetStatistics {
        taskStatistics {
            pending
            inProgress
            completed
            failed
            total
        }
        workerStatistics {
            totalWorkers
            busyWorkers
            successRate
        }
    }
    """
    
    print("📈 Statistics Query:")
    print("-" * 50)
    result = execute_query(query)
    if result and 'data' in result:
        task_stats = result['data']['taskStatistics']
        worker_stats = result['data']['workerStatistics']
        
        print("Task Statistics:")
        for key, value in task_stats.items():
            print(f"  {key}: {value}")
        
        print("\nWorker Statistics:")
        for key, value in worker_stats.items():
            print(f"  {key}: {value}")
    print()

def test_complex_query():
    """複雑なクエリ例"""
    query = """
    query ComplexQuery {
        pendingTasks(limit: 3) {
            id
            priority
            content
        }
        activeWorkers {
            id
            status
            currentTask
        }
        health
    }
    """
    
    print("🔍 Complex Query:")
    print("-" * 50)
    result = execute_query(query)
    if result and 'data' in result:
        data = result['data']
        
        print(f"Health: {data['health']}")
        
        print(f"\nPending Tasks ({len(data['pendingTasks'])}):")
        for task in data['pendingTasks']:
            print(f"  • {task['id']} (Priority: {task['priority']})")
        
        print(f"\nActive Workers ({len(data['activeWorkers'])}):")
        for worker in data['activeWorkers']:
            print(f"  • {worker['id']}: {worker['status']}")
            if worker['currentTask']:
                print(f"    Working on: {worker['currentTask']}")
    print()

def interactive_mode():
    """インタラクティブモード"""
    print("\n🎮 Interactive GraphQL Client")
    print("=" * 50)
    print("Type 'help' for commands, 'quit' to exit")
    print()
    
    while True:
        command = input("graphql> ").strip().lower()
        
        if command == 'quit' or command == 'exit':
            break
        elif command == 'help':
            print("\nAvailable commands:")
            print("  status    - Get system status")
            print("  submit    - Submit a test task")
            print("  tasks     - List tasks")
            print("  workers   - List workers")
            print("  stats     - Get statistics")
            print("  complex   - Run complex query")
            print("  custom    - Enter custom GraphQL query")
            print("  quit      - Exit")
            print()
        elif command == 'status':
            test_system_status()
        elif command == 'submit':
            test_submit_task()
        elif command == 'tasks':
            test_get_tasks()
        elif command == 'workers':
            test_get_workers()
        elif command == 'stats':
            test_task_statistics()
        elif command == 'complex':
            test_complex_query()
        elif command == 'custom':
            print("Enter your GraphQL query (end with empty line):")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            query = '\n'.join(lines)
            if query:
                result = execute_query(query)
                print(json.dumps(result, indent=2))
            print()
        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands")
        print()

if __name__ == "__main__":
    print("🧪 GraphQL API Test Client")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(GRAPHQL_URL)
        if response.status_code != 200:
            raise Exception()
    except:
        print("❌ GraphQL server is not running")
        print("Start it with: python .koubou/scripts/graphql_server.py")
        exit(1)
    
    print("✅ Connected to GraphQL server")
    print()
    
    # Run tests
    print("Running automated tests...")
    print()
    
    test_system_status()
    test_submit_task()
    test_get_tasks()
    test_get_workers()
    test_task_statistics()
    test_complex_query()
    
    # Interactive mode
    interactive_mode()