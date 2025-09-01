from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import json
import uuid
from datetime import datetime
import asyncio

app = FastAPI(title="レスポンシブタスク管理API", version="1.0.0")

# CORS設定（フロントエンドとの通信用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データベース初期化
def init_db():
    conn = sqlite3.connect("tasks.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Pydanticモデル
class Task(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "pending"
    priority: str = "medium"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None

class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    created_at: str
    updated_at: str

# WebSocket接続管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

# アプリ起動時にDB初期化
@app.on_event("startup")
def startup_event():
    init_db()

# ヘルスチェック
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Task Management API"}

# タスク一覧取得
@app.get("/api/tasks", response_model=List[TaskResponse])
def get_tasks():
    conn = sqlite3.connect("tasks.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    tasks = []
    for row in rows:
        tasks.append(TaskResponse(
            id=row[0],
            title=row[1],
            description=row[2],
            status=row[3],
            priority=row[4],
            created_at=row[5],
            updated_at=row[6]
        ))
    return tasks

# タスク作成
@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(task: Task):
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    conn = sqlite3.connect("tasks.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (id, title, description, status, priority, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (task_id, task.title, task.description, task.status, task.priority, now, now))
    conn.commit()
    conn.close()
    
    # WebSocketで新規作成を通知
    await manager.broadcast(json.dumps({
        "type": "task_created",
        "task": {
            "id": task_id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "created_at": now,
            "updated_at": now
        }
    }))
    
    return TaskResponse(
        id=task_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        created_at=now,
        updated_at=now
    )

# タスク更新
@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, task_update: TaskUpdate):
    conn = sqlite3.connect("tasks.db")
    cursor = conn.cursor()
    
    # 既存タスクの確認
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 更新フィールドの準備
    updates = []
    values = []
    
    if task_update.title is not None:
        updates.append("title = ?")
        values.append(task_update.title)
    if task_update.description is not None:
        updates.append("description = ?")
        values.append(task_update.description)
    if task_update.status is not None:
        updates.append("status = ?")
        values.append(task_update.status)
    if task_update.priority is not None:
        updates.append("priority = ?")
        values.append(task_update.priority)
    
    if updates:
        now = datetime.now().isoformat()
        updates.append("updated_at = ?")
        values.append(now)
        values.append(task_id)
        
        cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
    
    # 更新後のデータ取得
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    result = TaskResponse(
        id=row[0],
        title=row[1],
        description=row[2],
        status=row[3],
        priority=row[4],
        created_at=row[5],
        updated_at=row[6]
    )
    
    # WebSocketで更新を通知
    await manager.broadcast(json.dumps({
        "type": "task_updated",
        "task": result.dict()
    }))
    
    return result

# タスク削除
@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    conn = sqlite3.connect("tasks.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    # WebSocketで削除を通知
    await manager.broadcast(json.dumps({
        "type": "task_deleted",
        "task_id": task_id
    }))
    
    return {"message": "Task deleted successfully"}

# WebSocket接続
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 接続維持のためのping-pong
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)