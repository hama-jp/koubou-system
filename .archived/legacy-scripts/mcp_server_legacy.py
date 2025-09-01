#!/usr/bin/env python3
"""工房システム MCPサーバー - エージェント間連携"""

import json
import os
import sys
import subprocess
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from pathlib import Path

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.database import get_db_manager

app = Flask(__name__)
CORS(app)  # CORS設定を追加
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '.koubou')
PROJECT_ROOT = os.path.dirname(KOUBOU_HOME)
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
CODEX_EXEC = f"{KOUBOU_HOME}/scripts/codex-exec.sh"

# データベースマネージャーを初期化
db = get_db_manager(DB_PATH)

print(f"Starting MCP Server...")
print(f"KOUBOU_HOME: {KOUBOU_HOME}")
print(f"DB_PATH: {DB_PATH}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

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
    """タスクを委譲（Codex CLIまたはローカルワーカーへ）"""
    # タスク委託前の自動git保存
    auto_git_save()
    
    data = request.json
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    # タスクタイプを判定
    task_type = data.get('type', 'general')
    priority = data.get('priority', 5)
    
    # タスク内容を準備
    task_content = {
        'type': task_type,
        'prompt': data.get('content', data.get('prompt', '')),  # content または prompt
        'files': data.get('files', []),
        'options': data.get('options', {})
    }
    
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
    """タスクを同期的に実行（Codex CLI経由）"""
    prompt = task_content.get('prompt')
    
    # 全てのタスクをCodex CLI経由で実行（セキュアモード）
    # セキュアなCodexスクリプトを使用
    CODEX_SECURE = os.path.join(KOUBOU_HOME, 'scripts', 'codex-secure.sh')
    
    try:
        # 一時ファイルに出力をリダイレクトしてTTY問題を回避
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp_out:
            out_file = tmp_out.name
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp_err:
            err_file = tmp_err.name
        
        # TTYを維持するために標準入出力をファイルにリダイレクト
        cmd = f"{CODEX_SECURE} '{prompt}' > {out_file} 2> {err_file}"
        
        result = subprocess.run(
            cmd,
            shell=True,
            timeout=60,
            cwd=PROJECT_ROOT  # プロジェクトルートで実行
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
            'output': stdout,
            'error': stderr if result.returncode != 0 else None
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Codex task execution timed out'
        }
    except FileNotFoundError:
        return {
            'success': False,
            'output': '',
            'error': 'Codex secure script not found or not executable'
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': f'Unexpected error in codex execution: {str(e)}'
        }

@app.route('/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status, result FROM task_master WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return jsonify({"task_id": task_id, "status": row[0], "result": row[1]})
    else:
        return jsonify({"error": "Task not found"}), 404

@app.route('/tasks', methods=['GET'])
def list_tasks():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT task_id, status, created_at 
        FROM task_master 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    tasks = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "tasks": [
            {"task_id": t[0], "status": t[1], "created_at": t[2]}
            for t in tasks
        ]
    })

@app.route('/tasks/active', methods=['GET'])
def list_active_tasks():
    """アクティブタスクのリストを取得"""
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)  # 最大100件に制限
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT task_id, content, status, priority, 
                   created_by, assigned_to, created_at, updated_at
            FROM task_master 
            WHERE status IN ('pending', 'in_progress', 'processing')
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        tasks = cursor.fetchall()
    
    # contentから要約を抽出
    result_tasks = []
    for t in tasks:
        try:
            content_obj = json.loads(t[1]) if isinstance(t[1], str) else t[1]
            summary = content_obj.get('prompt', content_obj.get('content', ''))
            if len(summary) > 80:
                summary = summary[:80] + '...'
        except:
            summary = 'タスク内容取得エラー'
            
        result_tasks.append({
            "task_id": t[0],
            "content": t[1], 
            "status": t[2],
            "priority": t[3],
            "summary": summary,
            "created_by": t[4],
            "assigned_to": t[5],
            "created_at": t[6],
            "updated_at": t[7]
        })
    
    return jsonify(result_tasks)

@app.route('/tasks/completed', methods=['GET'])
def list_completed_tasks():
    """完了済みタスクのリストを取得"""
    limit = request.args.get('limit', 10, type=int)
    limit = min(limit, 100)  # 最大100件に制限
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT task_id, content, status, priority, result, 
                   created_by, assigned_to, created_at, updated_at
            FROM task_master 
            WHERE status IN ('completed', 'failed')
            ORDER BY updated_at DESC 
            LIMIT ?
        """, (limit,))
        tasks = cursor.fetchall()
    
    return jsonify([
        {
            "task_id": t[0],
            "content": t[1], 
            "status": t[2],
            "priority": t[3],
            "result": t[4],
            "created_by": t[5],
            "assigned_to": t[6],
            "created_at": t[7],
            "updated_at": t[8]
        }
        for t in tasks
    ])

if __name__ == '__main__':
    print(f"MCPサーバー起動 (KOUBOU_HOME: {KOUBOU_HOME})")
    print(f"http://0.0.0.0:8765")
    app.run(host='0.0.0.0', port=8765, debug=True)