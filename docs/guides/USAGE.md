# 使用ガイド

## 基本的な使い方

### システムの起動

```bash
# すべてのコンポーネントを起動
.koubou/start_system.sh

# 個別に起動する場合
# 1. Ollama
ollama serve

# 2. MCPサーバー
source .koubou/venv/bin/activate
python .koubou/scripts/mcp_server.py

# 3. ワーカープール
python .koubou/scripts/workers/worker_pool_manager.py
```

### 最初のタスク

#### 1. 簡単な質問（同期モード）

```python
import requests

response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'general',
    'prompt': 'What is Python?',
    'sync': True  # 結果を待つ
})

print(response.json()['result']['output'])
```

#### 2. コード生成（非同期モード）

```python
# タスク送信
response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'code',
    'prompt': 'Create a Python function to calculate factorial',
    'sync': False,  # バックグラウンド処理
    'priority': 8
})

task_id = response.json()['task_id']

# ステータス確認
import time
while True:
    status = requests.get(f'http://localhost:8765/task/{task_id}/status')
    if status.json()['status'] in ['completed', 'failed']:
        print(status.json()['result'])
        break
    time.sleep(2)
```

## Codex CLIの使用

### インタラクティブモード

```bash
# Ollamaを使用
.koubou/scripts/codex-ollama.sh

# プロンプト例
> Create a REST API with Flask
> Add error handling to the current code
> Refactor this function for better performance
```

### コマンドラインモード

```bash
# ファイル作成
.koubou/scripts/codex-exec.sh "Create a Python script that reads CSV files"

# 既存ファイルの修正
.koubou/scripts/codex-exec.sh "Add type hints to all functions in utils.py"

# テスト作成
.koubou/scripts/codex-exec.sh "Write unit tests for calculator.py using pytest"
```

## タスクの管理

### タスク一覧の取得

```bash
# curl経由
curl http://localhost:8765/tasks | jq

# Python経由
import requests
response = requests.get('http://localhost:8765/tasks')
for task in response.json()['tasks']:
    print(f"{task['task_id']}: {task['status']}")
```

### タスクの優先度設定

優先度は1（低）から10（高）まで：

```python
# 高優先度タスク
high_priority = {
    'type': 'code',
    'prompt': 'Fix critical bug in production',
    'priority': 10,
    'sync': False
}

# 低優先度タスク
low_priority = {
    'type': 'general',
    'prompt': 'Generate documentation',
    'priority': 3,
    'sync': False
}
```

## 負荷テスト

### バーストテスト

```bash
# 20個のタスクを一度に投入
python .koubou/scripts/load_test.py
# オプション1を選択
```

### 継続的負荷テスト

```python
import requests
import time
import random

# 10分間、毎秒1タスクを送信
end_time = time.time() + 600
while time.time() < end_time:
    requests.post('http://localhost:8765/task/delegate', json={
        'type': random.choice(['general', 'code']),
        'prompt': f'Test task {time.time()}',
        'priority': random.randint(1, 10),
        'sync': False
    })
    time.sleep(1)
```

## モニタリング

### システム状態の確認

```bash
# ヘルスチェック
curl http://localhost:8765/health

# ワーカー状態（データベース経由）
sqlite3 .koubou/db/koubou.db "
SELECT worker_id, status, tasks_completed, tasks_failed 
FROM workers 
WHERE last_heartbeat > datetime('now', '-1 minute');"

# タスク統計
sqlite3 .koubou/db/koubou.db "
SELECT status, COUNT(*) 
FROM task_master 
GROUP BY status;"
```

### ログの確認

```bash
# MCPサーバーログ
tail -f .koubou/logs/mcp_server.log

# ワーカープールログ
tail -f .koubou/logs/worker_pool.log

# 特定ワーカーのログ
tail -f .koubou/logs/workers/worker_*.log

# エラーのみ抽出
grep ERROR .koubou/logs/*.log
```

## 実践的な使用例

### 1. プロジェクトのリファクタリング

```bash
# プロジェクトディレクトリで実行
cd my_project

# コードの改善を依頼
.koubou/scripts/codex-exec.sh "
Refactor all Python files in this directory:
1. Add type hints
2. Improve error handling
3. Add docstrings
4. Follow PEP 8
"
```

### 2. テストスイートの作成

```python
# APIでタスク送信
import requests

tasks = [
    "Create unit tests for models.py",
    "Create integration tests for api.py",
    "Create end-to-end tests for the application",
    "Generate test data fixtures"
]

for task in tasks:
    requests.post('http://localhost:8765/task/delegate', json={
        'type': 'code',
        'prompt': task,
        'priority': 7,
        'sync': False
    })
```

### 3. ドキュメント生成

```bash
# バッチ処理
for file in *.py; do
    .koubou/scripts/codex-exec.sh "
    Generate comprehensive documentation for $file including:
    - Module overview
    - Function descriptions
    - Usage examples
    - Parameter explanations
    "
done
```

## Tips & Tricks

### パフォーマンス最適化

1. **適切な優先度設定**
   - 緊急タスク: 8-10
   - 通常タスク: 4-7
   - バックグラウンド: 1-3

2. **タスクの分割**
   - 大きなタスクは小さく分割
   - 並列処理可能な部分を識別

3. **モデル選択**
   - 簡単なタスク: 軽量モデル
   - 複雑なタスク: 大規模モデル

### エラー処理

```python
def submit_task_with_retry(task_data, max_retries=3):
    for i in range(max_retries):
        try:
            response = requests.post(
                'http://localhost:8765/task/delegate',
                json=task_data,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            time.sleep(2 ** i)  # 指数バックオフ
    return None
```

### カスタムワークフロー

```python
class TaskPipeline:
    def __init__(self):
        self.base_url = 'http://localhost:8765'
    
    def create_and_test(self, module_name):
        # 1. コード生成
        code_task = self.submit_task({
            'type': 'code',
            'prompt': f'Create {module_name}.py with basic functionality',
            'priority': 8,
            'sync': True
        })
        
        # 2. テスト作成
        test_task = self.submit_task({
            'type': 'code',
            'prompt': f'Create test_{module_name}.py with pytest',
            'priority': 7,
            'sync': True
        })
        
        # 3. ドキュメント生成
        doc_task = self.submit_task({
            'type': 'general',
            'prompt': f'Generate README for {module_name}',
            'priority': 5,
            'sync': True
        })
        
        return code_task, test_task, doc_task
    
    def submit_task(self, task_data):
        response = requests.post(
            f'{self.base_url}/task/delegate',
            json=task_data
        )
        return response.json()
```

## 次のステップ

- [API仕様](../api/MCP_SERVER_API.md) - APIの詳細
- [トラブルシューティング](../operations/TROUBLESHOOTING.md) - 問題解決
- [パフォーマンスチューニング](../operations/PERFORMANCE.md) - 最適化

---
最終更新: 2025-08-29
バージョン: 1.0.0