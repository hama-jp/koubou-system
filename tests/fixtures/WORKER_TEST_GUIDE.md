# Worker動作テストガイド

## 📁 ディレクトリ構造

```
tests/
├── fixtures/
│   ├── worker_tasks/           # Workerに与えるタスク定義ファイル
│   │   ├── simple_text_generation.txt
│   │   ├── code_generation.txt
│   │   ├── data_analysis.txt
│   │   ├── translation.txt
│   │   └── error_handling.txt
│   ├── worker_inputs/          # タスクで使用する入力データ
│   │   └── sample_sales_data.csv
│   ├── worker_test_config.json # テスト設定ファイル
│   └── WORKER_TEST_GUIDE.md   # このガイド
├── outputs/
│   └── worker_test_results/    # Worker出力結果保存先
│       ├── completed/          # 成功したタスクの結果
│       │   ├── text_generation/
│       │   ├── code_generation/
│       │   ├── data_analysis/
│       │   └── translation/
│       ├── failed/             # 失敗したタスクの結果
│       ├── logs/               # 実行ログ
│       └── performance/        # パフォーマンス測定結果
└── test_worker_operations.py   # Worker動作テストスイート
```

## 🎯 テスト種類

### 1. 基本動作テスト
- **simple_text_generation**: 文章生成能力
- **code_generation**: プログラムコード生成
- **data_analysis**: データ分析レポート作成
- **translation**: 多言語翻訳
- **error_handling**: エラー処理・例外処理

### 2. パフォーマンステスト
- **並行処理**: 複数タスクの同時実行
- **ベンチマーク**: 平均処理時間・成功率測定
- **高負荷**: システム安定性確認

### 3. 耐障害性テスト
- **Worker復旧**: プロセス再起動後の動作
- **高負荷安定性**: 大量タスク投入時の動作

## 🚀 テスト実行方法

### 全Worker動作テストを実行
```bash
uv run pytest tests/test_worker_operations.py -v
```

### 特定のテストのみ実行
```bash
# 文章生成テストのみ
uv run pytest tests/test_worker_operations.py::TestWorkerOperations::test_simple_text_generation_task -v

# パフォーマンステストのみ  
uv run pytest tests/test_worker_operations.py::TestWorkerOperations::test_worker_performance_benchmarks -v
```

### 結合テストのみ実行
```bash
uv run pytest tests/test_worker_operations.py -m integration -v
```

### 低速テストを除外
```bash
uv run pytest tests/test_worker_operations.py -m "not slow" -v
```

## ⚙️ テスト設定のカスタマイズ

`tests/fixtures/worker_test_config.json` を編集：

```json
{
  "test_environment": {
    "worker_timeout": 60,           # Worker応答タイムアウト
    "max_concurrent_tasks": 3,      # 最大同時実行数
    "cleanup_after_test": false     # テスト後のクリーンアップ
  },
  "performance_benchmarks": {
    "average_task_completion_time": 35,  # 平均完了時間(秒)
    "success_rate_threshold": 0.85,     # 成功率閾値
    "memory_usage_limit": "512MB"       # メモリ使用制限
  }
}
```

## 📊 結果の確認

### 1. 成功したタスク結果
```bash
ls tests/outputs/worker_test_results/test_run_*/completed/
```

### 2. パフォーマンス測定結果
```bash
cat tests/outputs/worker_test_results/test_run_*/performance/benchmark_results.json
```

### 3. エラーログ
```bash
cat tests/outputs/worker_test_results/test_run_*/failed/*.txt
```

## 🔧 新しいテストタスクの追加

1. **タスクファイル作成**
   ```bash
   touch tests/fixtures/worker_tasks/new_task.txt
   ```

2. **テスト設定に追加**
   ```json
   {
     "name": "new_task",
     "file": "worker_tasks/new_task.txt",
     "priority": 5,
     "expected_completion_time": 30,
     "expected_result_type": "text",
     "validation_criteria": ["contains keywords"]
   }
   ```

3. **テストケース実装**
   ```python
   def test_new_task(self, worker_test_config, output_dir, mcp_server_url):
       # テストロジックを実装
   ```

## 📝 テスト結果の評価基準

### ✅ 成功条件
- タスクが指定時間内に完了
- 結果が検証基準を満たす
- システムが安定動作

### ❌ 失敗条件  
- タイムアウト発生
- Worker応答なし
- 結果が検証基準に不合格
- システムエラー発生

## 🎭 Worker能力の評価指標

| 指標 | 基準値 | 説明 |
|------|--------|------|
| 成功率 | ≥85% | タスク完了成功率 |
| 平均処理時間 | ≤35秒 | 標準的なタスクの処理時間 |
| 並行処理能力 | 3タスク同時 | 同時実行可能数 |
| エラー回復時間 | ≤10秒 | 異常時の復旧時間 |

このテストスイートにより、Workerの実用性と信頼性を継続的に検証できます。