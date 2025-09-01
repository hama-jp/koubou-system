# 🔧 工房システム 拡張性ロードマップ

## 📋 review_report.md 課題解決状況

### ✅ 解決済み課題

| 課題 | 状況 | 実装内容 |
|------|------|----------|
| **データベース重複** | ✅ 完了 | `common/database.py`で一元化済み |
| **最大ワーカー数** | ✅ 完了 | デフォルト3に制限、警告メッセージ付き |
| **タイムアウト調整** | ✅ 完了 | 120秒に延長済み |
| **リトライ機構** | ✅ 完了 | 指数バックオフ付き3回リトライ実装 |

### 🎯 次期課題: Agent Adapter パターン導入

## 🏗️ v2.0 アーキテクチャ移行計画

### 現状の密結合構造
```
local_worker.py
├── run_codex_task() → codex-exec.sh
└── run_ollama_task() → ollama run gpt-oss:20b
```

### 目標の抽象化構造
```
local_worker.py
├── AgentManager
    ├── OllamaAdapter → ollama run [model]
    ├── CodexAdapter → codex-exec.sh
    ├── GPT4Adapter → openai api
    └── GeminiAdapter → google api
```

## 📈 段階的実装ロードマップ

### Phase 1: 基盤整備 (v2.1)
- [ ] `common/agent_adapter.py` 抽象基底クラス作成
- [ ] `StandardTask` データクラス定義
- [ ] 既存Ollama/Codexをアダプター形式でラップ
- [ ] **目標**: 機能維持しながら内部構造を抽象化

### Phase 2: 新エージェント追加 (v2.2)
- [ ] OpenAI GPT-4 Adapter 実装
- [ ] Google Gemini Adapter 実装 
- [ ] エージェント選択ロジックの実装
- [ ] **目標**: タスクタイプ別エージェント自動選択

### Phase 3: 高度な機能 (v2.3)
- [ ] エージェント性能監視・ベンチマーク
- [ ] 負荷分散アルゴリズム改善
- [ ] ハイブリッド実行（複数エージェント協調）
- [ ] **目標**: 最適なエージェント組み合わせで処理効率最大化

## 🧩 Agent Adapter パターン詳細設計

### 1. 抽象基底クラス
```python
# common/agent_adapter.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class StandardTask:
    task_id: str
    task_type: str  # 'general', 'code', 'analysis'
    prompt: str
    context: Optional[Dict[str, Any]] = None
    priority: int = 5

class AgentAdapter(ABC):
    @abstractmethod
    def execute_task(self, task: StandardTask) -> Dict[str, Any]:
        """タスクを実行し、標準形式で結果を返す"""
        pass
    
    @abstractmethod  
    def get_capabilities(self) -> Dict[str, Any]:
        """エージェントの能力・制約を返す"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """エージェントの稼働状況を確認"""
        pass
```

### 2. Ollama Adapter実装例
```python
# agents/ollama_adapter.py
class OllamaAdapter(AgentAdapter):
    def __init__(self, model: str = "gpt-oss:20b"):
        self.model = model
        self.timeout = 120
        self.max_retries = 3
    
    def execute_task(self, task: StandardTask) -> Dict[str, Any]:
        # 既存のrun_ollama_taskロジックを移植
        return self._execute_with_retry(task)
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "task_types": ["general", "analysis", "creative"],
            "max_tokens": 4096,
            "concurrent_limit": 3,
            "avg_response_time": 30.0
        }
```

### 3. エージェント管理クラス
```python
# common/agent_manager.py
class AgentManager:
    def __init__(self):
        self.adapters = {
            'ollama': OllamaAdapter(),
            'codex': CodexAdapter(),
            'gpt4': GPT4Adapter(),  # 将来追加
        }
    
    def select_best_agent(self, task: StandardTask) -> str:
        """タスクに最適なエージェントを選択"""
        if task.task_type == 'code':
            return 'codex'
        elif task.priority > 8:  # 高優先度
            return 'gpt4'  
        else:
            return 'ollama'
    
    def execute_task(self, task: StandardTask) -> Dict[str, Any]:
        agent_name = self.select_best_agent(task)
        return self.adapters[agent_name].execute_task(task)
```

## 🔄 移行戦略

### 移行手順
1. **抽象化レイヤー作成** - 既存コードに影響なし
2. **段階的置換** - `local_worker.py`を徐々にリファクタリング
3. **後方互換性維持** - 既存APIエンドポイント維持
4. **テスト駆動** - 各段階でのテスト実行

### リスク軽減
- **ブランチ戦略**: `feature/agent-adapter`で開発
- **フィーチャーフラグ**: 旧実装との切り替え可能性
- **段階的ロールアウト**: 一部タスクから開始

## 📊 成功指標

| 指標 | 現状 | 目標値 |
|------|------|--------|
| **サポートエージェント数** | 2種類 | 4-5種類 |
| **新エージェント追加工数** | 1週間 | 1日 |
| **処理成功率** | 95% | 98%+ |
| **平均応答時間** | 30秒 | 25秒 |

## 🎯 次のアクション

1. **Phase 1開始**: `common/agent_adapter.py`実装
2. **プロトタイプ作成**: 既存OllamaをAdapter形式でラップ
3. **テスト実行**: 機能回帰がないか確認

---

**すべての review_report.md 課題は解決済みです。次は将来性向上に取り組みます！** 🚀