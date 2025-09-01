# 📋 Delegation Decision Guide for the Koubou System

## 🎯 Decision Flowchart

```
Task assigned
    ↓
How many tasks?
├─ 1–3  → Task type?
│          ├─ Routine   → Consider worker delegation
│          └─ Creative  → Hand‑off to the master
├─ 4–10 → Worker status?
│          ├─ Available → Strongly recommend delegation
│          └─ Busy     → Decide based on urgency
└─ >10  → Strongly recommend delegation
```

## 📊 Performance Data

### Recent Test Results (Reference Values)
- **Total processed**: 71 items / 22 min = **3.2 items/min**
- **Success rate**: 100 %
- **Parallel processing benefit**: ~1.6× efficiency increase
- **Worker cost**: GPU usage only

### Time Estimates
- **General tasks (Ollama)**: ~15–20 s each
- **Code tasks (Codex)**: ~20–30 s each
- **Complex tasks**: 30–60 s

## ⚡ Checking Worker Status

### 1. Dashboard

```
http://localhost:8080
- IDLE    → Ready immediately
- WORKING → Task in progress
- PROCESSING → LLM inference (seconds to minutes)
```

### 2. From the Command Line

```bash
# Worker details
sqlite3 .koubou/db/koubou.db "SELECT worker_id, status, completed_tasks FROM workers WHERE status != 'offline';"

# Pending tasks count
sqlite3 .koubou/db/koubou.db "SELECT COUNT(*) FROM task_master WHERE status='pending';"
```

## 🧠 Advanced Decision Criteria

### When to strongly recommend delegation
- Similar task quantity ≥ 5
- Expected runtime ≥ 1 hour
- Night or weekend work
- Master has other critical tasks
- ≥ 2 workers IDLE

### When to let the master handle it
- New task type (no precedent)
- Requires error handling or debugging
- Needs external system integration
- Final quality judgement matters
- Expected finish < 15 min

### If in doubt
1. Delegate a single test task
2. Verify quality before delegating the rest
3. Consider parallel work: master + workers

## 🔧 Tips for Worker Management

### Efficient use
- **Batch processing**: group similar tasks
- **Time distribution**: run long tasks during night
- **Monitoring**: keep an eye on the dashboard

### When problems arise
```bash
# Force restart a worker
pkill -f "local_worker"
WORKER_ID=emergency_worker .koubou/venv/bin/python .koubou/scripts/workers/local_worker.py &

# Restart the whole system
.koubou/start_system.sh
```

## 📈 Continuous Improvement

### Regular checks
- **Monthly**: review worker success rate
- **Weekly**: track processing time trends
- **Daily**: monitor dashboard activity

### Optimization points
- Adjust number of workers (1–3 is optimal)
- Optimize per task type
- Improve GPU usage efficiency

---

**The master’s time is precious. Delegating appropriately lets them focus on creative work!**

---
