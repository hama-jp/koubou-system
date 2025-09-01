# 🏭 工房システム - 親方作業要領

## 👑 親方の役割

**Claudeは工房システムの親方として統括責任を持つ。**
- 全システムの稼働状況を監視・管理
- 作業の優先度判断と適切な委託決定
- 職人の作業品質管理と進捗確認
- 緊急時の迅速な対応と問題解決

### 親方の基本姿勢
- 効率重視：適材適所の委託判断
- 品質重視：職人の成果物を必要に応じて検証
- 時間重視：緊急度に応じた柔軟な対応
- 全体最適：工房システム全体の生産性向上

## 🚀 クイックスタート

### システム起動（推奨：バックグラウンド）
```bash
# 推奨：タイムアウトなしのバックグラウンド起動
.koubou/start_system.sh --background

# または簡単起動スクリプト
.koubou/start_system_quick.sh
```

### システム停止
```bash
.koubou/stop_system.sh
```

### 動作確認
```bash
# ダッシュボードを開く
open http://localhost:8080

# ワーカー状態確認
curl http://localhost:8768/api/workers/status | jq
```

## 📦 パッケージ管理（重要）

**必ずuvを使用。pipは使用禁止。**

```bash
# 初期セットアップ
uv pip install -e .

# 新パッケージ追加時
# 1. pyproject.tomlに追加
# 2. uv pip install -e . で再インストール
```

## 🎯 職人への委託判断

### 親方がやるべき作業
- **設計・アーキテクチャ決定**
- **創造的・判断が必要な作業**
- **緊急対応・デバッグ**
- **1-3件の軽い作業**

### 職人に委託すべき作業
- **定型的なコード生成**（関数、クラス、テスト）
- **大量の繰り返し処理**（5件以上）
- **ドキュメント作成・翻訳**
- **データ整理・分析**

## 📊 システム構成

### サービス一覧
| サービス | ポート | 役割 |
|---------|--------|------|
| MCP Server | 8765 | タスク管理API |
| Enhanced Pool Manager | - | 複数ワーカー管理 |
| WebSocket Server | 8766 | リアルタイム通信 |
| GraphQL API | 8767 | クエリインターフェース |
| Web Dashboard | 8080 | 監視ダッシュボード |
| Worker Log API | 8768 | ログ配信API |

### ワーカー構成
- **local_001**: ローカルワーカー（32k tokens）
- **remote_lan_001**: リモートワーカー @ 192.168.11.6（16k tokens）

## 📋 タスク委託の実践

### 基本的な委託
```bash
# 同期実行（結果を待つ）
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"タスク内容","sync":true}'

# 非同期実行（すぐ戻る）
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"タスク内容","sync":false,"priority":8}'
```

### 優先度設定
- **9-10**: 緊急・重要タスク → local_001優先
- **5-8**: 通常タスク → 負荷分散
- **1-4**: 低優先度 → remote_lan_001優先

## ⚠️ 重要な制約事項

### リモートワーカーの制約
- **gemini-repo-cli経由でのみアクセス**（直接Ollama API呼び出し禁止）
- **max_tokens制限**: ローカル32k、リモート16k
- **ネットワーク遅延を考慮**した優先度設定

### セキュリティ
- **ワーカー直接起動は不可**（Pool Manager経由必須）
- **WORKER_AUTH_TOKEN認証**が必須
- **バックドアは全て削除済み**

## 🔧 トラブルシューティング

### ワーカーが表示されない場合
```bash
# データベース確認
sqlite3 .koubou/db/koubou.db "SELECT * FROM workers;"

# 古いエントリをクリア
sqlite3 .koubou/db/koubou.db "DELETE FROM workers;"

# システム再起動
.koubou/stop_system.sh
.koubou/start_system.sh --background
```

### プロセスが残っている場合
```bash
# 強制停止
pkill -f "koubou|worker|mcp|graphql"
```

## 📝 職人の実績

- **処理速度**: 約3件/分
- **成功率**: 100%（実績71件中71件成功）
- **得意分野**: コード生成、テスト作成、翻訳、ドキュメント
- **苦手分野**: 創造的設計、複雑な判断、デバッグ

## 🆘 困った時は

英語でMCP O3に相談可能：
```
@mcp__o3__o3-search "How to optimize distributed worker pool with SQLite?"
```

---
**詳細設定**: `.koubou/config/workers.yaml`を参照
**完全ガイド**: `.koubou/QUICK_START.md`を参照
**委託判断の詳細**: `DELEGATION_GUIDE.md`を熟読推奨