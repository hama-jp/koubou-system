# 工房システム実装手順書
## Codex-CLI + GPT-5/gpt-oss-20b ハイブリッド職人実装

---

## 前提条件の確認

### 必要なソフトウェア
- [ ] Linux/WSL2環境
- [ ] Bash 4.0以上
- [ ] Python 3.8以上
- [ ] SQLite3
- [ ] inotify-tools
- [ ] jq（JSON処理用）
- [ ] Codex-CLI
- [ ] LMStudio（gpt-oss-20bモデル導入済み）

### 必要な認証情報
- [ ] OpenAI APIキー（GPT-5アクセス用）
- [ ] 十分なAPIクレジット残高

---

## Phase 1: 基本環境構築（Day 1-2）

### Step 1.1: ディレクトリ構造の作成

```bash
#!/bin/bash
# setup_directories.sh

# ベースディレクトリの作成
sudo mkdir -p /var/koubou/{config,tasks,logs,db,tmp}
sudo mkdir -p /var/koubou/tasks/{pending,in_progress,completed,failed}
sudo mkdir -p /var/koubou/logs/{master,workers,system}

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
-- タスクマスターテーブル
CREATE TABLE IF NOT EXISTS task_master (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    difficulty_level TEXT NOT NULL,
    sensitivity_level TEXT NOT NULL,
    assigned_worker_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    estimated_tokens INTEGER,
    actual_tokens INTEGER,
    estimated_cost REAL,
    actual_cost REAL,
    parent_task_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- コスト追跡テーブル
CREATE TABLE IF NOT EXISTS cost_tracking (
    tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    worker_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 月次予算管理テーブル
CREATE TABLE IF NOT EXISTS budget_management (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_month TEXT NOT NULL UNIQUE,
    budget_limit_usd REAL NOT NULL,
    spent_usd REAL DEFAULT 0,
    alert_threshold_percent INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ワーカー管理テーブル
CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    worker_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    api_endpoint TEXT NOT NULL,
    process_id INTEGER,
    status TEXT NOT NULL DEFAULT 'offline',
    capabilities JSON,
    rate_limit_remaining INTEGER,
    rate_limit_reset_at TIMESTAMP,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- システムログテーブル
CREATE TABLE IF NOT EXISTS system_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    worker_id TEXT,
    log_level TEXT,
    component TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_task_status ON task_master(status);
CREATE INDEX IF NOT EXISTS idx_task_priority ON task_master(priority DESC);
CREATE INDEX IF NOT EXISTS idx_worker_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_log_timestamp ON system_logs(created_at DESC);

-- 初期予算設定（2024年12月）
INSERT OR IGNORE INTO budget_management (year_month, budget_limit_usd)
VALUES ('2024-12', 100.0);

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

# AGENT.yaml の作成
cat > /var/koubou/config/agent.yaml << 'EOF'
master_agent: codex-cli
available_workers:
  - type: gpt5_high
    model: gpt-5-high
    endpoint: https://api.openai.com/v1
    max_rpm: 10
    use_for:
      - architecture_design
      - complex_algorithms
      - system_integration
  - type: gpt5_medium
    model: gpt-5-medium
    endpoint: https://api.openai.com/v1
    max_rpm: 30
    use_for:
      - code_generation
      - refactoring
      - api_development
  - type: local
    model: gpt-oss-20b
    endpoint: http://localhost:1234/v1
    max_rpm: unlimited
    use_for:
      - sensitive_data
      - simple_tasks
      - cost_optimization

security_policy:
  sensitive_patterns:
    - password
    - secret
    - api_key
    - token
    - private_key
  
routing_rules:
  - if: contains_sensitive_data
    then: local
  - if: high_difficulty
    then: gpt5_high
  - if: medium_difficulty
    then: gpt5_medium
  - else: local

cost_limits:
  daily_limit_usd: 10.0
  monthly_limit_usd: 100.0
  alert_threshold_percent: 80
EOF

echo "設定ファイルを作成しました"
```

### Step 1.4: 環境変数の設定

```bash
#!/bin/bash
# setup_environment.sh

# .envファイルの作成（実際のAPIキーに置き換えてください）
cat > /var/koubou/config/.env << 'EOF'
# OpenAI API設定
OPENAI_API_KEY=sk-your-api-key-here

# LMStudio設定
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=gpt-oss-20b

# システム設定
KOUBOU_HOME=/var/koubou
KOUBOU_DB=/var/koubou/db/koubou.db
KOUBOU_LOG_LEVEL=INFO

# 予算設定
MONTHLY_BUDGET_USD=100
DAILY_BUDGET_USD=10

# セキュリティ
MASTER_PASSWORD=your-secure-password-here
EOF

# 権限設定
chmod 600 /var/koubou/config/.env

# bashrcへの追加
echo "source /var/koubou/config/.env" >> ~/.bashrc

echo "環境変数を設定しました"
```

---

## Phase 2: ローカル職人の実装（Day 3-4）

### Step 2.1: ローカル職人ワーカースクリプト

```bash
#!/bin/bash
# local_worker.sh

source /var/koubou/config/.env

WORKER_ID="worker_local_$(date +%s)"
WORKER_TYPE="local"
MODEL_NAME="gpt-oss-20b"

# ワーカー登録
register_worker() {
    sqlite3 $KOUBOU_DB << EOF
INSERT INTO workers (worker_id, worker_type, model_name, api_endpoint, process_id, status)
VALUES ('$WORKER_ID', '$WORKER_TYPE', '$MODEL_NAME', '$LMSTUDIO_BASE_URL', $$, 'idle');
EOF
    echo "Worker registered: $WORKER_ID (PID: $$)"
}

# タスク取得
get_next_task() {
    sqlite3 -json $KOUBOU_DB << EOF
SELECT task_id, task_type, priority, sensitivity_level
FROM task_master
WHERE status = 'pending' 
  AND (sensitivity_level = 'confidential' OR difficulty_level = 'low')
ORDER BY priority DESC, created_at ASC
LIMIT 1;
EOF
}

# タスク実行
execute_task() {
    local task_json=$1
    local task_id=$(echo "$task_json" | jq -r '.[0].task_id')
    
    if [ -z "$task_id" ] || [ "$task_id" = "null" ]; then
        return 1
    fi
    
    echo "Executing task: $task_id"
    
    # タスクステータス更新
    sqlite3 $KOUBOU_DB "UPDATE task_master SET status = 'in_progress', assigned_worker_type = '$WORKER_TYPE' WHERE task_id = '$task_id';"
    
    # Codex-CLIでタスク実行
    codex-cli \
        --config /var/koubou/config/local-config.toml \
        --ask-for-approval never \
        --sandbox workspace-write \
        --quiet \
        --output-format json \
        execute-task "$task_id" > /var/koubou/tasks/in_progress/${task_id}.json 2>&1
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        sqlite3 $KOUBOU_DB "UPDATE task_master SET status = 'completed' WHERE task_id = '$task_id';"
        echo "Task completed: $task_id"
    else
        sqlite3 $KOUBOU_DB "UPDATE task_master SET status = 'failed' WHERE task_id = '$task_id';"
        echo "Task failed: $task_id"
    fi
    
    return $exit_code
}

# メインループ
main_loop() {
    register_worker
    
    trap "sqlite3 $KOUBOU_DB \"UPDATE workers SET status = 'offline' WHERE worker_id = '$WORKER_ID';\" && exit" SIGINT SIGTERM
    
    while true; do
        # ハートビート更新
        sqlite3 $KOUBOU_DB "UPDATE workers SET last_heartbeat = CURRENT_TIMESTAMP WHERE worker_id = '$WORKER_ID';"
        
        # タスク取得と実行
        task_json=$(get_next_task)
        
        if [ -n "$task_json" ] && [ "$task_json" != "[]" ]; then
            sqlite3 $KOUBOU_DB "UPDATE workers SET status = 'busy' WHERE worker_id = '$WORKER_ID';"
            execute_task "$task_json"
            sqlite3 $KOUBOU_DB "UPDATE workers SET status = 'idle' WHERE worker_id = '$WORKER_ID';"
        else
            sleep 5
        fi
    done
}

# 実行
main_loop
```

### Step 2.2: LMStudioの起動確認

```bash
#!/bin/bash
# check_lmstudio.sh

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
            "messages": [{"role": "user", "content": "Hello, respond with OK"}],
            "max_tokens": 10
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

---

## Phase 3: クラウド職人の実装（Day 5-6）

### Step 3.1: GPT-5職人ワーカースクリプト

```python
#!/usr/bin/env python3
# gpt5_worker.py

import os
import sys
import json
import time
import sqlite3
import openai
from datetime import datetime
from typing import Dict, Optional

class GPT5Worker:
    def __init__(self, worker_type: str):
        self.worker_type = worker_type  # 'gpt5_high' or 'gpt5_medium'
        self.model = 'gpt-5-high' if worker_type == 'gpt5_high' else 'gpt-5-medium'
        self.worker_id = f"worker_{worker_type}_{int(time.time())}"
        self.db_path = os.environ.get('KOUBOU_DB', '/var/koubou/db/koubou.db')
        
        # OpenAI クライアント初期化
        openai.api_key = os.environ.get('OPENAI_API_KEY')
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        self.rate_limits = {
            'gpt5_high': {'rpm': 10, 'cost_per_1k': 0.10},
            'gpt5_medium': {'rpm': 30, 'cost_per_1k': 0.03}
        }
        
        self.register_worker()
    
    def register_worker(self):
        """ワーカーをデータベースに登録"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO workers (worker_id, worker_type, model_name, api_endpoint, process_id, status)
            VALUES (?, ?, ?, ?, ?, 'idle')
        """, (self.worker_id, self.worker_type, self.model, 'https://api.openai.com/v1', os.getpid()))
        
        conn.commit()
        conn.close()
        print(f"Worker registered: {self.worker_id}")
    
    def get_next_task(self) -> Optional[Dict]:
        """次のタスクを取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 難易度に応じたタスク取得
        if self.worker_type == 'gpt5_high':
            difficulty_filter = "difficulty_level = 'high'"
        else:
            difficulty_filter = "difficulty_level = 'medium'"
        
        cursor.execute(f"""
            SELECT * FROM task_master
            WHERE status = 'pending' 
              AND sensitivity_level != 'confidential'
              AND {difficulty_filter}
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        """)
        
        task = cursor.fetchone()
        conn.close()
        
        return dict(task) if task else None
    
    def execute_task(self, task: Dict) -> bool:
        """タスクを実行"""
        task_id = task['task_id']
        
        try:
            # ステータス更新
            self.update_task_status(task_id, 'in_progress')
            
            # タスク詳細の取得（ここは簡略化）
            prompt = f"Execute task: {task['task_type']} with priority {task['priority']}"
            
            # OpenAI API呼び出し
            response = self.call_openai_with_retry(prompt)
            
            if response:
                # コスト記録
                self.log_cost(task_id, response['usage'])
                
                # 結果保存
                self.save_result(task_id, response['content'])
                
                # ステータス更新
                self.update_task_status(task_id, 'completed')
                return True
            else:
                self.update_task_status(task_id, 'failed')
                return False
                
        except Exception as e:
            print(f"Error executing task {task_id}: {e}")
            self.update_task_status(task_id, 'failed')
            return False
    
    def call_openai_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[Dict]:
        """OpenAI APIを呼び出し（リトライ付き）"""
        for attempt in range(max_retries):
            try:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful coding assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.7
                )
                
                return {
                    'content': response.choices[0].message.content,
                    'usage': response.usage
                }
                
            except openai.error.RateLimitError:
                wait_time = 30 if self.worker_type == 'gpt5_high' else 10
                print(f"Rate limit hit, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                
            except Exception as e:
                print(f"API call failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
        
        return None
    
    def log_cost(self, task_id: str, usage: Dict):
        """コストを記録"""
        total_tokens = usage.prompt_tokens + usage.completion_tokens
        cost = (total_tokens / 1000) * self.rate_limits[self.worker_type]['cost_per_1k']
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO cost_tracking (task_id, worker_type, model_name, 
                                     prompt_tokens, completion_tokens, total_tokens, cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, self.worker_type, self.model, 
              usage.prompt_tokens, usage.completion_tokens, total_tokens, cost))
        
        # 月次予算の更新
        year_month = datetime.now().strftime('%Y-%m')
        cursor.execute("""
            UPDATE budget_management 
            SET spent_usd = spent_usd + ?
            WHERE year_month = ?
        """, (cost, year_month))
        
        conn.commit()
        conn.close()
    
    def update_task_status(self, task_id: str, status: str):
        """タスクステータスを更新"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE task_master 
            SET status = ?, assigned_worker_type = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        """, (status, self.worker_type, task_id))
        
        conn.commit()
        conn.close()
    
    def save_result(self, task_id: str, content: str):
        """結果を保存"""
        output_path = f"/var/koubou/tasks/completed/{task_id}.json"
        with open(output_path, 'w') as f:
            json.dump({
                'task_id': task_id,
                'worker_id': self.worker_id,
                'model': self.model,
                'content': content,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
    
    def run(self):
        """メインループ"""
        print(f"Starting {self.worker_type} worker...")
        
        while True:
            try:
                # ハートビート更新
                self.update_heartbeat()
                
                # タスク取得
                task = self.get_next_task()
                
                if task:
                    print(f"Processing task: {task['task_id']}")
                    self.update_worker_status('busy')
                    self.execute_task(task)
                    self.update_worker_status('idle')
                else:
                    time.sleep(10)
                    
            except KeyboardInterrupt:
                print("Shutting down...")
                self.update_worker_status('offline')
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(30)
    
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

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ['gpt5_high', 'gpt5_medium']:
        print("Usage: python gpt5_worker.py [gpt5_high|gpt5_medium]")
        sys.exit(1)
    
    worker = GPT5Worker(sys.argv[1])
    worker.run()
```

---

## Phase 4: オーケストレーション（Day 7）

### Step 4.1: 親方起動スクリプト

```bash
#!/bin/bash
# start_master.sh

source /var/koubou/config/.env

echo "==================================="
echo "工房システム 親方プロセス起動"
echo "==================================="

# 設定読み込み
MASTER_AGENT=$(grep 'master_agent:' /var/koubou/config/agent.yaml | awk '{print $2}')

if [ -z "$MASTER_AGENT" ]; then
    echo "エラー: master_agentが設定されていません"
    exit 1
fi

echo "親方エージェント: $MASTER_AGENT"

# 監視プロセス起動
echo "監視プロセスを起動中..."
nohup /var/koubou/scripts/task_watcher.sh > /var/koubou/logs/system/watcher.log 2>&1 &
WATCHER_PID=$!
echo "監視プロセス起動 (PID: $WATCHER_PID)"

# コスト監視起動
echo "コスト監視を起動中..."
nohup python3 /var/koubou/scripts/cost_monitor.py > /var/koubou/logs/system/cost_monitor.log 2>&1 &
COST_PID=$!
echo "コスト監視起動 (PID: $COST_PID)"

# ローカル職人起動
echo "ローカル職人を起動中..."
nohup /var/koubou/scripts/local_worker.sh > /var/koubou/logs/workers/local_worker.log 2>&1 &
LOCAL_PID=$!
echo "ローカル職人起動 (PID: $LOCAL_PID)"

# クリーンアップ処理
cleanup() {
    echo "システムをシャットダウン中..."
    kill $WATCHER_PID $COST_PID $LOCAL_PID 2>/dev/null
    
    # 全ワーカーをオフラインに
    sqlite3 $KOUBOU_DB "UPDATE workers SET status = 'offline';"
    
    echo "シャットダウン完了"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 親方エージェント起動
echo "親方エージェントを起動中..."
echo "Ctrl+C で終了"
echo "==================================="

# Codex-CLI対話モード起動
$MASTER_AGENT --interactive
```

### Step 4.2: タスクルーター

```python
#!/usr/bin/env python3
# task_router.py

import re
import sqlite3
import json
from typing import Dict, Tuple

class TaskRouter:
    def __init__(self):
        self.db_path = '/var/koubou/db/koubou.db'
        self.sensitive_patterns = [
            r'(?i)password\s*[:=]',
            r'(?i)api[_-]?key\s*[:=]',
            r'(?i)secret\s*[:=]',
            r'(?i)token\s*[:=]',
            r'(?i)private[_-]?key'
        ]
        
        self.difficulty_keywords = {
            'high': ['architecture', 'design pattern', 'distributed', 
                    'optimization', 'algorithm', 'concurrent'],
            'medium': ['refactor', 'implement', 'api', 'database', 'integration'],
            'low': ['fix', 'update', 'add comment', 'rename', 'format']
        }
    
    def route_task(self, task_id: str, task_description: str) -> str:
        """タスクを適切な職人にルーティング"""
        
        # 機密性チェック
        if self._contains_sensitive_data(task_description):
            worker_type = 'local'
            difficulty = 'N/A'
            sensitivity = 'confidential'
        else:
            # 難易度評価
            difficulty = self._evaluate_difficulty(task_description)
            sensitivity = 'public'
            
            # 予算チェック
            if self._is_budget_critical():
                if difficulty != 'high':
                    worker_type = 'local'
                else:
                    worker_type = 'gpt5_high'  # 高難度は譲れない
            else:
                # 通常のルーティング
                routing_map = {
                    'high': 'gpt5_high',
                    'medium': 'gpt5_medium',
                    'low': 'local'
                }
                worker_type = routing_map[difficulty]
        
        # データベース更新
        self._update_task_routing(task_id, worker_type, difficulty, sensitivity)
        
        return worker_type
    
    def _contains_sensitive_data(self, text: str) -> bool:
        """機密データの検出"""
        for pattern in self.sensitive_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _evaluate_difficulty(self, text: str) -> str:
        """タスク難易度の評価"""
        text_lower = text.lower()
        
        # キーワードマッチング
        scores = {'high': 0, 'medium': 0, 'low': 0}
        
        for level, keywords in self.difficulty_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[level] += 1
        
        # 最高スコアの難易度を返す
        if scores['high'] > 0:
            return 'high'
        elif scores['medium'] > 0:
            return 'medium'
        else:
            return 'low'
    
    def _is_budget_critical(self) -> bool:
        """予算が逼迫しているかチェック"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT spent_usd, budget_limit_usd, alert_threshold_percent
            FROM budget_management
            WHERE year_month = strftime('%Y-%m', 'now')
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            spent, limit, threshold = result
            return (spent / limit) * 100 >= threshold
        
        return False
    
    def _update_task_routing(self, task_id: str, worker_type: str, 
                           difficulty: str, sensitivity: str):
        """タスクのルーティング情報を更新"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE task_master
            SET assigned_worker_type = ?,
                difficulty_level = ?,
                sensitivity_level = ?,
                status = 'routing',
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        """, (worker_type, difficulty, sensitivity, task_id))
        
        conn.commit()
        conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python task_router.py <task_id> <task_description>")
        sys.exit(1)
    
    router = TaskRouter()
    worker_type = router.route_task(sys.argv[1], sys.argv[2])
    print(f"Task routed to: {worker_type}")
```

---

## Phase 5: 統合テスト（Day 8）

### Step 5.1: システム全体のテスト

```bash
#!/bin/bash
# test_system.sh

echo "==================================="
echo "工房システム統合テスト"
echo "==================================="

# テストタスクの作成
create_test_tasks() {
    echo "テストタスクを作成中..."
    
    # 簡単なタスク（ローカル向け）
    sqlite3 $KOUBOU_DB << EOF
INSERT INTO task_master (task_id, task_type, difficulty_level, sensitivity_level, priority)
VALUES ('test_001', 'code_generation', 'low', 'public', 5);
EOF
    
    # 機密タスク（ローカル向け）
    sqlite3 $KOUBOU_DB << EOF
INSERT INTO task_master (task_id, task_type, difficulty_level, sensitivity_level, priority)
VALUES ('test_002', 'code_review', 'medium', 'confidential', 8);
EOF
    
    # 中難度タスク（GPT-5-medium向け）
    sqlite3 $KOUBOU_DB << EOF
INSERT INTO task_master (task_id, task_type, difficulty_level, sensitivity_level, priority)
VALUES ('test_003', 'refactoring', 'medium', 'public', 6);
EOF
    
    # 高難度タスク（GPT-5-high向け）
    sqlite3 $KOUBOU_DB << EOF
INSERT INTO task_master (task_id, task_type, difficulty_level, sensitivity_level, priority)
VALUES ('test_004', 'architecture', 'high', 'public', 10);
EOF
    
    echo "4つのテストタスクを作成しました"
}

# タスク実行状況の確認
check_task_status() {
    echo "タスク実行状況:"
    sqlite3 -header -column $KOUBOU_DB << EOF
SELECT task_id, status, assigned_worker_type, difficulty_level, sensitivity_level
FROM task_master
WHERE task_id LIKE 'test_%'
ORDER BY created_at;
EOF
}

# ワーカー状況の確認
check_worker_status() {
    echo "ワーカー状況:"
    sqlite3 -header -column $KOUBOU_DB << EOF
SELECT worker_id, worker_type, status, 
       datetime(last_heartbeat, 'localtime') as last_heartbeat
FROM workers
ORDER BY worker_type;
EOF
}

# コスト状況の確認
check_cost_status() {
    echo "コスト状況:"
    sqlite3 -header -column $KOUBOU_DB << EOF
SELECT 
    year_month,
    budget_limit_usd,
    ROUND(spent_usd, 2) as spent_usd,
    ROUND(budget_limit_usd - spent_usd, 2) as remaining_usd,
    ROUND((spent_usd / budget_limit_usd) * 100, 1) as usage_percent
FROM budget_management
WHERE year_month = strftime('%Y-%m', 'now');
EOF
}

# メインテスト実行
run_test() {
    create_test_tasks
    
    echo "タスクルーティングをテスト中..."
    python3 /var/koubou/scripts/task_router.py "test_001" "Fix a simple bug in the code"
    python3 /var/koubou/scripts/task_router.py "test_002" "Review code with password: secret123"
    python3 /var/koubou/scripts/task_router.py "test_003" "Refactor the API implementation"
    python3 /var/koubou/scripts/task_router.py "test_004" "Design distributed architecture pattern"
    
    echo ""
    echo "30秒待機中..."
    sleep 30
    
    echo ""
    check_task_status
    echo ""
    check_worker_status
    echo ""
    check_cost_status
}

# 実行
run_test
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

### 問題: OpenAI APIエラー
```bash
# 診断
python3 -c "import openai; openai.api_key='$OPENAI_API_KEY'; print(openai.Model.list())"

# 解決策
1. APIキーが正しいことを確認
2. APIクレジットが残っていることを確認
3. レート制限に達していないことを確認
```

### 問題: SQLiteロックエラー
```bash
# 診断
sqlite3 $KOUBOU_DB "PRAGMA journal_mode;"

# 解決策
sqlite3 $KOUBOU_DB "PRAGMA journal_mode=WAL;"
```

### 問題: ワーカーが動作しない
```bash
# 診断
ps aux | grep -E "worker|codex"
tail -f /var/koubou/logs/workers/*.log

# 解決策
1. ログファイルでエラーを確認
2. 必要な依存関係がインストールされているか確認
3. 権限設定を確認
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
```

### 月次レポート
```bash
#!/bin/bash
# monthly_report.sh

echo "月次レポート - $(date +'%Y年%m月')"
echo "================================"

sqlite3 -header -column $KOUBOU_DB << EOF
SELECT 
    worker_type,
    COUNT(*) as task_count,
    SUM(actual_tokens) as total_tokens,
    ROUND(SUM(actual_cost), 2) as total_cost_usd
FROM task_master
WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
GROUP BY worker_type;
EOF
```

---

## 改訂履歴

| 版 | 日付 | 変更内容 | 作成者 |
|----|------|----------|--------|
| 1.0 | 2024-12-29 | 初版作成 | AI Assistant |