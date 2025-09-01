# 📋 API仕様書

## REST API Endpoints

### タスク管理
- `GET /api/tasks` - タスク一覧取得
- `POST /api/tasks` - タスク作成
- `PUT /api/tasks/{id}` - タスク更新
- `DELETE /api/tasks/{id}` - タスク削除

### WebSocket
- `/ws` - リアルタイム更新通知

## データ構造
```json
{
  "id": "string",
  "title": "string", 
  "description": "string",
  "status": "pending|in_progress|completed",
  "priority": "low|medium|high",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```