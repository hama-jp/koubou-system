● gemini-repo-cliのOllama設定方法

  gemini-repo-cliがOllamaを呼び出す際の設定方法を調査しました。

  📝 設定方法

  1. デフォルト設定
  - モデル: qwen2.5-coder:1.5b (デフォルト)
  - ホスト: http://localhost:11434
  - 温度: 0.3
  - コンテキストウィンドウ: 4096

  2. 工房システムでの実際の使用
  - 使用モデル: gpt-oss:20b
  - 設定場所: .koubou/scripts/workers/local_worker.py:223

  ⚙️ 設定変更方法

  方法1: コード内で直接指定
  from gemini_repo.ollama_api import OllamaRepoAPI

  # モデル名とホストを指定
  api = OllamaRepoAPI(
      model_name="gpt-oss:20b",  # 使用するモデル
      host="http://localhost:11434"  # Ollamaサーバーのアドレス
  )

  方法2: 環境変数で設定
  export OLLAMA_HOST="http://localhost:11434"

  方法3: スクリプト実行時の引数
  # .koubou/scripts/gemini-exec.sh での例
  --provider ollama \
  --ollama-model gpt-oss:20b \
  --ollama-host http://localhost:11434

  📦 必要な依存関係

  - ollama>=0.1.0 (pyproject.tomlで定義済み)
  - Ollamaサーバーの起動が必要

  🔧 カスタマイズ可能なオプション

  options = {
      'temperature': 0.3,      # 生成の創造性（0.0-1.0）
      'num_ctx': 4096,        # コンテキストウィンドウサイズ
      # 'seed': 42,           # 再現性のためのシード値
      # 'top_p': 0.9,         # トークン選択の累積確率
  }
