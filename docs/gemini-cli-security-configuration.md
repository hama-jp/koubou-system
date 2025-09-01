# Gemini CLI セキュリティ設定ガイド

## 概要
Gemini CLIで危険なコマンド（rm、dd、formatなど）を制限し、安全に運用するための設定方法をまとめたドキュメントです。

## 設定ファイルの場所と優先順位

設定ファイルは以下の順序で読み込まれます（後のものが優先）：

1. **システム設定**: `/etc/gemini-cli/settings.json`
   - 環境変数 `$GEMINI_CLI_SYSTEM_SETTINGS_PATH` で変更可能
2. **ユーザー設定**: `~/.gemini/settings.json`
3. **プロジェクト設定**: `./.gemini/settings.json`
4. **環境変数**
5. **CLIフラグ** （最優先）

## 1. サンドボックスモード設定

### 有効化方法

#### ワンショット実行
```bash
gemini -s ...
gemini --sandbox ...
```

#### 永続的設定（settings.json）
```json
{
  "sandbox": true,
  // または
  "sandbox": "docker",
  "sandbox": "podman",
  "sandbox": "sandbox-exec"
}
```

#### 環境変数
```bash
export GEMINI_SANDBOX=true
export GEMINI_SANDBOX=docker
export GEMINI_SANDBOX=podman
export GEMINI_SANDBOX=sandbox-exec
```

### プラットフォーム別設定

#### macOS Seatbelt
プロファイル選択：
```bash
export SEATBELT_PROFILE=restrictive-open
```

利用可能なプロファイル：
- `permissive-open` （デフォルト）
- `permissive-closed` （ネットワークなし）
- `restrictive-open` / `restrictive-closed` （厳格なファイルシステムルール）

#### Docker/Podman
```bash
# カスタムフラグ設定
export SANDBOX_FLAGS="--security-opt label=disable ..."

# Linux UID/GID マッピング
export SANDBOX_SET_UID_GID=true
```

## 2. コマンドのホワイトリスト/ブラックリスト

### ホワイトリスト方式（推奨）

特定のコマンドのみを許可：
```json
{
  "coreTools": [
    "ReadFileTool",              // 読み取り専用ツール
    "GlobTool",
    "SearchText",
    "run_shell_command(ls)",     // lsコマンドのみ許可
    "run_shell_command(git)",    // gitコマンドのみ許可
    "run_shell_command(npm)"     // npmコマンドのみ許可
    // 注意: "run_shell_command" 単体は含めない
  ]
}
```

### ブラックリスト方式

特定のコマンドをブロック：
```json
{
  "coreTools": ["run_shell_command"],  // 基本的にすべて許可
  "excludeTools": [
    "run_shell_command(rm)",     // rmをブロック
    "run_shell_command(dd)",     // ddをブロック
    "run_shell_command(mkfs)",   // mkfsをブロック
    "run_shell_command(format)", // formatをブロック
    "run_shell_command(sudo)",   // sudoをブロック
    "run_shell_command(chmod)",  // chmodをブロック
    "run_shell_command(chown)"   // chownをブロック
  ]
}
```

### 実装の詳細

1. **プレフィックスマッチング**: `run_shell_command(rm)` は `rm -rf /tmp` や `rm -r` などをブロック
2. **優先順位**: ブラックリストが優先（両方にある場合はブロック）
3. **チェーンコマンド**: `cmd1 && cmd2` は分割されて各部分が検証される
4. **注意**: `excludeTools` は文字列マッチングのみ。バイナリ名を変更されると回避可能

## 3. 承認ポリシー設定

### CLIフラグでの設定
```bash
# デフォルト（すべてのツール呼び出しでプロンプト）
gemini --approval-mode=default

# 安全な編集ツールのみ自動承認
gemini --approval-mode=auto_edit

# すべて自動承認（危険！サンドボックスと併用推奨）
gemini --approval-mode=yolo
# または
gemini --yolo
```

### settings.jsonでの設定
```json
{
  "approvalMode": "default",    // または "auto_edit", "yolo"
  "autoAccept": false           // trueにすると読み取り専用ツールを自動承認
}
```

## 4. 実践的な設定例

### 開発環境用設定（~/.gemini/settings.json）
```json
{
  "theme": "GitHub",
  "vimMode": true,
  "sandbox": true,
  "approvalMode": "auto_edit",
  "coreTools": [
    "ReadFileTool",
    "GlobTool",
    "SearchText",
    "WriteFileTool",
    "run_shell_command(ls)",
    "run_shell_command(git)",
    "run_shell_command(npm)",
    "run_shell_command(node)",
    "run_shell_command(python)",
    "run_shell_command(make)"
  ],
  "excludeTools": [
    "run_shell_command(rm)",
    "run_shell_command(sudo)",
    "run_shell_command(dd)"
  ],
  "autoAccept": true,
  "contextFileName": ["GEMINI.md", "README.md"]
}
```

### 本番環境用設定（/etc/gemini-cli/settings.json）
```json
{
  "sandbox": "docker",
  "approvalMode": "default",
  "autoAccept": false,
  "coreTools": [
    "ReadFileTool",
    "GlobTool",
    "SearchText",
    "run_shell_command(ls)",
    "run_shell_command(git)",
    "run_shell_command(npm)"
  ],
  "excludeTools": [
    "run_shell_command(rm)",
    "run_shell_command(dd)",
    "run_shell_command(mkfs)",
    "run_shell_command(format)",
    "run_shell_command(sudo)",
    "run_shell_command(chmod)",
    "run_shell_command(chown)",
    "run_shell_command(kill)",
    "run_shell_command(pkill)",
    "run_shell_command(reboot)",
    "run_shell_command(shutdown)"
  ],
  "usageStatisticsEnabled": false,
  "maxSessionTurns": 10
}
```

### 最高セキュリティ設定（エンタープライズ向け）
```json
{
  "sandbox": "docker",
  "approvalMode": "default",
  "coreTools": [
    "ReadFileTool",
    "SearchText"
  ],
  "excludeTools": ["ShellTool", "run_shell_command"],
  "mcpServers": {
    "secure_api": {
      "url": "https://ai-tools.internal/api/sse",
      "trust": false,
      "includeTools": ["dataQuery", "reportGenerate"],
      "timeout": 10000
    }
  },
  "usageStatisticsEnabled": false,
  "hideTips": true,
  "hideBanner": true
}
```

## 5. MCPサーバー設定

カスタムツールの追加：
```json
{
  "mcpServers": {
    "my_server": {
      "command": "node /path/to/server.js",
      "args": ["--port", "3000"],
      "env": {
        "API_KEY": "$MY_API_KEY"
      },
      "cwd": "/workspace",
      "timeout": 5000,
      "trust": false,
      "includeTools": ["tool1", "tool2"],
      "excludeTools": ["dangerous_tool"]
    }
  },
  "allowMCPServers": ["my_server"],
  "excludeMCPServers": ["untrusted_server"]
}
```

## 6. その他の設定オプション

### ファイル関連
```json
{
  "contextFileName": ["GEMINI.md", "CONTEXT.md"],
  "fileFiltering": {
    "respectGitIgnore": true,
    "enableRecursiveFileSearch": true
  },
  "includeDirectories": ["./docs", "./src"],
  "loadMemoryFromIncludeDirectories": true
}
```

### UX設定
```json
{
  "vimMode": true,
  "theme": "GitHub",
  "hideTips": false,
  "hideBanner": false,
  "maxSessionTurns": 20
}
```

### プライバシー設定
```json
{
  "usageStatisticsEnabled": false,
  "excludedProjectEnvVars": ["DEBUG", "NODE_ENV", "API_KEY"]
}
```

## 7. 環境変数による設定

```bash
# モデル設定
export GEMINI_MODEL="gemini-1.5-flash"
export GEMINI_TEMPERATURE="0.7"
export GEMINI_MAX_TOKENS="2048"

# Google Cloud / Vertex AI
export GOOGLE_API_KEY="your-api-key"
export GOOGLE_CLOUD_PROJECT="your-project"
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# サンドボックス
export GEMINI_SANDBOX="docker"
export SANDBOX_FLAGS="--security-opt label=disable"
```

## 8. トラブルシューティング

### 設定の確認
```bash
# 現在の設定を表示
gemini config list

# デバッグモードで起動（設定ファイルパスを表示）
gemini --debug

# インタラクティブセッションでメモリを確認
/memory show
```

### よくある問題と解決策

1. **設定が反映されない**
   - 優先順位を確認（システム < ユーザー < プロジェクト < 環境変数 < CLIフラグ）
   - JSONの構文エラーをチェック

2. **コマンドがブロックされない**
   - プレフィックスマッチングが正しいか確認
   - ブラックリストよりホワイトリストを推奨

3. **サンドボックスが動作しない**
   - Docker/Podmanがインストールされているか確認
   - 必要な権限があるか確認

## 9. ベストプラクティス

### 使用シナリオ別推奨設定

| シナリオ | approval-mode | coreTools | sandbox | 備考 |
|---------|--------------|-----------|---------|------|
| 本番/CI | default | 厳格なホワイトリスト | docker | 最高セキュリティ |
| 日常開発 | auto_edit | 必要最小限 | true | バランス型 |
| 実験的作業 | yolo | 制限なし | docker | サンドボックス必須 |

### セキュリティの原則

1. **多層防御**: ホワイトリスト + サンドボックス + 承認ポリシー
2. **最小権限**: 必要最小限のツールのみ許可
3. **監査可能性**: すべての操作をログに記録
4. **デフォルトセキュア**: 明示的に許可しない限り拒否

## まとめ

Gemini CLIのセキュリティ設定は、以下の3つの要素を組み合わせることで実現します：

1. **サンドボックス**: システムレベルの隔離
2. **ツール制限**: コマンドのホワイトリスト/ブラックリスト
3. **承認ポリシー**: 実行前の確認プロセス

これらを適切に設定することで、AIアシスタントを安全かつ効率的に活用できます。