# 工房システム実装手順書 v2.0
## Claude Code + gpt-oss-20b 共通基盤実装

---

## 前提条件の確認

### 必要なソフトウェア
- [ ] Linux/WSL2環境
- [ ] Bash 4.0以上
- [ ] Python 3.8以上
- [ ] SQLite3
- [ ] inotify-tools
- [ ] jq（JSON処理用）
- [ ] Claude Code（インストール済み）
- [ ] LMStudio（gpt-oss-20bモデル導入済み）

### オプション（将来の拡張用）
- [ ] Codex-CLI（代替エージェント）
- [ ] Gemini-CLI（代替エージェント）

---

## Phase 1: 基本環境構築（Day 1-2）

### Step 1.1: ディレクトリ構造の作成

```bash
#!/bin/bash
# setup_directories.sh

# ベースディレクトリの作成
sudo mkdir -p /var/koubou/{config,tasks,logs,db,tmp,scripts}
sudo mkdir -p /var/koubou/tasks/{pending,in_progress,completed,failed}
sudo mkdir -p /var/koubou/logs/{agents,workers,system}
sudo mkdir -p /var/koubou/scripts/{adapters,workers,common}

# 権限設定
sudo chown -R $USER:$USER /var/koubou
chmod 755 /var/koubou
chmod 700 /var/koubou/config  # 設定ファイルは厳格な権限

echo "ディレクトリ構造を作成しました"
tree /var/koubou
```

### Step 1.2: SQLiteデータベースの初期化

```bash
#!/bin/bash
# init_database.sh

DB_PATH="/var/koubou/db/koubou.db"

# データベース作成
sqlite3 $DB_PATH << 'EOF'
-- エージェント管理テーブル
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL CHECK(agent_type IN ('claude-code', 'codex-cli', 'gemini-cli')),
    status TEXT NOT NULL CHECK(status IN ('active', 'inactive', 'error')),
    is_primary BOOLEAN DEFAULT FALSE,
    capabilities JSON,
    last_active TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- タスクマスターテーブル
CREATE TABLE IF NOT EXISTS task_master (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    difficulty_level TEXT DEFAULT 'medium',
    sensitivity_level TEXT DEFAULT 'public',
    assigned_agent_id TEXT,
    assigned_worker_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    content TEXT NOT NULL,
    context JSON,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_agent_id) REFERENCES agents(agent_id)
);

-- ワーカー管理テーブル
CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    worker_type TEXT NOT NULL DEFAULT 'local',
    model_name TEXT NOT NULL DEFAULT 'gpt-oss-20b',
    api_endpoint TEXT NOT NULL,
    process_id INTEGER,
    status TEXT NOT NULL DEFAULT 'offline',
    capabilities JSON,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- システムログテーブル
CREATE TABLE IF NOT EXISTS system_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,
    log_level TEXT CHECK(log_level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL')),
    message TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- エージェント間通信ログ
CREATE TABLE IF NOT EXISTS agent_communications (
    comm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    message_type TEXT NOT NULL,
    payload JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_task_status ON task_master(status);
CREATE INDEX IF NOT EXISTS idx_task_priority ON task_master(priority DESC);
CREATE INDEX IF NOT EXISTS idx_worker_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_log_timestamp ON system_logs(created_at DESC);

-- Claude Codeをプライマリエージェントとして登録
INSERT INTO agents (agent_id, agent_type, status, is_primary, capabilities)
VALUES ('claude_primary', 'claude-code', 'active', TRUE, 
        '{"mcp": true, "hooks": true, "tools": ["file", "bash", "web"]}');

PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
.exit
EOF

echo "データベースを初期化しました: $DB_PATH"
```

### Step 1.3: 設定ファイルの作成

```bash
#!/bin/bash
# create_configs.sh

# agent.yaml の作成（エージェント切替可能な設計）
cat > /var/koubou/config/agent.yaml << 'EOF'
# 工房システム設定
system:
  name: koubou-system
  version: 2.0

# 現在の親方エージェント
master_agent: claude-code

# 利用可能なエージェント
available_agents:
  - type: claude-code
    primary: true
    config:
      mcp_enabled: true
      hooks_enabled: true
  - type: codex-cli
    primary: false
    config:
      config_path: /var/koubou/config/codex-config.toml
  - type: gemini-cli
    primary: false
    config:
      project_path: /home/user/project

# ワーカー設定（実装テストではローカルのみ）
workers:
  - type: local
    model: gpt-oss-20b
    endpoint: http://localhost:1234/v1
    max_concurrent: 3
    
# セキュリティポリシー
security:
  sensitive_patterns:
    - password
    - secret
    - api_key
    - token
    - private_key
  
# タスクルーティング（実装テストでは全てローカル）
routing:
  default: local
  rules:
    - if: contains_sensitive_data
      then: local
    - else: local
EOF

# Claude Code用のMCP設定
cat > /var/koubou/config/claude_mcp_config.json << 'EOF'
{
  "mcpServers": {
    "koubou": {
      "command": "python3",
      "args": ["/var/koubou/scripts/mcp_server.py"],
      "env": {
        "KOUBOU_DB": "/var/koubou/db/koubou.db",
        "KOUBOU_HOME": "/var/koubou"
      }
    }
  }
}
EOF

echo "設定ファイルを作成しました"
```

### Step 1.4: 環境変数の設定

```bash
#!/bin/bash
# setup_environment.sh

# .envファイルの作成
cat > /var/koubou/config/.env << 'EOF'
# システム設定
KOUBOU_HOME=/var/koubou
KOUBOU_DB=/var/koubou/db/koubou.db
KOUBOU_LOG_LEVEL=INFO

# LMStudio設定
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=gpt-oss-20b

# エージェント設定
DEFAULT_AGENT=claude-code
AGENT_TIMEOUT=300

# ワーカー設定
MAX_WORKERS=3
WORKER_HEARTBEAT_INTERVAL=30
EOF

# 権限設定
chmod 600 /var/koubou/config/.env

# bashrcへの追加
echo "source /var/koubou/config/.env" >> ~/.bashrc

echo "環境変数を設定しました"
```

---

## Phase 2: 共通基盤の実装（Day 3-4）

### Step 2.1: エージェントアダプターの実装

```python
#!/usr/bin/env python3
# /var/koubou/scripts/adapters/agent_adapter.py

import os
import sys
import json
import subprocess
import sqlite3
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

class AgentInterface(ABC):
    """全エージェントの共通インターフェース"""
    
    def __init__(self):
        self.db_path = os.environ.get('KOUBOU_DB', '/var/koubou/db/koubou.db')
    
    @abstractmethod
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """タスクを実行"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """エージェントの状態を取得"""
        pass
    
    def delegate_task(self, task: Dict[str, Any], worker_type: str = 'local') -> str:
        """タスクを職人に委任（共通実装）"""
        task_id = f"task_{int(datetime.now().timestamp())}"
        
        # データベースに登録
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO task_master (task_id, task_type, content, context, 
                                   priority, status, created_by)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (task_id, task.get('type', 'general'), 
              task.get('content', ''), 
              json.dumps(task.get('context', {})),
              task.get('priority', 5),
              self.agent_name))
        
        conn.commit()
        conn.close()
        
        return task_id
    
    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """タスク結果を取得"""
        result_path = f"/var/koubou/tasks/completed/{task_id}.json"
        
        if os.path.exists(result_path):
            with open(result_path, 'r') as f:
                return json.load(f)
        return None

class ClaudeCodeAdapter(AgentInterface):
    """Claude Code用アダプター"""
    
    def __init__(self):
        super().__init__()
        self.agent_name = "claude-code"
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Claude Codeでタスクを実行（MCPツール経由）"""
        # MCPツールを通じて実行
        # 実際のClaude Code実装では、MCPサーバー経由で処理
        return {
            "status": "delegated",
            "task_id": self.delegate_task(task),
            "agent": self.agent_name
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Claude Codeの状態を取得"""
        return {
            "agent": self.agent_name,
            "status": "active",
            "mcp_enabled": True,
            "capabilities": ["file", "bash", "web", "mcp"]
        }

class CodexCLIAdapter(AgentInterface):
    """Codex-CLI用アダプター（将来実装用）"""
    
    def __init__(self):
        super().__init__()
        self.agent_name = "codex-cli"
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Codex-CLIでタスクを実行"""
        # Codex-CLIコマンドを実行
        command = [
            "codex-cli",
            "--ask-for-approval", "never",
            "--output-format", "json",
            "execute", json.dumps(task)
        ]
        
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            return json.loads(result.stdout)
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Codex-CLIの状態を取得"""
        return {
            "agent": self.agent_name,
            "status": "inactive",  # 将来実装
            "capabilities": ["code", "file"]
        }

def get_current_agent() -> AgentInterface:
    """現在のエージェントを取得"""
    # 設定ファイルから読み取り
    import yaml
    
    with open('/var/koubou/config/agent.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    agent_type = config.get('master_agent', 'claude-code')
    
    if agent_type == 'claude-code':
        return ClaudeCodeAdapter()
    elif agent_type == 'codex-cli':
        return CodexCLIAdapter()
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")

if __name__ == "__main__":
    # テスト
    agent = get_current_agent()
    print(json.dumps(agent.get_status(), indent=2))
```

### Step 2.2: MCPサーバーの実装（Claude Code用）

```python
#!/usr/bin/env python3
# /var/koubou/scripts/mcp_server.py

"""
Claude Code用のMCPサーバー実装
MCPツールとして工房システムの機能を提供
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List

class KoubouMCPServer:
    """工房システムMCPサーバー"""
    
    def __init__(self):
        self.db_path = os.environ.get('KOUBOU_DB', '/var/koubou/db/koubou.db')
        self.tools = {
            'koubou_delegate_task': self.delegate_task,
            'koubou_get_task_status': self.get_task_status,
            'koubou_list_tasks': self.list_tasks,
            'koubou_get_worker_status': self.get_worker_status
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """MCPリクエストを処理"""
        tool_name = request.get('tool')
        params = request.get('params', {})
        
        if tool_name not in self.tools:
            return {
                'error': f'Unknown tool: {tool_name}',
                'available_tools': list(self.tools.keys())
            }
        
        try:
            result = self.tools[tool_name](**params)
            return {'success': True, 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def delegate_task(self, content: str, priority: int = 5, 
                     task_type: str = 'general') -> Dict[str, Any]:
        """タスクを職人に委任"""
        task_id = f"mcp_{int(datetime.now().timestamp())}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO task_master (task_id, task_type, content, priority, 
                                   status, created_by)
            VALUES (?, ?, ?, ?, 'pending', 'claude-code')
        """, (task_id, task_type, content, priority))
        
        conn.commit()
        conn.close()
        
        return {
            'task_id': task_id,
            'status': 'delegated',
            'message': f'Task delegated to local worker'
        }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """タスクの状態を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM task_master WHERE task_id = ?
        """, (task_id,))
        
        task = cursor.fetchone()
        conn.close()
        
        if task:
            result = dict(task)
            
            # 完了タスクの結果を取得
            if result['status'] == 'completed':
                result_path = f"/var/koubou/tasks/completed/{task_id}.json"
                if os.path.exists(result_path):
                    with open(result_path, 'r') as f:
                        result['output'] = json.load(f)
            
            return result
        else:
            return {'error': f'Task not found: {task_id}'}
    
    def list_tasks(self, status: str = None, limit: int = 10) -> List[Dict]:
        """タスク一覧を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT task_id, task_type, status, priority, created_at
                FROM task_master
                WHERE status = ?
                ORDER BY priority DESC, created_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT task_id, task_type, status, priority, created_at
                FROM task_master
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return tasks
    
    def get_worker_status(self) -> List[Dict]:
        """ワーカーの状態を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT worker_id, worker_type, status, model_name, last_heartbeat
            FROM workers
            ORDER BY last_heartbeat DESC
        """)
        
        workers = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return workers

def main():
    """MCPサーバーのメインループ"""
    server = KoubouMCPServer()
    
    # 標準入力からリクエストを読み取り
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line)
            response = server.handle_request(request)
            
            # 標準出力にレスポンスを出力
            print(json.dumps(response))
            sys.stdout.flush()
            
        except Exception as e:
            error_response = {'error': str(e)}
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
```

---

## Phase 3: ローカル職人の実装（Day 5）

### Step 3.1: LMStudioの起動確認

```bash
#!/bin/bash
# check_lmstudio.sh

source /var/koubou/config/.env

check_lmstudio() {
    echo "LMStudioの接続確認中..."
    
    response=$(curl -s -X GET "$LMSTUDIO_BASE_URL/models" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "✓ LMStudioに接続できました"
        echo "利用可能なモデル:"
        echo "$response" | jq -r '.data[].id'
        
        # gpt-oss-20bの確認
        if echo "$response" | grep -q "gpt-oss-20b"; then
            echo "✓ gpt-oss-20bモデルが利用可能です"
            return 0
        else
            echo "✗ gpt-oss-20bモデルが見つかりません"
            echo "LMStudioでgpt-oss-20bをロードしてください"
            return 1
        fi
    else
        echo "✗ LMStudioに接続できません"
        echo "LMStudioが起動していることを確認してください"
        echo "Expected URL: $LMSTUDIO_BASE_URL"
        return 1
    fi
}

# テストリクエスト
test_request() {
    echo "テストリクエストを送信中..."
    
    response=$(curl -s -X POST "$LMSTUDIO_BASE_URL/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "gpt-oss-20b",
            "messages": [{"role": "user", "content": "Say OK if you are working"}],
            "max_tokens": 10,
            "temperature": 0.1
        }')
    
    if [ $? -eq 0 ]; then
        echo "✓ テストリクエスト成功"
        echo "レスポンス: $(echo "$response" | jq -r '.choices[0].message.content')"
        return 0
    else
        echo "✗ テストリクエスト失敗"
        return 1
    fi
}

# 実行
check_lmstudio && test_request
```

### Step 3.2: ローカル職人の実装

```python
#!/usr/bin/env python3
# /var/koubou/scripts/workers/local_worker.py

import os
import sys
import json
import time
import sqlite3
import requests
from datetime import datetime
from typing import Dict, Optional

class LocalWorker:
    """gpt-oss-20bを使用するローカル職人"""
    
    def __init__(self):
        self.worker_id = f"worker_local_{int(time.time())}"
        self.model = os.environ.get('LMSTUDIO_MODEL', 'gpt-oss-20b')
        self.base_url = os.environ.get('LMSTUDIO_BASE_URL', 'http://localhost:1234/v1')
        self.db_path = os.environ.get('KOUBOU_DB', '/var/koubou/db/koubou.db')
        self.register_worker()
    
    def register_worker(self):
        """ワーカーを登録"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO workers 
            (worker_id, worker_type, model_name, api_endpoint, process_id, status)
            VALUES (?, 'local', ?, ?, ?, 'idle')
        """, (self.worker_id, self.model, self.base_url, os.getpid()))
        
        conn.commit()
        conn.close()
        print(f"[INFO] Worker registered: {self.worker_id}")
    
    def get_next_task(self) -> Optional[Dict]:
        """次のタスクを取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # ペンディングタスクを取得
        cursor.execute("""
            SELECT * FROM task_master
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        """)
        
        task = cursor.fetchone()
        
        if task:
            # タスクを「割り当て済み」に更新
            cursor.execute("""
                UPDATE task_master
                SET status = 'assigned', 
                    assigned_worker_type = 'local',
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """, (task['task_id'],))
            conn.commit()
        
        conn.close()
        return dict(task) if task else None
    
    def execute_task(self, task: Dict) -> bool:
        """タスクを実行"""
        task_id = task['task_id']
        print(f"[INFO] Executing task: {task_id}")
        
        try:
            # ステータスを「実行中」に更新
            self.update_task_status(task_id, 'in_progress')
            
            # プロンプト構築
            prompt = self.build_prompt(task)
            
            # LMStudio APIコール
            response = self.call_lmstudio(prompt)
            
            if response:
                # 結果保存
                self.save_result(task_id, response)
                self.update_task_status(task_id, 'completed')
                print(f"[INFO] Task completed: {task_id}")
                return True
            else:
                self.update_task_status(task_id, 'failed')
                print(f"[ERROR] Task failed: {task_id}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Exception in task {task_id}: {e}")
            self.update_task_status(task_id, 'failed')
            self.log_error(task_id, str(e))
            return False
    
    def build_prompt(self, task: Dict) -> str:
        """タスク用のプロンプトを構築"""
        content = task.get('content', '')
        task_type = task.get('task_type', 'general')
        context = json.loads(task.get('context', '{}'))
        
        prompt = f"""You are an expert AI assistant specialized in {task_type} tasks.

Task: {content}

Context:
{json.dumps(context, indent=2) if context else 'No additional context provided.'}

Please complete this task and provide a detailed, actionable response.
If this is a coding task, provide complete, working code.
If this is an analysis task, provide thorough insights.
"""
        return prompt
    
    def call_lmstudio(self, prompt: str) -> Optional[str]:
        """LMStudio APIを呼び出し"""
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a helpful AI assistant with expertise in software development, analysis, and problem-solving."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 4000,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.Timeout:
            print(f"[ERROR] LMStudio API timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] LMStudio API error: {e}")
            return None
    
    def update_task_status(self, task_id: str, status: str):
        """タスクステータスを更新"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE task_master 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        """, (status, task_id))
        
        conn.commit()
        conn.close()
    
    def save_result(self, task_id: str, content: str):
        """結果を保存"""
        output_dir = "/var/koubou/tasks/completed"
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = f"{output_dir}/{task_id}.json"
        with open(output_path, 'w') as f:
            json.dump({
                'task_id': task_id,
                'worker_id': self.worker_id,
                'model': self.model,
                'content': content,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"[INFO] Result saved: {output_path}")
    
    def log_error(self, task_id: str, error_message: str):
        """エラーログを記録"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO system_logs (component, log_level, message, metadata)
            VALUES (?, 'ERROR', ?, ?)
        """, (self.worker_id, f"Task {task_id} failed", 
              json.dumps({'task_id': task_id, 'error': error_message})))
        
        conn.commit()
        conn.close()
    
    def update_heartbeat(self):
        """ハートビート更新"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE workers 
            SET last_heartbeat = CURRENT_TIMESTAMP 
            WHERE worker_id = ?
        """, (self.worker_id,))
        
        conn.commit()
        conn.close()
    
    def update_worker_status(self, status: str):
        """ワーカーステータス更新"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE workers 
            SET status = ? 
            WHERE worker_id = ?
        """, (status, self.worker_id))
        
        conn.commit()
        conn.close()
    
    def cleanup(self):
        """クリーンアップ処理"""
        print(f"[INFO] Cleaning up worker: {self.worker_id}")
        self.update_worker_status('offline')
    
    def run(self):
        """メインループ"""
        print(f"[INFO] Starting local worker with {self.model}")
        print(f"[INFO] Worker ID: {self.worker_id}")
        print(f"[INFO] Monitoring task queue...")
        
        try:
            while True:
                # ハートビート更新
                self.update_heartbeat()
                
                # タスク取得
                task = self.get_next_task()
                
                if task:
                    self.update_worker_status('busy')
                    success = self.execute_task(task)
                    self.update_worker_status('idle')
                    
                    if success:
                        print(f"[INFO] Task {task['task_id']} completed successfully")
                    else:
                        print(f"[WARN] Task {task['task_id']} failed")
                else:
                    # タスクがない場合は待機
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            print("\n[INFO] Received interrupt signal")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
        finally:
            self.cleanup()

if __name__ == "__main__":
    worker = LocalWorker()
    worker.run()
```

---

## Phase 4: システム統合と起動（Day 6）

### Step 4.1: システム起動スクリプト

```bash
#!/bin/bash
# /var/koubou/scripts/start_system.sh

source /var/koubou/config/.env

echo "==================================="
echo "工房システム v2.0 起動"
echo "==================================="

# PIDファイル
PID_DIR="/var/koubou/tmp"
mkdir -p $PID_DIR

# 設定読み込み
MASTER_AGENT=$(grep 'master_agent:' /var/koubou/config/agent.yaml | awk '{print $2}')
echo "親方エージェント: $MASTER_AGENT"

# LMStudioチェック
echo "LMStudioの確認中..."
if ! /var/koubou/scripts/check_lmstudio.sh; then
    echo "エラー: LMStudioが起動していません"
    echo "LMStudioを起動してgpt-oss-20bをロードしてください"
    exit 1
fi

# ローカル職人起動
start_workers() {
    echo "ローカル職人を起動中..."
    
    for i in {1..2}; do
        nohup python3 /var/koubou/scripts/workers/local_worker.py \
            > /var/koubou/logs/workers/worker_$i.log 2>&1 &
        
        WORKER_PID=$!
        echo $WORKER_PID > $PID_DIR/worker_$i.pid
        echo "  Worker #$i started (PID: $WORKER_PID)"
    done
}

# Claude Code用MCPサーバー起動
start_mcp_server() {
    if [ "$MASTER_AGENT" = "claude-code" ]; then
        echo "MCPサーバーを起動中..."
        
        # Claude Codeの設定にMCPサーバーを登録
        export CLAUDE_MCP_CONFIG=/var/koubou/config/claude_mcp_config.json
        
        echo "  MCPサーバー設定完了"
    fi
}

# モニター起動
start_monitor() {
    echo "システムモニターを起動中..."
    
    nohup python3 /var/koubou/scripts/system_monitor.py \
        > /var/koubou/logs/system/monitor.log 2>&1 &
    
    MONITOR_PID=$!
    echo $MONITOR_PID > $PID_DIR/monitor.pid
    echo "  Monitor started (PID: $MONITOR_PID)"
}

# クリーンアップ処理
cleanup() {
    echo ""
    echo "システムをシャットダウン中..."
    
    # PIDファイルから全プロセスを終了
    for pid_file in $PID_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            PID=$(cat $pid_file)
            if kill -0 $PID 2>/dev/null; then
                kill $PID
                echo "  Stopped process $PID"
            fi
            rm $pid_file
        fi
    done
    
    # ワーカーステータスをオフラインに
    sqlite3 $KOUBOU_DB "UPDATE workers SET status = 'offline';"
    
    echo "シャットダウン完了"
    exit 0
}

# シグナルハンドラー設定
trap cleanup SIGINT SIGTERM

# 起動実行
start_workers
start_mcp_server
start_monitor

echo "==================================="
echo "システム起動完了"
echo ""
echo "使用方法:"
echo "  1. Claude Codeを起動"
echo "  2. MCPツールから 'koubou_delegate_task' を使用"
echo "  3. または直接タスクをデータベースに登録"
echo ""
echo "Ctrl+C でシステムを停止"
echo "==================================="

# ログ監視
tail -f /var/koubou/logs/workers/worker_1.log
```

### Step 4.2: システムモニター

```python
#!/usr/bin/env python3
# /var/koubou/scripts/system_monitor.py

import os
import time
import sqlite3
from datetime import datetime, timedelta

class SystemMonitor:
    """システム全体の監視"""
    
    def __init__(self):
        self.db_path = os.environ.get('KOUBOU_DB', '/var/koubou/db/koubou.db')
        self.check_interval = 30  # 30秒ごとにチェック
    
    def check_worker_health(self):
        """ワーカーのヘルスチェック"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 5分以上ハートビートがないワーカーをオフラインに
        threshold = datetime.now() - timedelta(minutes=5)
        
        cursor.execute("""
            UPDATE workers
            SET status = 'offline'
            WHERE last_heartbeat < ? AND status != 'offline'
        """, (threshold,))
        
        affected = cursor.rowcount
        if affected > 0:
            print(f"[WARN] {affected} workers marked as offline")
        
        conn.commit()
        conn.close()
    
    def check_stuck_tasks(self):
        """スタックしているタスクをチェック"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 30分以上「実行中」のタスクを失敗扱いに
        threshold = datetime.now() - timedelta(minutes=30)
        
        cursor.execute("""
            UPDATE task_master
            SET status = 'failed'
            WHERE status = 'in_progress' 
            AND updated_at < ?
        """, (threshold,))
        
        affected = cursor.rowcount
        if affected > 0:
            print(f"[WARN] {affected} stuck tasks marked as failed")
        
        conn.commit()
        conn.close()
    
    def get_system_stats(self):
        """システム統計を取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # ワーカー統計
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM workers
            GROUP BY status
        """)
        worker_stats = cursor.fetchall()
        
        # タスク統計
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM task_master
            WHERE created_at > datetime('now', '-1 hour')
            GROUP BY status
        """)
        task_stats = cursor.fetchall()
        
        conn.close()
        
        print(f"[INFO] System Stats at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Workers: {dict(worker_stats)}")
        print(f"  Tasks (1h): {dict(task_stats)}")
    
    def run(self):
        """監視ループ"""
        print("[INFO] System monitor started")
        
        while True:
            try:
                self.check_worker_health()
                self.check_stuck_tasks()
                self.get_system_stats()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("[INFO] Monitor shutting down")
                break
            except Exception as e:
                print(f"[ERROR] Monitor error: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run()
```

---

## Phase 5: テストと検証（Day 7-8）

### Step 5.1: 統合テスト

```bash
#!/bin/bash
# /var/koubou/scripts/test_system.sh

source /var/koubou/config/.env

echo "==================================="
echo "工房システム統合テスト"
echo "==================================="

# テストタスク作成
create_test_task() {
    local content=$1
    local priority=$2
    local task_type=$3
    
    task_id="test_$(date +%s)_$RANDOM"
    
    sqlite3 $KOUBOU_DB << EOF
INSERT INTO task_master (task_id, task_type, content, priority, status, created_by)
VALUES ('$task_id', '$task_type', '$content', $priority, 'pending', 'test_script');
EOF
    
    echo $task_id
}

# タスク状態確認
check_task_status() {
    local task_id=$1
    
    sqlite3 -line $KOUBOU_DB "SELECT status FROM task_master WHERE task_id = '$task_id';"
}

# テスト1: 簡単なコード生成タスク
test_code_generation() {
    echo ""
    echo "テスト1: コード生成タスク"
    
    task_id=$(create_test_task "Write a Python function to calculate fibonacci numbers" 5 "code_generation")
    echo "  Created task: $task_id"
    
    # 完了を待つ（最大60秒）
    for i in {1..12}; do
        sleep 5
        status=$(sqlite3 -list $KOUBOU_DB "SELECT status FROM task_master WHERE task_id = '$task_id';")
        echo "  Status: $status"
        
        if [ "$status" = "completed" ]; then
            echo "  ✓ タスク完了"
            
            # 結果を表示
            if [ -f "/var/koubou/tasks/completed/${task_id}.json" ]; then
                echo "  結果:"
                jq -r '.content' "/var/koubou/tasks/completed/${task_id}.json" | head -20
            fi
            return 0
        fi
    done
    
    echo "  ✗ タスクがタイムアウトしました"
    return 1
}

# テスト2: 複数タスクの並列処理
test_parallel_tasks() {
    echo ""
    echo "テスト2: 複数タスクの並列処理"
    
    # 3つのタスクを作成
    task1=$(create_test_task "Explain what is a REST API" 8 "explanation")
    task2=$(create_test_task "Write a bash script to check disk usage" 6 "code_generation")
    task3=$(create_test_task "List best practices for Python coding" 7 "documentation")
    
    echo "  Created tasks: $task1, $task2, $task3"
    
    # 状態を監視
    for i in {1..20}; do
        sleep 5
        
        completed=$(sqlite3 -list $KOUBOU_DB "
            SELECT COUNT(*) FROM task_master 
            WHERE task_id IN ('$task1', '$task2', '$task3') 
            AND status = 'completed';
        ")
        
        echo "  Completed: $completed/3"
        
        if [ "$completed" = "3" ]; then
            echo "  ✓ 全タスク完了"
            return 0
        fi
    done
    
    echo "  ✗ タイムアウト"
    return 1
}

# ワーカー状態確認
check_workers() {
    echo ""
    echo "ワーカー状態:"
    
    sqlite3 -header -column $KOUBOU_DB << EOF
SELECT worker_id, status, model_name, 
       datetime(last_heartbeat, 'localtime') as last_heartbeat
FROM workers
WHERE last_heartbeat > datetime('now', '-5 minutes');
EOF
}

# システム統計
show_stats() {
    echo ""
    echo "システム統計:"
    
    sqlite3 -header -column $KOUBOU_DB << EOF
SELECT status, COUNT(*) as count
FROM task_master
GROUP BY status;
EOF
}

# メイン実行
main() {
    # システムが起動しているか確認
    worker_count=$(sqlite3 -list $KOUBOU_DB "SELECT COUNT(*) FROM workers WHERE status != 'offline';")
    
    if [ "$worker_count" = "0" ]; then
        echo "エラー: ワーカーが起動していません"
        echo "先に ./start_system.sh を実行してください"
        exit 1
    fi
    
    check_workers
    
    # テスト実行
    test_code_generation
    test_parallel_tasks
    
    # 最終統計
    show_stats
    
    echo ""
    echo "==================================="
    echo "テスト完了"
}

main
```

### Step 5.2: Claude Codeからのテスト

Claude Codeを起動して、以下のコマンドを実行してテストします:

```
# Claude Codeのプロンプトで実行

1. タスクの委任テスト:
   MCPツール koubou_delegate_task を使って、
   "Create a Python script that monitors system resources" 
   というタスクを委任してください。

2. 状態確認:
   MCPツール koubou_get_task_status で、
   作成したタスクの状態を確認してください。

3. タスク一覧:
   MCPツール koubou_list_tasks で、
   現在のタスク一覧を取得してください。

4. ワーカー状態:
   MCPツール koubou_get_worker_status で、
   ワーカーの状態を確認してください。
```

---

## トラブルシューティング

### 問題: LMStudioに接続できない

```bash
# 診断
curl -v http://localhost:1234/v1/models

# 解決策
1. LMStudioが起動していることを確認
2. ポート1234が使用されていることを確認
3. gpt-oss-20bモデルがロードされていることを確認
```

### 問題: ワーカーがタスクを処理しない

```bash
# 診断
tail -f /var/koubou/logs/workers/worker_1.log

# データベース確認
sqlite3 /var/koubou/db/koubou.db "SELECT * FROM workers;"
sqlite3 /var/koubou/db/koubou.db "SELECT * FROM task_master WHERE status = 'pending';"

# 解決策
1. ワーカーログでエラーを確認
2. データベースの権限を確認
3. LMStudioの応答を確認
```

### 問題: Claude CodeのMCPツールが動作しない

```bash
# MCPサーバーのテスト
echo '{"tool": "koubou_list_tasks", "params": {}}' | \
    python3 /var/koubou/scripts/mcp_server.py

# 解決策
1. CLAUDE_MCP_CONFIG環境変数が設定されているか確認
2. MCPサーバースクリプトの実行権限を確認
3. Claude Codeを再起動
```

---

## 運用ガイド

### 日次メンテナンス

```bash
#!/bin/bash
# daily_maintenance.sh

# ログローテーション
find /var/koubou/logs -name "*.log" -size +100M -exec mv {} {}.old \;

# 古いタスクのクリーンアップ
sqlite3 $KOUBOU_DB "DELETE FROM task_master WHERE status = 'completed' AND created_at < datetime('now', '-7 days');"

# データベース最適化
sqlite3 $KOUBOU_DB "VACUUM;"

echo "メンテナンス完了"
```

### システム状態レポート

```bash
#!/bin/bash
# system_report.sh

echo "=== 工房システムレポート ==="
echo "日時: $(date)"
echo ""

echo "ワーカー状態:"
sqlite3 -header -column $KOUBOU_DB "
SELECT worker_type, status, COUNT(*) as count
FROM workers
GROUP BY worker_type, status;"

echo ""
echo "本日のタスク統計:"
sqlite3 -header -column $KOUBOU_DB "
SELECT task_type, status, COUNT(*) as count
FROM task_master
WHERE created_at > datetime('now', 'start of day')
GROUP BY task_type, status;"

echo ""
echo "平均処理時間:"
sqlite3 -header -column $KOUBOU_DB "
SELECT task_type,
       AVG(julianday(updated_at) - julianday(created_at)) * 24 * 60 as avg_minutes
FROM task_master
WHERE status = 'completed'
GROUP BY task_type;"
```

---

## 改訂履歴

| 版 | 日付 | 変更内容 | 作成者 |
|----|------|----------|--------|
| 2.0 | 2024-12-29 | Claude Code対応、共通基盤実装 | AI Assistant |
| 1.0 | 2024-12-29 | 初版作成 | AI Assistant |