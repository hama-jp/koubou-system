# 自律型 AI エージェントシステム 設計ドキュメント

## 概要

本ドキュメントは、人間と AI が協働し、複雑なタスクを自律的に計画・実行するための AI エージェントシステムの設計について記述する。

このシステムは、**特定の AI エージェントツール(Claude Code, Gemini CLI, Codex-CLI など)によって駆動される「親方プロセス」**が、プレイヤー兼マネージャーとして振る舞うアーキテクチャを特徴とする。

- 親方は人間と対話しながら主体的にタスクを処理し、必要に応じて専門の「職人プロセス」に作業を非同期に委任する。
- 親方エージェントは、タスクの性質やユーザーの選択に応じて、gemini-cli、claude-code-cli、codex-cli などのコーディング用エージェントのいずれかを指定して起動される。これにより、システムの司令塔となる AI Agent の「個性」や「得意分野」を柔軟に選択できる。
- 職人には、本家 Gemini CLI を利用する**「Gemini 職人」と、ローカル LLM を利用するように Gemini CLI のコードを改良した「Gemma 職人」**の 2 種類が存在し、親方がタスクに応じて最適な AI リソースを使い分けることが可能となる。
- プロセス間の連携は「伝言板」「Hooks」「MCP サーバー」を組み合わせたイベント駆動型アーキテクチャを採用し、効率的な非同期処理と人間による適切な介入を実現する。

## 1. Requirements (要件定義)

### 1.1. 目的

- 人間の指示のもと、親方エージェントが主体となってタスクを対話的に、または自律的に処理する。
- 処理負荷の高いタスクや、機密情報を含むタスク、並列化したいタスクを、専門の職人エージェントに非同期で委任する。
- タスクの特性に応じてクラウド AI（Gemini）とローカル AI（Gemma 等）をシームレスに使い分ける。
- 職人エージェントは、単純なコマンド実行だけでなく、gemini-cli が持つツール連携などの高度な機能を継承し、責任を持ってタスクを完遂する。
- システム全体が協調して動作している状況で、人間が進捗を確認し、適切に介入できる仕組みを提供する。

### 1.2 主要機能

| 機能                   | 説明                                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 計画立案               | 親方エージェント（gemini-cli など）を通じて、ユーザーの指示を具体的なタスクリストに分解する。                      |
| 非同期タスク実行       | 時間のかかるタスクをバックグラウンドで実行させ、メインプロセスをブロックしない。                                   |
| 状態管理               | ファイルシステムを「伝言板」として利用し、各プロセスの状態を共有する。                                             |
| タスク実行             | クラウド/ローカル LLM を活用する専門エージェントが、具体的なコマンドを実行する。                                   |
| イベント駆動           | 「伝言板」の変更をリアルタイムに検知(Hooks)し、即座に対応する。                                                    |
| ヒューマンインザループ | 人間がプロセスに割り込んで指示を修正したり、MCP サーバーを通じてシステムの内部状態を問い合わせ・操作したりできる。 |

### 1.3. 主要登場人物 (Actors)

- 人間 (Operator): プロジェクトの目的を提示し、使用する親方エージェント（gemini-cli 等）を指定してシステムを起動する。最終的な監督者として、必要に応じて介入を行う。
- 親方プロセス (Master Agent / Player-Manager):GEMINI.md や AGENT.md のような設定ファイルで指定された、特定の AI エージェント CLI（gemini-cli, claude-code-cli, codex-cli）によって駆動される、システムの中心プロセス。
  - 人間と対話しながらタスクを直接実行するプレイヤーであり、職人にタスクを委任し進捗を管理するマネージャーでもある。
- 職人プロセス (Worker Agent): 親方から具体的な指示を受け、非対話モードで自律的にタスクを完遂する。
  - Gemini 職人: オリジナルの gemini-cli。
  - Gemma 職人: gemini-cli の改造版で、ローカル LLM（Ollama 等）と連携する。

### 1.4 技術スタックとその役割

| カテゴリ| 技術 |役割 | 実装方法  |
|------|----- |  --- | ------- |
| 親方エージェント (Master) | gemini-cli, claude-code-cli, etc.| 思考と判断の中心。 人間との対話、計画立案、タスクの主体的な実行、委任の判断| OS のプロセスとして、ラッパースクリプト(start_master.sh) から起動|
| 職人エージェント (Worker) | gemini-cli, 既存のローカルLLM用コーディングエージェント or gemma-cli (改造版) | 専門タスクの実行部 | 親方から委任されたタスクを非対話モードで自律的に実行する | 親方から/mcp tool 経由で OS のバックグラウンドプロセスとして起動 |
| AI 基盤 | Google Gemini API, LMStudio (gpt-oss-20b etc.) | tool use 対応LLMモデル | 親方や職人が思考するための LLM サービスを提供 | 親方/職人 CLI が内部で HTTP API コールを行う |
| オーケストレーター | Shell Script (Bash) | システムの骨格・神経系。 親方の起動、職人の管理、Hooks のセットアップなど、プロセス間の連携を司る | start_master.sh, master_orchestrator.sh, task_watcher.sh などのスクリプト群 |
| 状態共有 (伝言板) | SQLite or 最初期段階ではOS ファイルシステムを使ったテキストファイルベースでも可 | 非同期通信の中継点 | tasks/ディレクトリ内の status.txt, log.txt などでタスクの状態を共有する。 全てのプロセスがファイルを読み書きする。拡張性をローカルDB による実装を優先検討 |
| イベント通知 (Hooks)| inotify-tools 軽量メッセージキュー（Redis, NATSなど）| ファイル、掲示板の変更のリアルタイム検知 |エージェントのメンバーが実施したディレクトリ構造変更を他のエージェントに通知するなど。掲示板DBの変更通知は軽量メッセージキュー（Redis, NATSなど）を検討。親方 Agent-CLI の種類には依存しない機構を設計。 |
| trap (シェル組込み) | シグナル割り込みの捕捉 | Ctrl+C のような人間からの割り込みや、軽量メッセージキュー機構よりも有用ならスクリプト間の通知のハンドルも検討| シェルスクリプト (start_master.sh や task_watcher.sh) が OS のシグナルを捕捉する。親方 CLI の種類には依存しない |
| 対話 API | 親方プロセスが起動する mcp サーバー | 外部との相談窓口。実行状況のインジケータ。 親方、職人のタスク実行状況を表示。システムの内部状態を外部に API として公開し、人間や他のツールとの連携を可能にする。 | MCPは監視と操作の責務を分離したAPI設計とする。親方プロセスがダッシュボードの Web UI の HTTP サーバーを起動する。 |

## 2. Design (設計)
### 2.1. アーキテクチャ概要

- システムの起動時に、人間が親方として振る舞う AI エージェントを、AGENT.md で指定する。
- 指定された親方エージェントが中央に座し、作業をこなす。委任が必要なタスクが発生した時だけ、適切な職人を呼び出して「伝言板」に指示を書き、作業を任せる。

**システム概略図**

```Mermaid
graph TD
    %% サブグラフ
    subgraph システム起動定義
        MD["AGENT.yaml
---
master_agent: gemini-cli
---"]
    end

    subgraph 人間_Operator
        A["対話的ターミナル
(オペレーターがコマンド入力・状況確認)"]
    end

    subgraph 親方プロセス
        B["Master Agent CLI
(例: gemini-cli)
・全体の制御/監督
・タスク割当/実行"]
        C["bash/ 監視・検証ループ
(タスク進捗・エラー監視)"]
        D["Hooks: inotify/trap
(ファイル変更やシグナル検知)"]
        E["MCPサーバー/Marter
・直接指示
・注意事項伝達
・伝言板書き込み"]
    end

    subgraph 職人A_Gemini
        I["gemini-cli 非対話モード
(職人A: Gemini職人)"]
    end

    subgraph 職人B_Gemma
        J["gemma-cli 非対話モード
(職人B: Gemma職人)"]
    end

    subgraph 共有リソース
        F["伝言板: SQLite
・進捗/エラー/状態共有
・チケット管理
・職人から親方へのヘルプ要請
・職人間の情報連携"]
    end

    %% エッジ
    MD -- "1. AGENT.mdで親方プロセス(B)を指定
(起動時にmaster_agentを参照)" --> B
    A -- "2. オペレーターが
対話的に指示/問い合わせ" --> B
    B -- "3a. 親方が自分で
タスクを実行" --> B
    B -- "3b. タスクを
監視・検証ループへ委任" --> C
    C -- "4-a. Gemini職人プロセス呼び出し
・Gemini系タスクを検出
・gemini-cli 非対話モードで実行" --> I
    C -- "4-b. Gemma職人プロセス呼び出し
・Gemma系タスクを検出
・gemma-cli 非対話モードで実行" --> J
    I -- "掲示板参照" --> F
    I -- "掲示板書き込み" --> F
    J -- "掲示板参照" --> F
    J -- "掲示板書き込み" --> F
    B -- "掲示板参照" --> F
    B -- "掲示板書き込み
(進捗・指示・注意事項などを掲示)" --> F

    F -- "ファイル変更通知
(掲示板更新通知)" --> D
    D -- "イベント通知
(変更イベント通知)" --> B
    D -- "イベント通知
(変更イベント通知)" --> C
    A -- "シグナル送信
(手動イベント発火)" --> D
    A -- "割り込みや相談
(緊急対応や質問)" --> E

```

### 2.2. コンポーネント詳細

**親方プロセス (Master Agent)**
責務: AGENT.yaml の定義に基づき、指定された AI エージェント CLI として起動する。人間との対話、タスクの主体的な実行、委任判断、職人の管理、進捗の非同期監視、人間との対話インターフェース提供

実装: 親方を起動するラッパースクリプト (start_master.sh) が AGENT.md を読み込み、指定された CLI（例: gemini-cli）を対話モードで起動する。各種ヘルパースクリプト（タスク委任、監視）は、この親方プロセスから/tool として呼び出される

**設定ファイル (AGENT.yaml etc.):**
責務: システムの振る舞いを定義する。少なくとも、親方として使用する CLI エージェントを指定する。将来的には、使用可能な職人の種類や、プロジェクトの基本方針などを記述する。
実装: シンプルな YAML Frontmatter 形式のファイル

```Yaml
master_agent: gemini-cli
available_workers:
  - gemini
  - gemma
project_goal: "Webサイトからデータを取得するアプリを開発する"
---

# プロジェクトに関するメモ
このプロジェクトでは、特にスクレイピングの精度が重要...
```

**Gemma 職人 (Gemma-CLI):**
責務: gemini-cli の核となるロジックを継承しつつ、AI との通信部分を OpenAI 互換 API に接続できるように改造された Agent-CLI
実装: gemini-cli の Go 言語ソースコードをフォークし、ContentGenerator インターフェースを介して AI プロバイダーを切り替えられるようにする。

### 2.3. モックコード

start_master.sh (親方起動スクリプト)

```Bash
#!/bin/bash

# AGENT.yamlから親方エージェントのコマンド名を取得 (yqなどのYAMLパーサーを使うとより堅牢)
MASTER_AGENT_CMD=$(grep 'master_agent:' AGENT.yaml | awk '{print $2}')

if [ -z "$MASTER_AGENT_CMD" ]; then
    echo "エラー: AGENT.mdにmaster_agentが指定されていません。"
    exit 1
fi

echo "親方エージェント『$MASTER_AGENT_CMD』を起動します..."

# 監視プロセスやMCPサーバーなどをバックグラウンドで起動
./task_watcher.sh &
# ./mcp_server_manager.sh $MASTER_AGENT_CMD & # 必要に応じて

# 指定された親方エージェントを対話モードで実行
eval "$MASTER_AGENT_CMD"
```

## 3. Implementation (実装計画)

### **フェーズ 0-1: Gemma-CLI (改造版 gemini-cli) の開発**

- [ ] gemini-cli や codex-cli などのフォークでローカル LLM を利用できる既存のプロジェクトを調査する。
- [ ] 有望なプロジェクトがあった場合。
  - [ ] 本プロジェクトへの適用方法を詳細検討する。
- [ ] 有望なプロジェクトがなかった場合。
  - [ ] gemini-cli のソースコードをフォークする。
  - [ ] AI プロバイダーの抽象化: ContentGenerator インターフェースを定義し、既存ロジックを GeminiGenerator に整理する。
  - [ ] OpenAI 互換ジェネレーターの実装: OpenAICompatibleGenerator を新規作成する。
  - [ ] Gemma-CLI プロバイダーの切り替え機構: 設定ファイルや引数でジェネレーターを切り替えられるようにし、gemma-cli としてビルドする。

### **フェーズ 0-2: セキュリティ設計**

- [] 初期段階では実装は見送るが予約機能としてモック機能として設計に織り込む。
  - どのタスクが外部に出てよいかを制御するポリシーレイヤー設計
  - 例えば、個人情報データのデータ加工のタスクは Gemini に送らず Gemma に限定する」などルールを AGENT.yaml に書いて親方が参照できるようにすると、実レイヤーは設置せずとも実装できそうか？
  - 社外公開しない前提で、タスクをどのLLMに流すかをログに残すことを重視し
  - ポリシー制御（クラウドに出す/出さない）は「安全性」よりも「監査性・トレーサビリティ」重視で設計

#### AGENT.yamlへの追加例
```yaml
security_policy:
  data_classification:
    - type: "personal_info"
      allowed_workers: ["gemma"]  # ローカルのみ
    - type: "public"
      allowed_workers: ["gemini", "gemma"]
  
  audit_log:
    retention_days: 90
    log_level: "INFO"
```

#### ドメインモデルの明確化例(責務の明確化)
 Single Responsibility Principleに従い、以下のような分離を検討する。
```python
class MasterAgent:
    """タスク実行と判断の責務"""
    def execute_task()
    def decide_delegation()

class WorkerCoordinator:
    """職人管理の責務"""
    def assign_task()
    def monitor_progress()

class SystemMonitor:
    """監視とイベント通知の責務"""
    def watch_bulletin_board()
    def notify_changes()
```

### **フェーズ 1: 親方と職人の連携**

- [ ] 親方（人間）が、手動で gemma-cli や gemini-cli を非対話モードで実行し、期待通りにタスクを処理できるか確認する。
- [ ] 親方・職人のプロセス管理はsystemd管理で十分。ログ一元化をセットで設計
- [ ] AGENT.yaml ファイルのフォーマットを定義する。
- [ ] 掲示板用の DB 設計と実装、テストを行う。
- [ ] master_orchestrator.sh を作成し、親方の gemini-cli セッションから/tool として職人を呼び出せるようにする。職人は拡張性を考慮し、複数の職人を非同期で管理できる設計とする。
- [ ] 親方および職人が掲示板を参照、書き込みする機構を設計、実装する。
- [ ] 掲示板の変更を親方、職人に通知する機構を設計、実装する。
- [ ] 親方の gemini-cli から、/tool として master_orchestrator.sh を呼び出し、gemma-cli や gemini-cli の職人を起動できること、掲示板を通じたチケット管理をテストで確認する。
- [ ] エラー処理
  - 「自動リトライ」よりも「親方への即エスカレーション」を選択
  - 職人エラー → 掲示板に「要確認」ステータスを書き込み
  - inotify経由などで親方へ通知
  - 親方が再実行するかどうか判断（実装の初期段階は人間にフォールバックさせてデバック）
  - 自動化よりも「失敗ログを透明に見せる」設計を優先


#### エラー処理の具体化案

```bash
# error_handler.sh の例
handle_worker_error() {
    local task_id=$1
    local error_type=$2
    
    case $error_type in
        "timeout")
            notify_master "TIMEOUT" "$task_id"
            ;;
        "resource_exhausted")
            retry_with_backoff "$task_id"
            ;;
        "validation_failed")
            escalate_to_human "$task_id"
            ;;
    esac
}
```

### **フェーズ 2: 非同期連携と監視の自動化 (Hooks)**

- [ ] スケールや耐障害性を考えて SQLite や軽量メッセージキュー（Redis, NATS など）を検討する。
- [ ] task_watcher.sh を作成する。
  - このスクリプトは、親方プロセスが動作するターミナルとは別の監視スクリプトとし、tasks/ディレクトリ全体の変更を inotifywait で監視し、タスクのステータスが「完了」や「エラー」、「親方呼び出し」に変わったら親方のターミナルに通知する。
- [ ] trap を使い、親方の対話セッションで Ctrl+C が押された時に、実行中のタスク一覧を表示させたり、緊急停止させたりする機能を実装する。
- [ ] どのプロセスが責任を持つのか明確化。「進捗やエラーを伝言板に書く」ケースの、**リカバリポリシー（再実行、リトライ、親方へのエスカレーション）** などの機能を実装する。

#### プロセス管理の明確化案
  
```yaml
# systemd service例
[Unit]
Description=AI Agent Master Process
After=network.target

[Service]
Type=simple
ExecStart=/path/to/start_master.sh
Restart=on-failure
StandardOutput=journal
StandardError=journal  
```
### **フェーズ 3: 対話型インターフェースの強化 (MCP)**

- [ ] 親方エージェントの種類（gemini-cli など）に関わらず、共通のインターフェースで状態を照会できる MCP ツールを設計する。バックエンドの設計は操作 API と監視 API の責務を分けた設計（REST ＋ WebSocket など）を検討
  - 外部統合は不要なので、まずは監視ダッシュボード＋簡単な操作APIに絞る
    - WebUIで見たいのは：
      - 実行中タスク一覧
      - タスクの状態（進行中／完了／エラー）
      - 親方・職人のログ
    - RESTよりも WebSocket（イベントプッシュ） の方が監視用途には向か
- [ ] 現在進行中の親方、職人のタスク一覧やログを表示させる MCP ツール (get_tasks, get_log) を実装する。フロントエンドは実装は React を用いる。
- [ ] 親方プロセスが起動時に MCP サーバーを立ち上げるよう設定する。


## 懸念事項など
- 複雑性の増大：[対策] MVPではファイルベースの伝言板から開始
- 職人プロセスの暴走：[対策] タイムアウトとリソース制限の実装
- デバッグの困難さ：[対策] 分散トレーシングIDの導入
- 技術選択の検討事項
  - SQLiteと軽量メッセージキューの混在：
    - [推奨] 初期実装では一貫性のためSQLiteに統一
    - 将来的にRedis/NATSへの移行パスを設計に含める
  - inotify-toolsの制約：
    - [懸念] Linuxに依存するため、macOS/Windowsでの動作に制限
    - [代替案] ファイルシステム監視にはfswatchやポーリングベースの実装も検討
