# GraphQL API 仕様書

## 概要

工房システムのGraphQL APIは、柔軟なクエリインターフェースを提供し、必要なデータのみを効率的に取得できます。

**エンドポイント**: `http://localhost:8767/graphql`  
**Playground**: `http://localhost:8767/graphql` (ブラウザでアクセス)

## 主な特徴

- 🎯 **柔軟なクエリ**: 必要なフィールドのみを選択的に取得
- 🔄 **単一エンドポイント**: すべての操作を1つのURLで実行
- 📊 **型安全**: 強い型付けによるエラー防止
- 🎮 **Playground**: インタラクティブなクエリエディタ

## スキーマ

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

### システム状態

#### systemStatus
システム全体の状態を取得

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

### タスク関連

#### task
特定のタスクを取得

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
タスク一覧を取得（フィルタリング可能）

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

フィルタオプション:
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
保留中のタスクを優先度順に取得

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

### ワーカー関連

#### worker
特定のワーカーを取得

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
ワーカー一覧を取得

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
アクティブなワーカーのみを取得

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

### タスク操作

#### submitTask
新しいタスクを送信

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

入力:
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
タスクをキャンセル

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
失敗したタスクを再試行

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
タスクの優先度を更新

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

### ワーカー操作

#### spawnWorker
新しいワーカーを起動

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
ワーカーを停止

```graphql
mutation TerminateWorker($id: String!) {
    terminateWorker(id: $id) {
        success
        message
    }
}
```

#### scaleWorkers
ワーカー数を調整

```graphql
mutation ScaleWorkers($targetCount: Int!) {
    scaleWorkers(targetCount: $targetCount) {
        success
        message
    }
}
```

### メンテナンス操作

#### clearCompletedTasks
古い完了タスクを削除

```graphql
mutation ClearOldTasks($olderThanHours: Int) {
    clearCompletedTasks(olderThanHours: $olderThanHours)
}
```

#### cleanupDeadWorkers
応答のないワーカーをクリーンアップ

```graphql
mutation CleanupWorkers {
    cleanupDeadWorkers
}
```

## 使用例

### Python

```python
import requests

# GraphQLクエリ
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

# リクエスト送信
response = requests.post(
    'http://localhost:8767/graphql',
    json={'query': query}
)

data = response.json()
print(data['data']['systemStatus'])
```

### JavaScript

```javascript
// GraphQLクエリ
const query = `
    mutation SubmitTask($input: TaskInput!) {
        submitTask(input: $input) {
            success
            taskId
            message
        }
    }
`;

// 変数
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
# システムステータス取得
curl -X POST http://localhost:8767/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ systemStatus { status } }"}'

# タスク送信
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

ブラウザで `http://localhost:8767/graphql` にアクセスすると、インタラクティブなGraphQL Playgroundが利用できます。

### Playgroundの機能

- 📝 **クエリエディタ**: 自動補完とシンタックスハイライト
- 📚 **スキーマエクスプローラー**: 利用可能な型とフィールドを確認
- 📊 **リアルタイム実行**: クエリを即座に実行して結果を確認
- 💾 **履歴管理**: 実行したクエリの履歴を保存

## ベストプラクティス

### 1. 必要なフィールドのみを取得

```graphql
# Good - 必要なフィールドのみ
query {
    tasks {
        id
        status
    }
}

# Bad - すべてのフィールドを取得
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

### 2. 変数を使用

```graphql
# Good - 変数を使用
query GetTask($id: String!) {
    task(id: $id) {
        status
    }
}

# Bad - ハードコード
query {
    task(id: "task_20250829_123456") {
        status
    }
}
```

### 3. フラグメントで再利用

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

## エラーハンドリング

GraphQLエラーは以下の形式で返されます：

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

## パフォーマンス考慮事項

1. **N+1問題の回避**: DataLoaderパターンの使用を検討
2. **ページネーション**: 大量のデータには必ずlimitとoffsetを使用
3. **キャッシング**: 頻繁にアクセスされるデータはキャッシュを検討

---

最終更新: 2025-08-29
バージョン: 1.0.0