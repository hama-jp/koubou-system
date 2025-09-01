# 分散ワーカー（リモートノード）設計書

## 概要

分散ワーカーシステムは、工房システムを単一マシンから複数のリモートノードに拡張し、より大規模なタスク処理を可能にする機能です。

## 🎯 目的と利点

### 現在の制限（単一ノード）
- 最大ワーカー数: 3-4（ローカルリソースの制限）
- 処理能力: 1台のマシンのCPU/メモリに依存
- スケーラビリティ: 垂直スケーリングのみ

### 分散ワーカーで実現すること
- **水平スケーリング**: 複数マシンでワーカーを実行
- **地理的分散**: 異なる地域のサーバーで処理
- **リソース最適化**: 特定タスクに特化したノード
- **耐障害性**: ノード障害時の自動フェイルオーバー

## 🏗️ アーキテクチャ

```
┌─────────────────┐
│  Claude Code    │ ← メインエージェント
└────────┬────────┘
         │ MCP API
┌────────▼────────┐
│   MCP Server    │ ← 中央コントローラー
│  (Master Node)  │
└────────┬────────┘
         │
┌────────▼────────────────────────┐
│       Message Queue              │
│    (Redis/RabbitMQ/Kafka)        │
└──┬──────────┬──────────┬────────┘
   │          │          │
┌──▼───┐  ┌──▼───┐  ┌──▼───┐
│Node 1│  │Node 2│  │Node 3│  ← リモートワーカーノード
│Tokyo │  │Osaka │  │London│
└──┬───┘  └──┬───┘  └──┬───┘
   │          │          │
┌──▼───┐  ┌──▼───┐  ┌──▼───┐
│Worker│  │Worker│  │Worker│
│Pool  │  │Pool  │  │Pool  │
└──────┘  └──────┘  └──────┘
   ↓          ↓          ↓
[Ollama]  [Ollama]  [GPT-4]  ← 各ノードのLLM
```

## 📦 実装コンポーネント

### 1. マスターノード（中央管理）
```python
# master_node.py
class MasterNode:
    """分散ワーカーの中央管理ノード"""
    
    def __init__(self):
        self.registered_nodes = {}  # ノードID: ノード情報
        self.task_queue = None      # メッセージキュー
        self.health_monitor = None  # ヘルスチェック
        
    def register_node(self, node_info):
        """リモートノードを登録"""
        node_id = node_info['node_id']
        self.registered_nodes[node_id] = {
            'location': node_info['location'],
            'capacity': node_info['capacity'],
            'capabilities': node_info['capabilities'],
            'status': 'active',
            'last_heartbeat': datetime.now()
        }
        
    def assign_task(self, task):
        """タスクを適切なノードに割り当て"""
        # タスクの特性に応じて最適なノードを選択
        best_node = self.select_best_node(task)
        self.task_queue.publish(best_node, task)
        
    def select_best_node(self, task):
        """タスクに最適なノードを選択"""
        # 考慮要素:
        # - ノードの負荷状況
        # - タスクタイプとノードの能力
        # - データローカリティ
        # - レイテンシ
        pass
```

### 2. ワーカーノード（リモート実行）
```python
# remote_worker_node.py
class RemoteWorkerNode:
    """リモートワーカーノード"""
    
    def __init__(self, config):
        self.node_id = config['node_id']
        self.location = config['location']
        self.llm_endpoint = config['llm_endpoint']
        self.max_workers = config['max_workers']
        self.capabilities = config['capabilities']
        
    def connect_to_master(self, master_url):
        """マスターノードに接続"""
        self.register_with_master()
        self.start_heartbeat()
        self.subscribe_to_tasks()
        
    def process_task(self, task):
        """タスクを処理"""
        # ローカルのLLMを使用して処理
        if task['type'] in self.capabilities:
            result = self.execute_with_llm(task)
            self.report_result(result)
```

### 3. メッセージキューインターフェース
```python
# message_queue.py
class MessageQueueInterface:
    """メッセージキューの抽象インターフェース"""
    
    def publish(self, channel, message):
        """メッセージを発行"""
        pass
        
    def subscribe(self, channel, callback):
        """チャンネルを購読"""
        pass

class RedisQueue(MessageQueueInterface):
    """Redis実装"""
    def __init__(self):
        self.redis_client = redis.Redis()
        
class RabbitMQQueue(MessageQueueInterface):
    """RabbitMQ実装"""
    def __init__(self):
        self.connection = pika.BlockingConnection()
```

## 🌍 デプロイメント例

### ノード構成例

#### ノード1: 東京（高性能）
```yaml
node_id: tokyo-01
location: ap-northeast-1
capabilities:
  - code_generation
  - heavy_computation
llm:
  type: ollama
  model: gpt-oss:20b
  gpu: true
max_workers: 8
specialization: "コード生成特化"
```

#### ノード2: 大阪（汎用）
```yaml
node_id: osaka-01
location: ap-northeast-3
capabilities:
  - general_query
  - documentation
llm:
  type: ollama
  model: gemma2:2b
  gpu: false
max_workers: 4
specialization: "軽量タスク処理"
```

#### ノード3: ロンドン（機密データ処理）
```yaml
node_id: london-01
location: eu-west-2
capabilities:
  - confidential_processing
  - data_analysis
llm:
  type: local_gpt4
  model: gpt-4-local
  gpu: true
max_workers: 2
specialization: "機密データ処理（ローカル完結）"
```

## 🔄 タスクルーティング戦略

### 1. 地理的ルーティング
```python
def route_by_geography(task, nodes):
    """データローカリティを考慮したルーティング"""
    if task.data_location == 'japan':
        return select_japanese_node(nodes)
    elif task.data_location == 'europe':
        return select_european_node(nodes)
```

### 2. 能力ベースルーティング
```python
def route_by_capability(task, nodes):
    """ノードの特性に基づくルーティング"""
    if task.requires_gpu:
        return select_gpu_node(nodes)
    elif task.is_confidential:
        return select_secure_node(nodes)
```

### 3. 負荷分散ルーティング
```python
def route_by_load(task, nodes):
    """負荷状況に基づくルーティング"""
    return min(nodes, key=lambda n: n.current_load)
```

## 📊 モニタリングとメトリクス

### ノードメトリクス
- CPU/メモリ使用率
- タスク処理数/成功率
- 平均レスポンスタイム
- ネットワークレイテンシ

### ダッシュボード拡張
```javascript
// 分散ワーカー表示
const DistributedWorkerMap = () => {
  return (
    <WorldMap>
      <Node location="tokyo" status="active" load={75} />
      <Node location="osaka" status="active" load={30} />
      <Node location="london" status="idle" load={0} />
    </WorldMap>
  );
};
```

## 🔒 セキュリティ考慮事項

### 1. ノード間通信
- TLS/SSL暗号化
- 相互認証（mTLS）
- VPN/専用線接続

### 2. タスクの機密性
- 機密タスクは特定ノードのみ
- データの暗号化
- 監査ログ

### 3. アクセス制御
- ノード登録の認証
- APIキー管理
- ロールベースアクセス制御

## 🚀 実装ロードマップ

### Phase 1: 基本実装
1. メッセージキュー統合（Redis）
2. リモートノード登録機能
3. 基本的なタスクルーティング

### Phase 2: 高度な機能
1. 動的ノードディスカバリー
2. 自動フェイルオーバー
3. 地理的ルーティング

### Phase 3: エンタープライズ機能
1. Kubernetes統合
2. 自動スケーリング
3. マルチリージョン対応

## 📈 期待される効果

### パフォーマンス向上
- 処理能力: 10倍以上（ノード数に応じて）
- 同時処理数: 50+ タスク
- レスポンスタイム: 地理的に近いノードで高速化

### 可用性向上
- 99.9% アップタイム（冗長性により）
- 自動フェイルオーバー
- 無停止メンテナンス

### コスト最適化
- 必要に応じたノード追加/削除
- スポットインスタンス活用
- リソースの効率的利用

---

これが分散ワーカー（リモートノード）の実装内容です。
単一マシンの制限を超えて、グローバルスケールでタスク処理が可能になります！