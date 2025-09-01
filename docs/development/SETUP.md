# 🏭 工房システム - セットアップガイド

## 前提条件

- Python 3.9以上
- uv (Pythonパッケージマネージャー)
- SQLite3

## インストール手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/koubou-system.git
cd koubou-system
```

### 2. 仮想環境の作成（uvが自動的に管理）

```bash
# uvは自動的に.venvディレクトリに仮想環境を作成します
uv venv
```

### 3. 依存関係のインストール

```bash
# 本番環境用の依存関係をインストール
uv pip install -e .

# 開発環境用（テストツール含む）
uv pip install -e ".[dev]"

# テスト実行用
uv pip install -e ".[test]"
```

### 4. 環境設定

```bash
# .envファイルを作成（必要に応じて）
cp .env.example .env
```

### 5. データベースの初期化

```bash
# 工房システムのデータベースを初期化
python .koubou/scripts/init_db.py
```

### 6. システムの起動

```bash
# 全サービスを一括起動
.koubou/start_system.sh
```

## 依存関係の管理

### 新しいパッケージの追加

1. `pyproject.toml`を編集して依存関係を追加:
   ```toml
   dependencies = [
       # ... 既存の依存関係
       "new-package>=1.0.0",
   ]
   ```

2. 依存関係を再インストール:
   ```bash
   uv pip install -e .
   ```

### 開発用パッケージの追加

開発環境専用のパッケージは`[project.optional-dependencies]`の`dev`セクションに追加:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.4.0",
    "black>=25.0.0",
    # 新しい開発用パッケージ
]
```

## トラブルシューティング

### 依存関係の競合

```bash
# 依存関係をクリーンインストール
uv pip uninstall -y -r <(uv pip freeze)
uv pip install -e ".[dev]"
```

### ポート競合

デフォルトポート:
- MCP Server: 8765
- WebSocket Server: 8766
- GraphQL API: 8767
- Web Dashboard: 8080

ポートが使用中の場合は、各サービスの設定ファイルで変更可能です。

## 開発ワークフロー

### コードフォーマット

```bash
# blackでコードフォーマット
black .koubou/
```

### リント

```bash
# flake8でリントチェック
flake8 .koubou/
```

### テスト実行

```bash
# 全テスト実行
pytest

# カバレッジ付きテスト
pytest --cov=.koubou
```

## パッケージ管理のベストプラクティス

1. **直接インストールを避ける**: `uv pip install <package>`の代わりに`pyproject.toml`を編集
2. **バージョン指定**: セマンティックバージョニングに従って最小バージョンを指定
3. **定期的な更新**: `uv pip install --upgrade -e .`で依存関係を更新
4. **ロックファイル**: 本番環境では`uv pip freeze > requirements.lock`でバージョンを固定

## 注意事項

- `uv pip sync`は使用しない（予期しないパッケージの削除を防ぐため）
- 仮想環境は`.koubou/venv`または`.venv`を使用
- グローバル環境への直接インストールは禁止