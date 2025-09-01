#!/usr/bin/env python3
"""
Ollamaモデル切り替えユーティリティ
設定ファイルを使用してモデルを簡単に切り替える
"""

import os
import sys
import argparse
import yaml
from pathlib import Path

# KOUBOUのパスを追加
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
sys.path.insert(0, os.path.join(KOUBOU_HOME, 'scripts'))

from common.ollama_config import get_ollama_config

def list_models():
    """利用可能なモデルを一覧表示"""
    config = get_ollama_config()
    models = config.list_available_models()
    default_model = config.config.get('default_model')
    
    print("\n📋 利用可能なOllamaモデル:")
    print("=" * 60)
    
    for model_key in models:
        model_config = config.get_model_config(model_key)
        is_default = " ⭐ (デフォルト)" if model_key == default_model else ""
        
        print(f"\n🔸 {model_key}{is_default}")
        print(f"   名前: {model_config.get('name')}")
        print(f"   説明: {model_config.get('description', 'N/A')}")
        
        use_cases = model_config.get('use_cases', [])
        if use_cases:
            print(f"   用途: {', '.join(use_cases[:3])}")
        
        options = model_config.get('options', {})
        if options:
            print(f"   設定: temp={options.get('temperature', 'N/A')}, ctx={options.get('num_ctx', 'N/A')}")
    
    print("\n" + "=" * 60)

def show_model_details(model_key):
    """特定モデルの詳細を表示"""
    config = get_ollama_config()
    
    if model_key not in config.list_available_models():
        print(f"❌ モデル '{model_key}' が見つかりません")
        print("利用可能なモデルを確認するには --list を使用してください")
        return
    
    model_config = config.get_model_config(model_key)
    
    print(f"\n🔍 モデル詳細: {model_key}")
    print("=" * 60)
    print(f"名前: {model_config.get('name')}")
    print(f"説明: {model_config.get('description', 'N/A')}")
    
    use_cases = model_config.get('use_cases', [])
    if use_cases:
        print("\n用途:")
        for use_case in use_cases:
            print(f"  • {use_case}")
    
    options = model_config.get('options', {})
    if options:
        print("\nオプション設定:")
        for key, value in options.items():
            print(f"  • {key}: {value}")
    
    print("\n" + "=" * 60)

def set_default_model(model_key):
    """デフォルトモデルを変更"""
    config_path = os.path.join(KOUBOU_HOME, 'config', 'ollama_models.yaml')
    
    # 設定ファイルを読み込み
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    if model_key not in config_data.get('models', {}):
        print(f"❌ モデル '{model_key}' が設定ファイルに存在しません")
        return
    
    # デフォルトモデルを更新
    old_default = config_data.get('default_model')
    config_data['default_model'] = model_key
    
    # 設定ファイルに書き込み
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"✅ デフォルトモデルを変更しました:")
    print(f"   {old_default} → {model_key}")
    
    # モデルの詳細を表示
    config = get_ollama_config()
    config.reload_config()
    model_config = config.get_model_config(model_key)
    print(f"   名前: {model_config.get('name')}")
    print(f"   説明: {model_config.get('description', 'N/A')}")

def test_model(model_key=None):
    """モデルをテスト実行"""
    config = get_ollama_config()
    
    if model_key and model_key not in config.list_available_models():
        print(f"❌ モデル '{model_key}' が見つかりません")
        return
    
    model_name = config.get_model_name(model_key)
    model_options = config.get_model_options(model_key)
    server_host = config.get_server_host()
    
    print(f"\n🧪 モデルテスト: {model_key or 'default'}")
    print(f"   使用モデル: {model_name}")
    print(f"   サーバー: {server_host}")
    
    # Ollamaが起動しているか確認
    import subprocess
    try:
        result = subprocess.run(
            ['curl', '-s', f'{server_host}/api/tags'],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            print("⚠️  Ollamaサーバーが起動していません")
            print("   起動コマンド: ollama serve")
            return
    except Exception as e:
        print(f"⚠️  Ollamaサーバーへの接続に失敗: {e}")
        return
    
    # モデルが存在するか確認
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if model_name.split(':')[0] not in result.stdout:
            print(f"⚠️  モデル {model_name} がローカルに存在しません")
            print(f"   ダウンロードコマンド: ollama pull {model_name}")
            return
    except Exception as e:
        print(f"⚠️  モデル確認に失敗: {e}")
        return
    
    print("✅ モデルは利用可能です")
    
    # 簡単なテストプロンプトを実行
    print("\n📝 テストプロンプト実行中...")
    try:
        # gemini-repo-cliのパスを追加
        gemini_repo_cli_path = os.path.join(KOUBOU_HOME, "..", "gemini-repo-cli", "src")
        if gemini_repo_cli_path not in sys.path:
            sys.path.insert(0, gemini_repo_cli_path)
        
        from gemini_repo.ollama_api import OllamaRepoAPI
        
        api = OllamaRepoAPI(model_name=model_name, host=server_host)
        if model_options:
            api.options.update(model_options)
        
        # シンプルなテスト
        test_prompt = "Write a simple Python function that returns 'Hello, World!'"
        response = api.client.generate(
            model=model_name,
            prompt=test_prompt,
            stream=False,
            options=api.options
        )
        
        print("✅ テスト成功！")
        print("\n--- 生成結果（最初の200文字）---")
        print(response.get('response', '')[:200])
        print("...")
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='Ollamaモデル管理ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 利用可能なモデル一覧
  %(prog)s --list
  
  # モデルの詳細表示
  %(prog)s --show gpt-oss-20b
  
  # デフォルトモデルを変更
  %(prog)s --set-default qwen-coder-7b
  
  # モデルをテスト
  %(prog)s --test
  %(prog)s --test qwen-coder-1.5b
        """
    )
    
    parser.add_argument('--list', '-l', action='store_true',
                       help='利用可能なモデル一覧を表示')
    parser.add_argument('--show', '-s', metavar='MODEL_KEY',
                       help='特定モデルの詳細を表示')
    parser.add_argument('--set-default', '-d', metavar='MODEL_KEY',
                       help='デフォルトモデルを変更')
    parser.add_argument('--test', '-t', nargs='?', const='_default_', metavar='MODEL_KEY',
                       help='モデルをテスト実行（MODEL_KEY省略時はデフォルト）')
    
    args = parser.parse_args()
    
    # 引数がない場合は一覧表示
    if not any([args.list, args.show, args.set_default, args.test]):
        list_models()
        print("\n💡 ヘルプを表示: python3 ollama_model_switch.py -h")
        return
    
    if args.list:
        list_models()
    
    if args.show:
        show_model_details(args.show)
    
    if args.set_default:
        set_default_model(args.set_default)
    
    if args.test is not None:
        model_key = None if args.test == '_default_' else args.test
        test_model(model_key)

if __name__ == "__main__":
    main()