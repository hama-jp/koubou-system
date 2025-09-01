# GraphQL API Specification

## Overview

Koubou System's GraphQL API provides a flexible query interface that enables efficient retrieval of only the data you need.

**Endpoint**: `http://localhost:8767/graphql`  
**Playground**: `http://localhost:8767/graphql` (access via browser)

## Key Features

- 🎯 **Flexible Queries**: Selectively fetch only the fields you require  
- 🔄 **Single Endpoint**: Execute all operations at one URL  
- 📊 **Type Safety**: Strong typing prevents errors  
- 🎮 **Playground**: Interactive query editor  

## Schema

### Types

#### Task
```graphql
type Task {
    id: String!           # タスクID
    content: JSON!        # タスク内容
    status: TaskStatus!   # ステータス
    priority: Int!        # 優先度 (1-10)
    result: JSON         # 実行結果
    createdBy: String    # 作成者
    assignedTo: String   # 割り当て先ワーカー
    createdAt: DateTime! # 作成日時
    updatedAt: DateTime! # 更新日時
}
```

#### Worker
```graphql
type Worker {
    id: String!              # ワーカーID
    status: WorkerStatus!    # ステータス
    currentTask: String      # 現在のタスク
    tasksCompleted: Int!     # 完了タスク数
    tasksFailed: Int!        # 失敗タスク数
    lastHeartbeat: DateTime! # 最終ハートビート
    createdAt: DateTime!     # 作成日時
}
```

### Enums

```graphql
enum TaskStatus {
    PENDING
    IN_PROGRESS
    COMPLETED
    FAILED
    CANCELLED
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
```

## Queries

### System Status

#### systemStatus
Retrieve the overall status of the system

```graphql
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
```

### Task Related

#### task
Retrieve a specific task

```graphql
query GetTask($id: String!) {
    task(id: $id) {
        id
        content
        status
        priority
        result
        createdBy
        assignedTo
        createdAt
        updatedAt
    }
}
```

#### tasks
Retrieve a list of tasks (filterable)

```graphql
query GetTasks($filter: TaskFilter, $limit: Int, $offset: Int) {
    tasks(filter: $filter, limit: $limit, offset: $offset) {
        id
        status
        priority
        createdAt
    }
}
```

Filter options:
```graphql
input TaskFilter {
    status: TaskStatus
    createdBy: String
    assignedTo: String
    minPriority: Int
    maxPriority: Int
}
```

#### pendingTasks
Retrieve pending tasks sorted by priority

```graphql
query GetPendingTasks($limit: Int) {
    pendingTasks(limit: $limit) {
        id
        priority
        content
        createdAt
    }
}
```

### Worker Related

#### worker
Retrieve a specific worker

```graphql
query GetWorker($id: String!) {
    worker(id: $id) {
        id
        status
        currentTask
        tasksCompleted
        tasksFailed
        lastHeartbeat
    }
}
```

#### workers
Retrieve a list of workers

```graphql
query GetWorkers($filter: WorkerFilter, $activeOnly: Boolean) {
    workers(filter: $filter, activeOnly: $activeOnly) {
        id
        status
        tasksCompleted
        tasksFailed
    }
}
```

#### activeWorkers
Retrieve only active workers

```graphql
query GetActiveWorkers {
    activeWorkers {
        id
        status
        currentTask
    }
}
```

## Mutations

### Task Operations

#### submitTask
Submit a new task

```graphql
mutation SubmitTask($input: TaskInput!) {
    submitTask(input: $input) {
        success
        taskId
        message
        task {
            id
            status
            priority
        }
    }
}
```

Input:
```graphql
input TaskInput {
    type: TaskType!      # CODE または GENERAL
    prompt: String!      # タスクの内容
    priority: Int        # 優先度 (1-10)
    files: [String!]     # 関連ファイル
    options: JSON        # 追加オプション
    sync: Boolean        # 同期実行フラグ
}
```

#### cancelTask
Cancel a task

```graphql
mutation CancelTask($id: String!) {
    cancelTask(id: $id) {
        success
        message
        task {
            id
            status
        }
    }
}
```

#### retryTask
Retry a failed task

```graphql
mutation RetryTask($id: String!) {
    retryTask(id: $id) {
        success
        taskId
        message
        task {
            id
            status
        }
    }
}
```

#### updateTaskPriority
Update the priority of a task

```graphql
mutation UpdatePriority($id: String!, $priority: Int!) {
    updateTaskPriority(id: $id, priority: $priority) {
        success
        message
        task {
            id
            priority
        }
    }
}
```

### Worker Operations

#### spawnWorker
Spawn new workers

```graphql
mutation SpawnWorker($count: Int) {
    spawnWorker(count: $count) {
        success
        workerId
        message
    }
}
```

#### terminateWorker
Terminate a worker

```graphql
mutation TerminateWorker($id: String!) {
    terminateWorker(id: $id) {
        success
        message
    }
}
```

#### scaleWorkers
Adjust the number of workers

```graphql
mutation ScaleWorkers($targetCount: Int!) {
    scaleWorkers(targetCount: $targetCount) {
        success
        message
    }
}
```

### Maintenance Operations

#### clearCompletedTasks
Delete old completed tasks

```graphql
mutation ClearOldTasks($olderThanHours: Int) {
    clearCompletedTasks(olderThanHours: $olderThanHours)
}
```

#### cleanupDeadWorkers
Clean up unresponsive workers

```graphql
mutation CleanupWorkers {
    cleanupDeadWorkers
}
```

## Usage Examples

### Python

```python
import requests

# GraphQL query
query = """
query GetSystemStatus {
    systemStatus {
        status
        taskStats {
            pending
            completed
        }
    }
}
"""

# Send request
response = requests.post(
    'http://localhost:8767/graphql',
    json={'query': query}
)

data = response.json()
print(data['data']['systemStatus'])
```

### JavaScript

```javascript
// GraphQL query
const query = `
    mutation SubmitTask($input: TaskInput!) {
        submitTask(input: $input) {
            success
            taskId
            message
        }
    }
`;

// Variables
const variables = {
    input: {
        type: 'GENERAL',
        prompt: 'Hello from GraphQL',
        priority: 5
    }
};

// Fetch API
fetch('http://localhost:8767/graphql', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        query,
        variables
    })
})
.then(res => res.json())
.then(data => console.log(data));
```

### cURL

```bash
# Retrieve system status
curl -X POST http://localhost:8767/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ systemStatus { status } }"}'

# Submit a task
curl -X POST http://localhost:8767/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation SubmitTask($input: TaskInput!) { submitTask(input: $input) { success taskId } }",
    "variables": {
        "input": {
            "type": "GENERAL",
            "prompt": "Test task",
            "priority": 5
        }
    }
  }'
```

## GraphQL Playground

Access `http://localhost:8767/graphql` in your browser to use the interactive GraphQL Playground.

### Playground Features

- 📝 **Query Editor**: Autocomplete and syntax highlighting  
- 📚 **Schema Explorer**: View available types and fields  
- 📊 **Real‑time Execution**: Execute queries instantly and see results  
- 💾 **History Management**: Store a history of executed queries  

## Best Practices

### 1. Retrieve Only Necessary Fields

```graphql
# Good - retrieve only the fields you need
query {
    tasks {
        id
        status
    }
}

# Bad - fetch all fields
query {
    tasks {
        id
        content
        status
        priority
        result
        createdBy
        assignedTo
        createdAt
        updatedAt
    }
}
```

### 2. Use Variables

```graphql
# Good - use variables
query GetTask($id: String!) {
    task(id: $id) {
        status
    }
}

# Bad - hard‑code the ID
query {
    task(id: "task_20250829_123456") {
        status
    }
}
```

### 3. Reuse with Fragments

```graphql
fragment TaskBasic on Task {
    id
    status
    priority
}

query {
    pendingTasks {
        ...TaskBasic
    }
    tasks {
        ...TaskBasic
        createdAt
    }
}
```

## Error Handling

GraphQL errors are returned in the following format:

```json
{
    "errors": [
        {
            "message": "Task not found",
            "path": ["task"],
            "extensions": {
                "code": "NOT_FOUND"
            }
        }
    ],
    "data": {
        "task": null
    }
}
```

## Performance Considerations

1. **Avoid N+1 Problems**: Consider using the DataLoader pattern  
2. **Pagination**: Always use `limit` and `offset` for large datasets  
3. **Caching**: Cache frequently accessed data where appropriate  

---  

Last Updated: 2025-08-29  
Version: 1.0.0