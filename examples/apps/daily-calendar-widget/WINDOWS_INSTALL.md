# 🗓️ 日めくりカレンダー Windows デスクトップウィジェット

## 📦 提供バージョン

### 1. HTA版（最も簡単）
**ファイル**: `windows-version/daily-calendar.hta`

#### インストール方法
1. `daily-calendar.hta` をデスクトップにコピー
2. ダブルクリックで起動
3. Windows Defenderの警告が出たら「詳細情報」→「実行」

#### 特徴
- ✅ インストール不要
- ✅ Windows標準機能で動作
- ✅ ドラッグで移動可能
- ✅ 透過背景対応
- ⚠️ Windows 10/11のみ対応

#### 自動起動設定
1. `Win + R` → `shell:startup` を実行
2. 開いたフォルダに `daily-calendar.hta` のショートカットを配置

---

### 2. Electron版（高機能）
**フォルダ**: `electron-version/`

#### インストール方法

##### 開発者向け（Node.js必要）
```bash
cd electron-version
npm install
npm start
```

##### エンドユーザー向け（実行ファイル作成）
```bash
cd electron-version
npm install
npm run build-win
# dist/フォルダに実行ファイルが生成される
```

#### 特徴
- ✅ システムトレイ常駐
- ✅ 最前面表示切り替え
- ✅ より美しいデザイン
- ✅ アップデート機能対応可能
- ✅ クロスプラットフォーム（Mac/Linux対応）

#### 起動オプション
- システムトレイアイコンを右クリックでメニュー表示
- ダブルクリックで最前面表示切り替え
- ドラッグで位置調整

---

## 🎨 カスタマイズ方法

### 位置の変更
- **HTA版**: ドラッグで自由に移動
- **Electron版**: ドラッグまたはトレイメニューから位置リセット

### サイズの変更
HTAまたはElectronのソースコード内の以下を編集：
```javascript
// HTAの場合
window.resizeTo(220, 250);  // 幅, 高さ

// Electronの場合
width: 220,
height: 250,
```

### デザインの変更
CSS部分を編集：
```css
/* 背景色 */
background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(240,240,240,0.95) 100%);

/* 文字色 */
.weekday-sun { color: #ff4500; }  /* 日曜日 */
.weekday-sat { color: #1e90ff; }  /* 土曜日 */
```

### 祝日の追加
JavaScriptの祝日リストに追加：
```javascript
const holidays = {
  '2025-1-1': '元日',
  '2025-5-5': 'こどもの日',
  // 新しい祝日を追加
  '2025-12-25': 'クリスマス'
};
```

---

## 🚀 スタートアップ登録

### 方法1: スタートアップフォルダ
1. `Win + R` → `shell:startup`
2. HTAファイルまたはElectron実行ファイルのショートカットを配置

### 方法2: タスクスケジューラ
1. タスクスケジューラを開く
2. 「基本タスクの作成」
3. トリガー：「ログオン時」
4. 操作：プログラムの開始
5. プログラム：HTAまたはElectron実行ファイルのパス

### 方法3: レジストリ（上級者向け）
```cmd
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DailyCalendar" /t REG_SZ /d "C:\path\to\daily-calendar.hta" /f
```

---

## 🔧 トラブルシューティング

### Q: HTAが起動しない
A: Windows Defenderまたはウイルス対策ソフトでブロックされている可能性
- 右クリック → プロパティ → 「ブロックの解除」にチェック

### Q: 文字化けする
A: 文字コードがUTF-8でない可能性
- メモ帳で開いて「UTF-8」で保存し直す

### Q: 透過が効かない
A: Windows 7以前では透過非対応
- Windows 10/11へのアップグレードを推奨

### Q: Electronが起動しない
A: Node.jsまたは依存関係の問題
```bash
# 依存関係の再インストール
rm -rf node_modules
npm install
```

---

## 📱 その他のプラットフォーム

### PowerToys版（Windows 10/11）
Microsoft PowerToysのWidgetsランチャーに登録可能

### Rainmeter版
Rainmeter用スキンとして変換可能（要追加開発）

---

## 📄 ライセンス
MIT License - 自由に改変・再配布可能

## 🤝 サポート
問題が発生した場合は、工房システムの親方にご相談ください。