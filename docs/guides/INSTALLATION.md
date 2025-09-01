# インストールガイド

## 前提条件

### 必須要件
- **OS**: Linux (Ubuntu 20.04+推奨) / macOS / WSL2
- **Python**: 3.9以上
- **メモリ**: 最小4GB、推奨8GB以上
- **ディスク**: 10GB以上の空き容量

### 必須ソフトウェア
```bash
# 確認コマンド
python3 --version  # Python 3.9+
sqlite3 --version  # SQLite 3.x
npm --version      # Node.js/npm (Codex CLI用)
```

## インストール手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/koubou-system.git
cd koubou-system
```

### 2. uvのインストール

```bash
# uvがない場合
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
```

### 3. Ollamaのインストール

```bash
# Linux/WSL
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# 起動
ollama serve
```

### 4. モデルのダウンロード

```bash
# gpt-oss:20bモデルをダウンロード（約13GB）
ollama pull gpt-oss:20b

# 確認
ollama list
```

### 5. Codex CLIのインストール

```bash
# npm経由でインストール
npm install -g @openai/codex

# 確認
codex --version
```

### 6. 工房システムのセットアップ

```bash
# POC版セットアップスクリプトを実行
chmod +x scripts/setup_poc.sh
./scripts/setup_poc.sh
```

セットアップスクリプトが以下を実行：
- `.koubou/`ディレクトリ構造の作成
- Python仮想環境の作成（uv使用）
- 必要なPythonパッケージのインストール
- SQLiteデータベースの初期化
- 設定ファイルの生成

## 設定

### 1. LMStudio設定（Ollamaの代替）

`.koubou/config/agent.yaml`を編集：
```yaml
workers:
  local:
    endpoint: "http://192.168.11.29:1234/v1"  # LMStudioのエンドポイント
    model: "gpt-oss-20b@f16"                  # モデル識別子
```

### 2. 環境変数

`.koubou/config/.env`を編集：
```bash
KOUBOU_HOME=/path/to/koubou-system/.koubou
LMSTUDIO_ENDPOINT=http://localhost:1234/v1
OLLAMA_NUM_GPU=999  # GPU最大使用
```

### 3. Codex CLI設定

`.koubou/config/codex.toml`：
```toml
model = "gpt-oss:20b"
sandbox_mode = "workspace-write"
approval_policy = "never"
```

## 動作確認

### 1. 基本テスト

```bash
# MCPサーバーテスト
source .koubou/venv/bin/activate
python .koubou/scripts/test_integration.py
```

### 2. Codex CLIテスト

```bash
# Ollamaとの接続確認
.koubou/scripts/test-codex.sh

# 簡単なタスク実行
.koubou/scripts/codex-ollama.sh exec "Write a hello world in Python"
```

### 3. システム全体テスト

```bash
# システム起動
.koubou/start_system.sh

# 別ターミナルで負荷テスト
python .koubou/scripts/load_test.py

# システム停止
.koubou/stop_system.sh
```

## トラブルシューティング

### Ollamaが起動しない
```bash
# サービスの状態確認
systemctl status ollama

# 手動起動
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Codex CLIが書き込めない
```bash
# 環境変数を設定
export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1

# 危険モードで実行
codex --dangerously-bypass-approvals-and-sandbox
```

### データベースエラー
```bash
# データベース修復
sqlite3 .koubou/db/koubou.db "VACUUM;"
sqlite3 .koubou/db/koubou.db "REINDEX;"

# 初期化し直す
rm .koubou/db/koubou.db
sqlite3 .koubou/db/koubou.db < scripts/init_database.sql
```

### メモリ不足
```bash
# ワーカー数を制限
python .koubou/scripts/workers/worker_pool_manager.py --max 2

# 軽量モデルに変更
ollama pull gemma2:2b
# agent.yamlでモデルを変更
```

## アンインストール

### 完全削除
```bash
# 工房システムの削除
./cleanup.sh

# Ollamaモデルの削除
ollama rm gpt-oss:20b

# Codex CLIの削除
npm uninstall -g @openai/codex
```

### 部分削除
```bash
# データのみ削除（設定は保持）
rm -rf .koubou/db/* .koubou/logs/* .koubou/tasks/*

# ログのみ削除
rm -rf .koubou/logs/*
```

## 次のステップ

- [使用ガイド](./USAGE.md) - 基本的な使い方を学ぶ
- [API仕様](../api/MCP_SERVER_API.md) - APIの詳細を確認
- [システム管理](../operations/SYSTEM_MANAGEMENT.md) - 運用方法を学ぶ

---
最終更新: 2025-08-29
バージョン: 1.0.0