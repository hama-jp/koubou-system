-- リモートワーカー対応のためのデータベーススキーマ拡張
-- 実行日: 2025-09-01

-- workers テーブルに新しいカラムを追加
ALTER TABLE workers ADD COLUMN location TEXT DEFAULT 'local';
ALTER TABLE workers ADD COLUMN performance_factor REAL DEFAULT 1.0;
ALTER TABLE workers ADD COLUMN endpoint_url TEXT;
ALTER TABLE workers ADD COLUMN network_latency_ms INTEGER;
ALTER TABLE workers ADD COLUMN last_health_check TIMESTAMP;

-- ワーカーメトリクステーブルの作成
CREATE TABLE IF NOT EXISTS worker_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    tokens_processed INTEGER,
    prompt_length INTEGER,
    output_length INTEGER,
    success BOOLEAN NOT NULL,
    error_type TEXT,
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- インデックスの追加
CREATE INDEX IF NOT EXISTS idx_worker_metrics_worker_id ON worker_metrics(worker_id);
CREATE INDEX IF NOT EXISTS idx_worker_metrics_measured_at ON worker_metrics(measured_at);
CREATE INDEX IF NOT EXISTS idx_workers_location ON workers(location);
CREATE INDEX IF NOT EXISTS idx_workers_performance ON workers(performance_factor);

-- 既存のワーカーのlocationとperformance_factorを初期化
UPDATE workers SET location = 'local', performance_factor = 1.0 WHERE location IS NULL;