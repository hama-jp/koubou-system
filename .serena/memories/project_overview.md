# 工房システム (Koubou System) - プロジェクト概要

## プロジェクトの目的
動的スケーリング対応AIタスク処理システム。Claude Codeと複数のローカルLLMワーカーが協働する分散処理フレームワーク。

## 技術スタック
- **Python 3.9+**: メイン言語
- **Flask**: MCPサーバー、GraphQL API
- **SQLite**: タスクデータベース
- **Ollama**: ローカルLLM (gpt-oss:20b)
- **Codex CLI**: コード生成タスク用
- **WebSocket**: リアルタイム通信
- **GraphQL (Ariadne)**: API層
- **uv**: パッケージ管理
- **pytest**: テストフレームワーク

## 主要コンポーネント
1. **MCP Server** (`.koubou/scripts/mcp_server.py`) - タスクルーティングの中核
2. **Worker Pool Manager** (`.koubou/scripts/workers/worker_pool_manager.py`) - 動的スケーリング
3. **Local Worker** (`.koubou/scripts/workers/local_worker.py`) - タスク実行ワーカー
4. **WebSocket Server** - リアルタイム通知
5. **GraphQL Server** - 高度なAPI
6. **Web Dashboard** - モニタリングUI

## システムアーキテクチャ
```
Claude Code → MCP Server (Flask) → Task Queue (SQLite) 
              ↓
    Worker Pool Manager (動的スケーリング)
              ↓
    Local Workers (1-8個) → Ollama/Codex CLI
```

## 動的スケーリング
- 最小ワーカー数: 1
- 最大ワーカー数: 8 (設定可能)
- スケールアップ閾値: pending_tasks > active_workers × 2
- スケールダウン閾値: pending_tasks < active_workers × 0.5

## 分散処理対応
- Redis Queue対応 (オプション)
- リモートワーカーノード対応
- 負荷分散とフェイルオーバー機能

## データベーススキーマ
- `task_master`: タスクマスターテーブル
- `workers`: ワーカー状態管理
- インデックス最適化済み