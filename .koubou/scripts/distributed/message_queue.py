#!/usr/bin/env python3
"""
メッセージキューインターフェース - 分散ワーカー通信基盤
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Dict
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageQueueInterface(ABC):
    """メッセージキューの抽象インターフェース"""
    
    @abstractmethod
    def connect(self, **config) -> bool:
        """接続を確立"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """接続を切断"""
        pass
    
    @abstractmethod
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """メッセージを発行"""
        pass
    
    @abstractmethod
    def subscribe(self, channel: str, callback: Callable) -> bool:
        """チャンネルを購読"""
        pass
    
    @abstractmethod
    def unsubscribe(self, channel: str) -> bool:
        """購読を解除"""
        pass
    
    @abstractmethod
    def get_queue_size(self, channel: str) -> int:
        """キューサイズを取得"""
        pass


class RedisQueue(MessageQueueInterface):
    """Redis実装"""
    
    def __init__(self):
        self.redis_client = None
        self.pubsub = None
        self.subscriptions = {}
        
    def connect(self, host='localhost', port=6379, db=0, **kwargs) -> bool:
        """Redis接続を確立"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                **kwargs
            )
            self.pubsub = self.redis_client.pubsub()
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Redis接続を切断"""
        try:
            if self.pubsub:
                self.pubsub.close()
            if self.redis_client:
                self.redis_client.close()
            logger.info("Disconnected from Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect from Redis: {e}")
            return False
    
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """メッセージを発行"""
        try:
            # メッセージにタイムスタンプを追加
            message['timestamp'] = datetime.now().isoformat()
            
            # JSONシリアライズ
            message_str = json.dumps(message)
            
            # Pub/Subチャンネルに発行
            self.redis_client.publish(channel, message_str)
            
            # キューにも追加（永続化）
            queue_key = f"queue:{channel}"
            self.redis_client.lpush(queue_key, message_str)
            
            # キューサイズ制限（最新1000件を保持）
            self.redis_client.ltrim(queue_key, 0, 999)
            
            logger.debug(f"Published message to {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
    
    def subscribe(self, channel: str, callback: Callable) -> bool:
        """チャンネルを購読"""
        try:
            self.pubsub.subscribe(channel)
            self.subscriptions[channel] = callback
            
            # 購読スレッドを開始
            import threading
            thread = threading.Thread(
                target=self._listen_channel,
                args=(channel, callback),
                daemon=True
            )
            thread.start()
            
            logger.info(f"Subscribed to channel: {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            return False
    
    def _listen_channel(self, channel: str, callback: Callable):
        """チャンネルをリッスン"""
        for message in self.pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    callback(data)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
    
    def unsubscribe(self, channel: str) -> bool:
        """購読を解除"""
        try:
            self.pubsub.unsubscribe(channel)
            if channel in self.subscriptions:
                del self.subscriptions[channel]
            logger.info(f"Unsubscribed from channel: {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False
    
    def get_queue_size(self, channel: str) -> int:
        """キューサイズを取得"""
        try:
            queue_key = f"queue:{channel}"
            return self.redis_client.llen(queue_key)
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0


class RabbitMQQueue(MessageQueueInterface):
    """RabbitMQ実装"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        
    def connect(self, host='localhost', port=5672, **kwargs) -> bool:
        """RabbitMQ接続を確立"""
        try:
            import pika
            parameters = pika.ConnectionParameters(
                host=host,
                port=port,
                **kwargs
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info(f"Connected to RabbitMQ at {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False
    
    def disconnect(self) -> bool:
        """RabbitMQ接続を切断"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Disconnected from RabbitMQ")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect from RabbitMQ: {e}")
            return False
    
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """メッセージを発行"""
        try:
            # キューを宣言（存在しない場合作成）
            self.channel.queue_declare(queue=channel, durable=True)
            
            # メッセージにタイムスタンプを追加
            message['timestamp'] = datetime.now().isoformat()
            
            # JSONシリアライズ
            message_str = json.dumps(message)
            
            # メッセージを発行
            self.channel.basic_publish(
                exchange='',
                routing_key=channel,
                body=message_str,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 永続化
                )
            )
            
            logger.debug(f"Published message to {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
    
    def subscribe(self, channel: str, callback: Callable) -> bool:
        """チャンネルを購読"""
        try:
            # キューを宣言
            self.channel.queue_declare(queue=channel, durable=True)
            
            # コールバックラッパー
            def wrapper(ch, method, properties, body):
                try:
                    data = json.loads(body)
                    callback(data)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag)
            
            # 購読開始
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=channel,
                on_message_callback=wrapper,
                auto_ack=False
            )
            
            # 消費開始（別スレッド推奨）
            import threading
            thread = threading.Thread(
                target=self.channel.start_consuming,
                daemon=True
            )
            thread.start()
            
            logger.info(f"Subscribed to queue: {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            return False
    
    def unsubscribe(self, channel: str) -> bool:
        """購読を解除"""
        try:
            self.channel.stop_consuming()
            logger.info(f"Unsubscribed from queue: {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False
    
    def get_queue_size(self, channel: str) -> int:
        """キューサイズを取得"""
        try:
            method = self.channel.queue_declare(
                queue=channel,
                durable=True,
                passive=True
            )
            return method.method.message_count
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0


class LocalQueue(MessageQueueInterface):
    """ローカルファイルベース実装（開発・テスト用、プロセス間対応）"""
    
    def __init__(self):
        import os
        import tempfile
        from collections import defaultdict
        
        # プロセス間通信用のファイルベースシステム
        koubou_home = os.environ.get('KOUBOU_HOME', tempfile.gettempdir())
        self.notifications_dir = os.path.join(koubou_home, 'notifications')
        os.makedirs(self.notifications_dir, exist_ok=True)
        
        self.subscribers = defaultdict(list)
        self.connected = False
        self.processed_files = set()
    
    def connect(self, **config) -> bool:
        """接続を確立（ダミー）"""
        self.connected = True
        logger.info("Connected to LocalQueue (in-memory)")
        return True
    
    def disconnect(self) -> bool:
        """接続を切断（ダミー）"""
        self.connected = False
        logger.info("Disconnected from LocalQueue")
        return True
    
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """メッセージを発行（ファイルベース、プロセス間対応）"""
        if not self.connected:
            return False
        
        try:
            # ファイルベースの通知作成
            notification_file = os.path.join(
                self.notifications_dir,
                f"{channel}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
            )
            
            # メッセージにタイムスタンプを追加
            message['timestamp'] = datetime.now().isoformat()
            message['channel'] = channel
            
            # ファイルに書き込み
            with open(notification_file, 'w', encoding='utf-8') as f:
                json.dump(message, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Published notification to file: {notification_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
    
    def subscribe(self, channel: str, callback: Callable) -> bool:
        """チャンネルを購読（ファイルベース）"""
        if not self.connected:
            return False
        
        self.subscribers[channel].append(callback)
        self.channel = channel
        self.callback = callback
        logger.info(f"Subscribed to channel: {channel}")
        return True
    
    def check_for_notifications(self):
        """ファイルベースの通知をチェック"""
        try:
            import glob
            import os
            pattern = os.path.join(self.notifications_dir, f"{self.channel}_*.json")
            notification_files = glob.glob(pattern)
            
            for file_path in notification_files:
                if file_path not in self.processed_files:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            notification = json.load(f)
                        
                        # コールバックを実行
                        self.callback(notification)
                        self.processed_files.add(file_path)
                        
                        # ファイルを削除（処理済み）
                        os.remove(file_path)
                        
                    except Exception as e:
                        logger.error(f"通知ファイル処理エラー {file_path}: {e}")
                        
        except Exception as e:
            logger.error(f"通知チェックエラー: {e}")
    
    def unsubscribe(self, channel: str) -> bool:
        """購読を解除"""
        if channel in self.subscribers:
            self.subscribers[channel].clear()
        logger.info(f"Unsubscribed from channel: {channel}")
        return True
    
    def get_queue_size(self, channel: str) -> int:
        """キューサイズを取得"""
        return len(self.queues[channel])


def get_queue_instance(queue_type: str = 'local') -> MessageQueueInterface:
    """キューインスタンスを取得"""
    if queue_type == 'redis':
        return RedisQueue()
    elif queue_type == 'rabbitmq':
        return RabbitMQQueue()
    else:
        return LocalQueue()


if __name__ == "__main__":
    # テスト実行
    import time
    
    # ローカルキューでテスト
    queue = get_queue_instance('local')
    queue.connect()
    
    # コールバック関数
    def on_message(data):
        print(f"Received: {data}")
    
    # 購読
    queue.subscribe('test_channel', on_message)
    
    # メッセージ発行
    for i in range(3):
        queue.publish('test_channel', {
            'id': i,
            'message': f'Test message {i}'
        })
        time.sleep(1)
    
    print(f"Queue size: {queue.get_queue_size('test_channel')}")
    
    # 切断
    queue.disconnect()