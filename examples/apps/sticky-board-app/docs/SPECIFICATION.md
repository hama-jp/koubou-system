# StickyBoard アプリケーション仕様書

## 1. アプリケーション概要

StickyBoard は、Web ブラウザ上で動作する付箋ボード型メモアプリです。  
ユーザーは自由に付箋を作成・編集・削除・移動し、色を変更して情報を整理できます。  
フロントエンドはシンプルな HTML5/CSS3/JavaScript で構築し、バックエンドは Python-Flask を使用して REST API を提供します。  
データはサーバー側で永続化（SQLite）し、クライアントはローカルストレージで一時的にキャッシュします。

## 2. 機能要件

| 機能 | 説明 | 重要度 |
|------|------|--------|
| 付箋作成 | クリックまたはドラッグで新規付箋を作成。 | ★★ |
| 付箋編集 | テキストをダブルクリックで編集。 | ★★ |
| 付箋削除 | 付箋上の「×」ボタンで削除。 | ★★ |
| 付箋移動 | ドラッグ＆ドロップで位置を変更。 | ★★ |
| 色変更 | 付箋の色をカラーピッカーで変更。 | ★ |
| 位置保存 | 付箋の位置（x, y）をサーバーへ保存。 | ★★ |
| 同期 | 複数デバイス間でデータを同期。 | ★ |
| レスポンシブ | PC・タブレット・スマホでレイアウトが崩れない。 | ★★ |
| バックアップ | 付箋データを JSON 形式でエクスポート/インポート。 | ★ |

## 3. 非機能要件

| 項目 | 要件 | 具体例 |
|------|------|--------|
| **レスポンシブデザイン** | 画面幅 320px 〜 1920px でレイアウトが崩れない。 | CSS Grid / Flexbox を使用。 |
| **パフォーマンス** | 1000 付箋以上でも 1 秒以内に描画完了。 | Canvas で描画、仮想 DOM を最小化。 |
| **データ永続化** | SQLite を使用し、データベースは `data/stickies.db`。 | Flask-SQLAlchemy で ORM。 |
| **セキュリティ** | CSRF / XSS 対策。 | Flask-WTF、JSON エスケープ。 |
| **可用性** | 99.9% 稼働率。 | Docker コンテナ化、CI/CD で自動デプロイ。 |
| **アクセシビリティ** | キーボード操作で全機能利用可能。 | `tabindex`、ARIA 属性。 |

## 4. 技術スタック

| フロントエンド | バックエンド | データベース | 開発・デプロイ |
|----------------|--------------|--------------|----------------|
| HTML5, CSS3, JavaScript (ES6+) | Python 3.11, Flask 2.3 | SQLite 3 | GitHub Actions, Docker, Nginx |

- **フロントエンド**  
  - `public/index.html`  
  - `public/css/style.css`  
  - `public/js/app.js`  
- **バックエンド**  
  - `app/__init__.py`  
  - `app/routes.py`  
  - `app/models.py`  
  - `config.py`  
- **データ永続化**  
  - `data/stickies.db`（SQLite）  
  - `migrations/`（Alembic でマイグレーション管理）  

## 5. データモデル

```json
{
  "id": "string",          // UUID v4
  "title": "string",       // 付箋タイトル（任意）
  "content": "string",     // 付箋本文
  "color": "#RRGGBB",      // 付箋色
  "position": {            // 付箋位置（ピクセル単位）
    "x": 120,
    "y": 240
  },
  "created_at": "ISO8601", // 作成日時
  "updated_at": "ISO8601"  // 更新日時
}
```

- **id**: 主キー。UUID を生成して一意に管理。  
- **position**: 付箋の左上座標。  
- **color**: ユーザーが選択した色。デフォルトは `#FFFF88`。  

## 6. API 仕様（REST API）

| メソッド | エンドポイント | 説明 | リクエスト例 | レスポンス例 |
|----------|----------------|------|--------------|--------------|
| `GET` | `/api/stickies` | すべての付箋を取得 | `-` | `200 OK`<br>`[{...}, {...}]` |
| `POST` | `/api/stickies` | 新規付箋作成 | `{"title":"Todo","content":"Buy milk","color":"#FFEEAA","position":{"x":100,"y":200}}` | `201 Created`<br>`{"id":"uuid", ...}` |
| `GET` | `/api/stickies/<id>` | 指定付箋取得 | `-` | `200 OK`<br>`{...}` |
| `PUT` | `/api/stickies/<id>` | 付箋更新（全体） | `{"title":"Todo","content":"Buy milk and eggs","color":"#FFEEAA","position":{"x":120,"y":220}}` | `200 OK`<br>`{...}` |
| `PATCH` | `/api/stickies/<id>` | 部分更新（例: 位置のみ） | `{"position":{"x":150,"y":250}}` | `200 OK`<br>`{...}` |
| `DELETE` | `/api/stickies/<id>` | 付箋削除 | `-` | `204 No Content` |
| `GET` | `/api/stickies/export` | 付箋データを JSON でダウンロード | `-` | `200 OK`<br>`{ "stickies": [...] }` |
| `POST` | `/api/stickies/import` | JSON で付箋データをインポート | `{"stickies":[{...}, {...}]}` | `201 Created` |

### エラーレスポンス

| ステータス | コード | メッセージ |
|------------|--------|------------|
| `400 Bad Request` | `INVALID_INPUT` | 入力値が不正 |
| `404 Not Found` | `NOT_FOUND` | 指定 ID の付箋が存在しない |
| `500 Internal Server Error` | `SERVER_ERROR` | サーバー内部エラー |

### 認証・認可

- 現在はオープンアクセス（認証なし）。  
- 将来的に JWT ベースの認証を追加予定。  

## 7. デプロイ手順（Docker）

```bash
# ビルド
docker build -t stickyboard .

# 実行
docker run -d -p 80:5000 stickyboard
```

## 8. テスト計画

- **ユニットテスト**: `tests/` ディレクトリに Flask-Testing で API エンドポイントをテスト。  
- **E2Eテスト**: Cypress で UI 操作を自動化。  
- **パフォーマンステスト**: Locust で 1000 付箋同時アクセスをシミュレーション。  

## 9. 今後の拡張

1. **ユーザー管理**（ログイン/登録）  
2. **コラボレーション**（複数ユーザーで同一ボードを共有）  
3. **タグ付け**（付箋にタグを付けてフィルタリング）  
4. **画像添付**（付箋に画像を添付）  

---

> **備考**  
> - 本仕様書は開発初期段階のものであり、実装に伴い随時更新します。  
> - 変更点は `CHANGELOG.md` に記載し、GitHub の PR でレビューを行います。