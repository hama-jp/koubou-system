# 工房システム - コードスタイルと規約

## 全般的なスタイル

### 言語とエンコーディング
- 主要言語: Python 3.9+
- エンコーディング: UTF-8
- コメントと文字列: 日本語可 (ドキュメント、ログメッセージ等)
- 変数名・関数名: 英語

### ファイル構造
- 設定ファイル: `.koubou/config/`
- スクリプト: `.koubou/scripts/`
- ログ: `.koubou/logs/`
- データベース: `.koubou/db/`

## Pythonコードスタイル

### フォーマット
- **Black**: 自動フォーマッター使用
- 行幅: 88文字 (Black標準)
- インデント: 4スペース
- 文字列: ダブルクォート優先

### 命名規約
- 関数・変数: `snake_case`
- クラス: `PascalCase`
- 定数: `UPPER_CASE`
- プライベート変数: `_leading_underscore`

### docstring
- 関数・クラスには必須
- フォーマット: Google形式推奨
```python
def example_function(param1: str, param2: int) -> bool:
    """関数の簡潔な説明.
    
    Args:
        param1: パラメータ1の説明
        param2: パラメータ2の説明
        
    Returns:
        戻り値の説明
        
    Raises:
        ValueError: エラーの説明
    """
```

### 型ヒント
- Python 3.9+ type hints使用
- 必須: 関数の引数と戻り値
- Optional: 変数 (複雑な場合のみ)
```python
from typing import Optional, Dict, List, Union

def process_task(task_id: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pass
```

### エラーハンドリング
- 具体的な例外クラス使用
- ログ出力必須
- ユーザー向けメッセージと内部ログを分離
```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"操作失敗: {e}")
    return {"error": "操作に失敗しました"}
```

## ファイル別パターン

### MCPサーバー (`mcp_server.py`)
- Flask アプリケーション
- JSON API
- CORS対応
- エラーレスポンス統一フォーマット

### ワーカー (`workers/`)
- 非同期処理パターン
- ハートビート機能
- プロセス間通信
- データベース接続管理

### テストファイル (`test_*.py`)
- pytest使用
- テスト関数: `test_` prefix
- フィクスチャ活用
- 日本語テストケース名可

### 設定ファイル
- **YAML**: 構造化設定
- **TOML**: パッケージ設定
- **ENV**: 環境変数
- **JSON**: Claude MCP設定

## ログ出力規約

### ログレベル
- **DEBUG**: 開発用詳細情報
- **INFO**: 通常動作 (起動、終了、タスク完了)
- **WARNING**: 注意が必要 (リトライ、設定問題)
- **ERROR**: エラー (処理失敗、例外)
- **CRITICAL**: システム停止レベル

### ログフォーマット
```python
import logging

# 標準フォーマット
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### ログメッセージ
- 日本語可 (ユーザー向け)
- 英語推奨 (開発者向け)
- 文脈情報含める (task_id, worker_id等)

## データベース規約

### テーブル名・カラム名
- `snake_case`
- 複数形: テーブル名
- 単数形: カラム名

### インデックス
- 頻繁にクエリするカラムに付与
- 複合インデックス考慮
- 命名: `idx_<table>_<columns>`

## API設計規約

### RESTful API
- GET: 取得
- POST: 作成・実行
- PUT/PATCH: 更新
- DELETE: 削除

### レスポンス形式
```json
{
  "status": "success|error",
  "data": {...},
  "message": "説明メッセージ",
  "task_id": "uuid"
}
```

### GraphQL
- Query: 読み取り専用
- Mutation: データ変更
- Subscription: リアルタイム更新