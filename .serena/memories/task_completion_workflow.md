# タスク完了後の推奨ワークフロー

## 必須チェック項目

### 1. テスト実行
```bash
# 統合テストで基本機能確認
python .koubou/scripts/test_integration.py

# 該当機能の単体テスト (存在する場合)
pytest tests/test_*.py -v

# システム全体テスト (重要な変更の場合)
python .koubou/scripts/load_test.py
```

### 2. コードスタイルチェック
```bash
# コードフォーマット
black .

# リント実行  
flake8 .

# 型チェック (推奨)
mypy . --ignore-missing-imports
```

### 3. システム動作確認
```bash
# ヘルスチェック
curl http://localhost:8765/health

# ワーカー状態確認
sqlite3 .koubou/db/koubou.db "SELECT worker_id, status FROM workers;"

# ログエラー確認
tail -50 .koubou/logs/mcp_server.log | grep -i error
tail -50 .koubou/logs/worker_pool.log | grep -i error
```

## 新機能追加時の追加手順

### 1. テストカバレッジ確認
- 新しいAPIエンドポイントのテスト追加
- エッジケースのテスト追加
- エラーハンドリングのテスト追加

### 2. ドキュメント更新
- API仕様書更新 (該当する場合)
- README.md更新 (必要に応じて)
- 設定例更新

### 3. 設定ファイル確認
- `agent.yaml` の設定項目追加確認
- `.env` ファイルの環境変数追加確認
- `pyproject.toml` の依存関係更新確認

## バグ修正時の確認手順

### 1. 根本原因確認
- ログファイルでエラートレース確認
- データベース状態確認
- 設定ファイル問題確認

### 2. 修正範囲の影響確認
- 関連機能のテスト実行
- 副作用がないかテスト
- パフォーマンス影響確認

### 3. 回帰テスト
- 既存機能の動作確認
- 修正前の問題が解決されているか確認

## パフォーマンス関連の変更時

### 1. ベンチマーク実行
```bash
# 負荷テストで性能確認
python .koubou/scripts/load_test.py heavy

# ワーカースケーリング動作確認
python .koubou/scripts/load_test.py gradual -d 60 -r 3
```

### 2. リソース使用量確認
```bash
# メモリ使用量監視
ps aux | grep python

# データベースサイズ確認
ls -lh .koubou/db/koubou.db
```

## デプロイメント前の最終チェック

### 1. 環境依存性確認
- Ollama動作確認
- 必要なPythonパッケージ確認
- ポート使用状況確認 (8765, 8766, 8767, 8080)

### 2. セキュリティチェック
- 機密情報のログ出力確認
- APIエンドポイントの認証確認 (実装されている場合)
- ファイル権限確認

### 3. バックアップ確認
- データベースバックアップ
- 設定ファイルバックアップ
- ロールバック手順確認

## エラー対応ガイド

### よくあるエラーパターン
1. **Ollamaサーバー未起動**: `ollama serve` で起動
2. **ポート競合**: 別ポート使用または既存プロセス停止
3. **依存関係不足**: `uv pip install -e .` で再インストール
4. **データベース破損**: `.koubou/db/koubou.db` 削除後初期化
5. **ワーカー停止**: `pkill -f worker` 後、システム再起動

### ログ確認コマンド
```bash
# エラーログ一括確認
grep -r "ERROR\|Exception\|Failed" .koubou/logs/ --include="*.log" | tail -20

# 特定時間のログ確認  
journalctl --since "10 minutes ago" | grep koubou
```