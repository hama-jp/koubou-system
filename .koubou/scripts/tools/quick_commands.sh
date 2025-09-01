#!/bin/bash
# 親方向けクイックコマンド集 - よく使うコマンドをエラーなしで実行

set -e

KOUBOU_HOME=${KOUBOU_HOME:-".koubou"}
DB_PATH="${KOUBOU_HOME}/db/koubou.db"

show_help() {
    cat << EOF
🏭 親方向けクイックコマンド集

基本コマンド:
  $0 workers          # 職人の状況確認
  $0 tasks            # ペンディングタスク確認
  $0 stats            # システム統計情報
  $0 health           # システム健全性チェック
  $0 deliverables     # 新しい成果物確認
  $0 logs [worker_id] # ワーカーログ確認

システム管理:
  $0 start            # 工房システム起動
  $0 stop             # 工房システム停止
  $0 restart          # 工房システム再起動
  $0 clean            # ログ・一時ファイル清掃

SQL実行（エスケープエラー回避）:
  $0 sql "SELECT * FROM workers"
  $0 sql "SELECT COUNT(*) FROM task_master WHERE status='pending'"
EOF
}

check_workers() {
    echo "👷 職人の状況確認"
    echo "=================="
    sqlite3 "$DB_PATH" "SELECT worker_id, status, current_task, tasks_completed, tasks_failed, 
                              datetime(last_heartbeat) as last_seen 
                       FROM workers 
                       WHERE status <> 'offline' 
                       ORDER BY last_heartbeat DESC;"
    
    echo ""
    echo "📊 サマリー:"
    local idle_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM workers WHERE status = 'idle';")
    local working_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM workers WHERE status = 'working';")
    local processing_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM workers WHERE status = 'processing';")
    
    echo "  🟢 待機中: ${idle_count}名"
    echo "  🟡 作業中: ${working_count}名" 
    echo "  🔵 処理中: ${processing_count}名"
}

check_tasks() {
    echo "📋 ペンディングタスク確認"
    echo "======================"
    sqlite3 "$DB_PATH" "SELECT task_id, 
                              SUBSTR(content, 1, 50) || '...' as content_preview,
                              priority,
                              datetime(created_at) as created
                       FROM task_master 
                       WHERE status = 'pending' 
                       ORDER BY priority DESC, created_at ASC
                       LIMIT 10;"
    
    echo ""
    local pending_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM task_master WHERE status = 'pending';")
    echo "📊 待機中タスク: ${pending_count}件"
}

show_stats() {
    echo "📈 システム統計情報"
    echo "=================="
    echo "🏭 タスク処理状況:"
    sqlite3 "$DB_PATH" "SELECT 
                          status,
                          COUNT(*) as count,
                          ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM task_master), 1) as percentage
                        FROM task_master 
                        GROUP BY status 
                        ORDER BY count DESC;"
    
    echo ""
    echo "👷 職人パフォーマンス:"
    sqlite3 "$DB_PATH" "SELECT 
                          worker_id,
                          tasks_completed,
                          tasks_failed,
                          ROUND(tasks_completed * 100.0 / NULLIF(tasks_completed + tasks_failed, 0), 1) as success_rate
                        FROM workers 
                        WHERE tasks_completed > 0 OR tasks_failed > 0
                        ORDER BY tasks_completed DESC;"
}

check_health() {
    echo "🔍 システム健全性チェック"
    echo "======================"
    
    # API健全性
    if curl -s http://localhost:8765/health > /dev/null 2>&1; then
        echo "✅ MCP Server (8765): 正常"
    else
        echo "❌ MCP Server (8765): 停止中"
    fi
    
    # ダッシュボード
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo "✅ Dashboard (8080): 正常"
    else
        echo "❌ Dashboard (8080): 停止中"
    fi
    
    # データベース
    if sqlite3 "$DB_PATH" "SELECT 1;" > /dev/null 2>&1; then
        echo "✅ Database: 正常"
    else
        echo "❌ Database: 接続エラー"
    fi
    
    # ディスク容量
    local disk_usage=$(df . | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -lt 90 ]; then
        echo "✅ Disk Usage: ${disk_usage}% (正常)"
    else
        echo "⚠️ Disk Usage: ${disk_usage}% (注意)"
    fi
}

check_deliverables() {
    echo "📦 新しい成果物確認"
    echo "=================="
    ${KOUBOU_HOME}/scripts/tools/review_deliverable.sh --summary
}

show_logs() {
    local worker_id=$1
    
    if [ -z "$worker_id" ]; then
        echo "📄 利用可能なワーカーログ:"
        ls -la "${KOUBOU_HOME}/logs/workers/" | grep "\.log$" | awk '{print "  " $9}'
        echo ""
        echo "使用方法: $0 logs <worker_id>"
        return
    fi
    
    local log_file="${KOUBOU_HOME}/logs/workers/${worker_id}.log"
    if [ -f "$log_file" ]; then
        echo "📄 ワーカーログ: $worker_id"
        echo "==================="
        tail -20 "$log_file"
    else
        echo "❌ ログファイルが見つかりません: $log_file"
    fi
}

start_system() {
    echo "🚀 工房システム起動中..."
    ${KOUBOU_HOME}/start_system.sh
}

stop_system() {
    echo "🛑 工房システム停止中..."
    pkill -f "worker_pool_manager.py" || true
    pkill -f "mcp_server.py" || true
    pkill -f "websocket_server.py" || true
    echo "✅ システム停止完了"
}

restart_system() {
    echo "🔄 工房システム再起動中..."
    stop_system
    sleep 2
    start_system
}

clean_system() {
    echo "🧹 システムクリーンアップ中..."
    
    # 古いログファイル削除（7日以上前）
    find "${KOUBOU_HOME}/logs" -name "*.log" -mtime +7 -delete 2>/dev/null || true
    
    # 一時ファイル削除
    rm -f "${KOUBOU_HOME}/tmp/"*.tmp 2>/dev/null || true
    
    # 完了済みタスクのアーカイブ（30日以上前）
    sqlite3 "$DB_PATH" "DELETE FROM task_master WHERE status = 'completed' AND created_at < datetime('now', '-30 days');" 2>/dev/null || true
    
    echo "✅ クリーンアップ完了"
}

execute_sql() {
    local sql_query="$1"
    
    if [ -z "$sql_query" ]; then
        echo "❌ SQLクエリが指定されていません"
        echo "使用方法: $0 sql \"SELECT * FROM workers\""
        return 1
    fi
    
    echo "🗃️ SQL実行結果:"
    echo "================"
    
    # エスケープエラーを回避してSQL実行
    echo "$sql_query" | sqlite3 "$DB_PATH" || {
        echo "❌ SQL実行エラー"
        echo "クエリ: $sql_query"
        return 1
    }
}

# メイン処理
case "${1:-help}" in
    workers)
        check_workers
        ;;
    tasks)
        check_tasks
        ;;
    stats)
        show_stats
        ;;
    health)
        check_health
        ;;
    deliverables)
        check_deliverables
        ;;
    logs)
        show_logs "$2"
        ;;
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    restart)
        restart_system
        ;;
    clean)
        clean_system
        ;;
    sql)
        execute_sql "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ 不明なコマンド: $1"
        echo ""
        show_help
        exit 1
        ;;
esac