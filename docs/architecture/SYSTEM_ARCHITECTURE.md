# 工房システム アーキテクチャドキュメント

## システム概要

工房システムは、Claude Code（メインエージェント）から複雑なタスクをローカルLLM（Ollama/Codex CLI）に委譲し、効率的に処理するための分散タスク処理システムです。

## 主要コンセプト

### 1. タスク委譲パターン
```
高コストタスク → ローカルLLM
単純な判断 → Claude Code
コード生成 → Codex CLI → Ollama
一般的な質問 → Ollama直接
```

### 2. 非同期処理
- バックグラウンドでの並列処理
- 複数ワーカーによる同時実行
- タスクキューによる負荷分散

### 3. 動的スケーリング
- 負荷に応じたワーカー数の自動調整
- リソースの効率的な利用
- 自動障害復旧

## システム構成図

```
┌─────────────────────────────────────────────────────┐
│                   User Interface                     │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                  Claude Code                         │
│            (Primary AI Assistant)                    │
│  ┌────────────────────────────────────────────┐    │
│  │ MCP Client (Model Context Protocol)         │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP/JSON
┌─────────────────────▼───────────────────────────────┐
│                  MCP Server                          │
│                 (Flask API)                          │
│  ┌──────────────────────────────────────────┐      │
│  │ • Task Router                             │      │
│  │ • Queue Manager                           │      │
│  │ • Result Aggregator                       │      │
│  └──────────────────────────────────────────┘      │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                SQLite Database                       │
│  ┌──────────────────────────────────────────┐      │
│  │ Tables:                                    │      │
│  │ • task_master (タスク管理)                  │      │
│  │ • workers (ワーカー状態)                   │      │
│  │ • agents (エージェント登録)                │      │
│  │ • system_logs (ログ)                      │      │
│  │ • agent_communications (通信記録)          │      │
│  └──────────────────────────────────────────┘      │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│            Worker Pool Manager                       │
│         (Dynamic Scaling Controller)                 │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│   Worker #1   │           │   Worker #N   │
│               │    ...    │               │
└───────┬───────┘           └───────┬───────┘
        │                           │
        ▼                           ▼
┌───────────────────────────────────────────┐
│           Local LLM Layer                  │
│  ┌─────────────┐    ┌──────────────┐     │
│  │   Ollama    │    │  Codex CLI   │     │
│  │ (gpt-oss:20b)│    │  (via Ollama) │     │
│  └─────────────┘    └──────────────┘     │
└───────────────────────────────────────────┘
```

## ディレクトリ構造

```
koubou-system/
├── .koubou/                    # システムホームディレクトリ
│   ├── config/                 # 設定ファイル
│   │   ├── agent.yaml         # エージェント設定
│   │   ├── codex.toml         # Codex CLI設定
│   │   └── .env               # 環境変数
│   ├── db/                    # データベース
│   │   └── koubou.db         # SQLiteデータベース
│   ├── logs/                  # ログファイル
│   │   ├── agents/           # エージェントログ
│   │   ├── workers/          # ワーカーログ
│   │   └── system/           # システムログ
│   ├── scripts/              # 実行スクリプト
│   │   ├── mcp_server.py     # MCPサーバー
│   │   ├── workers/          # ワーカースクリプト
│   │   │   ├── local_worker.py
│   │   │   └── worker_pool_manager.py
│   │   ├── codex-*.sh        # Codexラッパー
│   │   └── test_*.py         # テストスクリプト
│   ├── tasks/                # タスクファイル
│   │   ├── pending/          # 保留中
│   │   ├── in_progress/      # 処理中
│   │   ├── completed/        # 完了
│   │   └── failed/          # 失敗
│   └── venv/                 # Python仮想環境
├── scripts/                   # セットアップスクリプト
│   ├── setup_poc.sh          # POCセットアップ
│   └── init_database.sql     # DB初期化SQL
├── DYNAMIC_SCALING.md        # スケーリングドキュメント
├── SYSTEM_ARCHITECTURE.md    # このファイル
└── README.md                 # プロジェクト概要
```

## API仕様

### MCP Server API

#### POST /task/delegate
タスクを委譲する

**リクエスト:**
```json
{
  "type": "code|general",
  "prompt": "タスクの説明",
  "priority": 1-10,
  "sync": true|false,
  "files": ["file1.py", "file2.py"],
  "options": {
    "timeout": 120,
    "model": "gpt-oss:20b"
  }
}
```

**レスポンス:**
```json
{
  "task_id": "task_20250829_123456",
  "status": "delegated|completed",
  "result": {
    "success": true,
    "output": "処理結果",
    "error": null
  }
}
```

#### GET /task/{task_id}/status
タスクの状態を取得

**レスポンス:**
```json
{
  "task_id": "task_20250829_123456",
  "status": "pending|in_progress|completed|failed",
  "result": {...},
  "created_at": "2025-08-29T12:34:56",
  "updated_at": "2025-08-29T12:35:00"
}
```

## データベーススキーマ

### task_master テーブル
| カラム | 型 | 説明 |
|-------|-----|------|
| task_id | TEXT | タスクID（主キー） |
| task_type | TEXT | タスクタイプ（code/general） |
| status | TEXT | ステータス |
| priority | INTEGER | 優先度（1-10） |
| content | JSON | タスク内容 |
| result | JSON | 実行結果 |
| assigned_worker_type | TEXT | 割り当てワーカー |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

### workers テーブル
| カラム | 型 | 説明 |
|-------|-----|------|
| worker_id | TEXT | ワーカーID（主キー） |
| worker_type | TEXT | ワーカータイプ |
| model_name | TEXT | 使用モデル |
| status | TEXT | 状態（idle/busy/offline） |
| tasks_completed | INTEGER | 完了タスク数 |
| tasks_failed | INTEGER | 失敗タスク数 |
| last_heartbeat | TIMESTAMP | 最終生存確認 |

## 環境変数

```bash
# 必須
KOUBOU_HOME=/path/to/.koubou
OPENAI_API_BASE=http://192.168.11.29:1234/v1

# オプション
WORKER_ID=worker_001
OLLAMA_NUM_GPU=999
OLLAMA_GPU_LAYERS=999
CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
```

## セキュリティ考慮事項

1. **サンドボックス実行**
   - Codex CLIは`danger-full-access`モードで動作
   - 本番環境では適切な権限制限を推奨

2. **ネットワーク分離**
   - 現在はローカルネットワークのみ
   - 本番環境では適切なファイアウォール設定

3. **認証・認可**
   - 現在は認証なし
   - 本番環境ではAPI認証の実装を推奨

4. **データ保護**
   - SQLiteは単一ファイル
   - 定期的なバックアップを推奨

## パフォーマンス指標

### 処理能力
- 同時処理可能タスク数: max_workers設定に依存（デフォルト5）
- タスク処理時間: 
  - 一般タスク: 5-30秒
  - コードタスク: 10-120秒

### リソース使用量
- メモリ: 各ワーカー約2-4GB（モデルサイズに依存）
- CPU: 各ワーカー1-2コア
- GPU: モデルロード時に使用（共有可能）

## 運用ガイド

### 日常運用

```bash
# システム起動
.koubou/start_system.sh

# ステータス確認
curl http://localhost:8765/health

# ログ監視
tail -f .koubou/logs/worker_pool.log

# システム停止
.koubou/stop_system.sh
```

### バックアップ

```bash
# データベースバックアップ
sqlite3 .koubou/db/koubou.db ".backup backup.db"

# 設定ファイルバックアップ
tar -czf koubou_config_backup.tar.gz .koubou/config/
```

### 障害対応

```bash
# ワーカー再起動
pkill -f local_worker.py
python .koubou/scripts/workers/worker_pool_manager.py

# データベース修復
sqlite3 .koubou/db/koubou.db "VACUUM;"
sqlite3 .koubou/db/koubou.db "REINDEX;"

# ログクリーンアップ
find .koubou/logs -name "*.log" -mtime +7 -delete
```

## 制限事項と今後の計画

### 現在の制限
- SQLiteによる同時書き込み制限
- ローカルネットワークのみ対応
- 単一ノード実行

### 今後の拡張計画
- PostgreSQL/MySQL対応
- 分散ワーカー対応
- Kubernetes対応
- Web管理画面
- メトリクスダッシュボード（Grafana）
- メッセージキュー（Redis/RabbitMQ）統合

## ライセンスと貢献

このプロジェクトはPOC（Proof of Concept）として開発されています。
本番環境での使用前に、適切なセキュリティレビューとテストを実施してください。

---
最終更新: 2025-08-29
バージョン: 1.0.0