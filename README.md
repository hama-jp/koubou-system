# 🏭 Koubou System

> **Distributed AI Task Processing System** - A scalable framework for delegating complex tasks from Claude Code to local LLM workers

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](#)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/AI-Claude%20Code-orange.svg)](https://claude.ai/code)

<p align="center">
  <a href="./docs/">📚 Documentation</a> •
  <a href="./docs/guides/QUICKSTART.md">🚀 Quick Start</a> •
  <a href="./docs/api/MCP_SERVER_API.md">🔌 API</a> •
  <a href="./docs/guides/INSTALLATION.md">📦 Installation</a> •
  <a href="./system_configuration_report.md">🏗️ System Report</a> •
  <a href="./ATTRIBUTION.md">🙏 Credits</a>
</p>

## 📖 Overview

Koubou System is a distributed task processing framework that enables Claude Code to delegate complex tasks to local LLM workers (LMStudio/Gemini CLI) with dynamic scaling and real-time monitoring.

### 主な特徴

- 🎯 **動的ワーカースケーリング** - タスク量に応じて自動的にワーカー数を調整
- 🤖 **複数LLM統合** - LMStudio（gpt-oss-20b@f16）とGemini CLIの統合
- 🔄 **非同期処理** - バックグラウンドでの並列タスク処理
- 📊 **リアルタイム監視** - タスクとワーカーの状態を常時把握
- 🔒 **ローカル処理** - 機密データをクラウドに送信せず安全に処理

## 🏗️ システムアーキテクチャ

詳細なアーキテクチャ図とシステム構成については、[**📊 システム構成レポート**](./system_configuration_report.md) をご覧ください。

```
┌─────────────────┐
│  Claude Code    │ ← ユーザーインタラクション
└────────┬────────┘
         │ MCP API
┌────────▼────────┐
│   MCP Server    │ ← タスクルーティング
│   (Flask API)   │
└────────┬────────┘
         │
┌────────▼────────┐
│   Task Queue    │ ← SQLiteデータベース
└────────┬────────┘
         │
┌────────▼─────────────────────┐
│   Worker Pool Manager         │ ← 動的スケーリング
│  (min: 1, max: 8 workers)    │
└────────┬─────────────────────┘
         │
    ┌────▼────┐  ┌─────────┐
    │Worker #1│  │Worker #N│  ← 並列処理
    └────┬────┘  └────┬────┘
         │            │
    ┌────▼────────────▼────┐
    │   LMStudio / Gemini CLI │ ← ローカルLLM
    │    (gpt-oss-20b@f16)   │
    └───────────────────────┘
```

## 🚀 クイックスタート

### 必要条件

- **OS**: Linux/macOS/WSL2
- **Python**: 3.9+
- **メモリ**: 8GB以上推奨
- **その他**: SQLite3, npm, LMStudio, Gemini CLI

### 30秒セットアップ

```bash
# 1. クローン
git clone https://github.com/[your-username]/koubou-system.git
cd koubou-system

# 2. 依存関係インストール
uv pip install -e .

# 3. システム起動
.koubou/start_system.sh --background
```

詳細は [インストールガイド](./docs/guides/INSTALLATION.md) を参照。

## 💻 使用例

### Python API

```python
import requests

# タスク送信（コード生成）
response = requests.post('http://localhost:8765/task/delegate', json={
    'type': 'code',
    'prompt': 'Create a REST API with Flask',
    'priority': 8,
    'sync': False  # 非同期処理
})

task_id = response.json()['task_id']

# ステータス確認
status = requests.get(f'http://localhost:8765/task/{task_id}/status')
print(status.json())
```

### Gemini CLI（直接実行）

```bash
# タスク実行
.koubou/scripts/gemini-exec.sh "Add unit tests to calculator.py"
```

### 負荷テスト

```bash
# 複数タスクを投入してスケーリングを確認
python .koubou/scripts/load_test.py
```

## 📁 プロジェクト構造

```
koubou-system/
├── 📁 .koubou/                    # システムホーム（セットアップで生成）
│   ├── config/                    # 設定ファイル
│   ├── db/koubou.db              # SQLiteデータベース
│   ├── logs/                      # ログファイル
│   ├── scripts/                   # 実行スクリプト
│   │   ├── mcp_server.py         # MCPサーバー
│   │   ├── workers/              # ワーカー関連
│   │   │   ├── local_worker.py
│   │   │   └── worker_pool_manager.py
│   │   └── gemini-exec.sh        # Geminiラッパー
│   └── venv/                     # Python仮想環境
│
├── 📁 docs/                       # ドキュメント
│   ├── README.md                 # ドキュメントインデックス
│   ├── architecture/             # アーキテクチャ文書
│   ├── guides/                   # 使用ガイド
│   ├── api/                      # API仕様
│   └── operations/               # 運用ガイド
│
└── 📁 scripts/                    # セットアップスクリプト
    ├── setup_poc.sh              # POCセットアップ
    └── init_database.sql         # DB初期化
```

## 🎯 主要機能

### 動的ワーカースケーリング

```python
# タスクが増えると自動的にワーカーが増加
pending_tasks: 2  → Workers: 1
pending_tasks: 10 → Workers: 5 (自動スケールアップ)
pending_tasks: 0  → Workers: 1 (自動スケールダウン)
```

### タスクルーティング

- **コードタスク** → Gemini CLI → LMStudio
- **一般タスク** → Gemini CLI → LMStudio
- **優先度処理** → 高優先度タスクを優先実行

### モニタリング

```bash
# システム統計
curl http://localhost:8765/health

# ワーカー状態
sqlite3 .koubou/db/koubou.db "SELECT * FROM workers;"

# リアルタイムログ
tail -f .koubou/logs/worker_pool.log
```

## 📊 パフォーマンス

- **同時処理**: 最大8ワーカー
- **処理時間**: 
  - 一般タスク: 5-30秒
  - コードタスク: 10-120秒
- **スループット**: 約100タスク/時（8ワーカー時）

## 🛠️ トラブルシューティング

| 問題 | 解決方法 |
|------|----------|
| LMStudioが起動しない | LMStudio APIサーバーを手動起動 |
| ワーカーが増えない | `worker_pool_manager.py --max 10` で上限変更 |
| メモリ不足 | ワーカー数を制限 `--max 3` |
| Gemini CLI書き込み失敗 | セキュリティ設定を確認 |

詳細は [トラブルシューティング](./docs/operations/TROUBLESHOOTING.md) を参照。

## 🚦 開発ロードマップ

### ✅ 完了
- [x] 基本的なタスク委譲システム
- [x] 動的ワーカースケーリング
- [x] Gemini CLI統合
- [x] 負荷テストツール

### 🔄 進行中
- [ ] WebSocketリアルタイム通知
- [ ] Webダッシュボード
- [ ] メトリクス収集（Prometheus）

### 📋 計画中
- [ ] Kubernetes対応
- [ ] 分散ワーカー（リモートノード）
- [ ] メッセージキュー（Redis/RabbitMQ）
- [ ] GraphQL API

## 🤝 コントリビューション

プルリクエストを歓迎します！

1. フォーク
2. フィーチャーブランチ作成 (`git checkout -b feature/amazing`)
3. コミット (`git commit -m 'Add amazing feature'`)
4. プッシュ (`git push origin feature/amazing`)
5. プルリクエスト作成

## 📄 ライセンス

Apache License 2.0 - 詳細は [LICENSE](LICENSE) を参照。

## 🙏 謝辞

- [Anthropic Claude](https://www.anthropic.com/) - メインAIアシスタント
- [LMStudio](https://lmstudio.ai/) - ローカルLLM実行環境
- [gemini-repo-cli](https://github.com/deniskropp/gemini-repo-cli) - リモートワーカー実装に活用（MIT License）
- [Denis Kropp](https://github.com/deniskropp) - gemini-repo-cli開発者

## 📞 サポート

- 🐛 Issues: [GitHub Issues](https://github.com/[your-username]/koubou-system/issues)
- 📖 Documentation: [Wiki](https://github.com/[your-username]/koubou-system/wiki)
- 💡 Discussions: [GitHub Discussions](https://github.com/[your-username]/koubou-system/discussions)

---

**工房システム** - AIエージェントの協調による次世代タスク処理 🚀

*Made with ❤️ by the Koubou System Team*