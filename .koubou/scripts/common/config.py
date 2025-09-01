#!/usr/bin/env python3
"""
中央設定管理モジュール
System-wide configuration management for Koubou
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class ConfigManager:
    """中央設定を管理するクラス"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        """シングルトンパターンの実装"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """設定マネージャーの初期化"""
        if self._config is None:
            self.reload()
    
    def reload(self):
        """設定ファイルを再読み込み"""
        koubou_home = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
        config_path = os.path.join(koubou_home, 'config', 'system.yaml')
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            
            # 環境変数の展開
            self._config = self._expand_env_vars(self._config)
            
            logger.info(f"Configuration loaded from {config_path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            self._config = self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults", exc_info=True)
            self._config = self._get_default_config()
    
    def _expand_env_vars(self, config: Any) -> Any:
        """設定値内の環境変数を展開"""
        if isinstance(config, dict):
            return {k: self._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            # ${VAR:-default}形式の環境変数を展開
            pattern = r'\$\{([^:}]+)(?::([^}]*))?\}'
            
            def replacer(match):
                var_name = match.group(1)
                default_value = match.group(2) or ''
                # KOUBOU_HOMEの特別処理
                if var_name == 'KOUBOU_HOME' and not os.environ.get(var_name):
                    return '/home/hama/project/koubou-system/.koubou'
                return os.environ.get(var_name, default_value if default_value else '')
            
            return re.sub(pattern, replacer, config)
        else:
            return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を返す"""
        koubou_home = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
        return {
            'system': {
                'name': 'koubou-system',
                'version': '1.0.0',
                'environment': 'production'
            },
            'paths': {
                'koubou_home': koubou_home,
                'database': f"{koubou_home}/db/koubou.db",
                'logs': f"{koubou_home}/logs",
                'outputs': f"{koubou_home}/outputs",
                'pids': f"{koubou_home}/pids",
                'cache': f"{koubou_home}/cache",
                'allowed_dirs': [
                    f"{koubou_home}/outputs",
                    f"{koubou_home}/workspaces",
                    "/tmp/koubou"
                ]
            },
            'database': {
                'type': 'sqlite',
                'path': f"{koubou_home}/db/koubou.db",
                'pool_size': 10,
                'timeout': 30,
                'retry_count': 3,
                'retry_delay': 0.5
            },
            'api': {
                'mcp_server': {
                    'host': '0.0.0.0',
                    'port': 8765
                },
                'websocket': {
                    'host': '0.0.0.0',
                    'port': 8766
                },
                'graphql': {
                    'host': '0.0.0.0',
                    'port': 8767
                },
                'dashboard': {
                    'host': '0.0.0.0',
                    'port': 8080
                }
            },
            'logging': {
                'level': 'INFO',
                'file': {
                    'enabled': True,
                    'path': f"{koubou_home}/logs/system.log"
                },
                'detailed': {
                    'error_stack_traces': True
                }
            },
            'security': {
                'file_operations': {
                    'enabled': True,
                    'max_file_size': 104857600,
                    'allowed_extensions': ['.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml', '.md', '.txt', '.sh']
                }
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        ドット記法でネストされた設定値を取得
        
        Args:
            key_path: 設定キーのパス（例: "api.mcp_server.port"）
            default: キーが存在しない場合のデフォルト値
        
        Returns:
            設定値またはデフォルト値
        """
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_path(self, path_key: str) -> Path:
        """
        パス設定を取得してPathオブジェクトとして返す
        
        Args:
            path_key: パスのキー名
        
        Returns:
            Pathオブジェクト
        """
        path_str = self.get(f'paths.{path_key}', '')
        if not path_str:
            koubou_home = self.get('paths.koubou_home', '/home/hama/project/koubou-system/.koubou')
            path_str = f"{koubou_home}/{path_key}"
        return Path(path_str)
    
    def get_db_config(self) -> Dict[str, Any]:
        """データベース設定を取得"""
        return self.get('database', {})
    
    def get_api_config(self, api_name: str) -> Dict[str, Any]:
        """
        特定APIの設定を取得
        
        Args:
            api_name: API名（mcp_server, websocket, graphql, dashboard）
        
        Returns:
            API設定の辞書
        """
        return self.get(f'api.{api_name}', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """ロギング設定を取得"""
        return self.get('logging', {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """セキュリティ設定を取得"""
        return self.get('security', {})
    
    def is_path_allowed(self, path: str) -> bool:
        """
        指定されたパスが許可されたディレクトリ内にあるか確認
        
        Args:
            path: 確認するパス
        
        Returns:
            許可されている場合True
        """
        if not self.get('security.file_operations.enabled', True):
            return True
        
        allowed_dirs = self.get('paths.allowed_dirs', [])
        abs_path = os.path.abspath(path)
        
        for allowed_dir in allowed_dirs:
            allowed_abs = os.path.abspath(allowed_dir)
            if abs_path.startswith(allowed_abs):
                return True
        
        return False
    
    def is_extension_allowed(self, filename: str) -> bool:
        """
        ファイルの拡張子が許可されているか確認
        
        Args:
            filename: ファイル名
        
        Returns:
            許可されている場合True
        """
        if not self.get('security.file_operations.enabled', True):
            return True
        
        allowed_exts = self.get('security.file_operations.allowed_extensions', [])
        _, ext = os.path.splitext(filename)
        return ext.lower() in allowed_exts
    
    def validate_file_operation(self, filepath: str) -> tuple[bool, str]:
        """
        ファイル操作の妥当性を検証
        
        Args:
            filepath: 操作対象のファイルパス
        
        Returns:
            (有効性, エラーメッセージ)のタプル
        """
        # パスの検証
        if not self.is_path_allowed(filepath):
            allowed_dirs = ', '.join(self.get('paths.allowed_dirs', []))
            return False, f"Path not in allowed directories: {allowed_dirs}"
        
        # 拡張子の検証
        if not self.is_extension_allowed(filepath):
            allowed_exts = ', '.join(self.get('security.file_operations.allowed_extensions', []))
            return False, f"File extension not allowed. Allowed: {allowed_exts}"
        
        # ファイルサイズの検証（既存ファイルの場合）
        if os.path.exists(filepath):
            max_size = self.get('security.file_operations.max_file_size', 104857600)
            file_size = os.path.getsize(filepath)
            if file_size > max_size:
                return False, f"File size {file_size} exceeds maximum {max_size}"
        
        return True, ""
    
    def update_runtime(self, key_path: str, value: Any):
        """
        実行時に設定を一時的に更新（ファイルには保存しない）
        
        Args:
            key_path: 設定キーのパス
            value: 新しい値
        """
        keys = key_path.split('.')
        config = self._config
        
        # 最後のキー以外をたどる
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 最後のキーに値を設定
        config[keys[-1]] = value
        logger.info(f"Updated runtime config: {key_path} = {value}")
    
    @property
    def config(self) -> Dict[str, Any]:
        """設定全体を取得（読み取り専用）"""
        return self._config.copy()


# グローバルインスタンス
_config_manager = None

def get_config() -> ConfigManager:
    """設定マネージャーのグローバルインスタンスを取得"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def setup_logging():
    """設定に基づいてロギングをセットアップ"""
    config = get_config()
    log_config = config.get_logging_config()
    
    # ログレベルの設定
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    
    # ログフォーマットの設定
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # ファイルハンドラーの設定
    handlers = []
    if log_config.get('file.enabled', True):
        log_path = log_config.get('file.path', '/tmp/system.log')
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=log_config.get('file.max_size', 10485760),
            backupCount=log_config.get('file.backup_count', 5)
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # ルートロガーの設定
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )
    
    logger.info("Logging configured successfully")


if __name__ == "__main__":
    # テスト用コード
    setup_logging()
    config = get_config()
    
    print("=== Configuration Manager Test ===")
    print(f"System name: {config.get('system.name')}")
    print(f"Database path: {config.get('database.path')}")
    print(f"MCP Server port: {config.get('api.mcp_server.port')}")
    print(f"Log level: {config.get('logging.level')}")
    
    # パス検証テスト
    print("\n--- Path Validation Test ---")
    test_paths = [
        "/home/hama/project/koubou-system/.koubou/outputs/test.py",
        "/etc/passwd",
        "/tmp/koubou/test.sh"
    ]
    
    for path in test_paths:
        is_valid, msg = config.validate_file_operation(path)
        print(f"{path}: {'✅ Valid' if is_valid else f'❌ {msg}'}")