# 動的ワーカースケーリングシステム

## 概要

工房システムの動的ワーカースケーリングシステムは、タスクの負荷に応じて自動的にワーカー（職人エージェント）の数を調整する仕組みです。タスクが増えると新しいワーカーを起動し、タスクが減ると不要なワーカーを停止することで、効率的なリソース利用を実現します。

## アーキテクチャ

```
┌─────────────────┐
│  Claude Code    │
│ (メインエージェント) │
└────────┬────────┘
         │ タスク委譲
         ▼
┌─────────────────┐
│   MCP Server    │
│   (Flask API)   │
└────────┬────────┘
         │ タスク登録
         ▼
┌─────────────────┐      ┌──────────────┐
│   Task Queue    │◀────▶│   Database   │
│   (SQLite)      │      │   (SQLite)   │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────────────────────┐
│    Worker Pool Manager          │
│  (動的スケーリングコントローラー)    │
└────────┬────────────────────────┘
         │ 管理・監視
         ▼
┌──────────────────────────────────────┐
│          Worker Pool                 │
│  ┌──────────┐  ┌──────────┐        │
│  │ Worker 1 │  │ Worker 2 │  ...   │
│  └──────────┘  └──────────┘        │
│       ▼              ▼              │
│  [ Ollama / Codex CLI ]             │
└──────────────────────────────────────┘
```

## コンポーネント詳細

### 1. Worker Pool Manager (`worker_pool_manager.py`)

**主要機能:**
- ワーカーのライフサイクル管理（起動・停止・監視）
- 負荷に基づく自動スケーリング
- ヘルスチェックとクラッシュリカバリ
- 統計情報の収集と表示

**設定パラメータ:**
```python
min_workers = 1    # 最小ワーカー数
max_workers = 5    # 最大ワーカー数
scale_up_threshold = 2    # ワーカー追加の閾値（pending_tasks / active_workers）
idle_timeout = 30  # アイドルタイムアウト（秒）
```

### 2. Local Worker (`local_worker.py`)

**機能:**
- タスクキューからタスクを取得
- タスクタイプに応じた処理の振り分け
  - `code`: Codex CLI経由で処理
  - `general`: Ollama直接処理
- 結果のデータベース更新
- ハートビート送信

**環境変数:**
```bash
WORKER_ID=worker_20250829_123456  # ワーカー識別子
KOUBOU_HOME=/path/to/.koubou      # 工房ホームディレクトリ
```

### 3. MCP Server (`mcp_server.py`)

**エンドポイント:**

| エンドポイント | メソッド | 説明 |
|--------------|---------|------|
| `/health` | GET | ヘルスチェック |
| `/task/delegate` | POST | タスク委譲 |
| `/task/<id>/status` | GET | タスク状態取得 |
| `/tasks` | GET | タスク一覧取得 |

**タスク委譲リクエスト例:**
```json
{
  "type": "code",
  "prompt": "Create a Python function...",
  "priority": 8,
  "sync": false
}
```

## スケーリングアルゴリズム

### スケールアップ条件
```python
if pending_tasks > active_workers * 2 and active_workers < max_workers:
    # 新しいワーカーを起動
    spawn_worker()
```

### スケールダウン条件
```python
if pending_tasks == 0 and active_workers > min_workers:
    # アイドルワーカーを停止
    shutdown_idle_workers()
```

### ワーカー選択戦略
1. **タスク取得**: 優先度が高く、作成時刻が古いタスクから処理
2. **ワーカー割り当て**: アイドル状態のワーカーを優先的に使用
3. **負荷分散**: 各ワーカーが独立してタスクを取得（プル型）

## 使用方法

### システム起動

```bash
# 全コンポーネントを起動
.koubou/start_system.sh

# カスタム設定で起動
python .koubou/scripts/workers/worker_pool_manager.py --min 2 --max 10
```

### 負荷テスト

```bash
# インタラクティブ負荷テスト
python .koubou/scripts/load_test.py

# プログラマティック使用
import requests

# タスク送信
response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'code',
    'prompt': 'Write a function...',
    'priority': 8,
    'sync': False
})

task_id = response.json()['task_id']

# ステータス確認
status = requests.get(f'http://localhost:8765/task/{task_id}/status')
print(status.json())
```

### システム停止

```bash
# 安全な停止
.koubou/stop_system.sh

# 緊急停止
pkill -f "worker_pool_manager"
pkill -f "local_worker"
```

## モニタリング

### ログファイル
```
.koubou/logs/
├── mcp_server.log      # MCPサーバーログ
├── worker_pool.log     # プールマネージャーログ
├── ollama.log          # Ollamaサーバーログ
└── workers/
    ├── worker_001.log  # 個別ワーカーログ
    └── worker_002.log
```

### データベース統計
```sql
-- アクティブワーカー確認
SELECT worker_id, status, tasks_completed, tasks_failed 
FROM workers 
WHERE last_heartbeat > datetime('now', '-1 minute');

-- タスク統計
SELECT status, COUNT(*) as count 
FROM task_master 
GROUP BY status;

-- 平均処理時間
SELECT AVG(julianday(updated_at) - julianday(created_at)) * 24 * 60 as avg_minutes
FROM task_master 
WHERE status = 'completed';
```

### リアルタイム統計

Worker Pool Managerは30秒ごとに統計を表示:

```
==================================================
Worker Pool Statistics
==================================================

Active Workers:
  • worker_001: busy | Tasks: 5 completed, 0 failed (100.0% success)
  • worker_002: idle | Tasks: 3 completed, 1 failed (75.0% success)
  • worker_003: busy | Tasks: 2 completed, 0 failed (100.0% success)

Task Statistics:
  • pending: 8 tasks
  • in_progress: 3 tasks
  • completed: 45 tasks
  • failed: 2 tasks
==================================================
```

## パフォーマンス最適化

### 推奨設定

| タスク特性 | min_workers | max_workers | 備考 |
|-----------|------------|-------------|------|
| 軽量・高頻度 | 2 | 8 | レスポンス重視 |
| 重量・低頻度 | 1 | 3 | リソース効率重視 |
| バースト型 | 1 | 10 | 急激な負荷変動対応 |
| 定常負荷 | 3 | 5 | 安定性重視 |

### チューニングポイント

1. **Ollamaメモリ使用量**
   - 各ワーカーが独立してOllamaを使用
   - GPUメモリに注意（モデルサイズ × ワーカー数）

2. **データベース接続**
   - SQLiteは同時書き込みに制限あり
   - 必要に応じてPostgreSQL等への移行を検討

3. **タスクタイムアウト**
   - コードタスク: 120秒
   - 一般タスク: 60秒
   - 長時間タスクは分割を推奨

## トラブルシューティング

### ワーカーが起動しない
```bash
# Ollamaサーバー確認
curl http://localhost:11434/api/tags

# データベース確認
sqlite3 .koubou/db/koubou.db "SELECT * FROM workers;"

# ログ確認
tail -f .koubou/logs/worker_pool.log
```

### タスクが処理されない
```bash
# タスクキュー確認
sqlite3 .koubou/db/koubou.db "SELECT * FROM task_master WHERE status='pending';"

# ワーカー状態確認
curl http://localhost:8765/tasks
```

### メモリ不足
```bash
# ワーカー数を制限
python .koubou/scripts/workers/worker_pool_manager.py --max 3

# モデルを軽量版に変更
# local_worker.py内のself.modelを変更
```

## 今後の拡張計画

1. **優先度ベースのキューイング**
   - 現在: FIFOベース
   - 計画: 優先度キューの実装

2. **分散ワーカー対応**
   - 現在: ローカルのみ
   - 計画: リモートワーカーのサポート

3. **WebSocketによるリアルタイム通知**
   - 現在: ポーリング
   - 計画: プッシュ通知

4. **メトリクス収集**
   - Prometheus/Grafana統合
   - 詳細なパフォーマンス分析

5. **障害復旧の強化**
   - タスクの再試行メカニズム
   - ワーカーの自動復旧

## まとめ

動的ワーカースケーリングシステムにより、工房システムは負荷に応じて自動的にリソースを調整し、効率的にタスクを処理できます。最小限のリソースで開始し、必要に応じてスケールアップすることで、コスト効率とパフォーマンスのバランスを保ちます。