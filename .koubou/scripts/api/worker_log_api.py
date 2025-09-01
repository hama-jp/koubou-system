#!/usr/bin/env python3
"""
ワーカーログAPI - リアルタイムログ配信
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import re

# プロジェクトパス設定
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
sys.path.insert(0, os.path.join(KOUBOU_HOME, 'scripts'))

from common.database import get_db_manager

app = Flask(__name__)
CORS(app)

# ログディレクトリ
LOG_DIR = Path(f"{KOUBOU_HOME}/logs/workers")

# ログバッファ（メモリ内キャッシュ）
log_buffer = []
MAX_BUFFER_SIZE = 500  # 最大500エントリを保持

# データベース
db = get_db_manager(f"{KOUBOU_HOME}/db/koubou.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LogParser:
    """ログファイルを解析して構造化データに変換"""
    
    @staticmethod
    def parse_log_line(line: str, worker_id: str) -> Optional[Dict]:
        """ログ行を解析"""
        try:
            # タイムスタンプを抽出
            timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                message = line[len(timestamp):].strip()
            else:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message = line.strip()
            
            # ログレベルを判定
            log_type = 'info'
            if any(word in line.lower() for word in ['error', '❌', 'failed', 'exception']):
                log_type = 'error'
            elif any(word in line.lower() for word in ['warning', '⚠️', 'warn']):
                log_type = 'warning'
            elif any(word in line.lower() for word in ['success', '✅', 'completed']):
                log_type = 'success'
            elif any(word in line.lower() for word in ['processing', '🔄', 'generating']):
                log_type = 'processing'
            
            # トークン節約: 長いメッセージは切り詰め
            if len(message) > 200:
                message = message[:197] + '...'
            
            return {
                'timestamp': timestamp,
                'worker': worker_id,
                'type': log_type,
                'message': message
            }
        except Exception as e:
            logger.error(f"Failed to parse log line: {e}")
            return None


class LogMonitor:
    """ログファイルを監視してリアルタイム更新を検出"""
    
    def __init__(self):
        self.file_positions = {}  # ファイルごとの読み取り位置を記録
        self.running = True
        
    def monitor_worker_logs(self):
        """ワーカーログファイルを監視"""
        while self.running:
            try:
                # ログディレクトリ内のすべてのログファイルをチェック
                for log_file in LOG_DIR.glob("*.log"):
                    worker_id = log_file.stem
                    
                    # ファイルサイズをチェック
                    current_size = log_file.stat().st_size
                    last_position = self.file_positions.get(str(log_file), 0)
                    
                    # 新しいデータがある場合
                    if current_size > last_position:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            f.seek(last_position)
                            new_lines = f.readlines()
                            
                            for line in new_lines[-10:]:  # 最新10行のみ処理（トークン節約）
                                if line.strip():
                                    parsed = LogParser.parse_log_line(line, worker_id)
                                    if parsed:
                                        add_log_entry(parsed)
                            
                            self.file_positions[str(log_file)] = f.tell()
                    
                    # ファイルが縮小した場合（ローテーション等）
                    elif current_size < last_position:
                        self.file_positions[str(log_file)] = 0
                
            except Exception as e:
                logger.error(f"Log monitoring error: {e}")
            
            time.sleep(1)  # 1秒ごとにチェック


def add_log_entry(entry: Dict):
    """ログエントリをバッファに追加"""
    global log_buffer
    
    # タイムスタンプを追加
    if 'timestamp' not in entry:
        entry['timestamp'] = datetime.now().isoformat()
    
    log_buffer.append(entry)
    
    # バッファサイズ制限
    if len(log_buffer) > MAX_BUFFER_SIZE:
        log_buffer = log_buffer[-MAX_BUFFER_SIZE:]


@app.route('/api/logs/recent', methods=['GET'])
def get_recent_logs():
    """最近のログエントリを取得"""
    try:
        # パラメータ取得
        worker_id = request.args.get('worker')
        log_type = request.args.get('type')
        limit = min(int(request.args.get('limit', 100)), 200)  # 最大200件
        
        # フィルタリング
        filtered_logs = log_buffer
        
        if worker_id and worker_id != 'all':
            filtered_logs = [log for log in filtered_logs if log['worker'] == worker_id]
        
        if log_type:
            filtered_logs = [log for log in filtered_logs if log['type'] == log_type]
        
        # 最新のものから返す
        return jsonify({
            'status': 'success',
            'logs': filtered_logs[-limit:],
            'total': len(filtered_logs)
        })
        
    except Exception as e:
        logger.error(f"Error getting recent logs: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/logs/stats', methods=['GET'])
def get_log_stats():
    """ログ統計を取得"""
    try:
        stats = {
            'total_entries': len(log_buffer),
            'by_type': {},
            'by_worker': {},
            'message_rate': 0
        }
        
        # タイプ別集計
        for log in log_buffer:
            log_type = log.get('type', 'info')
            stats['by_type'][log_type] = stats['by_type'].get(log_type, 0) + 1
            
            worker = log.get('worker', 'unknown')
            stats['by_worker'][worker] = stats['by_worker'].get(worker, 0) + 1
        
        # 直近1分のメッセージレート計算
        one_minute_ago = datetime.now().timestamp() - 60
        recent_logs = [log for log in log_buffer 
                      if log.get('timestamp', '') > datetime.fromtimestamp(one_minute_ago).isoformat()]
        stats['message_rate'] = len(recent_logs) / 60  # messages per second
        
        return jsonify({
            'status': 'success',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/workers/status', methods=['GET'])
def get_workers_status():
    """ワーカーの現在の状態を取得"""
    try:
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT worker_id, location, status, performance_factor,
                       tasks_completed, tasks_failed, endpoint_url, current_task
                FROM workers
                WHERE datetime('now', '-120 seconds') <= last_heartbeat
                   OR status = 'idle'
                ORDER BY location, worker_id
            """)
            
            workers = []
            for row in cursor.fetchall():
                worker = {
                    'worker_id': row[0],
                    'location': row[1] or 'local',
                    'status': row[2] or 'offline',
                    'performance_factor': row[3] or 1.0,
                    'tasks_completed': row[4] or 0,
                    'tasks_failed': row[5] or 0,
                    'endpoint_url': row[6],
                    'current_task': row[7]
                }
                
                # 現在のタスク内容を取得
                if worker['current_task']:
                    task_cursor = conn.execute("""
                        SELECT content FROM task_master
                        WHERE task_id = ?
                    """, (worker['current_task'],))
                    task_row = task_cursor.fetchone()
                    if task_row:
                        try:
                            content = json.loads(task_row[0]) if task_row[0] else {}
                            worker['current_task_content'] = content.get('prompt', '')[:100]
                        except:
                            worker['current_task_content'] = str(task_row[0])[:100]
                
                workers.append(worker)
        
        return jsonify({
            'status': 'success',
            'workers': workers
        })
        
    except Exception as e:
        logger.error(f"Error getting workers status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/tasks/queue', methods=['GET'])
def get_task_queue():
    """タスクキューの状態を取得"""
    try:
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT task_id, priority, status, assigned_to, 
                       created_at, content
                FROM task_master
                WHERE status IN ('pending', 'in_progress')
                ORDER BY priority DESC, created_at ASC
                LIMIT 20
            """)
            
            tasks = []
            for row in cursor.fetchall():
                content_json = {}
                try:
                    content_json = json.loads(row[5]) if row[5] else {}
                except:
                    pass
                
                tasks.append({
                    'task_id': row[0],
                    'priority': row[1],
                    'status': row[2],
                    'assigned_to': row[3],
                    'created_at': row[4],
                    'type': content_json.get('type', 'general'),
                    'prompt_preview': content_json.get('prompt', '')[:50] + '...' if content_json.get('prompt', '') else ''
                })
            
            # 統計情報も追加
            cursor = conn.execute("""
                SELECT 
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_count,
                    COUNT(CASE WHEN status = 'completed' AND datetime('now', '-1 hour') <= updated_at THEN 1 END) as completed_last_hour
                FROM task_master
            """)
            stats = cursor.fetchone()
            
            return jsonify({
                'status': 'success',
                'tasks': tasks,
                'stats': {
                    'pending': stats[0] or 0,
                    'in_progress': stats[1] or 0,
                    'completed_last_hour': stats[2] or 0
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting task queue: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/logs/tail/<worker_id>', methods=['GET'])
def tail_worker_log(worker_id):
    """特定ワーカーのログをtail（最新部分を取得）"""
    try:
        log_file = LOG_DIR / f"{worker_id}.log"
        
        if not log_file.exists():
            return jsonify({
                'status': 'error',
                'message': f'Log file not found for worker {worker_id}'
            }), 404
        
        # 最後の50行を取得（トークン節約）
        lines = []
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-50:]
        
        # パース
        logs = []
        for line in lines:
            if line.strip():
                parsed = LogParser.parse_log_line(line, worker_id)
                if parsed:
                    logs.append(parsed)
        
        return jsonify({
            'status': 'success',
            'worker_id': worker_id,
            'logs': logs
        })
        
    except Exception as e:
        logger.error(f"Error tailing log for {worker_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


def main():
    """メインエントリーポイント"""
    # ログモニタースレッドを開始
    monitor = LogMonitor()
    monitor_thread = threading.Thread(target=monitor.monitor_worker_logs, daemon=True)
    monitor_thread.start()
    
    # 初期ログ
    add_log_entry({
        'worker': 'system',
        'type': 'success',
        'message': '🚀 Worker Log API started'
    })
    
    # APIサーバー起動
    logger.info("Starting Worker Log API on port 8768")
    app.run(host='0.0.0.0', port=8768, debug=False)


if __name__ == '__main__':
    main()