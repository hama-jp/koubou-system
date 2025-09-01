# 🏭 工房システム完全ガイド v2.1.0

## 📚 目次

1. [概要](#概要)
2. [システムアーキテクチャ](#システムアーキテクチャ)
3. [インストール](#インストール)
4. [基本的な使い方](#基本的な使い方)
5. [高度な機能](#高度な機能)
6. [トラブルシューティング](#トラブルシューティング)
7. [開発者向け情報](#開発者向け情報)

## 概要

工房システムは、Claude Code（親方）と複数のローカルLLMワーカー（職人）が協働する分散タスク処理フレームワークです。

### 主な特徴

- 🤖 **マルチLLM対応**: Ollama、Codex CLI、各種APIを統合
- 🔄 **動的スケーリング**: タスク量に応じてワーカー数を自動調整
- 🌐 **分散処理**: Redis/RabbitMQを使った水平スケーリング
- 📊 **リアルタイム監視**: WebSocket、GraphQL、Webダッシュボード
- 🔒 **ローカル処理**: 機密データをクラウドに送信せず安全に処理

## システムアーキテクチャ

### コンポーネント構成

```
┌─────────────────┐
│  Claude Code    │ ← ユーザーインターフェース
└────────┬────────┘
         │ MCP API
┌────────▼────────┐
│   MCP Server    │ ← 中央コントローラー (Flask)
│  (localhost:8765)│
└────────┬────────┘
         │
    ┌────▼────────────────────────┐
    │     Task Queue (SQLite)      │
    └────────────┬─────────────────┘
                 │
    ┌────────────▼─────────────────┐
    │   Worker Pool Manager        │
    │  (動的スケーリング 1-8)      │
    └────────────┬─────────────────┘
                 │
         ┌───────┴───────┐
         ▼               ▼
    ┌─────────┐    ┌─────────┐
    │Worker #1│    │Worker #N│
    └────┬────┘    └────┬────┘
         │               │
    ┌────▼───────────────▼────┐
    │   LLM Backend            │
    │  - Ollama (gemma2:2b)    │
    │  - Codex CLI             │
    └──────────────────────────┘
```

### 通信フロー

1. **タスク送信**: Client → MCP Server → Task Queue
2. **タスク処理**: Worker Pool → Worker → LLM → Result
3. **結果返却**: Result → MCP Server → Client

## インストール

### 必要条件

- **OS**: Linux/macOS/WSL2
- **Python**: 3.9以上
- **uv**: Astralの高速Pythonパッケージマネージャー
- **SQLite3**: データベース
- **Redis**: 分散機能使用時（オプション）
- **Ollama**: ローカルLLM実行環境（オプション）

### クイックインストール

```bash
# 1. リポジトリのクローン
git clone https://github.com/your-repo/koubou-system.git
cd koubou-system

# 2. セットアップスクリプト実行（v2.1.0）
./scripts/setup_poc_v2.sh

# 3. LLMモデルのダウンロード（Ollama使用時）
ollama pull gemma2:2b
```

### 手動インストール

```bash
# 1. ディレクトリ作成
mkdir -p .koubou/{scripts,config,db,logs,venv}

# 2. Python仮想環境
uv venv .koubou/venv

# 3. 依存関係インストール
cd .koubou
uv pip install --python venv/bin/python \
    flask flask-cors requests pyyaml psutil \
    websockets ariadne redis click rich

# 4. データベース初期化
sqlite3 db/koubou.db < ../scripts/init_database.sql
```

## 基本的な使い方

### システム起動

```bash
# 基本システム起動
.koubou/start_system.sh

# 個別コンポーネント起動
.koubou/venv/bin/python .koubou/scripts/mcp_server.py &
.koubou/venv/bin/python .koubou/scripts/workers/worker_pool_manager.py &
```

### タスク送信

#### Python API

```python
import requests

# タスク送信
response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'code',
    'prompt': 'Create a Python function for fibonacci',
    'priority': 8
})

task_id = response.json()['task_id']

# ステータス確認
status = requests.get(f'http://localhost:8765/task/{task_id}/status')
print(status.json())
```

#### cURL

```bash
# タスク送信
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{"type": "general", "prompt": "Explain Python decorators"}'

# ステータス確認
curl http://localhost:8765/task/{task_id}/status
```

## 高度な機能

### 1. 分散ワーカーシステム

Redis経由で複数ノードに処理を分散：

```bash
# Redisサーバー起動
redis-server

# マスターノード起動
.koubou/venv/bin/python .koubou/scripts/distributed/master_node.py \
    --node-id master-01 --queue-type redis

# ワーカーノード起動
.koubou/venv/bin/python .koubou/scripts/distributed/remote_worker_node.py \
    --node-id worker-01 --queue-type redis --capabilities "general code"

# タスククライアント
.koubou/venv/bin/python .koubou/scripts/distributed/task_client.py
```

### 2. WebSocketリアルタイム通信

```javascript
// WebSocket接続
const ws = new WebSocket('ws://localhost:8766');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Task update:', data);
};

// タスク送信
ws.send(JSON.stringify({
    type: 'submit_task',
    payload: {
        type: 'code',
        prompt: 'Generate unit tests'
    }
}));
```

### 3. GraphQL API

```graphql
# GraphQL Playground: http://localhost:8767/graphql

query {
  systemStatus {
    activeWorkers
    pendingTasks
    completedTasks
  }
  
  task(id: "task-123") {
    id
    status
    result
  }
}

mutation {
  submitTask(
    type: "code"
    prompt: "Create a REST API"
    priority: 9
  ) {
    taskId
    status
  }
}
```

### 4. Webダッシュボード

ブラウザで `http://localhost:8765/dashboard` を開くと：

- リアルタイムタスク状況
- ワーカー稼働状態
- システムメトリクス
- タスク履歴

## トラブルシューティング

### よくある問題と解決方法

| 問題 | 原因 | 解決方法 |
|------|------|----------|
| ワーカーが起動しない | Ollamaが未起動 | `ollama serve` を実行 |
| タスクがタイムアウト | LLMモデル未ダウンロード | `ollama pull gemma2:2b` |
| Redis接続エラー | Redisサーバー未起動 | `redis-server` を実行 |
| メモリ不足 | ワーカー数過多 | `--max-workers 2` で制限 |
| Codex書き込みエラー | サンドボックス制限 | `export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1` |

### ログ確認

```bash
# システムログ
tail -f .koubou/logs/mcp_server.log

# ワーカーログ
tail -f .koubou/logs/worker_pool.log

# 個別ワーカーログ
tail -f .koubou/logs/workers/worker_*.log
```

### デバッグモード

```bash
# 詳細ログ出力
export LOG_LEVEL=DEBUG
.koubou/start_system.sh
```

## 開発者向け情報

### プロジェクト構造

```
koubou-system/
├── .koubou/                    # システムホーム
│   ├── scripts/               # 実行スクリプト
│   │   ├── mcp_server.py     # MCPサーバー
│   │   ├── workers/          # ワーカー関連
│   │   ├── distributed/      # 分散システム
│   │   └── common/           # 共通モジュール
│   ├── config/                # 設定ファイル
│   ├── db/koubou.db          # SQLiteデータベース
│   ├── logs/                  # ログファイル
│   └── venv/                  # Python仮想環境
│
├── docs/                       # ドキュメント
│   ├── architecture/         # アーキテクチャ設計
│   ├── api/                  # API仕様
│   └── guides/                # 使用ガイド
│
└── scripts/                    # セットアップスクリプト
    └── setup_poc_v2.sh        # v2.1.0セットアップ
```

### 拡張方法

#### 新しいワーカータイプの追加

```python
# .koubou/scripts/workers/custom_worker.py
from workers.base_worker import BaseWorker

class CustomWorker(BaseWorker):
    def process_task(self, task):
        # カスタム処理ロジック
        result = self.custom_llm_call(task['prompt'])
        return result
```

#### 新しいタスクタイプの追加

```python
# .koubou/scripts/mcp_server.py
@app.route('/task/custom', methods=['POST'])
def handle_custom_task():
    data = request.json
    task_id = create_task(
        type='custom',
        content=data['prompt'],
        priority=data.get('priority', 5)
    )
    return jsonify({'task_id': task_id})
```

### テスト実行

```bash
# ユニットテスト
.koubou/venv/bin/pytest tests/

# 負荷テスト
.koubou/venv/bin/python scripts/load_test.py

# 分散システムテスト
.koubou/venv/bin/python scripts/distributed/test_distributed.py
```

## パフォーマンス指標

- **同時処理数**: 最大8ワーカー（ローカル）、無制限（分散）
- **処理時間**: 
  - 一般タスク: 5-30秒
  - コード生成: 10-120秒
- **スループット**: 
  - ローカル: 約100タスク/時（8ワーカー）
  - 分散: 約1000タスク/時（10ノード）

## ライセンスと謝辞

- **ライセンス**: MIT
- **作者**: Koubou System Team
- **謝辞**:
  - Anthropic Claude
  - Ollama Team
  - OpenAI Codex

## サポート

- 📧 Email: support@koubou-system.example.com
- 🐛 Issues: [GitHub Issues](https://github.com/your-repo/koubou-system/issues)
- 💬 Discord: [Community Server](https://discord.gg/example)

---

*工房システム - AIエージェントの協調による次世代タスク処理* 🚀