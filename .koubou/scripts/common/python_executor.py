#!/usr/bin/env python3
"""
Python実行環境の統一化モジュール - uv優先実行

工房システム内でのPython実行を統一し、環境の違いによるエラーを防ぐ
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any


class PythonExecutor:
    """統一Python実行環境管理クラス"""
    
    def __init__(self, koubou_home: Optional[str] = None):
        self.koubou_home = koubou_home or os.environ.get('KOUBOU_HOME', '.koubou')
        self.project_root = Path(self.koubou_home).parent
        
    def get_python_command(self) -> List[str]:
        """最適なPython実行コマンドを決定"""
        
        # 1. uvが利用可能かチェック
        if self._is_uv_available():
            return ['uv', 'run', 'python']
            
        # 2. 仮想環境のPythonをチェック
        venv_python = self.project_root / '.venv' / 'bin' / 'python'
        if venv_python.exists():
            return [str(venv_python)]
            
        # 3. システムのpython3をチェック
        if self._is_command_available('python3'):
            return ['python3']
            
        # 4. システムのpythonをチェック（最終手段）
        if self._is_command_available('python'):
            return ['python']
            
        # 5. どれも利用できない場合はエラー
        raise RuntimeError("No Python interpreter found. Please install Python or uv.")
    
    def execute(self, script_path: str, args: Optional[List[str]] = None, 
                cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None,
                capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Pythonスクリプトを統一環境で実行
        
        Args:
            script_path: 実行するPythonスクリプトのパス
            args: スクリプトに渡す引数
            cwd: 実行ディレクトリ
            env: 環境変数
            capture_output: 出力をキャプチャするか
            
        Returns:
            subprocess.CompletedProcess: 実行結果
        """
        python_cmd = self.get_python_command()
        cmd = python_cmd + [script_path]
        
        if args:
            cmd.extend(args)
            
        # 環境変数の設定
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)
            
        # KOUBOU_HOME を確実に設定
        exec_env['KOUBOU_HOME'] = str(Path(self.koubou_home).resolve())
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or str(self.project_root),
                env=exec_env,
                capture_output=capture_output,
                text=True,
                timeout=600  # 10分タイムアウト
            )
            return result
            
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Python execution timed out: {e}")
        except FileNotFoundError as e:
            raise RuntimeError(f"Failed to execute Python: {e}")
    
    def execute_module(self, module_name: str, args: Optional[List[str]] = None,
                      cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None,
                      capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Pythonモジュールを統一環境で実行（python -m module_name）
        
        Args:
            module_name: 実行するモジュール名
            args: モジュールに渡す引数
            cwd: 実行ディレクトリ
            env: 環境変数
            capture_output: 出力をキャプチャするか
            
        Returns:
            subprocess.CompletedProcess: 実行結果
        """
        python_cmd = self.get_python_command()
        cmd = python_cmd + ['-m', module_name]
        
        if args:
            cmd.extend(args)
            
        # 環境変数の設定
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)
        exec_env['KOUBOU_HOME'] = str(Path(self.koubou_home).resolve())
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or str(self.project_root),
                env=exec_env,
                capture_output=capture_output,
                text=True,
                timeout=600
            )
            return result
            
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Python module execution timed out: {e}")
        except FileNotFoundError as e:
            raise RuntimeError(f"Failed to execute Python module: {e}")
    
    def install_package(self, package_name: str) -> bool:
        """
        パッケージを統一環境でインストール
        
        Args:
            package_name: インストールするパッケージ名
            
        Returns:
            bool: インストール成功
        """
        try:
            if self._is_uv_available():
                cmd = ['uv', 'pip', 'install', package_name]
            elif self._is_command_available('pip3'):
                cmd = ['pip3', 'install', package_name]
            elif self._is_command_available('pip'):
                cmd = ['pip', 'install', package_name]
            else:
                return False
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _is_uv_available(self) -> bool:
        """uvが利用可能かチェック"""
        return self._is_command_available('uv')
    
    def _is_command_available(self, command: str) -> bool:
        """指定コマンドが利用可能かチェック"""
        try:
            subprocess.run(
                [command, '--version'], 
                capture_output=True, 
                check=True, 
                timeout=5
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def get_environment_info(self) -> Dict[str, Any]:
        """現在のPython実行環境情報を取得"""
        info = {
            'python_command': None,
            'uv_available': self._is_uv_available(),
            'venv_active': 'VIRTUAL_ENV' in os.environ,
            'koubou_home': self.koubou_home,
            'project_root': str(self.project_root)
        }
        
        try:
            info['python_command'] = self.get_python_command()
        except RuntimeError as e:
            info['error'] = str(e)
            
        return info


# グローバルエグゼキューター（シングルトン）
_executor = None

def get_executor() -> PythonExecutor:
    """グローバルPythonエグゼキューターを取得"""
    global _executor
    if _executor is None:
        _executor = PythonExecutor()
    return _executor

def execute_python_script(script_path: str, args: Optional[List[str]] = None,
                         **kwargs) -> subprocess.CompletedProcess:
    """便利関数: Pythonスクリプトを実行"""
    return get_executor().execute(script_path, args, **kwargs)

def execute_python_module(module_name: str, args: Optional[List[str]] = None,
                         **kwargs) -> subprocess.CompletedProcess:
    """便利関数: Pythonモジュールを実行"""
    return get_executor().execute_module(module_name, args, **kwargs)


if __name__ == '__main__':
    # テスト実行
    executor = PythonExecutor()
    env_info = executor.get_environment_info()
    
    print("🐍 Python実行環境情報:")
    for key, value in env_info.items():
        print(f"  {key}: {value}")
        
    # 簡単なテスト
    try:
        result = executor.execute_module('sys', ['-c', 'import sys; print(f"Python: {sys.version}")'])
        print(f"\n✅ テスト実行成功:")
        print(f"  stdout: {result.stdout.strip()}")
    except Exception as e:
        print(f"\n❌ テスト実行失敗: {e}")