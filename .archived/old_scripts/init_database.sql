-- 工房システム データベース初期化スクリプト
-- SQLite3用

-- 既存テーブルの削除（開発用）
DROP TABLE IF EXISTS agent_communications;
DROP TABLE IF EXISTS system_logs;
DROP TABLE IF EXISTS workers;
DROP TABLE IF EXISTS task_master;
DROP TABLE IF EXISTS agents;

-- エージェント管理テーブル
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL CHECK(agent_type IN ('claude-code', 'codex-cli', 'gemini-cli')),
    status TEXT NOT NULL CHECK(status IN ('active', 'inactive', 'error')),
    is_primary BOOLEAN DEFAULT FALSE,
    capabilities JSON,
    last_active TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- タスクマスターテーブル
CREATE TABLE task_master (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL DEFAULT 'general',
    difficulty_level TEXT DEFAULT 'medium' CHECK(difficulty_level IN ('high', 'medium', 'low')),
    sensitivity_level TEXT DEFAULT 'public' CHECK(sensitivity_level IN ('confidential', 'internal', 'public')),
    assigned_agent_id TEXT,
    assigned_worker_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'routing', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')),
    priority INTEGER DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
    content TEXT NOT NULL,
    context JSON,
    result JSON,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_agent_id) REFERENCES agents(agent_id)
);

-- ワーカー管理テーブル
CREATE TABLE workers (
    worker_id TEXT PRIMARY KEY,
    worker_type TEXT NOT NULL DEFAULT 'local',
    model_name TEXT NOT NULL DEFAULT 'gpt-oss-20b',
    api_endpoint TEXT NOT NULL,
    process_id INTEGER,
    status TEXT NOT NULL DEFAULT 'offline' CHECK(status IN ('idle', 'busy', 'offline', 'error')),
    capabilities JSON,
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- システムログテーブル
CREATE TABLE system_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,
    log_level TEXT CHECK(log_level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL')),
    message TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- エージェント間通信ログ
CREATE TABLE agent_communications (
    comm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    message_type TEXT NOT NULL,
    payload JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- タスク履歴テーブル（統計用）
CREATE TABLE task_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    status_from TEXT,
    status_to TEXT NOT NULL,
    worker_id TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task_master(task_id)
);

-- インデックス作成
CREATE INDEX idx_task_status ON task_master(status);
CREATE INDEX idx_task_priority ON task_master(priority DESC);
CREATE INDEX idx_task_created ON task_master(created_at DESC);
CREATE INDEX idx_worker_status ON workers(status);
CREATE INDEX idx_worker_heartbeat ON workers(last_heartbeat DESC);
CREATE INDEX idx_log_timestamp ON system_logs(created_at DESC);
CREATE INDEX idx_log_level ON system_logs(log_level);
CREATE INDEX idx_comm_timestamp ON agent_communications(timestamp DESC);

-- トリガー：タスク更新時のタイムスタンプ自動更新
CREATE TRIGGER update_task_timestamp 
AFTER UPDATE ON task_master
BEGIN
    UPDATE task_master 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE task_id = NEW.task_id;
END;

-- トリガー：タスク状態変更の履歴記録
CREATE TRIGGER record_task_history
AFTER UPDATE OF status ON task_master
BEGIN
    INSERT INTO task_history (task_id, status_from, status_to, worker_id)
    VALUES (NEW.task_id, OLD.status, NEW.status, NEW.assigned_worker_type);
END;

-- 初期データ挿入

-- Claude Codeをプライマリエージェントとして登録
INSERT INTO agents (agent_id, agent_type, status, is_primary, capabilities)
VALUES (
    'claude_primary', 
    'claude-code', 
    'active', 
    TRUE, 
    '{"mcp": true, "hooks": true, "tools": ["file", "bash", "web", "task", "todo"]}'
);

-- 代替エージェントの登録（非アクティブ）
INSERT INTO agents (agent_id, agent_type, status, is_primary, capabilities)
VALUES (
    'codex_backup', 
    'codex-cli', 
    'inactive', 
    FALSE, 
    '{"sandbox": true, "auto_approve": true, "tools": ["file", "code"]}'
);

INSERT INTO agents (agent_id, agent_type, status, is_primary, capabilities)
VALUES (
    'gemini_backup', 
    'gemini-cli', 
    'inactive', 
    FALSE, 
    '{"project_mode": true, "tools": ["file", "bash", "git"]}'
);

-- システム起動ログ
INSERT INTO system_logs (component, log_level, message)
VALUES ('database', 'INFO', 'Database initialized successfully');

-- 設定
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

-- 統計ビュー作成
CREATE VIEW task_statistics AS
SELECT 
    task_type,
    status,
    COUNT(*) as count,
    AVG(CASE 
        WHEN status = 'completed' 
        THEN (julianday(updated_at) - julianday(created_at)) * 24 * 60 
        ELSE NULL 
    END) as avg_completion_minutes
FROM task_master
GROUP BY task_type, status;

CREATE VIEW worker_statistics AS
SELECT 
    worker_id,
    worker_type,
    status,
    tasks_completed,
    tasks_failed,
    CASE 
        WHEN tasks_completed + tasks_failed > 0 
        THEN CAST(tasks_completed AS FLOAT) / (tasks_completed + tasks_failed) * 100 
        ELSE 0 
    END as success_rate,
    datetime(last_heartbeat, 'localtime') as last_seen
FROM workers;

-- バージョン情報
CREATE TABLE IF NOT EXISTS system_info (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO system_info (key, value)
VALUES ('version', '2.0.0');

INSERT OR REPLACE INTO system_info (key, value)
VALUES ('initialized_at', datetime('now'));

-- 完了メッセージ
SELECT 'Database initialization completed successfully' as message;