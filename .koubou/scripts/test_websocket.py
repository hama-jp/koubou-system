#!/usr/bin/env python3
"""
WebSocketクライアントテスト
"""

import asyncio
import json
import websockets
from datetime import datetime

async def test_client():
    """テストクライアント"""
    uri = "ws://localhost:8766"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")
            
            # タスクチャンネルに購読
            await websocket.send(json.dumps({
                'command': 'subscribe',
                'channel': 'task'
            }))
            
            # ワーカーチャンネルに購読
            await websocket.send(json.dumps({
                'command': 'subscribe',
                'channel': 'worker'
            }))
            
            # システムチャンネルに購読
            await websocket.send(json.dumps({
                'command': 'subscribe',
                'channel': 'system'
            }))
            
            # 統計情報を要求
            await websocket.send(json.dumps({
                'command': 'get_stats'
            }))
            
            # Pingテスト
            await websocket.send(json.dumps({
                'command': 'ping'
            }))
            
            print("\n📡 Listening for messages... (Press Ctrl+C to stop)\n")
            
            # メッセージを受信
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get('type')
                timestamp = data.get('timestamp', '')
                
                if msg_type == 'initial_state':
                    print(f"[{timestamp}] 📊 Initial State:")
                    print(f"  Tasks: {data['data']['tasks']}")
                    print(f"  Workers: {data['data']['workers']}")
                
                elif msg_type == 'subscribed':
                    print(f"[{timestamp}] ✅ Subscribed to: {data['channel']}")
                
                elif msg_type == 'task_update':
                    print(f"[{timestamp}] 📝 Task Update: {data['task_id']} -> {data['status']}")
                
                elif msg_type == 'worker_update':
                    print(f"[{timestamp}] 👷 Worker Update: {data['worker_id']} -> {data['status']}")
                
                elif msg_type == 'system_event':
                    print(f"[{timestamp}] 🔔 System Event: {data['event']}")
                
                elif msg_type == 'periodic_stats':
                    print(f"[{timestamp}] 📈 Periodic Stats:")
                    print(f"  Tasks: {data['data']['tasks']}")
                    print(f"  Active Workers: {data['data']['workers'].get('total_workers', 0)}")
                    print(f"  Connections: {data['data']['active_connections']}")
                
                elif msg_type == 'stats':
                    print(f"[{timestamp}] 📊 Current Stats:")
                    print(f"  {json.dumps(data['data'], indent=2)}")
                
                elif msg_type == 'pong':
                    print(f"[{timestamp}] 🏓 Pong received")
                
                else:
                    print(f"[{timestamp}] ❓ Unknown message type: {msg_type}")
                    print(f"  {json.dumps(data, indent=2)}")
                
                print("-" * 50)
    
    except websockets.exceptions.ConnectionRefused:
        print("❌ Could not connect to WebSocket server")
        print("Make sure the WebSocket server is running:")
        print("  python .koubou/scripts/websocket_server.py")
    except KeyboardInterrupt:
        print("\n👋 Disconnecting...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 WebSocket Client Test")
    print("=" * 50)
    asyncio.run(test_client())