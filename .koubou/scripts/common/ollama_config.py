#!/usr/bin/env python3
"""
Ollama設定管理モジュール
設定ファイルからOllamaモデルの設定を読み込み、管理する
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

class OllamaConfigManager:
    """Ollamaモデルの設定を管理するクラス"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        設定マネージャーの初期化
        
        Args:
            config_path: 設定ファイルのパス（省略時はデフォルトパスを使用）
        """
        if config_path is None:
            koubou_home = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
            config_path = os.path.join(koubou_home, 'config', 'ollama_models.yaml')
        
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded Ollama config from {self.config_path}")
                return config
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を返す"""
        return {
            'default_model': 'gpt-oss-20b',
            'server': {
                'host': 'http://localhost:11434',
                'timeout': 300,
                'retry_count': 3,
                'retry_delay': 5
            },
            'models': {
                'gpt-oss-20b': {
                    'name': 'gpt-oss:20b',
                    'options': {
                        'temperature': 0.3,
                        'num_ctx': 8192
                    }
                }
            }
        }
    
    def get_model_config(self, model_key: Optional[str] = None) -> Dict[str, Any]:
        """
        指定されたモデルの設定を取得
        
        Args:
            model_key: モデルのキー名（省略時はデフォルトモデル）
        
        Returns:
            モデル設定の辞書
        """
        if model_key is None:
            model_key = self.config.get('default_model', 'gpt-oss-20b')
        
        models = self.config.get('models', {})
        if model_key not in models:
            logger.warning(f"Model '{model_key}' not found in config, using default")
            model_key = self.config.get('default_model', 'gpt-oss-20b')
        
        return models.get(model_key, self._get_default_config()['models']['gpt-oss-20b'])
    
    def get_model_name(self, model_key: Optional[str] = None) -> str:
        """
        モデルの実際の名前を取得
        
        Args:
            model_key: モデルのキー名
        
        Returns:
            Ollamaで使用するモデル名
        """
        model_config = self.get_model_config(model_key)
        return model_config.get('name', 'gpt-oss:20b')
    
    def get_model_options(self, model_key: Optional[str] = None) -> Dict[str, Any]:
        """
        モデルのオプション設定を取得
        
        Args:
            model_key: モデルのキー名
        
        Returns:
            モデルのオプション辞書
        """
        model_config = self.get_model_config(model_key)
        return model_config.get('options', {})
    
    def get_server_config(self) -> Dict[str, Any]:
        """サーバー設定を取得"""
        return self.config.get('server', self._get_default_config()['server'])
    
    def get_server_host(self) -> str:
        """サーバーホストを取得"""
        server_config = self.get_server_config()
        return server_config.get('host', 'http://localhost:11434')
    
    def get_recommended_model_for_task(self, task_type: str) -> str:
        """
        タスクタイプに応じた推奨モデルを取得
        
        Args:
            task_type: タスクのタイプ
        
        Returns:
            推奨モデルのキー名
        """
        recommendations = self.config.get('task_recommendations', {})
        return recommendations.get(task_type, self.config.get('default_model', 'gpt-oss-20b'))
    
    def list_available_models(self) -> List[str]:
        """利用可能なモデルのリストを取得"""
        return list(self.config.get('models', {}).keys())
    
    def get_model_description(self, model_key: str) -> str:
        """モデルの説明を取得"""
        model_config = self.get_model_config(model_key)
        return model_config.get('description', 'No description available')
    
    def get_model_use_cases(self, model_key: str) -> List[str]:
        """モデルの使用ケースを取得"""
        model_config = self.get_model_config(model_key)
        return model_config.get('use_cases', [])
    
    def reload_config(self):
        """設定ファイルを再読み込み"""
        self.config = self._load_config()
        logger.info("Reloaded Ollama configuration")
    
    def update_model_in_runtime(self, model_key: str, options: Dict[str, Any]):
        """
        実行時にモデル設定を一時的に更新（ファイルには保存しない）
        
        Args:
            model_key: モデルのキー名
            options: 更新するオプション
        """
        if 'models' not in self.config:
            self.config['models'] = {}
        
        if model_key not in self.config['models']:
            self.config['models'][model_key] = {}
        
        if 'options' not in self.config['models'][model_key]:
            self.config['models'][model_key]['options'] = {}
        
        self.config['models'][model_key]['options'].update(options)
        logger.info(f"Updated runtime options for model '{model_key}': {options}")


# グローバルインスタンス（シングルトン）
_config_manager = None

def get_ollama_config() -> OllamaConfigManager:
    """設定マネージャーのグローバルインスタンスを取得"""
    global _config_manager
    if _config_manager is None:
        _config_manager = OllamaConfigManager()
    return _config_manager


if __name__ == "__main__":
    # テスト用コード
    config = get_ollama_config()
    
    print("=== Ollama Configuration Manager Test ===")
    print(f"Default model: {config.config.get('default_model')}")
    print(f"Server host: {config.get_server_host()}")
    print(f"Available models: {config.list_available_models()}")
    
    # デフォルトモデルの情報表示
    default_model = config.config.get('default_model')
    print(f"\n--- Default Model: {default_model} ---")
    print(f"Name: {config.get_model_name()}")
    print(f"Description: {config.get_model_description(default_model)}")
    print(f"Options: {config.get_model_options()}")
    print(f"Use cases: {config.get_model_use_cases(default_model)}")
    
    # タスク別推奨モデル
    print("\n--- Task Recommendations ---")
    for task in ['code_generation', 'code_review', 'documentation']:
        model = config.get_recommended_model_for_task(task)
        print(f"{task}: {model}")