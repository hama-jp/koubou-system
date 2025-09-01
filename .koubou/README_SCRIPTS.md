# 🏭 工房システム - スクリプト配置ガイド

## 📁 ディレクトリ構造

すべての実行スクリプトは `.koubou/` 以下に配置されています。

```
.koubou/
├── scripts/                    # メインのスクリプト群
│   ├── mcp_server.py          # MCPサーバー（タスク管理API）
│   ├── websocket_server.py    # WebSocketサーバー（リアルタイム通信）
│   ├── graphql_server.py      # GraphQL API
│   ├── lmstudio_proxy.py      # LMStudioプロキシ
│   ├── gemini-exec.sh         # Gemini実行スクリプト
│   │
│   ├── common/                # 共通モジュール
│   │   ├── database.py        # DB管理
│   │   ├── error_handler.py   # エラー処理
│   │   └── notification_hooks.py
│   │
│   ├── workers/               # ワーカー関連
│   │   ├── local_worker.py    # ローカルワーカー
│   │   └── worker_pool_manager.py
│   │
│   ├── distributed/           # 分散システム（将来用）
│   │   └── ...
│   │
│   └── adapters/              # 各種アダプタ（未使用）
│
├── start_system.sh            # システム一括起動スクリプト
├── start_gemini_system.sh     # Gemini版起動スクリプト
├── worker_helper.sh           # ワーカー起動ヘルパー
│
├── db/                        # データベース
│   └── koubou.db
│
├── logs/                      # ログファイル
│   ├── mcp_server.log
│   ├── websocket_server.log
│   ├── worker_pool_manager.log
│   └── ...
│
└── web_dashboard/            # Webダッシュボード
    └── index.html
```

## ⚠️ 重要な注意事項

1. **プロジェクトルートの `scripts/` フォルダは使用しません**
   - 古いセットアップスクリプトは `.archived/old_scripts/` に移動済み
   - すべての実行スクリプトは `.koubou/scripts/` を使用

2. **パスの指定**
   - 常に `.koubou/` からの相対パスを使用
   - 例: `.koubou/scripts/workers/local_worker.py`

3. **uvコマンドの使用**
   - Pythonスクリプト実行時は必ず `uv run` を使用
   - ヘルパースクリプト（`.koubou/worker_helper.sh`）が自動的に処理

## 🚀 システム起動方法

```bash
# 工房システム全体を起動
.koubou/start_system.sh

# 個別ワーカーを起動
.koubou/worker_helper.sh test_worker_1
```

## 📝 スクリプト修正時の確認事項

1. **インポートパスの確認**
   - 相対インポートが正しいか
   - `sys.path` の設定が適切か

2. **環境変数の確認**
   - `KOUBOU_HOME` が正しく設定されているか
   - デフォルト値が適切か

3. **ファイルパスの確認**
   - ハードコードされたパスがないか
   - 相対パスが正しく解決されるか

## 🔧 トラブルシューティング

もし誤って `scripts/` フォルダを参照するコードを見つけた場合：

1. `.koubou/scripts/` に変更
2. インポートパスを修正
3. 動作確認を実施

---
最終更新: 2025-08-30