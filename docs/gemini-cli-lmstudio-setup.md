# Gemini CLI + LMStudio セットアップガイド

## 概要
Google Gemini CLIをローカルLLM（LMStudio）で動作させるための改造と設定手順です。  
Riti0208さんの改造版を使用し、LMStudioのOpenAI互換APIに接続します。

## 前提条件
- Node.js v18以上
- LMStudio（http://192.168.11.29:1234でAPI稼働中）
- モデル: gpt-oss-20b@f16

## セットアップ手順

### 1. 改造済みGemini CLIのクローン
```bash
# Riti0208さんの改造版をクローン
git clone https://github.com/Riti0208/gemini-cli-local.git
cd gemini-cli-local
```

### 2. TypeScriptビルドエラーの修正

#### packages/core/src/utils/getFolderStructure.test.ts
```typescript
// 34行目付近を修正
const createDirent = (name: string, type: 'file' | 'dir'): FSDirent => ({
  name,
  isFile: () => type === 'file',
  isDirectory: () => type === 'dir',
  isBlockDevice: () => false,
  isCharacterDevice: () => false,
  isSymbolicLink: () => false,
  isFIFO: () => false,
  isSocket: () => false,
  parentPath: '',  // この行を追加
} as FSDirent);    // as FSDirent を追加
```

### 3. 環境変数の設定

#### .envファイルを作成
```bash
cat > .env << 'EOF'
# LMStudio Configuration
LOCAL_LLM_ENDPOINT=http://192.168.11.29:1234/v1
LOCAL_LLM_MODEL=gpt-oss-20b@f16
EOF
```

### 4. ビルドと実行

```bash
# 依存関係のインストール
npm install

# プロジェクトのビルド
npm run build

# 環境変数を設定して実行
export LOCAL_LLM_ENDPOINT="http://192.168.11.29:1234/v1"
export LOCAL_LLM_MODEL="gpt-oss-20b@f16"
npm run start
```

## 改造ポイント

### OpenAI互換アダプタの実装
`packages/core/src/core/openAICompatibleContentGenerator.ts`
- OpenAI APIフォーマットとGemini APIフォーマットの変換処理
- ストリーミング対応
- エラーハンドリング

### ContentGeneratorの変更
`packages/core/src/core/contentGenerator.ts`
```typescript
export async function createContentGenerator(
  config: ContentGeneratorConfig,
): Promise<ContentGenerator> {
  // Always use local LLM (OpenAI compatible)
  return new OpenAICompatibleContentGenerator({
    endpoint: process.env.LOCAL_LLM_ENDPOINT || 'http://localhost:11434/v1',
    model: process.env.LOCAL_LLM_MODEL || 'gemma3n:latest',
  });
}
```

### 認証タイプの追加
```typescript
export enum AuthType {
  LOGIN_WITH_GOOGLE_PERSONAL = 'oauth-personal',
  USE_GEMINI = 'gemini-api-key',
  USE_VERTEX_AI = 'vertex-ai',
  USE_LOCAL_LLM = 'local-llm',  // 追加
}
```

## 使用方法

### 基本的な使い方
```bash
# インタラクティブモード
npm run start

# ワンショット実行
echo "What is 2+2?" | npm run start
```

### 工房システムでの起動スクリプト
```bash
#!/bin/bash
# .koubou/scripts/gemini-cli-lmstudio.sh

export LOCAL_LLM_ENDPOINT="http://192.168.11.29:1234/v1"
export LOCAL_LLM_MODEL="gpt-oss-20b@f16"

cd /home/hama/project/koubou-system/gemini-cli-local
npm run start "$@"
```

## 動作確認済み環境
- OS: Linux (WSL2)
- Node.js: v22.16.0
- LMStudio: API v1互換
- モデル: gpt-oss-20b@f16（コンテキスト長: 16384）

## トラブルシューティング

### ビルドエラーが発生する場合
```bash
# node_modulesをクリーンアップ
rm -rf node_modules package-lock.json
npm install
npm run build
```

### LMStudioとの接続確認
```bash
# APIの動作確認
curl -X POST 'http://192.168.11.29:1234/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-oss-20b@f16",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

## 利点
- ✅ ローカルLLMで完全オフライン動作
- ✅ プライバシー保護（データが外部に送信されない）
- ✅ API制限なし
- ✅ カスタマイズ可能
- ✅ Gemini CLIの豊富な機能をそのまま利用可能

## 参考資料
- [元記事: Gemini CLIをローカルLLMで動かす](https://zenn.dev/riti0208/articles/d982e3b4adfde2)
- [改造版リポジトリ](https://github.com/Riti0208/gemini-cli-local)
- [オリジナルGemini CLI](https://github.com/google-gemini/gemini-cli)

## 今後の改善案
- [ ] 複数のLLMプロバイダーへの対応（Ollama、LM Studio、OpenAI互換）
- [ ] モデル切り替え機能
- [ ] プロンプトテンプレートのカスタマイズ
- [ ] 工房システムとの深い統合