#!/usr/bin/env python3
"""
タスク結果管理システム - 本番環境用

親方が職人の作業成果を効率的に確認・評価するためのシステム
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class TaskResultManager:
    """職人の作業成果を管理・フォーマットするクラス"""
    
    def __init__(self, output_base_dir: Optional[str] = None):
        """
        初期化
        
        Args:
            output_base_dir: 成果物保存先ディレクトリ（デフォルト: .koubou/outputs）
        """
        koubou_home = os.environ.get('KOUBOU_HOME', '.koubou')
        self.output_base_dir = Path(output_base_dir or f"{koubou_home}/outputs")
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # 親方確認用ディレクトリを作成
        self.review_dir = self.output_base_dir / "for_review"
        self.archive_dir = self.output_base_dir / "archived" 
        self.review_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        
    def save_task_deliverable(self, task_result: Any, task_id: str, task_type: str, 
                             task_content: str = "", priority: int = 5) -> Dict[str, Path]:
        """
        職人の作業成果を親方確認用に保存
        
        Args:
            task_result: タスク実行結果
            task_id: タスクID
            task_type: タスクタイプ（general, code_generation等）
            task_content: タスク内容（要約用）
            priority: タスク優先度
            
        Returns:
            保存されたファイルのパス辞書
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 結果テキストを抽出
        if isinstance(task_result, dict):
            result_text = task_result.get("output", str(task_result))
            success = task_result.get("success", True)
            error = task_result.get("error", None)
        else:
            result_text = str(task_result)
            success = True
            error = None
            
        # タスクタイプを推定（内容から）
        inferred_type = self._infer_task_type(task_content, result_text)
        
        # 親方確認用ディレクトリを準備
        date_dir = self.review_dir / timestamp[:8]  # YYYYMMDD
        task_dir = date_dir / f"{task_id}_{inferred_type}"
        task_dir.mkdir(parents=True, exist_ok=True)
        
        files = {}
        
        # 1. メイン成果物ファイル
        main_file = self._save_formatted_result(
            result_text, task_id, inferred_type, task_dir, timestamp, success
        )
        files['main'] = main_file
        
        # 2. 親方確認用サマリー
        summary_file = task_dir / f"{task_id}_summary.md"
        summary_content = self._create_review_summary(
            task_id, task_content, result_text, success, error, priority, timestamp, inferred_type
        )
        summary_file.write_text(summary_content, encoding='utf-8')
        files['summary'] = summary_file
        
        # 3. 詳細メタデータ（JSON）
        metadata_file = task_dir / f"{task_id}_metadata.json"
        metadata = {
            "task_id": task_id,
            "timestamp": timestamp,
            "task_type": inferred_type,
            "priority": priority,
            "success": success,
            "error": error,
            "content_summary": task_content[:200] + "..." if len(task_content) > 200 else task_content,
            "result_length": len(result_text),
            "files_generated": [str(f.name) for f in files.values() if f.exists()],
            "review_status": "pending",  # pending, approved, revision_needed
            "created_at": datetime.now().isoformat()
        }
        metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
        files['metadata'] = metadata_file
        
        # 4. 親方への通知ファイル
        notification_file = self.review_dir / f"new_deliverable_{timestamp}.txt"
        notification_content = f"""🎯 新しい職人の成果物

タスクID: {task_id}
タイプ: {inferred_type}
優先度: {priority}
状態: {'✅ 成功' if success else '❌ 失敗'}
保存先: {task_dir}

確認方法:
  cat {summary_file}
  # または
  .koubou/scripts/tools/review_deliverable.sh {task_id}

"""
        notification_file.write_text(notification_content, encoding='utf-8')
        files['notification'] = notification_file
        
        return files
    
    def _infer_task_type(self, task_content: str, result_text: str) -> str:
        """タスク内容と結果からタスクタイプを推定"""
        content_lower = task_content.lower()
        result_lower = result_text.lower()
        
        # コード生成の判定
        if any(keyword in content_lower for keyword in ['コード生成', 'code', 'function', 'class', 'プログラム']):
            return "code_generation"
        if any(keyword in result_lower for keyword in ['def ', 'class ', 'import ', 'function', '```']):
            return "code_generation"
            
        # データ分析の判定
        if any(keyword in content_lower for keyword in ['分析', 'analysis', 'データ', 'レポート', '統計']):
            return "data_analysis" 
        if any(keyword in result_lower for keyword in ['##', '###', '分析', 'グラフ', '結果']):
            return "data_analysis"
            
        # 翻訳の判定  
        if any(keyword in content_lower for keyword in ['翻訳', 'translation', '英訳', '和訳']):
            return "translation"
        if '翻訳:' in result_lower or 'translation:' in result_lower:
            return "translation"
            
        # エラーハンドリングの判定
        if any(keyword in content_lower for keyword in ['エラー', 'error', '例外', 'exception']):
            return "error_handling"
        if any(keyword in result_lower for keyword in ['error', 'exception', 'エラー', 'failed']):
            return "error_handling"
            
        return "text_generation"  # デフォルト
    
    def _save_formatted_result(self, result_text: str, task_id: str, task_type: str, 
                              output_dir: Path, timestamp: str, success: bool) -> Path:
        """結果をタスクタイプに応じた形式で保存"""
        import re
        
        if task_type == "code_generation":
            # Web開発ファイル（HTML/CSS/JS）の検出と個別保存
            files_created = []
            
            # パターン1: --- filename --- 形式
            file_pattern = r'---\s*([^\s-]+\.\w+)\s*---'
            sections = re.split(file_pattern, result_text)
            
            if len(sections) > 1:
                # ファイルごとに分割して保存
                for i in range(1, len(sections), 2):
                    if i+1 < len(sections):
                        filename = sections[i].strip()
                        content = sections[i+1].strip()
                        
                        # コードブロックマーカーを削除
                        content = re.sub(r'^```\w*\n?', '', content)
                        content = re.sub(r'\n?```$', '', content)
                        
                        # ファイルを保存
                        file_path = output_dir / filename
                        file_path.write_text(content, encoding='utf-8')
                        files_created.append(filename)
            
            # パターン2: // ===== filename ===== 形式
            if not files_created:
                section_pattern = r'//\s*=+\s*([^\s=]+\.\w+)\s*=+'
                sections = re.split(section_pattern, result_text)
                
                if len(sections) > 1:
                    for i in range(1, len(sections), 2):
                        if i+1 < len(sections):
                            filename = sections[i].strip()
                            content = sections[i+1].strip()
                            
                            # コードブロックマーカーを削除
                            content = re.sub(r'^```\w*\n?', '', content)
                            content = re.sub(r'\n?```$', '', content)
                            
                            file_path = output_dir / filename
                            file_path.write_text(content, encoding='utf-8')
                            files_created.append(filename)
            
            # パターン3: /* === filename === */ 形式
            if not files_created:
                section_pattern = r'/\*\s*=+\s*([^\s=]+\.\w+)\s*=+\s*\*/'
                sections = re.split(section_pattern, result_text)
                
                if len(sections) > 1:
                    for i in range(1, len(sections), 2):
                        if i+1 < len(sections):
                            filename = sections[i].strip()
                            content = sections[i+1].strip()
                            
                            # コードブロックマーカーを削除
                            content = re.sub(r'^```\w*\n?', '', content)
                            content = re.sub(r'\n?```$', '', content)
                            
                            file_path = output_dir / filename
                            file_path.write_text(content, encoding='utf-8')
                            files_created.append(filename)
            
            # 個別ファイルが作成された場合
            if files_created:
                # index.htmlまたは最初のHTMLファイルをメインファイルとする
                main_file = None
                for fname in files_created:
                    if fname.endswith('.html'):
                        main_file = output_dir / fname
                        break
                if not main_file and files_created:
                    main_file = output_dir / files_created[0]
                    
                # README.mdを作成
                readme_content = f"""# 🔨 職人作業成果 - Web開発
Task ID: {task_id}
Generated: {timestamp}
Status: {'✅ Success' if success else '❌ Failed'}

## 生成されたファイル
{chr(10).join(f'- {f}' for f in files_created)}

## 使用方法
1. すべてのファイルを同じディレクトリに配置
2. {'index.html' if 'index.html' in files_created else files_created[0] if files_created else 'HTMLファイル'}をブラウザで開く

## 親方確認事項
- [ ] コードの動作確認
- [ ] セキュリティチェック
- [ ] ブラウザ互換性確認
- [ ] レスポンシブデザイン確認
"""
                readme_file = output_dir / "README.md"
                readme_file.write_text(readme_content, encoding='utf-8')
                
                return main_file if main_file else readme_file
            
            # 個別ファイルが検出されなかった場合は従来通り.pyファイルとして保存
            output_file = output_dir / f"{task_id}_result.py"
            header = f"""# 🔨 職人作業成果 - コード生成
# Task ID: {task_id}
# Generated: {timestamp}
# Status: {'✅ Success' if success else '❌ Failed'}
# 
# 親方確認要：このコードをプロジェクトに統合する前に
# 動作確認、コードレビューを実施してください

"""
            content = header + result_text
            output_file.write_text(content, encoding='utf-8')
            return output_file
            
        elif task_type == "data_analysis":
            # Markdown レポートとして保存
            output_file = output_dir / f"{task_id}_analysis.md"
            header = f"""# 📊 データ分析レポート

**タスクID:** {task_id}  
**作成日時:** {timestamp}  
**ステータス:** {'✅ 成功' if success else '❌ 失敗'}  
**担当職人:** システム職人

> 🚨 **親方確認要**: この分析結果を意思決定に使用する前に、データの正確性とロジックを確認してください

---

"""
            content = header + result_text
            
        elif task_type == "translation":
            # 対訳形式で保存
            output_file = output_dir / f"{task_id}_translation.txt"
            header = f"""📝 翻訳作業成果
================
Task ID: {task_id}
作成日時: {timestamp}
ステータス: {'成功' if success else '失敗'}

🔍 親方確認ポイント:
- 専門用語の統一性
- 文脈の適切性  
- 顧客要件との整合性

---

"""
            content = header + result_text
            
        elif task_type == "error_handling":
            # ログ形式で保存
            output_file = output_dir / f"{task_id}_error_log.txt"
            header = f"""🚨 エラーハンドリング実行ログ
====================================
[{timestamp}] TASK EXECUTION REPORT
Task ID: {task_id}
Status: {'SUCCESS' if success else 'FAILED'}

親方チェック項目:
- システム安定性への影響
- 根本原因の対策必要性
- 再発防止策の検討

詳細ログ:
---
"""
            content = header + result_text
            
        else:
            # 一般的なテキストファイル
            output_file = output_dir / f"{task_id}_deliverable.txt"
            header = f"""📄 職人作業成果
================
Task ID: {task_id}
タイプ: {task_type}
作成日時: {timestamp}
ステータス: {'成功' if success else '失敗'}

📋 親方確認事項:
- 要求仕様との適合性
- 品質基準の充足
- 顧客提出前の最終チェック

---
成果物内容:

"""
            content = header + result_text
            
        output_file.write_text(content, encoding='utf-8')
        return output_file
    
    def _create_review_summary(self, task_id: str, task_content: str, result_text: str,
                              success: bool, error: Optional[str], priority: int, 
                              timestamp: str, task_type: str) -> str:
        """親方確認用サマリーを作成"""
        
        # 品質評価を自動実行
        quality_score = self._assess_quality(result_text, task_type)
        
        summary = f"""# 🎯 職人作業成果確認書

## 基本情報
- **タスクID**: `{task_id}`
- **作業タイプ**: {task_type}
- **優先度**: {priority}/10
- **完了時刻**: {timestamp}
- **実行結果**: {'✅ 成功' if success else '❌ 失敗'}

## 作業内容
```
{task_content[:300]}{'...' if len(task_content) > 300 else ''}
```

## 成果物概要
- **文字数**: {len(result_text):,}文字
- **品質スコア**: {quality_score}/100
- **推定作業時間**: 約{self._estimate_work_time(result_text)}分

## 品質チェック項目

### ✅ 自動チェック結果
{self._generate_quality_checklist(result_text, task_type)}

### 🔍 親方確認必須項目
- [ ] 要求仕様との適合性確認
- [ ] 品質基準の充足確認  
- [ ] 顧客提出可能レベルの達成確認
- [ ] セキュリティ・安全性の確認

## 推奨アクション

{self._generate_recommendations(quality_score, success, task_type)}

## エラー詳細
{error if error else "なし"}

---
**確認者**: _________________ **日時**: _________________

**総合評価**: ⭐⭐⭐⭐⭐ (5段階)

**承認**: □ 承認 □ 修正要 □ 差し戻し
"""
        return summary
    
    def _assess_quality(self, result_text: str, task_type: str) -> int:
        """成果物の品質を自動評価（100点満点）"""
        score = 70  # ベーススコア
        
        # 基本的な品質チェック
        if len(result_text) > 50:
            score += 10  # 十分な分量
        if len(result_text) > 200:
            score += 5   # 詳細な内容
            
        # タスクタイプ別評価
        if task_type == "code_generation":
            if "def " in result_text or "class " in result_text:
                score += 10
            if '"""' in result_text or "'''" in result_text:
                score += 5  # ドキュメント文字列
                
        elif task_type == "data_analysis":
            if "##" in result_text:
                score += 10  # 構造化
            if any(word in result_text for word in ["結論", "推奨", "分析"]):
                score += 5
                
        # 上限調整
        return min(score, 100)
    
    def _estimate_work_time(self, result_text: str) -> int:
        """作業時間を推定（分）"""
        # 文字数ベースの簡易推定
        char_count = len(result_text)
        if char_count < 100:
            return 5
        elif char_count < 500:
            return 15
        elif char_count < 1000:
            return 30
        else:
            return 45
    
    def _generate_quality_checklist(self, result_text: str, task_type: str) -> str:
        """品質チェックリストを生成"""
        checks = []
        
        # 基本チェック
        if len(result_text) > 50:
            checks.append("- ✅ 十分な分量")
        else:
            checks.append("- ⚠️ 分量不足の可能性")
            
        # タスク固有チェック
        if task_type == "code_generation":
            if "def " in result_text:
                checks.append("- ✅ 関数定義あり")
            if '"""' in result_text:
                checks.append("- ✅ ドキュメント文字列あり")
                
        elif task_type == "data_analysis":
            if "##" in result_text:
                checks.append("- ✅ 構造化された分析")
            if "結論" in result_text:
                checks.append("- ✅ 結論記載")
                
        return "\n".join(checks)
    
    def _generate_recommendations(self, quality_score: int, success: bool, task_type: str) -> str:
        """推奨アクションを生成"""
        if not success:
            return "🚨 **緊急**: タスクが失敗しています。エラー内容を確認し、再実行を検討してください。"
            
        if quality_score >= 90:
            return "🎉 **優秀**: 高品質な成果物です。最終確認後、承認可能です。"
        elif quality_score >= 80:
            return "👍 **良好**: 良質な成果物です。細部確認後、承認を検討してください。"
        elif quality_score >= 70:
            return "📝 **要確認**: 基準を満たしていますが、品質向上の余地があります。"
        else:
            return "⚠️ **要改善**: 品質基準を下回っています。修正または再作業を推奨します。"


# コマンドライン使用時のヘルパー関数
def save_production_result(task_id: str, result: Any, task_content: str = "", priority: int = 5) -> Dict[str, Path]:
    """本番環境でタスク結果を保存するヘルパー関数"""
    manager = TaskResultManager()
    return manager.save_task_deliverable(result, task_id, "general", task_content, priority)


if __name__ == "__main__":
    # テスト用のサンプル実行
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # テスト実行
        test_result = {
            "success": True,
            "output": "春の公園での風景描写が完成しました。桜の花びらが舞い散る美しい情景を、季節感豊かな表現で描写いたしました。",
            "error": None
        }
        
        manager = TaskResultManager()
        files = manager.save_task_deliverable(
            test_result, 
            "task_test_001", 
            "general",
            "春の公園の風景を200文字程度で描写してください", 
            8
        )
        
        print("✅ テスト成果物を保存しました:")
        for file_type, file_path in files.items():
            print(f"  {file_type}: {file_path}")