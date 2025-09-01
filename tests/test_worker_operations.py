"""
Worker動作テストスイート

このモジュールは、工房システムのWorkerの動作を総合的にテストします。
"""

import pytest
import requests
import time
import json
from pathlib import Path
from typing import Any, Dict, List


@pytest.mark.integration
class TestWorkerOperations:
    """Worker操作の統合テスト"""
    
    @pytest.fixture
    def worker_test_config(self):
        """ワーカーテスト設定をロード"""
        config_path = Path("tests/fixtures/worker_test_config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @pytest.fixture
    def output_dir(self):
        """テスト出力ディレクトリを作成"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"tests/outputs/worker_test_results/test_run_{timestamp}")
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 結果格納用のサブディレクトリを作成
        for subdir in ["completed", "failed", "logs", "performance"]:
            (output_path / subdir).mkdir(exist_ok=True)
            
        # 各タスクタイプごとの出力ディレクトリを作成
        for task_type in ["text_generation", "code_generation", "data_analysis", "translation", "error_handling"]:
            (output_path / "completed" / task_type).mkdir(exist_ok=True)
            (output_path / "failed" / task_type).mkdir(exist_ok=True)
            
        return output_path
        
    @pytest.fixture
    def mcp_server_url(self):
        """MCP Server URL"""
        return "http://localhost:8765"

    def load_task_content(self, task_file_path: Path) -> str:
        """タスクファイルからコンテンツを読み込み"""
        return task_file_path.read_text(encoding='utf-8')

    def delegate_task_to_worker(self, server_url: str, content: str, priority: int = 5) -> str:
        """Worker にタスクを委託"""
        task_data = {"type": "general", "content": content, "priority": priority}
        response = requests.post(f"{server_url}/task/delegate", json=task_data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["task_id"]

    def wait_for_task_completion(self, server_url: str, task_id: str, timeout: int = 60) -> Any:
        """タスク完了を待機"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(f"{server_url}/task/{task_id}/status", timeout=30)
            if response.status_code == 200:
                status_data = response.json()
                if status_data.get("status") == "completed":
                    # 結果取得
                    result_response = requests.get(f"{server_url}/task/{task_id}/result", timeout=30)
                    result_response.raise_for_status()
                    return result_response.json()
            time.sleep(2)
        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")

    def save_task_result(self, task_result: Any, task_id: str, task_name: str, output_dir: Path) -> Path:
        """タスク結果を適切な形式で保存"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 結果テキストを抽出
        if isinstance(task_result, dict):
            result_text = task_result.get("output", str(task_result))
            success = task_result.get("success", True)
        else:
            result_text = str(task_result)
            success = True
            
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # タスクタイプに応じて適切な形式で保存
        if task_name == "code_generation":
            # Python ファイルとして保存
            output_file = output_dir / f"{task_id}_result.py"
            header = f"""# Code Generation Result
# Task ID: {task_id}
# Generated: {timestamp}
# Success: {success}

"""
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header + result_text)
                
        elif task_name == "data_analysis":
            # Markdown レポートとして保存
            output_file = output_dir / f"{task_id}_report.md"
            header = f"""# Data Analysis Report
**Task ID:** {task_id}  
**Generated:** {timestamp}  
**Status:** {'✅ Success' if success else '❌ Failed'}

---

"""
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header + result_text)
                
        elif task_name == "translation":
            # 対訳形式で保存
            output_file = output_dir / f"{task_id}_translation.txt"
            header = f"""Translation Result
Task ID: {task_id}
Generated: {timestamp}
Status: {'Success' if success else 'Failed'}

---

"""
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header + result_text)
                
        elif task_name == "error_handling":
            # ログ形式で保存
            output_file = output_dir / f"{task_id}_error_log.txt"
            header = f"""[{timestamp}] ERROR HANDLING TEST RESULT
Task ID: {task_id}
Status: {'SUCCESS' if success else 'FAILED'}

Error Details:
"""
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header + result_text)
        else:
            # 一般的なテキストファイル
            output_file = output_dir / f"{task_id}_result.txt"
            header = f"""Task Result
Task ID: {task_id}
Task Type: {task_name}
Generated: {timestamp}
Status: {'Success' if success else 'Failed'}

---

"""
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header + result_text)
        
        # JSON メタデータファイルも作成
        metadata = {
            "task_id": task_id,
            "task_name": task_name,
            "timestamp": timestamp,
            "success": success,
            "output_file": str(output_file),
            "result_length": len(result_text)
        }
        metadata_file = output_dir / f"{task_id}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
            
        return output_file

    def validate_task_result(self, task_result: Any, validation_criteria: List[str]) -> None:
        """タスク結果の検証"""
        if isinstance(task_result, dict):
            result_text = task_result.get("output", str(task_result))
        else:
            result_text = str(task_result)
            
        for criterion in validation_criteria:
            if "length >=" in criterion:
                min_length = int(criterion.split(">=")[1].strip())
                assert len(result_text) >= min_length, f"Result too short: {len(result_text)} < {min_length}"
            elif "contains" in criterion:
                search_term = criterion.replace("contains", "").strip().strip("'\"")
                assert search_term in result_text, f"Missing required content: '{search_term}'"

    @pytest.mark.slow
    def test_simple_text_generation_task(self, worker_test_config, output_dir, mcp_server_url):
        """Worker の基本的なテキスト生成能力をテスト"""
        task_config = next(task for task in worker_test_config["test_tasks"] 
                          if task["name"] == "simple_text_generation")
        
        task_content = self.load_task_content(Path("tests/fixtures") / task_config["file"])
        task_id = self.delegate_task_to_worker(mcp_server_url, task_content, task_config["priority"])
        
        # タスク完了を待機
        task_result = self.wait_for_task_completion(mcp_server_url, task_id, task_config["expected_completion_time"])
        
        # タスク結果の検証
        self.validate_task_result(task_result, task_config["validation_criteria"])
        
        # 適切な形式で結果を保存
        output_file = self.save_task_result(task_result, task_id, task_config["name"], 
                                          output_dir / "completed" / "text_generation")
        print(f"✅ テスト結果保存: {output_file}")

    @pytest.mark.slow  
    def test_code_generation_task(self, worker_test_config, output_dir, mcp_server_url):
        """Worker のコード生成能力をテスト"""
        task_config = next(task for task in worker_test_config["test_tasks"] 
                          if task["name"] == "code_generation")
        
        task_content = self.load_task_content(Path("tests/fixtures") / task_config["file"])
        task_id = self.delegate_task_to_worker(mcp_server_url, task_content, task_config["priority"])
        
        # タスク完了を待機
        task_result = self.wait_for_task_completion(mcp_server_url, task_id, task_config["expected_completion_time"])
        
        # 結果を Python ファイルとして保存
        output_file = self.save_task_result(task_result, task_id, task_config["name"], 
                                          output_dir / "completed" / "code_generation")
        
        # コード固有の検証
        if isinstance(task_result, dict):
            result_text = task_result.get("output", str(task_result))
        else:
            result_text = str(task_result)
            
        for criterion in task_config["validation_criteria"]:
            if criterion == "contains 'def calculate_fibonacci'":
                assert "def calculate_fibonacci" in result_text, "Missing fibonacci function definition"
            elif criterion == "contains docstring":
                assert '"""' in result_text or "'''" in result_text, "Missing docstring"
            elif criterion == "contains error handling":
                assert ("try:" in result_text and "except" in result_text) or \
                       ("raise" in result_text) or ("ValueError" in result_text), "Missing error handling"
        
        print(f"✅ コード生成結果保存: {output_file}")

    @pytest.mark.slow
    def test_error_handling_task(self, worker_test_config, output_dir, mcp_server_url):
        """Worker のエラーハンドリング能力をテスト"""
        task_config = next(task for task in worker_test_config["test_tasks"] 
                          if task["name"] == "error_handling")
        
        task_content = self.load_task_content(Path("tests/fixtures") / task_config["file"])
        task_id = self.delegate_task_to_worker(mcp_server_url, task_content, task_config["priority"])
        
        # エラーハンドリングタスクなので少し長めのタイムアウト
        task_result = self.wait_for_task_completion(mcp_server_url, task_id, task_config["expected_completion_time"])
        
        # 結果をログ形式で保存
        output_file = self.save_task_result(task_result, task_id, task_config["name"], 
                                          output_dir / "completed" / "error_handling")
        
        # エラーハンドリング固有の検証
        result_text = task_result.get("output", str(task_result)) if isinstance(task_result, dict) else str(task_result)
        assert "error" in result_text.lower() or "エラー" in result_text, "Should contain error information"
        
        # 検証基準のチェック
        self.validate_task_result(task_result, task_config["validation_criteria"])
        
        print(f"✅ エラーハンドリング結果保存: {output_file}")

    @pytest.mark.slow
    @pytest.mark.concurrent
    def test_concurrent_worker_tasks(self, worker_test_config, output_dir, mcp_server_url):
        """複数 Worker の並行タスク処理をテスト"""
        # 並行実行用に複数のタスクを選択
        concurrent_tasks = worker_test_config["test_tasks"][:3]  # 最初の3つのタスク
        
        task_ids = []
        task_configs = {}
        
        # すべてのタスクを並行して投入
        for task_config in concurrent_tasks:
            task_content = self.load_task_content(Path("tests/fixtures") / task_config["file"])
            task_id = self.delegate_task_to_worker(mcp_server_url, task_content, task_config["priority"])
            task_ids.append(task_id)
            task_configs[task_id] = task_config
        
        # すべてのタスク完了を待機
        results = {}
        max_timeout = max(task["expected_completion_time"] for task in concurrent_tasks) + 30
        
        for task_id in task_ids:
            task_result = self.wait_for_task_completion(mcp_server_url, task_id, max_timeout)
            results[task_id] = task_result
            
            # 各結果を保存
            task_config = task_configs[task_id]
            output_file = self.save_task_result(task_result, task_id, task_config["name"], 
                                              output_dir / "completed" / task_config["name"])
            
            # 結果検証
            self.validate_task_result(task_result, task_config["validation_criteria"])
        
        # すべてのタスクが成功したことを確認
        assert len(results) == len(concurrent_tasks), f"Expected {len(concurrent_tasks)} results, got {len(results)}"
        
        for task_id, result in results.items():
            success = result.get("success", True) if isinstance(result, dict) else True
            assert success, f"Task {task_id} should have completed successfully"
            
        print(f"✅ 並行処理テスト完了: {len(results)}件")

    @pytest.mark.slow
    @pytest.mark.benchmark  
    def test_worker_performance_benchmarks(self, worker_test_config, output_dir):
        """Worker のパフォーマンスベンチマークをテスト"""
        benchmark_config = worker_test_config["performance_benchmarks"]
        
        # パフォーマンス結果ディレクトリ作成
        perf_dir = output_dir / "performance"
        perf_dir.mkdir(parents=True, exist_ok=True)
        
        # 一貫したベンチマーク用に simple_text_generation を使用
        simple_task = next(task for task in worker_test_config["test_tasks"] 
                          if task["name"] == "simple_text_generation")
        
        task_content = self.load_task_content(Path("tests/fixtures") / simple_task["file"])
        
        # 複数回実行してパフォーマンス測定
        execution_times = []
        success_count = 0
        total_tasks = 5
        
        for i in range(total_tasks):
            start_time = time.time()
            
            try:
                task_id = self.delegate_task_to_worker("http://localhost:8765", task_content, simple_task["priority"])
                task_result = self.wait_for_task_completion("http://localhost:8765", task_id, simple_task["expected_completion_time"])
                
                execution_time = time.time() - start_time
                execution_times.append(execution_time)
                
                # パフォーマンステスト結果保存
                output_file = self.save_task_result(task_result, task_id, f"performance_test_{i+1}", 
                                                  perf_dir / f"benchmark_run_{i+1}")
                
                # 成功判定
                success = task_result.get("success", True) if isinstance(task_result, dict) else True
                if success:
                    success_count += 1
                    
            except Exception as e:
                print(f"Task {i+1} failed: {e}")
                execution_times.append(float('inf'))  # 失敗マーク
        
        # パフォーマンス指標計算
        valid_times = [t for t in execution_times if t != float('inf')]
        if valid_times:
            average_time = sum(valid_times) / len(valid_times)
        else:
            average_time = float('inf')
            
        success_rate = success_count / total_tasks
        
        # パフォーマンスレポート作成
        performance_report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": total_tasks,
            "successful_tasks": success_count,
            "success_rate": success_rate,
            "average_execution_time": average_time,
            "execution_times": execution_times,
            "benchmark_thresholds": {
                "average_completion_time": benchmark_config["average_task_completion_time"],
                "success_rate_threshold": benchmark_config["success_rate_threshold"]
            },
            "performance_assessment": {
                "time_performance": "PASS" if average_time <= benchmark_config["average_task_completion_time"] else "FAIL",
                "success_rate_performance": "PASS" if success_rate >= benchmark_config["success_rate_threshold"] else "FAIL"
            }
        }
        
        # レポート保存
        report_file = perf_dir / "benchmark_results.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(performance_report, f, indent=2, ensure_ascii=False)
        
        # ベンチマーク基準の検証
        assert success_rate >= benchmark_config["success_rate_threshold"], \
            f"Success rate {success_rate:.2%} below threshold {benchmark_config['success_rate_threshold']:.2%}"
        
        assert average_time <= benchmark_config["average_task_completion_time"], \
            f"Average time {average_time:.1f}s exceeds threshold {benchmark_config['average_task_completion_time']}s"
        
        print(f"✅ パフォーマンスベンチマーク完了:")
        print(f"  成功率: {success_rate:.2%} (基準: {benchmark_config['success_rate_threshold']:.2%})")
        print(f"  平均時間: {average_time:.1f}s (基準: {benchmark_config['average_task_completion_time']}s)")
        print(f"  結果保存: {report_file}")