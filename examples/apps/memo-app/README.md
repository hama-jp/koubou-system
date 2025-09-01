# 📝 MemoWall - ビジュアル付箋メモアプリ

## 🎯 プロジェクト概要

タイトルと内容を短冊状に管理できる、ビジュアル面もイケてるメモアプリ

### ✨ 主要機能
- 📋 短冊型カードUI（タイトル + 内容）
- 🎨 7色のテーマカラー選択
- 🔍 リアルタイム検索・フィルター
- 💾 ローカルストレージ永続化
- 📱 モバイル完全対応
- ✨ スムーズアニメーション

### 🏗 技術構成
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript
- **Layout**: Masonry Layout (Pinterest風)
- **Storage**: localStorage
- **Design**: Material Design + ガラスモーフィズム

### 📁 プロジェクト構造
```
memo-app/
├── index.html          # メインページ
├── assets/
│   ├── css/
│   │   └── style.css   # メインスタイル
│   ├── js/
│   │   └── app.js      # アプリケーションロジック
│   └── images/         # アイコン・画像
├── components/         # 再利用コンポーネント
└── docs/              # ドキュメント
```

## 🚀 開発フロー

1. **親方** - 企画・設計・仕様策定 ✅
2. **職人** - HTML基盤構造実装
3. **職人** - CSS デザイン実装  
4. **職人** - JavaScript機能実装
5. **親方** - 最終仕上げ・統合・品質確認

## 📋 実装仕様書

### UI要件
- ヘッダー: タイトル + 新規作成ボタン + 検索バー
- メインエリア: Masonryレイアウトのメモカード群
- カード: タイトル・内容・色選択・編集・削除ボタン
- モーダル: 新規作成・編集用ダイアログ

### データ構造
```javascript
{
  id: "unique-id",
  title: "メモタイトル", 
  content: "メモ内容",
  color: "theme-color", // red, blue, green, yellow, purple, orange, pink
  createdAt: "2025-08-31T10:00:00",
  updatedAt: "2025-08-31T10:00:00"
}
```

### カラーパレット
- 🔴 Red: #FF6B6B
- 🔵 Blue: #4ECDC4  
- 🟢 Green: #45B7D1
- 🟡 Yellow: #FFA07A
- 🟣 Purple: #9B59B6
- 🟠 Orange: #F39C12
- 🩷 Pink: #E91E63