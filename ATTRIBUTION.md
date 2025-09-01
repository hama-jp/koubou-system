# 🙏 Attribution & Credits

工房システムの開発において、以下のオープンソースプロジェクトとコミュニティの貢献に感謝いたします。

## 🔧 Core Dependencies

### [gemini-repo-cli](https://github.com/deniskropp/gemini-repo-cli)
- **作者**: [Denis Kropp](https://github.com/deniskropp)
- **ライセンス**: MIT License
- **用途**: リモートワーカーのOllama API統合
- **役割**: リポジトリコンテキスト付きAI処理を実現する重要な基盤技術

**使用箇所**:
```python
# .koubou/scripts/workers/remote_worker.py
# リモートワーカーがgemini-repo-cli経由でOllamaにアクセス
result = self.gemini_cli.process_with_context(
    prompt=task_prompt,
    model=self.model_name,
    context=repo_context
)
```

**感謝の理由**:
- 高品質なコード実装
- 柔軟なAPI設計
- 優れたドキュメント
- MIT Licenseによる商用利用許可

## 🤖 AI Platforms

### [Anthropic Claude](https://www.anthropic.com/)
- **役割**: システム設計・開発・ドキュメント作成の主要AI
- **使用**: Claude Code経由でのインタラクティブ開発

### [LMStudio](https://lmstudio.ai/)
- **役割**: ローカルLLM実行環境
- **モデル**: gpt-oss:20b、qwen2.5-coder系列等

## 🛠️ Development Tools

### [Python](https://python.org/) Ecosystem
- **FastAPI**: 高速Web APIフレームワーク
- **SQLite**: 軽量データベース
- **WebSocket**: リアルタイム通信
- **uv**: 高速Pythonパッケージマネージャー

### Frontend Technologies
- **Mermaid.js**: 図表生成（システム構成図）
- **HTML5/CSS3/JavaScript**: Webアプリケーション基盤
- **React**: モダンフロントエンド（一部アプリ）

## 🏆 Special Thanks

### Denis Kropp ([deniskropp](https://github.com/deniskropp))
工房システムのリモートワーカー機能は、Denis Kropp氏の`gemini-repo-cli`なしには実現できませんでした。高品質なOSSの提供に心から感謝いたします。

### Open Source Community
- 数多くのライブラリとツールの開発者の皆様
- バグレポートや改善提案をしてくださったコミュニティメンバー
- オープンソース文化の発展に貢献するすべての方々

## 📜 License Compatibility

工房システムはApache License 2.0で提供されており、以下の依存関係とライセンス互換性を保っています：

| プロジェクト | ライセンス | 互換性 |
|------------|-----------|--------|
| gemini-repo-cli | MIT | ✅ 完全互換 |
| Python | PSF License | ✅ 互換 |
| FastAPI | MIT | ✅ 完全互換 |
| SQLite | Public Domain | ✅ 互換 |

## 🔗 References

- [gemini-repo-cli Repository](https://github.com/deniskropp/gemini-repo-cli)
- [MIT License Text](https://opensource.org/licenses/MIT)
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [Denis Kropp's Profile](https://github.com/deniskropp)

---

**工房システム開発チーム一同**  
*2025年9月2日*

*"Standing on the shoulders of giants" - オープンソースの力で、より良いAI開発環境の実現を目指します。*