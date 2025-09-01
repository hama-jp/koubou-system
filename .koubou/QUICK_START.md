# 🏭 工房システム クイックスタートガイド

## 🚀 システム起動

### 推奨：バックグラウンド起動（タイムアウトなし）
```bash
# クイック起動（推奨）
.koubou/start_system_quick.sh

# または直接バックグラウンドフラグを使用
.koubou/start_system.sh --background
```

### フォアグラウンド起動（Ctrl+Cで停止可能）
```bash
.koubou/start_system.sh
```

## 🛑 システム停止
```bash
.koubou/stop_system.sh
```

## 📊 システム構成

### 起動されるサービス
1. **MCP Server** (Port 8765) - タスク管理API
2. **Enhanced Pool Manager** - 複数ワーカー管理
   - local_001: ローカルワーカー
   - remote_lan_001: リモートワーカー (192.168.11.6)
3. **WebSocket Server** (Port 8766) - リアルタイム通信
4. **GraphQL API** (Port 8767) - クエリインターフェース
5. **Web Dashboard** (Port 8080) - 監視ダッシュボード
6. **Worker Log API** (Port 8768) - ログ配信API

### アクセスURL
- **ダッシュボード**: http://localhost:8080
- **MCP API**: http://localhost:8765
- **Worker Logs API**: http://localhost:8768/api/workers/status

## 🔧 設定ファイル

### ワーカー設定 (.koubou/config/workers.yaml)
```yaml
local_workers:
  - worker_id: "local_001"
    model: "gpt-oss:20b"
    max_tokens: 32768
    performance_factor: 1.0

remote_workers:
  - worker_id: "remote_lan_001" 
    remote_host: "192.168.11.6"
    remote_port: 11434
    model: "gpt-oss:20b"
    max_tokens: 16384
    performance_factor: 0.5
```

## 🔍 システム確認

### ワーカー状態確認
```bash
curl http://localhost:8768/api/workers/status | jq
```

### タスクキュー確認
```bash
curl http://localhost:8768/api/tasks/queue | jq
```

### ヘルスチェック
```bash
curl http://localhost:8765/health
```

## 🎯 タスク投入例

### 同期実行
```bash
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello World!","sync":true}'
```

### 非同期実行（高優先度）
```bash
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Important task","sync":false,"priority":9}'
```

## 📝 改善履歴

### 2025-09-02 実装内容
1. **バックグラウンド起動オプション追加**
   - `--background`フラグでタイムアウトなし起動
   - Worker Log APIも自動起動

2. **Enhanced Pool Manager統合**
   - workers.yaml設定に基づく複数ワーカー管理
   - ローカル/リモートワーカーの統合管理

3. **セキュリティ強化**
   - ワーカー直接起動のバックドア削除
   - WORKER_AUTH_TOKEN必須化

4. **ダッシュボード改善**
   - リアルタイムワーカー状態表示
   - タスクキュー表示
   - ログストリーミング（最大100行）

## ⚠️ 注意事項

- リモートワーカーはgemini-repo-cli経由でのみアクセス
- 直接のOllama API呼び出しは禁止
- max_tokens: ローカル32k、リモート16k推奨
- ワーカーはPool Manager経由でのみ起動可能