# 🏭 工房システム - リモートワーカー拡張設計書

## 📋 概要

工房システムをLAN上のOllamaサーバーへ拡張する設計案です。重要な点として、**リモートOllamaも直接使用せず、gemini-repo-cli経由でエージェントとして活用**します。

### 設計方針
- ✅ **統一インターフェース**: すべてのLLMアクセスはgemini-repo-cli経由
- ✅ **エージェント化**: リモートOllamaも職人（エージェント）として動作
- ✅ **品質保証**: gemini-repo-cliのコンテキスト管理・プロンプト最適化を活用

## 🏗️ アーキテクチャ設計

### 1. ワーカー階層構造

```
┌─────────────────────────────────────────────────────────┐
│                   Worker Pool Manager                     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │            gemini-repo-cli (統一インターフェース)  │    │
│  └──────────────┬─────────────────┬────────────────┘    │
│                 │                 │                      │
│     ┌───────────▼──────┐   ┌─────▼──────────────┐      │
│     │  Local Worker    │   │  Remote Worker     │      │
│     │  ---------------  │   │  ----------------  │      │
│     │  Ollama@localhost│   │  Ollama@LAN       │      │
│     │  gpt-oss:20b    │   │  gpt-oss:20b      │      │
│     │  100% speed     │   │  50% speed        │      │
│     └──────────────────┘   └────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### 2. RemoteWorker実装

```python
class RemoteWorker(LocalWorker):
    """
    リモートOllamaサーバーを使用するワーカー
    LocalWorkerを継承し、gemini-repo-cli経由でアクセス
    """
    
    def __init__(self, worker_id: str, worker_config: dict):
        # 基本設定を継承
        super().__init__(worker_id, worker_config)
        
        # リモート特有の設定
        self.remote_host = worker_config.get('remote_host', 'localhost')
        self.remote_port = worker_config.get('remote_port', 11434)
        self.performance_factor = worker_config.get('performance_factor', 0.5)
        self.network_timeout = worker_config.get('network_timeout', 300)
        
        # gemini-repo-cli用の設定を更新
        self.server_host = f"http://{self.remote_host}:{self.remote_port}"
        
        # ワーカー識別情報
        self.worker_location = 'remote'
        self.endpoint_url = self.server_host
        
        self.logger.info(f"🌐 Remote worker initialized: {worker_id} @ {self.server_host}")
    
    def run_gemini_repo_cli_direct(self, prompt: str, input_files: list, output_file: str = None) -> Dict[str, Any]:
        """
        リモートOllama向けにカスタマイズされたgemini-repo-cli実行
        """
        # 基本的な処理は親クラスと同じだが、リモート特有の設定を追加
        try:
            from gemini_repo.ollama_api import OllamaRepoAPI
            
            # リモートOllamaサーバーへの接続
            api = OllamaRepoAPI(
                model_name=self.model,
                host=self.server_host,
                timeout=self.network_timeout
            )
            
            # ネットワーク遅延を考慮した設定
            if hasattr(api, 'options'):
                api.options.update({
                    **self.model_options,
                    'num_predict': 4096,  # レスポンスサイズ制限
                    'num_ctx': 8192,      # コンテキストサイズ
                })
            
            # 以降は親クラスと同様の処理
            return super().run_gemini_repo_cli_direct(prompt, input_files, output_file)
            
        except Exception as e:
            self.logger.error(f"Remote worker error: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }
    
    def health_check(self) -> bool:
        """リモートサーバーのヘルスチェック"""
        try:
            import requests
            response = requests.get(
                f"{self.server_host}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
```

### 3. ワーカー設定ファイル

```yaml
# .koubou/config/workers.yaml
workers:
  # ローカルワーカー
  local_workers:
    - worker_id: "local_001"
      worker_type: "local"
      model: "gpt-oss:20b"
      server_host: "http://localhost:11434"
      performance_factor: 1.0
      max_concurrent_tasks: 2
      
  # リモートワーカー
  remote_workers:
    - worker_id: "remote_lan_001"
      worker_type: "remote"
      model: "gpt-oss:20b"
      remote_host: "192.168.1.100"
      remote_port: 11434
      performance_factor: 0.5
      max_concurrent_tasks: 1
      network_timeout: 300
      
    - worker_id: "remote_lan_002"
      worker_type: "remote"
      model: "gpt-oss:20b"
      remote_host: "192.168.1.101"
      remote_port: 11434
      performance_factor: 0.5
      max_concurrent_tasks: 1
      network_timeout: 300

# ルーティングポリシー
routing_policy:
  strategy: "priority_based"
  rules:
    - priority_range: [8, 10]
      preferred_workers: ["local"]
      reason: "高優先度タスクは高速なローカル処理"
      
    - priority_range: [5, 7]
      preferred_workers: ["local", "remote"]
      reason: "中優先度は負荷分散"
      
    - priority_range: [1, 4]
      preferred_workers: ["remote"]
      reason: "低優先度はリモート優先でローカルリソース温存"
```

### 4. WorkerPoolManager拡張

```python
class EnhancedWorkerPoolManager(WorkerPoolManager):
    """拡張版ワーカープールマネージャー"""
    
    def __init__(self, min_workers=1, max_workers=5, max_active_tasks=2):
        super().__init__(min_workers, max_workers, max_active_tasks)
        
        # ワーカー設定の読み込み
        self.worker_configs = self.load_worker_configs()
        
        # リモートワーカーの管理
        self.remote_workers = {}
        
        # タスクルーター
        self.task_router = TaskRouter(self.worker_configs.get('routing_policy', {}))
        
    def load_worker_configs(self) -> dict:
        """ワーカー設定ファイルの読み込み"""
        config_path = f"{KOUBOU_HOME}/config/workers.yaml"
        if os.path.exists(config_path):
            import yaml
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    def initialize_workers(self):
        """ローカル・リモートワーカーの初期化"""
        # ローカルワーカーの起動
        for config in self.worker_configs.get('local_workers', []):
            self.start_local_worker(config)
        
        # リモートワーカーの起動
        for config in self.worker_configs.get('remote_workers', []):
            self.start_remote_worker(config)
    
    def start_remote_worker(self, config: dict):
        """リモートワーカーの起動"""
        worker_id = config['worker_id']
        
        # リモートワーカースクリプトの起動
        worker_script = f"{KOUBOU_HOME}/scripts/workers/remote_worker.py"
        
        cmd = [
            sys.executable, worker_script,
            '--worker-id', worker_id,
            '--config', json.dumps(config)
        ]
        
        # ログファイルのパス
        log_file = LOG_DIR / f"{worker_id}.log"
        
        try:
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env={**os.environ, 'PYTHONUNBUFFERED': '1'}
                )
            
            self.remote_workers[worker_id] = process
            
            # データベースに登録
            db.register_worker(
                worker_id=worker_id,
                worker_type='remote',
                capabilities=config.get('capabilities', ['general']),
                location=config.get('remote_host', 'unknown'),
                performance_factor=config.get('performance_factor', 0.5)
            )
            
            self.logger.info(f"🌐 Started remote worker: {worker_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to start remote worker {worker_id}: {e}")
```

### 5. タスクルーティング実装

```python
class TaskRouter:
    """優先度ベースのタスクルーティング"""
    
    def __init__(self, routing_policy: dict):
        self.policy = routing_policy
        self.strategy = routing_policy.get('strategy', 'priority_based')
        self.rules = routing_policy.get('rules', [])
    
    def route_task(self, task: dict, available_workers: list) -> Optional[str]:
        """
        タスクを最適なワーカーにルーティング
        
        Args:
            task: タスク情報（priority含む）
            available_workers: 利用可能なワーカーリスト
            
        Returns:
            選択されたworker_id または None
        """
        priority = task.get('priority', 5)
        
        # 優先度ベースのルール適用
        for rule in self.rules:
            priority_range = rule.get('priority_range', [1, 10])
            if priority_range[0] <= priority <= priority_range[1]:
                preferred_types = rule.get('preferred_workers', [])
                
                # 優先ワーカータイプから選択
                for worker_type in preferred_types:
                    candidates = [
                        w for w in available_workers 
                        if self._match_worker_type(w, worker_type)
                    ]
                    
                    if candidates:
                        # パフォーマンスファクターで重み付け選択
                        return self._select_best_worker(candidates, task)
        
        # デフォルト: 最初の利用可能なワーカー
        return available_workers[0]['worker_id'] if available_workers else None
    
    def _match_worker_type(self, worker: dict, worker_type: str) -> bool:
        """ワーカータイプのマッチング"""
        if worker_type == 'local':
            return worker.get('location', 'local') == 'local'
        elif worker_type == 'remote':
            return worker.get('location', 'local') != 'local'
        return True
    
    def _select_best_worker(self, candidates: list, task: dict) -> str:
        """候補から最適なワーカーを選択"""
        # スコア計算
        scores = []
        for worker in candidates:
            score = self._calculate_worker_score(worker, task)
            scores.append((worker['worker_id'], score))
        
        # 最高スコアのワーカーを選択
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0] if scores else None
    
    def _calculate_worker_score(self, worker: dict, task: dict) -> float:
        """ワーカーのスコア計算"""
        score = 0.0
        
        # パフォーマンスファクター
        score += worker.get('performance_factor', 1.0) * 100
        
        # 現在の負荷（アイドル優先）
        if worker.get('status') == 'idle':
            score += 50
        elif worker.get('status') == 'busy':
            score -= 30
        
        # 成功率
        success_rate = worker.get('success_rate', 1.0)
        score += success_rate * 30
        
        # タスクタイプとの相性
        task_type = task.get('type', 'general')
        capabilities = worker.get('capabilities', [])
        if task_type in capabilities:
            score += 20
        
        return score
```

### 6. データベーススキーマ拡張

```sql
-- workers テーブルの拡張
ALTER TABLE workers ADD COLUMN location TEXT DEFAULT 'local';
ALTER TABLE workers ADD COLUMN performance_factor REAL DEFAULT 1.0;
ALTER TABLE workers ADD COLUMN endpoint_url TEXT;
ALTER TABLE workers ADD COLUMN network_latency_ms INTEGER;
ALTER TABLE workers ADD COLUMN last_health_check TIMESTAMP;

-- ワーカーメトリクステーブル
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

-- インデックス追加
CREATE INDEX idx_worker_metrics_worker_id ON worker_metrics(worker_id);
CREATE INDEX idx_worker_metrics_measured_at ON worker_metrics(measured_at);
```

## 📊 モニタリング機能

### パフォーマンス監視

```python
class WorkerPerformanceMonitor:
    """ワーカーパフォーマンス監視"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.performance_cache = {}
        
    def record_execution(self, worker_id: str, task_id: str, 
                        execution_time: float, success: bool,
                        prompt_length: int = 0, output_length: int = 0):
        """実行メトリクスの記録"""
        self.db.execute("""
            INSERT INTO worker_metrics 
            (worker_id, task_id, execution_time_ms, success, 
             prompt_length, output_length, measured_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (worker_id, task_id, int(execution_time * 1000), 
              success, prompt_length, output_length))
    
    def get_worker_stats(self, worker_id: str, hours: int = 24) -> dict:
        """ワーカーの統計情報取得"""
        stats = self.db.query_one("""
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_tasks,
                AVG(execution_time_ms) as avg_execution_time,
                MIN(execution_time_ms) as min_execution_time,
                MAX(execution_time_ms) as max_execution_time,
                AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
            FROM worker_metrics
            WHERE worker_id = ?
                AND measured_at > datetime('now', '-{} hours')
        """.format(hours), (worker_id,))
        
        return dict(stats) if stats else {}
    
    def update_performance_factors(self):
        """実測値に基づくパフォーマンスファクター更新"""
        # ローカルワーカーの平均実行時間を基準とする
        local_stats = self.db.query_one("""
            SELECT AVG(execution_time_ms) as avg_time
            FROM worker_metrics wm
            JOIN workers w ON wm.worker_id = w.worker_id
            WHERE w.location = 'local'
                AND wm.measured_at > datetime('now', '-24 hours')
        """)
        
        if not local_stats or not local_stats['avg_time']:
            return
        
        local_avg_time = local_stats['avg_time']
        
        # 各ワーカーのパフォーマンスファクター更新
        workers = self.db.query("""
            SELECT DISTINCT w.worker_id, w.location,
                AVG(wm.execution_time_ms) as avg_time
            FROM workers w
            LEFT JOIN worker_metrics wm ON w.worker_id = wm.worker_id
            WHERE wm.measured_at > datetime('now', '-24 hours')
            GROUP BY w.worker_id
        """)
        
        for worker in workers:
            if worker['avg_time']:
                # パフォーマンスファクター = ローカル平均時間 / ワーカー平均時間
                new_factor = local_avg_time / worker['avg_time']
                # 0.1〜2.0の範囲に制限
                new_factor = max(0.1, min(2.0, new_factor))
                
                self.db.execute("""
                    UPDATE workers 
                    SET performance_factor = ?
                    WHERE worker_id = ?
                """, (new_factor, worker['worker_id']))
```

## 🚀 実装手順

### Phase 1: 基盤準備（2-3日）
1. `remote_worker.py`の作成（LocalWorkerを継承）
2. データベーススキーマの拡張
3. 設定ファイル形式の定義

### Phase 2: ルーティング実装（2-3日）
1. TaskRouterクラスの実装
2. WorkerPoolManagerの拡張
3. 優先度ベースルーティングのテスト

### Phase 3: モニタリング（1-2日）
1. パフォーマンスメトリクス収集
2. ダッシュボードへの統合
3. アラート機能の追加

### Phase 4: 運用最適化（継続）
1. 実測値に基づく調整
2. エラーハンドリング強化
3. フェイルオーバー機能

## ⚠️ 注意事項

### セキュリティ
- LAN内通信のみに限定
- gemini-repo-cli経由でのアクセス統制
- プロンプトインジェクション対策

### 信頼性
- ネットワーク断絶時の処理
- タイムアウト設定の最適化
- 自動リトライメカニズム

### パフォーマンス
- ネットワーク遅延の影響を考慮
- バッチ処理の最適化
- キャッシュ活用

## 📈 期待される効果

1. **処理能力の拡張**: LAN内リソースの有効活用
2. **品質の統一**: gemini-repo-cliによる一貫した処理
3. **柔軟な拡張性**: 新しいOllamaサーバーの追加が容易
4. **リソース最適化**: 優先度に応じた適切な振り分け

## 🔄 移行パス

1. **後方互換性維持**: 既存のローカルワーカーはそのまま動作
2. **段階的導入**: 設定ファイルでリモートワーカーを段階的に追加
3. **フォールバック**: リモート利用不可時はローカルのみで継続動作

---

この設計により、すべてのLLMアクセスをgemini-repo-cli経由で統一し、品質と管理性を保ちながらスケーラビリティを実現します。