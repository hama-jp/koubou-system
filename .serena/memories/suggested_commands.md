# 工房システム - 推奨コマンド

## 基本的な開発コマンド

### システム起動・停止
```bash
# システム起動
.koubou/start_system.sh

# システム停止  
.koubou/stop_system.sh
```

### テスト実行
```bash
# 統合テスト
python .koubou/scripts/test_integration.py

# 負荷テスト
python .koubou/scripts/load_test.py

# GraphQLテスト
python .koubou/scripts/test_graphql.py

# WebSocketテスト
python .koubou/scripts/test_websocket.py

# 分散システムテスト
python .koubou/scripts/distributed/test_distributed.py

# pytest実行 (tests/ディレクトリ)
pytest tests/
```

### パッケージ管理
```bash
# 依存関係インストール
uv pip install -e .

# 開発用ツールインストール
uv pip install -e ".[dev]"

# 新しいパッケージ追加
uv pip install <package_name>
```

### 開発ツール
```bash
# コードフォーマット
black .

# リント実行
flake8 .

# 型チェック
mypy .
```

## システム監視・デバッグ

### ヘルスチェック
```bash
curl http://localhost:8765/health
```

### ログ確認
```bash
# リアルタイムログ監視
tail -f .koubou/logs/*.log

# 特定ログファイル
tail -f .koubou/logs/mcp_server.log
tail -f .koubou/logs/worker_pool.log
```

### データベース確認
```bash
# SQLite直接アクセス
sqlite3 .koubou/db/koubou.db "SELECT * FROM task_master LIMIT 10;"
sqlite3 .koubou/db/koubou.db "SELECT * FROM workers;"
```

## タスク実行

### Codex CLI直接実行
```bash
# 対話モード
.koubou/scripts/codex-ollama.sh

# タスク実行
.koubou/scripts/codex-exec.sh "コード生成タスクの内容"
```

### API経由でタスク送信
```bash
# 一般タスク
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{"type": "general", "prompt": "What is 2+2?", "sync": true}'

# コードタスク
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{"type": "code", "prompt": "Write a Python function", "sync": true}'
```

## 分散システム管理

### Redis使用時
```bash
# Redis起動確認
redis-cli ping

# 分散テスト
python .koubou/scripts/distributed/test_redis.py
```

### リモートノード展開
```bash
# ノード展開スクリプト実行
.koubou/scripts/distributed/deploy_node.sh <remote_host>
```

## ユーティリティコマンド

### システム情報
```bash
# システム統計
curl http://localhost:8765/tasks | jq .

# ワーカー状態
curl http://localhost:8765/health | jq .workers
```

### クリーンアップ
```bash
# 完全クリーンアップ
./cleanup.sh
```