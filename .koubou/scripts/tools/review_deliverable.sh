#!/bin/bash
# 職人成果物確認スクリプト - 親方用

set -e

KOUBOU_HOME=${KOUBOU_HOME:-".koubou"}
OUTPUTS_DIR="${KOUBOU_HOME}/outputs"

show_help() {
    cat << EOF
🎯 職人成果物確認ツール - 親方専用

使用方法:
  $0 <task_id>                    # 特定タスクの詳細確認
  $0 --list                       # 新しい成果物一覧
  $0 --summary                    # 今日の成果物サマリー
  $0 --pending                    # 確認待ち成果物一覧
  $0 --approve <task_id>          # 成果物承認
  $0 --reject <task_id> <reason>  # 成果物差戻し

例:
  $0 task_20250831_180243_145684  # タスク詳細確認
  $0 --list                       # 新着成果物確認
  $0 --approve task_123           # 承認処理
EOF
}

list_new_deliverables() {
    echo "🆕 新しい成果物一覧:"
    echo "=================="
    
    if [ -d "${OUTPUTS_DIR}/for_review" ]; then
        find "${OUTPUTS_DIR}/for_review" -name "new_deliverable_*.txt" -newer "${OUTPUTS_DIR}/.last_check" 2>/dev/null || find "${OUTPUTS_DIR}/for_review" -name "new_deliverable_*.txt" -mtime -1 2>/dev/null | sort -r | head -10 | while read notification; do
            if [ -f "$notification" ]; then
                echo ""
                cat "$notification"
                echo "----------------------------------------"
            fi
        done
        
        # 最後のチェック時刻を更新
        touch "${OUTPUTS_DIR}/.last_check"
    else
        echo "成果物ディレクトリが見つかりません: ${OUTPUTS_DIR}/for_review"
    fi
}

show_task_detail() {
    local task_id=$1
    
    echo "🔍 タスク詳細: $task_id"
    echo "==================="
    
    # タスクディレクトリを検索
    task_dirs=$(find "${OUTPUTS_DIR}/for_review" -name "*${task_id}*" -type d 2>/dev/null)
    
    if [ -z "$task_dirs" ]; then
        echo "❌ タスク $task_id が見つかりません"
        return 1
    fi
    
    for task_dir in $task_dirs; do
        echo "📁 ディレクトリ: $task_dir"
        echo ""
        
        # サマリーファイル表示
        summary_file=$(find "$task_dir" -name "*summary.md" | head -1)
        if [ -f "$summary_file" ]; then
            echo "📋 確認書:"
            cat "$summary_file"
            echo ""
        fi
        
        # ファイル一覧表示
        echo "📄 成果物ファイル:"
        ls -la "$task_dir/" | grep -v "^d" | awk '{print "  " $9 " (" $5 " bytes)"}'
        echo ""
        
        # メイン成果物の先頭表示
        main_file=$(find "$task_dir" -name "*result.*" -o -name "*deliverable.*" -o -name "*analysis.*" | head -1)
        if [ -f "$main_file" ]; then
            echo "🎯 成果物プレビュー (先頭20行):"
            head -20 "$main_file"
            echo ""
            echo "完全な内容: cat $main_file"
        fi
    done
}

show_summary() {
    echo "📊 今日の成果物サマリー"
    echo "====================="
    
    today=$(date +%Y%m%d)
    today_dir="${OUTPUTS_DIR}/for_review/$today"
    
    if [ -d "$today_dir" ]; then
        task_count=$(find "$today_dir" -maxdepth 1 -type d | wc -l)
        task_count=$((task_count - 1))  # ディレクトリ自体を除外
        
        echo "📈 今日の成果物: ${task_count}件"
        echo ""
        
        if [ $task_count -gt 0 ]; then
            echo "📝 内訳:"
            find "$today_dir" -name "*_metadata.json" | while read metadata; do
                task_type=$(jq -r '.task_type' "$metadata" 2>/dev/null || echo "unknown")
                task_id=$(jq -r '.task_id' "$metadata" 2>/dev/null || echo "unknown")
                success=$(jq -r '.success' "$metadata" 2>/dev/null || echo "unknown")
                status_icon=$([ "$success" = "true" ] && echo "✅" || echo "❌")
                echo "  $status_icon $task_id ($task_type)"
            done
        fi
    else
        echo "今日の成果物はまだありません"
    fi
}

show_pending() {
    echo "⏳ 確認待ち成果物一覧"
    echo "=================="
    
    find "${OUTPUTS_DIR}/for_review" -name "*_metadata.json" | while read metadata; do
        review_status=$(jq -r '.review_status' "$metadata" 2>/dev/null || echo "unknown")
        if [ "$review_status" = "pending" ]; then
            task_id=$(jq -r '.task_id' "$metadata" 2>/dev/null || echo "unknown")
            task_type=$(jq -r '.task_type' "$metadata" 2>/dev/null || echo "unknown")
            priority=$(jq -r '.priority' "$metadata" 2>/dev/null || echo "5")
            echo "  🔔 $task_id ($task_type) - 優先度: $priority"
        fi
    done
}

approve_task() {
    local task_id=$1
    
    metadata_files=$(find "${OUTPUTS_DIR}/for_review" -name "*${task_id}*_metadata.json")
    
    for metadata in $metadata_files; do
        # メタデータを更新
        jq '.review_status = "approved" | .approved_at = now | .approved_by = "master"' "$metadata" > "${metadata}.tmp" && mv "${metadata}.tmp" "$metadata"
        
        task_dir=$(dirname "$metadata")
        archive_dir="${OUTPUTS_DIR}/archived/$(date +%Y%m%d)"
        mkdir -p "$archive_dir"
        
        echo "✅ タスク $task_id を承認しました"
        echo "📦 アーカイブ先: $archive_dir/$(basename $task_dir)"
        
        # アーカイブに移動
        mv "$task_dir" "$archive_dir/"
    done
}

reject_task() {
    local task_id=$1
    local reason=$2
    
    metadata_files=$(find "${OUTPUTS_DIR}/for_review" -name "*${task_id}*_metadata.json")
    
    for metadata in $metadata_files; do
        # メタデータを更新
        jq --arg reason "$reason" '.review_status = "revision_needed" | .rejected_at = now | .rejected_by = "master" | .rejection_reason = $reason' "$metadata" > "${metadata}.tmp" && mv "${metadata}.tmp" "$metadata"
        
        echo "❌ タスク $task_id を差戻ししました"
        echo "理由: $reason"
    done
}

# メイン処理
case "${1:-}" in
    --help|-h)
        show_help
        ;;
    --list)
        list_new_deliverables
        ;;
    --summary)
        show_summary
        ;;
    --pending)
        show_pending
        ;;
    --approve)
        if [ -z "$2" ]; then
            echo "❌ タスクIDが必要です: $0 --approve <task_id>"
            exit 1
        fi
        approve_task "$2"
        ;;
    --reject)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "❌ タスクIDと理由が必要です: $0 --reject <task_id> <reason>"
            exit 1
        fi
        reject_task "$2" "$3"
        ;;
    "")
        show_help
        ;;
    *)
        show_task_detail "$1"
        ;;
esac