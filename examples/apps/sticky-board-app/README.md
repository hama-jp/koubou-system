# StickyBoard - 付箋ボード型メモアプリ

## 概要
StickyBoardは、ブラウザ上で動作する付箋型メモアプリケーションです。  
ドラッグ&ドロップで自由に付箋を配置し、ブレーンストーミングやタスク管理に活用できます。

## 機能
- ✨ 付箋の作成・編集・削除
- 🎨 5色のカラーバリエーション
- 🖱️ ドラッグ&ドロップで自由配置
- 💾 LocalStorageへの自動保存
- 📱 レスポンシブデザイン
- 🔄 バックエンドAPI連携（オプション）

## プロジェクト構造
```
sticky-board-app/
├── frontend/          # フロントエンド
│   ├── index.html    # メインHTML
│   ├── styles.css    # スタイルシート
│   └── script.js     # JavaScript
├── backend/           # バックエンドAPI
│   └── app.py        # Flask APIサーバー
├── docs/              # ドキュメント
│   └── SPECIFICATION.md  # 詳細仕様書
├── package.json       # プロジェクト設定
└── README.md         # このファイル
```

## クイックスタート

### フロントエンドのみで使用する場合

```bash
# プロジェクトディレクトリに移動
cd sticky-board-app/frontend

# HTTPサーバーを起動（Python）
python -m http.server 8000

# ブラウザでアクセス
# http://localhost:8000
```

### バックエンドAPIも使用する場合

1. 必要なパッケージのインストール
```bash
cd backend
pip install flask flask-cors
```

2. APIサーバーの起動
```bash
python app.py
# http://localhost:5000 で起動
```

3. フロントエンドの起動
```bash
cd ../frontend
python -m http.server 8000
```

## 使い方

1. **付箋の追加**
   - 右上の「+」ボタンをクリック
   - またはボード上の空いている場所をクリック

2. **付箋の編集**
   - 付箋のテキスト部分をクリックして編集

3. **付箋の移動**
   - 付箋をドラッグして好きな位置に配置

4. **色の変更**
   - 右下のカラーパレットから色を選択
   - 新しく作成する付箋に適用されます

5. **付箋の削除**
   - 付箋右上の「×」ボタンをクリック

## 技術スタック

- **フロントエンド**
  - HTML5
  - CSS3 (Material Design風)
  - JavaScript (ES6+)
  - Material Design Lite (CDN)

- **バックエンド**
  - Python 3.x
  - Flask
  - SQLite
  - Flask-CORS

## ライセンス
MIT

## 作成者
工房システム - 親方と職人たちの協働作品

---
🏭 Powered by Koubou System