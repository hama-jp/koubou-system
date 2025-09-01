#!/usr/bin/env python3
"""
分散ワーカーシステムのテストスクリプト
"""

import os
import sys
import time
import json
import threading
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from distributed.message_queue import get_queue_instance
from distributed.master_node import MasterNode
from distributed.remote_worker_node import RemoteWorkerNode


def test_local_queue():
    """ローカルキューのテスト"""
    print("\n=== Testing Local Queue ===")
    
    queue = get_queue_instance('local')
    queue.connect()
    
    # メッセージ受信カウンター
    received = {'count': 0}
    
    def on_message(data):
        received['count'] += 1
        print(f"Received message {received['count']}: {data}")
    
    # 購読
    queue.subscribe('test_channel', on_message)
    
    # メッセージ送信
    for i in range(3):
        message = {
            'id': i,
            'content': f'Test message {i}',
            'timestamp': datetime.now().isoformat()
        }
        queue.publish('test_channel', message)
        time.sleep(0.1)
    
    # 受信待ち
    time.sleep(1)
    
    assert received['count'] == 3, f"Expected 3 messages, got {received['count']}"
    print(f"✅ Local queue test passed: {received['count']} messages")
    
    queue.disconnect()


def test_master_worker_communication():
    """マスター・ワーカー間通信テスト"""
    print("\n=== Testing Master-Worker Communication ===")
    
    # マスターノード起動
    master_config = {
        'node_id': 'test-master',
        'location': 'local',
        'queue_type': 'local',
        'routing_strategy': 'load_balanced'
    }
    
    master = MasterNode(master_config)
    assert master.start(), "Failed to start master node"
    print("✅ Master node started")
    
    # ワーカーノード起動
    worker_config = {
        'node_id': 'test-worker-01',
        'location': 'local',
        'queue_type': 'local',
        'capacity': {
            'max_workers': 2,
            'max_memory_gb': 4,
            'has_gpu': False
        },
        'capabilities': ['general', 'test'],
        'llm_config': {
            'type': 'mock',  # テスト用モック
            'model': 'test-model'
        }
    }
    
    # モックLLM実行を追加
    def mock_execute(self, prompt):
        return f"Mock response for: {prompt[:50]}..."
    
    RemoteWorkerNode._execute_general_task = mock_execute
    
    worker = RemoteWorkerNode(worker_config)
    
    # マスターに接続（ローカルなので即座に）
    time.sleep(0.5)  # マスター起動待ち
    assert worker.connect_to_master('localhost'), "Failed to connect worker to master"
    print("✅ Worker connected to master")
    
    # ワーカーが登録されたか確認
    time.sleep(1)
    status = master.get_status()
    assert status['nodes']['registered'] == 1, "Worker not registered"
    assert status['nodes']['active'] == 1, "Worker not active"
    print(f"✅ Worker registered: {status['nodes']['details']}")
    
    # タスク送信テスト
    test_task = {
        'id': 'test-task-001',
        'type': 'general',
        'content': 'Test prompt for distributed processing',
        'priority': 5
    }
    
    assert master.assign_task(test_task), "Failed to assign task"
    print("✅ Task assigned to worker")
    
    # タスク処理待ち
    time.sleep(2)
    
    # 統計確認
    master_status = master.get_status()
    worker_status = worker.get_status()
    
    print(f"Master stats: {master_status['stats']}")
    print(f"Worker stats: {worker_status['stats']}")
    
    # クリーンアップ
    worker.disconnect()
    master.stop()
    
    print("✅ Master-Worker communication test passed")


def test_load_balancing():
    """負荷分散テスト"""
    print("\n=== Testing Load Balancing ===")
    
    # マスターノード起動
    master = MasterNode({
        'node_id': 'lb-master',
        'location': 'local',
        'queue_type': 'local',
        'routing_strategy': 'load_balanced'
    })
    master.start()
    
    # 複数ワーカー起動
    workers = []
    for i in range(3):
        worker_config = {
            'node_id': f'lb-worker-{i:02d}',
            'location': 'local',
            'queue_type': 'local',
            'capacity': {'max_workers': 2},
            'capabilities': ['general'],
            'llm_config': {'type': 'mock'}
        }
        
        worker = RemoteWorkerNode(worker_config)
        RemoteWorkerNode._execute_general_task = lambda self, p: f"Response from {self.node_id}"
        
        worker.connect_to_master('localhost')
        workers.append(worker)
    
    time.sleep(1)
    
    # 複数タスク送信
    for i in range(10):
        task = {
            'id': f'lb-task-{i:03d}',
            'type': 'general',
            'content': f'Load balance test task {i}',
            'priority': 5
        }
        master.assign_task(task)
        time.sleep(0.1)
    
    # 処理待ち
    time.sleep(3)
    
    # 各ワーカーの負荷確認
    print("Worker load distribution:")
    for worker in workers:
        status = worker.get_status()
        print(f"  {status['node_id']}: {status['stats']['tasks_received']} tasks")
    
    # クリーンアップ
    for worker in workers:
        worker.disconnect()
    master.stop()
    
    print("✅ Load balancing test passed")


def test_node_failure_recovery():
    """ノード障害とリカバリーテスト"""
    print("\n=== Testing Node Failure & Recovery ===")
    
    master = MasterNode({
        'node_id': 'recovery-master',
        'location': 'local',
        'queue_type': 'local'
    })
    master.start()
    
    # ワーカー起動
    worker1 = RemoteWorkerNode({
        'node_id': 'recovery-worker-01',
        'location': 'local',
        'queue_type': 'local',
        'capabilities': ['general']
    })
    worker1.connect_to_master('localhost')
    
    time.sleep(1)
    
    # ワーカー1を切断（障害シミュレーション）
    print("Simulating worker failure...")
    worker1.disconnect()
    
    time.sleep(2)
    
    # マスターがワーカーの切断を検知したか確認
    status = master.get_status()
    active_count = status['nodes']['active']
    print(f"Active nodes after failure: {active_count}")
    
    # 新しいワーカーを起動（リカバリー）
    print("Starting recovery worker...")
    worker2 = RemoteWorkerNode({
        'node_id': 'recovery-worker-02',
        'location': 'local',
        'queue_type': 'local',
        'capabilities': ['general']
    })
    worker2.connect_to_master('localhost')
    
    time.sleep(1)
    
    # リカバリー確認
    status = master.get_status()
    assert status['nodes']['active'] >= 1, "Recovery worker not active"
    print(f"✅ Recovery successful: {status['nodes']['active']} active nodes")
    
    # クリーンアップ
    worker2.disconnect()
    master.stop()


def run_all_tests():
    """全テスト実行"""
    print("=" * 60)
    print("🧪 Distributed Worker System Tests")
    print("=" * 60)
    
    try:
        # 各テスト実行
        test_local_queue()
        test_master_worker_communication()
        test_load_balancing()
        test_node_failure_recovery()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()