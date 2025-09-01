# 📚 Examples Directory

このディレクトリには、工房システムの使用例とサンプルコードが含まれています。

## 📁 ディレクトリ構造

```
examples/
├── 📁 apps/              # サンプルアプリケーション
│   ├── memo-app/             # メモ帳アプリ
│   ├── realtime-translation-chat/  # リアルタイム翻訳チャット
│   ├── sticky-board-app/     # 付箋ボードアプリ
│   ├── daily-calendar-widget/  # カレンダーウィジェット
│   ├── analog-clock-app/     # アナログ時計アプリ
│   └── responsive-task-manager/  # タスク管理アプリ
├── 🐍 Python関数サンプル
│   ├── fib_recursive.py      # 再帰フィボナッチ
│   ├── fibonacci_calc.py     # フィボナッチ計算
│   ├── timer_decorator.py    # タイマーデコレータ
│   └── ...
└── 📖 README.md          # このファイル
```

## 🎯 用途別ガイド

### 🏗️ 完全なアプリケーション
[**apps/**](./apps/) ディレクトリをご覧ください
- 6つの実用的なWebアプリケーション
- 工房システムで3-12分で開発
- 本番レベルの品質

### ⚡ 簡単な関数・スクリプト
- `fib_recursive.py` - 再帰的フィボナッチ実装
- `timer_decorator.py` - 実行時間測定デコレータ
- `fibonacci_calc.py` - 最適化されたフィボナッチ計算

## 🚀 工房システムでの作成方法

### アプリケーション作成例
```bash
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "React + FastAPIでTodoアプリを作成。CRUD機能完備",
    "priority": 8,
    "task_type": "code_generation"
  }'
```

### 関数・ユーティリティ作成例
```bash
curl -X POST http://localhost:8765/task/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Pythonでソートアルゴリズムを実装（バブル、クイック、マージ）",
    "priority": 5,
    "task_type": "code_generation"
  }'
```

## 📊 開発効率データ

| カテゴリ | 平均開発時間 | 従来比 | 品質 |
|---------|------------|--------|------|
| Webアプリ | 3-12分 | 10-50倍速 | ✅ 本番レベル |
| Python関数 | 30-120秒 | 20-100倍速 | ✅ 最適化済み |
| ユーティリティ | 1-3分 | 15-30倍速 | ✅ テスト済み |

## 🛠️ 実行方法

### アプリケーション
各アプリのREADMEに従ってセットアップ・実行

### Python関数
```bash
# 直接実行
python examples/fib_recursive.py

# インポートして使用
from examples.timer_decorator import timer
```

## 🔗 関連リンク

- [工房システム概要](../README_JP.md)
- [システム構成レポート](../system_configuration_report.md)  
- [API直接操作ガイド](../system_configuration_report.md#-ユーザー直接操作ガイド)

---

**💡 ヒント**: 新しい例が欲しい場合は、工房システムに委託してください！親方が職人と協力して、あなたの要望を具現化します。