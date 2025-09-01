#!/usr/bin/env python3
"""工房システム MCPサーバー - Gemini CLI版"""

import json
import os
import sys
import subprocess
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from pathlib import Path
import tempfile

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.database import get_db_manager

app = Flask(__name__)
CORS(app)
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '.koubou')
PROJECT_ROOT = os.path.dirname(KOUBOU_HOME)
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
GEMINI_EXEC = f"{KOUBOU_HOME}/scripts/gemini-exec.sh"

# データベースマネージャーを初期化
db = get_db_manager(DB_PATH)

print(f"Starting Koubou MCP Server...")
print(f"KOUBOU_HOME: {KOUBOU_HOME}")
print(f"DB_PATH: {DB_PATH}")
print(f"GEMINI_EXEC: {GEMINI_EXEC}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "server": "koubou-mcp", "timestamp": datetime.now().isoformat()})

def auto_git_save():
    """タスク委託前の自動git保存"""
    try:
        # 変更があるかチェック
        result = subprocess.run(['git', 'diff', '--exit-code'], 
                              cwd=PROJECT_ROOT, capture_output=True)
        if result.returncode != 0:  # 変更がある場合
            # ファイルを追加
            subprocess.run(['git', 'add', '.'], cwd=PROJECT_ROOT, check=True)
            # コミット
            commit_msg = f"🏭 Auto-save before task delegation - {datetime.now().isoformat()}"
            subprocess.run(['git', 'commit', '-m', commit_msg], 
                         cwd=PROJECT_ROOT, check=True)
            app.logger.info(f"Auto-saved changes to git: {commit_msg}")
            return True
    except Exception as e:
        app.logger.warning(f"Git auto-save failed: {str(e)}")
        return False
    return False  # 変更なし

@app.route('/task/delegate', methods=['POST'])
def delegate_task():
    """タスクを委譲（Gemini CLI経由）"""
    # タスク委託前の自動git保存
    auto_git_save()
    
    app.logger.info(f"Request method: {request.method}")
    app.logger.info(f"Content-Type: {request.headers.get('Content-Type')}")
    app.logger.info(f"Raw data: {request.data}")
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        app.logger.info(f"Received task data: {data}")
        
    except Exception as e:
        app.logger.error(f"Failed to parse JSON: {str(e)}")
        return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400
    
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    # タスクタイプを判定
    task_type = data.get('type', 'general')
    priority = data.get('priority', 5)
    
    # タスク内容を準備
    task_content = {
        'type': task_type,
        'prompt': data.get('content', data.get('prompt', '')),
        'files': data.get('files', []),
        'output_file': data.get('output_file'),
        'options': data.get('options', {})
    }
    
    if not task_content['prompt']:
        return jsonify({"error": "No prompt provided"}), 400
    
    task_content_json = json.dumps(task_content)
    
    # DBに保存
    if not db.create_task(
        task_id=task_id,
        content=task_content_json,
        priority=priority,
        created_by='claude_code'
    ):
        return jsonify({"error": "Failed to create task"}), 500
    
    # 即座に実行する場合（同期モード）
    if data.get('sync', False):
        result = execute_task_sync(task_id, task_content)
        db.update_task_status(
            task_id=task_id,
            status='completed',
            result=json.dumps(result)
        )
        return jsonify({
            "task_id": task_id, 
            "status": "completed",
            "result": result
        })
    
    return jsonify({"task_id": task_id, "status": "delegated"})

def execute_task_sync(task_id, task_content):
    """タスクを同期的に実行（Gemini CLI経由）"""
    prompt = task_content.get('prompt')
    
    if not prompt:
        return {
            'success': False,
            'output': '',
            'error': 'No prompt provided'
        }
    
    try:
        # 一時ファイルに出力をリダイレクト
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp_out:
            out_file = tmp_out.name
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp_err:
            err_file = tmp_err.name
        
        # Gemini CLIを実行
        cmd = f"{GEMINI_EXEC} '{prompt}' > {out_file} 2> {err_file}"
        
        result = subprocess.run(
            cmd,
            shell=True,
            timeout=120,  # Gemini CLIは少し時間がかかる場合がある
            cwd=PROJECT_ROOT
        )
        
        # ファイルから出力を読み取り
        with open(out_file, 'r') as f:
            stdout = f.read()
        with open(err_file, 'r') as f:
            stderr = f.read()
        
        # 一時ファイルを削除
        os.unlink(out_file)
        os.unlink(err_file)
        
        return {
            'success': result.returncode == 0,
            'output': stdout.strip(),
            'error': stderr.strip() if result.returncode != 0 else None
        }
    
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Gemini CLI task execution timed out'
        }
    except FileNotFoundError:
        return {
            'success': False,
            'output': '',
            'error': f'Gemini CLI script not found: {GEMINI_EXEC}'
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': f'Unexpected error: {str(e)}'
        }

@app.route('/task/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """タスクステータスを取得"""
    task_data = db.get_task(task_id)
    if task_data:
        return jsonify({
            "task_id": task_id,
            "status": task_data.get('status'),
            "result": json.loads(task_data.get('result', '{}')) if task_data.get('result') else None,
            "created_at": task_data.get('created_at'),
            "updated_at": task_data.get('updated_at')
        })
    else:
        return jsonify({"error": "Task not found"}), 404

@app.route('/workers/status', methods=['GET'])
def get_workers_status():
    """ワーカーステータスを取得"""
    workers = db.get_all_workers()
    return jsonify({"workers": workers})

@app.route('/tasks/pending', methods=['GET'])
def get_pending_tasks():
    """保留中のタスクを取得"""
    limit = request.args.get('limit', 10, type=int)
    tasks = db.get_pending_tasks(limit=limit)
    return jsonify(tasks)

@app.route('/tasks/completed', methods=['GET'])
def get_completed_tasks():
    """完了済みタスクを取得"""
    limit = request.args.get('limit', 10, type=int)
    try:
        # DatabaseManagerを使用してタスクを取得
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, content, status, priority, result, 
                       created_by, assigned_to, created_at, updated_at
                FROM task_master 
                WHERE status = 'completed'
                ORDER BY updated_at DESC 
                LIMIT ?
            """, (limit,))
            
            tasks = [dict(row) for row in cursor.fetchall()]
        
        # サマリー情報を追加
        tasks = db.get_task_summary(tasks)
        
        # 必要なフィールドを整形
        for task in tasks:
            task['content'] = task.get('content', '')  # 元のcontent追加
        
        return jsonify(tasks)
        
    except Exception as e:
        logger.error(f"Failed to get completed tasks: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/tasks/active', methods=['GET'])
def get_active_tasks():
    """アクティブタスクを取得"""
    limit = request.args.get('limit', 10, type=int)
    try:
        # DatabaseManagerを使用してタスクを取得
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, content, status, priority, result, 
                       created_by, assigned_to, created_at, updated_at
                FROM task_master 
                WHERE status IN ('pending', 'in_progress', 'processing')
                ORDER BY priority DESC, created_at DESC
                LIMIT ?
            """, (limit,))
            
            tasks = [dict(row) for row in cursor.fetchall()]
        
        # サマリー情報を追加
        tasks = db.get_task_summary(tasks)
        
        return jsonify(tasks)
        
    except Exception as e:
        logger.error(f"Failed to get active tasks: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/system/info', methods=['GET'])
def system_info():
    """システム情報を取得"""
    return jsonify({
        "server_type": "koubou-mcp",
        "koubou_home": KOUBOU_HOME,
        "project_root": PROJECT_ROOT,
        "gemini_exec": GEMINI_EXEC,
        "db_path": DB_PATH,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port, debug=False)