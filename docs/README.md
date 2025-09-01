# 工房システム ドキュメント

## 📚 ドキュメント構成

### 🏗️ [アーキテクチャ](./architecture/)
- [システムアーキテクチャ](./architecture/SYSTEM_ARCHITECTURE.md) - システム全体の設計と構成
- [動的スケーリング](./architecture/DYNAMIC_SCALING.md) - ワーカープールの自動スケーリング機能

### 📖 [ガイド](./guides/)
- [クイックスタート](./guides/QUICKSTART.md) - 5分で始める工房システム
- [インストールガイド](./guides/INSTALLATION.md) - 詳細なセットアップ手順
- [使用ガイド](./guides/USAGE.md) - 基本的な使い方

### 🔌 [API仕様](./api/)
- [MCP Server API](./api/MCP_SERVER_API.md) - タスク委譲API
- [Worker API](./api/WORKER_API.md) - ワーカー管理API

### ⚙️ [運用](./operations/)
- [システム管理](./operations/SYSTEM_MANAGEMENT.md) - 起動・停止・監視
- [トラブルシューティング](./operations/TROUBLESHOOTING.md) - 問題解決ガイド
- [パフォーマンスチューニング](./operations/PERFORMANCE.md) - 最適化のヒント

### 🔧 [開発](./development/)
- [要件定義](./development/01_requirements.md) - システム要件
- [設計書](./development/02_design_v2.md) - 詳細設計
- [実装ガイド](./development/03_implementation_guide_v2.md) - 開発者向けガイド

### 📊 [レポート](./reports/)
- [システムレビューレポート](./reports/review_report.md) - 総合的なシステム分析
- [Gemini CLI移行レビュー](./reports/gemini_migration_review.md) - codex-cli→gemini-cli移行の完全記録
- [改善提案](./reports/IMPROVEMENTS.md) - システム改善推奨事項

## 🚀 クイックリンク

### はじめに
1. [システム概要を理解する](./architecture/SYSTEM_ARCHITECTURE.md#システム概要)
2. [5分でセットアップ](./guides/QUICKSTART.md)
3. [最初のタスクを実行](./guides/USAGE.md#最初のタスク)

### よくある質問

**Q: 必要な環境は？**
- Python 3.9+
- SQLite3
- LMStudio + Gemini CLI
- 8GB以上のメモリ

**Q: 複数のタスクを同時に処理できる？**
- はい。[動的スケーリング機能](./architecture/DYNAMIC_SCALING.md)により、負荷に応じて自動的にワーカーが増減します。

**Q: どんなタスクを委譲できる？**
- コード生成・修正（Gemini CLI経由）
- 一般的な質問応答（LMStudio経由）
- ファイル処理
- データ分析

## 📊 システム構成図

```
Claude Code → MCP Server → Task Queue → Worker Pool → Local LLM
                              ↓
                          Database
```

## 🔗 関連リンク

- [プロジェクトホーム](../)
- [ソースコード](../scripts/)
- [設定ファイル](../.koubou/config/)
- [ログ](../.koubou/logs/)

## 📝 ドキュメント規約

### ファイル命名
- 大文字とアンダースコア（例: `SYSTEM_ARCHITECTURE.md`）
- 機能別にグループ化

### 内容構成
1. 概要
2. 詳細説明
3. 使用例
4. トラブルシューティング
5. 関連情報

### 更新ポリシー
- 機能追加時は必ずドキュメント更新
- バージョン番号と更新日を記載
- 変更履歴を維持

---
最終更新: 2025-08-30
バージョン: 2.0.0 (Gemini CLI統合版)