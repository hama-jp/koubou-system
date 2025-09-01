# MCP Server API仕様

## 概要

MCP (Model Context Protocol) ServerはClaude Codeと工房システムを繋ぐRESTful APIサーバーです。

**ベースURL**: `http://localhost:8765`

## 認証

現在のPOC版では認証は実装されていません。本番環境では適切な認証機構の実装を推奨します。

## エンドポイント

### GET /health

システムのヘルスチェック

#### リクエスト
```http
GET /health HTTP/1.1
Host: localhost:8765
```

#### レスポンス
```json
{
  "status": "healthy",
  "timestamp": "2025-08-29T12:34:56.789Z"
}
```

#### ステータスコード
- `200 OK`: システム正常

---

### POST /task/delegate

タスクを委譲する

#### リクエスト
```http
POST /task/delegate HTTP/1.1
Host: localhost:8765
Content-Type: application/json

{
  "type": "code",
  "prompt": "Create a Python function to calculate prime numbers",
  "priority": 8,
  "sync": false,
  "files": ["utils.py", "main.py"],
  "options": {
    "timeout": 120,
    "model": "gpt-oss:20b"
  }
}
```

#### パラメータ

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| type | string | Yes | タスクタイプ: `code` または `general` |
| prompt | string | Yes | タスクの内容/指示 |
| priority | integer | No | 優先度 (1-10)、デフォルト: 5 |
| sync | boolean | No | 同期実行フラグ、デフォルト: false |
| files | array | No | 関連ファイルのリスト |
| options | object | No | 追加オプション |

#### レスポンス（非同期）
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "delegated"
}
```

#### レスポンス（同期）
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "completed",
  "result": {
    "success": true,
    "output": "def is_prime(n):\n    if n <= 1:\n        return False\n    ...",
    "error": null
  }
}
```

#### ステータスコード
- `200 OK`: タスク委譲成功
- `400 Bad Request`: 無効なリクエスト
- `500 Internal Server Error`: サーバーエラー

---

### GET /task/{task_id}/status

タスクのステータスを取得

#### リクエスト
```http
GET /task/task_20250829_123456_789012/status HTTP/1.1
Host: localhost:8765
```

#### レスポンス
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "completed",
  "result": {
    "success": true,
    "output": "Task output...",
    "error": null
  },
  "created_at": "2025-08-29T12:34:56",
  "updated_at": "2025-08-29T12:35:12"
}
```

#### ステータス値
- `pending`: 処理待ち
- `in_progress`: 処理中
- `completed`: 完了
- `failed`: 失敗
- `cancelled`: キャンセル

#### ステータスコード
- `200 OK`: 成功
- `404 Not Found`: タスクが見つからない

---

### GET /tasks

タスク一覧を取得

#### リクエスト
```http
GET /tasks?status=pending&limit=10 HTTP/1.1
Host: localhost:8765
```

#### クエリパラメータ

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| status | string | フィルタするステータス |
| limit | integer | 取得件数の上限（デフォルト: 10） |
| offset | integer | オフセット |

#### レスポンス
```json
{
  "tasks": [
    {
      "task_id": "task_20250829_123456_789012",
      "status": "completed",
      "created_at": "2025-08-29T12:34:56"
    },
    {
      "task_id": "task_20250829_123457_890123",
      "status": "pending",
      "created_at": "2025-08-29T12:34:57"
    }
  ],
  "total": 42
}
```

---

### DELETE /task/{task_id}

タスクをキャンセル（未実装）

#### リクエスト
```http
DELETE /task/task_20250829_123456_789012 HTTP/1.1
Host: localhost:8765
```

#### レスポンス
```json
{
  "task_id": "task_20250829_123456_789012",
  "status": "cancelled"
}
```

## エラーレスポンス

すべてのエラーレスポンスは以下の形式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {}
  }
}
```

### エラーコード

| コード | 説明 |
|--------|------|
| INVALID_REQUEST | リクエストが無効 |
| TASK_NOT_FOUND | タスクが見つからない |
| SERVER_ERROR | サーバー内部エラー |
| WORKER_UNAVAILABLE | ワーカーが利用不可 |
| TIMEOUT | タイムアウト |

## 使用例

### Python

```python
import requests
import json

class MCPClient:
    def __init__(self, base_url='http://localhost:8765'):
        self.base_url = base_url
    
    def submit_task(self, prompt, task_type='general', sync=False, priority=5):
        response = requests.post(
            f'{self.base_url}/task/delegate',
            json={
                'type': task_type,
                'prompt': prompt,
                'sync': sync,
                'priority': priority
            }
        )
        return response.json()
    
    def get_status(self, task_id):
        response = requests.get(
            f'{self.base_url}/task/{task_id}/status'
        )
        return response.json()
    
    def wait_for_completion(self, task_id, timeout=300):
        import time
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(task_id)
            if status['status'] in ['completed', 'failed']:
                return status
            time.sleep(2)
        raise TimeoutError(f"Task {task_id} timed out")

# 使用例
client = MCPClient()

# 同期実行
result = client.submit_task(
    "Write a haiku about programming",
    task_type='general',
    sync=True
)
print(result['result']['output'])

# 非同期実行
task = client.submit_task(
    "Create a REST API with Flask",
    task_type='code',
    sync=False,
    priority=8
)
result = client.wait_for_completion(task['task_id'])
print(result['result']['output'])
```

### cURL

```bash
# ヘルスチェック
curl http://localhost:8765/health

# タスク送信（同期）
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "type": "general",
    "prompt": "What is recursion?",
    "sync": true
  }'

# タスク送信（非同期）
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "type": "code",
    "prompt": "Create a binary search function",
    "sync": false,
    "priority": 7
  }'

# ステータス確認
curl http://localhost:8765/task/task_20250829_123456_789012/status

# タスク一覧
curl "http://localhost:8765/tasks?status=pending&limit=5"
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

class MCPClient {
    constructor(baseURL = 'http://localhost:8765') {
        this.client = axios.create({ baseURL });
    }
    
    async submitTask(prompt, options = {}) {
        const { data } = await this.client.post('/task/delegate', {
            type: options.type || 'general',
            prompt,
            sync: options.sync || false,
            priority: options.priority || 5
        });
        return data;
    }
    
    async getStatus(taskId) {
        const { data } = await this.client.get(`/task/${taskId}/status`);
        return data;
    }
    
    async waitForCompletion(taskId, timeout = 300000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const status = await this.getStatus(taskId);
            if (['completed', 'failed'].includes(status.status)) {
                return status;
            }
            await new Promise(r => setTimeout(r, 2000));
        }
        throw new Error(`Task ${taskId} timed out`);
    }
}

// 使用例
(async () => {
    const client = new MCPClient();
    
    // 同期実行
    const result = await client.submitTask(
        'Explain async/await in JavaScript',
        { sync: true }
    );
    console.log(result.result.output);
    
    // 非同期実行
    const task = await client.submitTask(
        'Create an Express.js server',
        { type: 'code', priority: 8 }
    );
    const completed = await client.waitForCompletion(task.task_id);
    console.log(completed.result.output);
})();
```

## レート制限

現在のPOC版ではレート制限は実装されていません。本番環境では以下を推奨：

- リクエスト/秒: 100
- 同時タスク数: max_workers設定に依存
- タスクサイズ: 最大1MB

## WebSocket（計画中）

リアルタイム更新のためのWebSocketエンドポイント（未実装）：

```javascript
// 将来の実装例
const ws = new WebSocket('ws://localhost:8765/ws');

ws.on('message', (data) => {
    const event = JSON.parse(data);
    switch(event.type) {
        case 'task_started':
            console.log(`Task ${event.task_id} started`);
            break;
        case 'task_completed':
            console.log(`Task ${event.task_id} completed`);
            break;
        case 'worker_spawned':
            console.log(`New worker ${event.worker_id} spawned`);
            break;
    }
});
```

---
最終更新: 2025-08-29
バージョン: 1.0.0