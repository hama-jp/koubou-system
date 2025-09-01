#!/usr/bin/env python3
"""
Redis通信テスト - 分散ワーカーシステム
"""

import sys
import os
import time
import threading

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from distributed.message_queue import RedisQueue


def test_redis_connection():
    """Redis接続テスト"""
    print("\n=== Testing Redis Connection ===")
    
    queue = RedisQueue()
    
    # 接続
    if queue.connect(host='localhost', port=6379):
        print("✅ Connected to Redis successfully")
    else:
        print("❌ Failed to connect to Redis")
        return False
    
    # Ping確認
    try:
        queue.redis_client.ping()
        print("✅ Redis is responding")
    except Exception as e:
        print(f"❌ Redis ping failed: {e}")
        return False
    
    queue.disconnect()
    return True


def test_redis_pubsub():
    """Redis Pub/Sub通信テスト"""
    print("\n=== Testing Redis Pub/Sub ===")
    
    # 送信側
    publisher = RedisQueue()
    publisher.connect()
    
    # 受信側
    subscriber = RedisQueue()
    subscriber.connect()
    
    # 受信メッセージ格納
    received_messages = []
    
    def on_message(data):
        received_messages.append(data)
        print(f"Received: {data}")
    
    # 購読開始
    subscriber.subscribe('test_channel', on_message)
    
    # 少し待つ（購読準備）
    time.sleep(0.5)
    
    # メッセージ送信
    for i in range(3):
        message = {
            'id': i,
            'content': f'Redis test message {i}'
        }
        publisher.publish('test_channel', message)
        time.sleep(0.1)
    
    # 受信待ち
    time.sleep(1)
    
    # 結果確認
    if len(received_messages) == 3:
        print(f"✅ All {len(received_messages)} messages received")
    else:
        print(f"❌ Expected 3 messages, got {len(received_messages)}")
    
    # クリーンアップ
    subscriber.unsubscribe('test_channel')
    publisher.disconnect()
    subscriber.disconnect()
    
    return len(received_messages) == 3


def test_redis_queue_persistence():
    """Redisキューの永続性テスト"""
    print("\n=== Testing Redis Queue Persistence ===")
    
    queue1 = RedisQueue()
    queue1.connect()
    
    # メッセージをキューに追加
    for i in range(5):
        message = {'id': i, 'content': f'Persistent message {i}'}
        queue1.publish('persist_test', message)
    
    # キューサイズ確認
    size = queue1.get_queue_size('persist_test')
    print(f"Queue size after publishing: {size}")
    
    queue1.disconnect()
    
    # 別の接続でキューを確認
    queue2 = RedisQueue()
    queue2.connect()
    
    size = queue2.get_queue_size('persist_test')
    print(f"Queue size from new connection: {size}")
    
    # キューをクリア
    queue2.redis_client.delete('queue:persist_test')
    
    queue2.disconnect()
    
    return size >= 5


def test_multiple_subscribers():
    """複数購読者テスト"""
    print("\n=== Testing Multiple Subscribers ===")
    
    publisher = RedisQueue()
    publisher.connect()
    
    # 複数の購読者
    subscribers = []
    received_counts = []
    
    for i in range(3):
        sub = RedisQueue()
        sub.connect()
        
        count = {'value': 0}
        received_counts.append(count)
        
        def make_callback(idx, counter):
            def callback(data):
                counter['value'] += 1
                print(f"Subscriber {idx} received: {data['id']}")
            return callback
        
        sub.subscribe('broadcast_channel', make_callback(i, count))
        subscribers.append(sub)
    
    # 購読準備待ち
    time.sleep(0.5)
    
    # ブロードキャストメッセージ送信
    for i in range(5):
        message = {'id': i, 'type': 'broadcast'}
        publisher.publish('broadcast_channel', message)
        time.sleep(0.1)
    
    # 受信待ち
    time.sleep(1)
    
    # 結果確認
    print("\nReceived counts:")
    for i, count in enumerate(received_counts):
        print(f"  Subscriber {i}: {count['value']} messages")
    
    # 全員が全メッセージを受信したか
    all_received = all(count['value'] == 5 for count in received_counts)
    
    if all_received:
        print("✅ All subscribers received all messages")
    else:
        print("❌ Not all messages were received by all subscribers")
    
    # クリーンアップ
    for sub in subscribers:
        sub.unsubscribe('broadcast_channel')
        sub.disconnect()
    publisher.disconnect()
    
    return all_received


def main():
    """メインテスト実行"""
    print("=" * 60)
    print("🔴 Redis Distributed Communication Test")
    print("=" * 60)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Redis Pub/Sub", test_redis_pubsub),
        ("Queue Persistence", test_redis_queue_persistence),
        ("Multiple Subscribers", test_multiple_subscribers)
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test '{name}' failed with error: {e}")
            results.append((name, False))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:.<40} {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 All Redis tests passed!")
    else:
        print("\n⚠️ Some tests failed")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())