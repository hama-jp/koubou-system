# 工房システム クイックスタートガイド

## 🚀 5分で始める工房システム

このガイドでは、AIエージェント協調システム「工房システム」を素早くセットアップして動作確認する方法を説明します。

---

## 📋 前提条件

以下のソフトウェアがインストールされていることを確認してください：

- **Linux/WSL2環境**（Ubuntu 20.04以降推奨）
- **Python 3.8以上**
- **SQLite3**
- **LMStudio**（gpt-oss-20bモデル用）
- **Claude Code**（親方エージェント用）

### 必要なパッケージのインストール

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip sqlite3 jq inotify-tools

# Python パッケージ
pip3 install requests pyyaml flask
```

---

## 🛠️ セットアップ（3ステップ）

### ステップ 1: リポジトリのクローンと初期設定

```bash
# リポジトリをクローン（または解凍）
cd ~
git clone https://github.com/your-repo/koubou-system.git
cd koubou-system

# セットアップスクリプトに実行権限を付与
chmod +x scripts/setup_all.sh

# 完全セットアップを実行
./scripts/setup_all.sh
```

セットアップスクリプトは以下を自動的に行います：
- ✅ ディレクトリ構造の作成
- ✅ データベースの初期化
- ✅ 設定ファイルの配置
- ✅ 必要なスクリプトのコピー

### ステップ 2: LMStudioの準備

1. **LMStudioを起動**
2. **gpt-oss-20bモデルをロード**
3. **サーバーモードで起動**（ポート1234）

```bash
# LMStudioの接続確認
/var/koubou/scripts/check_lmstudio.sh
```

成功すると以下のように表示されます：
```
✓ LMStudioに接続できました
✓ gpt-oss-20bモデルが利用可能です
```

### ステップ 3: システムの起動

```bash
# システムを起動
cd /var/koubou/scripts
./start_system.sh
```

起動メッセージ：
```
===================================
工房システム v2.0 起動
===================================
親方エージェント: claude-code
ローカル職人を起動中...
  Worker #1 started (PID: 12345)
  Worker #2 started (PID: 12346)
システム起動完了
```

---

## 🎯 動作確認

### 方法1: コマンドラインから直接テスト

```bash
# テストタスクを作成
sqlite3 /var/koubou/db/koubou.db << EOF
INSERT INTO task_master (task_id, content, task_type, priority, status)
VALUES ('test_001', 'Write a Python hello world program', 'code_generation', 5, 'pending');
EOF

# タスクの状態を確認（数秒待ってから）
sqlite3 /var/koubou/db/koubou.db "SELECT task_id, status FROM task_master WHERE task_id = 'test_001';"

# 完了したタスクの結果を確認
cat /var/koubou/tasks/completed/test_001.json | jq -r '.content'
```

### 方法2: Claude Codeから使用

Claude Codeで以下のMCPツールを使用できます：

1. **タスクを委任**
```
koubou_delegate_task ツールを使用して、
"Create a Python function to calculate factorial" 
というタスクを委任してください。
```

2. **状態を確認**
```
koubou_get_task_status ツールで、
返されたtask_idの状態を確認してください。
```

3. **タスク一覧を表示**
```
koubou_list_tasks ツールで、
現在のタスク一覧を確認してください。
```

---

## 📊 システム監視

### リアルタイムログ監視

```bash
# ワーカーログを監視
tail -f /var/koubou/logs/workers/worker_1.log

# システムモニターログを監視
tail -f /var/koubou/logs/system/monitor.log
```

### データベース状態確認

```bash
# ワーカー状態
sqlite3 -header -column /var/koubou/db/koubou.db \
  "SELECT worker_id, status, model_name FROM workers;"

# タスク統計
sqlite3 -header -column /var/koubou/db/koubou.db \
  "SELECT status, COUNT(*) as count FROM task_master GROUP BY status;"
```

---

## 🔧 トラブルシューティング

### よくある問題と解決方法

#### 1. LMStudioに接続できない
```bash
# ポート確認
netstat -tln | grep 1234

# 解決策
- LMStudioが起動していることを確認
- モデルがロードされていることを確認
- ファイアウォール設定を確認
```

#### 2. ワーカーがタスクを処理しない
```bash
# ワーカープロセス確認
ps aux | grep local_worker

# データベース確認
sqlite3 /var/koubou/db/koubou.db "SELECT * FROM workers;"

# 解決策
- ワーカーログでエラーを確認
- データベースの権限を確認（chmod 666）
```

#### 3. パーミッションエラー
```bash
# 権限修正
sudo chown -R $USER:$USER /var/koubou
chmod 755 /var/koubou
chmod 666 /var/koubou/db/koubou.db
```

---

## 🛑 システムの停止

```bash
# Ctrl+C でシステムを停止
# または別ターミナルから
pkill -f start_system.sh
pkill -f local_worker.py

# 完全なクリーンアップ
sqlite3 /var/koubou/db/koubou.db "UPDATE workers SET status = 'offline';"
```

---

## 📚 次のステップ

### 基本的な使い方をマスターしたら

1. **設定のカスタマイズ**
   - `/var/koubou/config/agent.yaml` を編集
   - ワーカー数や優先度ルールを調整

2. **高度な機能**
   - 複数タスクの並列処理
   - タスク優先度の活用
   - カスタムタスクタイプの追加

3. **システムの拡張**
   - 新しいエージェントアダプターの追加
   - クラウドLLMワーカーの統合
   - Webダッシュボードの有効化

### 詳細ドキュメント

- [要件定義書](01_requirements.md) - システムの詳細な要件
- [設計書](02_design_v2.md) - アーキテクチャと設計詳細
- [実装手順書](03_implementation_guide_v2.md) - 完全な実装ガイド

---

## 💡 Tips & Tricks

### パフォーマンス最適化
```bash
# ワーカー数を増やす
# /var/koubou/config/agent.yaml を編集
workers:
  local:
    max_concurrent: 5  # 3から5に増加
```

### デバッグモード
```bash
# 環境変数でデバッグを有効化
export KOUBOU_LOG_LEVEL=DEBUG
./start_system.sh
```

### バックアップ
```bash
# データベースバックアップ
cp /var/koubou/db/koubou.db /var/koubou/db/koubou.db.backup

# 完全バックアップ
tar -czf koubou-backup-$(date +%Y%m%d).tar.gz /var/koubou
```

---

## 🆘 サポート

問題が解決しない場合：

1. **ログファイルを確認**
   - `/var/koubou/logs/` 配下の各ログ
   
2. **システム状態レポートを生成**
   ```bash
   /var/koubou/scripts/system_report.sh > report.txt
   ```

3. **Issue を作成**
   - GitHubリポジトリにIssueを作成
   - `report.txt` を添付

---

## 📜 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

---

## 🎉 準備完了！

これで工房システムの基本的なセットアップが完了しました。
AIエージェントと職人たちがあなたのタスクを効率的に処理する準備ができています！

Happy Coding with AI Agents! 🤖✨