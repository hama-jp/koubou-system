#!/usr/bin/env python3
"""
工房システム ベンチマークテストスイート
ワーカーの性能と機能を総合的に評価
"""

import json
import time
import requests
import statistics
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

# 設定
API_URL = "http://localhost:8765/task/delegate"
HEADERS = {"Content-Type": "application/json"}
TEST_DIR = Path("/home/hama/project/koubou-system/benchmark_test_files")

class BenchmarkTest:
    def __init__(self):
        self.results = []
        self.test_categories = {
            "file_operations": [],
            "text_generation": [],
            "code_generation": [],
            "analysis": [],
            "translation": []
        }
        
        # テストディレクトリを作成
        TEST_DIR.mkdir(exist_ok=True)
        
    def measure_task(self, task_name: str, prompt: str, category: str, sync: bool = True) -> Dict[str, Any]:
        """タスクを実行して測定"""
        print(f"  Testing: {task_name}...")
        
        payload = {
            "type": "general",
            "prompt": prompt,
            "sync": sync
        }
        
        start_time = time.time()
        try:
            response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=120)
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                success = result.get("result", {}).get("success", False) if sync else True
                output = result.get("result", {}).get("output", "") if sync else "Async task submitted"
                
                test_result = {
                    "name": task_name,
                    "category": category,
                    "success": success,
                    "time": elapsed_time,
                    "output_length": len(output),
                    "sync": sync
                }
                
                self.results.append(test_result)
                self.test_categories[category].append(test_result)
                
                return test_result
            else:
                print(f"    ❌ HTTP Error: {response.status_code}")
                return {"name": task_name, "success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return {"name": task_name, "success": False, "error": str(e)}
    
    def run_file_operation_tests(self):
        """ファイル操作テスト"""
        print("\n📁 File Operation Tests")
        print("=" * 50)
        
        # テスト1: ファイル作成
        self.measure_task(
            "Create test file",
            f"Create a file at {TEST_DIR}/test_output.txt with content 'Benchmark test file created at ' followed by the current timestamp",
            "file_operations"
        )
        
        # テスト2: ファイル読み取り
        self.measure_task(
            "Read file",
            f"Read the file at {TEST_DIR}/test_output.txt and tell me what it contains",
            "file_operations"
        )
        
        # テスト3: ディレクトリリスト
        self.measure_task(
            "List directory",
            f"List all files in the directory {TEST_DIR}",
            "file_operations"
        )
        
        # テスト4: 複数ファイル操作
        self.measure_task(
            "Multiple file operations",
            f"Create three files in {TEST_DIR}: file1.txt with 'First file', file2.txt with 'Second file', file3.txt with 'Third file'",
            "file_operations"
        )
    
    def run_text_generation_tests(self):
        """テキスト生成テスト"""
        print("\n📝 Text Generation Tests")
        print("=" * 50)
        
        # テスト1: 短文生成
        self.measure_task(
            "Short text (haiku)",
            "Write a haiku about distributed systems",
            "text_generation"
        )
        
        # テスト2: 中文生成
        self.measure_task(
            "Medium text (paragraph)",
            "Write a 100-word paragraph explaining microservices architecture",
            "text_generation"
        )
        
        # テスト3: 長文生成
        self.measure_task(
            "Long text (essay)",
            "Write a 500-word essay about the future of AI in software development",
            "text_generation"
        )
        
        # テスト4: リスト生成
        self.measure_task(
            "Structured list",
            "Create a numbered list of 10 best practices for Python programming",
            "text_generation"
        )
    
    def run_code_generation_tests(self):
        """コード生成テスト"""
        print("\n💻 Code Generation Tests")
        print("=" * 50)
        
        # テスト1: 簡単な関数
        self.measure_task(
            "Simple function",
            "Write a Python function to calculate factorial of a number",
            "code_generation"
        )
        
        # テスト2: クラス実装
        self.measure_task(
            "Class implementation",
            "Write a Python class for a simple todo list with add, remove, and list methods",
            "code_generation"
        )
        
        # テスト3: アルゴリズム
        self.measure_task(
            "Algorithm implementation",
            "Implement quicksort algorithm in Python with comments",
            "code_generation"
        )
        
        # テスト4: Web API
        self.measure_task(
            "REST API endpoint",
            "Write a Flask REST API endpoint for user registration with validation",
            "code_generation"
        )
    
    def run_analysis_tests(self):
        """分析タスクテスト"""
        print("\n🔍 Analysis Tests")
        print("=" * 50)
        
        # テスト1: 要約
        self.measure_task(
            "Text summarization",
            "Summarize the key concepts of object-oriented programming in 3 bullet points",
            "analysis"
        )
        
        # テスト2: 比較分析
        self.measure_task(
            "Comparison analysis",
            "Compare and contrast SQL and NoSQL databases, listing 3 advantages of each",
            "analysis"
        )
        
        # テスト3: 問題解決
        self.measure_task(
            "Problem solving",
            "A web application is running slowly. List 5 possible causes and solutions",
            "analysis"
        )
        
        # テスト4: 設計提案
        self.measure_task(
            "System design",
            "Design a high-level architecture for a real-time chat application",
            "analysis"
        )
    
    def run_translation_tests(self):
        """翻訳テスト"""
        print("\n🌐 Translation Tests")
        print("=" * 50)
        
        # テスト1: 技術文書翻訳（英→日）
        self.measure_task(
            "Technical translation (EN→JP)",
            "Translate to Japanese: 'Kubernetes is an open-source container orchestration platform that automates deployment, scaling, and management of containerized applications.'",
            "translation"
        )
        
        # テスト2: エラーメッセージ翻訳
        self.measure_task(
            "Error message translation",
            "Translate this error message to user-friendly Japanese: 'Error: Connection timeout. The server did not respond within the specified time limit.'",
            "translation"
        )
        
        # テスト3: ドキュメント翻訳
        self.measure_task(
            "Documentation translation",
            "Translate to Japanese and keep technical terms in English: 'To install Python packages, use pip install command. Virtual environments are recommended for project isolation.'",
            "translation"
        )
    
    def run_stress_test(self):
        """ストレステスト（非同期タスク）"""
        print("\n⚡ Stress Test (Async Tasks)")
        print("=" * 50)
        
        # 5つの非同期タスクを同時投入
        tasks = []
        for i in range(5):
            result = self.measure_task(
                f"Async task {i+1}",
                f"Generate a random 5-line poem about the number {i+1}",
                "text_generation",
                sync=False
            )
            tasks.append(result)
            time.sleep(0.5)  # 少し間隔を空ける
        
        return tasks
    
    def generate_report(self):
        """ベンチマークレポート生成"""
        print("\n" + "=" * 70)
        print("📊 BENCHMARK REPORT")
        print("=" * 70)
        
        # 全体統計
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.get("success", False))
        sync_tests = [r for r in self.results if r.get("sync", True)]
        
        print(f"\n📈 Overall Statistics:")
        print(f"  • Total tests: {total_tests}")
        print(f"  • Successful: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)")
        print(f"  • Average response time: {statistics.mean([r['time'] for r in sync_tests if 'time' in r]):.2f}s")
        
        # カテゴリ別統計
        print(f"\n📊 Category Performance:")
        for category, tests in self.test_categories.items():
            if tests:
                sync_category_tests = [t for t in tests if t.get("sync", True)]
                if sync_category_tests:
                    avg_time = statistics.mean([t['time'] for t in sync_category_tests if 'time' in t])
                    success_rate = sum(1 for t in tests if t.get("success", False)) / len(tests) * 100
                    print(f"\n  {category.upper()}:")
                    print(f"    • Tests: {len(tests)}")
                    print(f"    • Success rate: {success_rate:.1f}%")
                    print(f"    • Avg time: {avg_time:.2f}s")
                    
                    # 個別テスト結果
                    for test in sync_category_tests:
                        status = "✅" if test.get("success", False) else "❌"
                        print(f"      {status} {test['name']}: {test.get('time', 0):.2f}s")
        
        # ファイル操作能力評価
        file_ops = self.test_categories.get("file_operations", [])
        file_ops_success = sum(1 for t in file_ops if t.get("success", False))
        
        print(f"\n🔧 Special Capabilities:")
        if file_ops_success > 0:
            print(f"  ✅ File Operations: SUPPORTED ({file_ops_success}/{len(file_ops)} tests passed)")
        else:
            print(f"  ❌ File Operations: NOT SUPPORTED")
        
        # パフォーマンス評価
        print(f"\n⚡ Performance Rating:")
        avg_response = statistics.mean([r['time'] for r in sync_tests if 'time' in r])
        if avg_response < 5:
            rating = "EXCELLENT"
            stars = "⭐⭐⭐⭐⭐"
        elif avg_response < 10:
            rating = "GOOD"
            stars = "⭐⭐⭐⭐"
        elif avg_response < 20:
            rating = "AVERAGE"
            stars = "⭐⭐⭐"
        else:
            rating = "NEEDS IMPROVEMENT"
            stars = "⭐⭐"
        
        print(f"  • Rating: {rating} {stars}")
        print(f"  • Response time: {avg_response:.2f}s average")
        
        # 保存
        report_file = Path(f"/home/hama/project/koubou-system/benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_tests": total_tests,
                    "successful_tests": successful_tests,
                    "success_rate": successful_tests/total_tests*100 if total_tests > 0 else 0,
                    "average_response_time": avg_response,
                    "file_operations_supported": file_ops_success > 0
                },
                "categories": self.test_categories,
                "detailed_results": self.results
            }, f, indent=2)
        
        print(f"\n💾 Report saved to: {report_file}")
        print("=" * 70)
        
        return report_file


def main():
    """メインベンチマーク実行"""
    print("🏭 工房システム ベンチマークテスト")
    print("Starting at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # システム稼働確認
    print("\n🔍 Checking system status...")
    try:
        response = requests.get("http://localhost:8765/health", timeout=5)
        if response.status_code == 200:
            print("  ✅ MCP Server is running")
        else:
            print("  ❌ MCP Server is not responding properly")
            return
    except:
        print("  ❌ Cannot connect to MCP Server. Please start the system first.")
        print("  Run: .koubou/start_system.sh")
        return
    
    # ベンチマーク実行
    benchmark = BenchmarkTest()
    
    # 各テストカテゴリを実行
    benchmark.run_file_operation_tests()
    benchmark.run_text_generation_tests()
    benchmark.run_code_generation_tests()
    benchmark.run_analysis_tests()
    benchmark.run_translation_tests()
    benchmark.run_stress_test()
    
    # レポート生成
    report_file = benchmark.generate_report()
    
    print(f"\n✅ Benchmark completed successfully!")
    print(f"📊 Results saved to: {report_file}")


if __name__ == "__main__":
    main()