#!/usr/bin/env python3
"""
Enhanced Gemini Local Worker with File Operation Support
"""

import os
import sys
import json
import time
import subprocess
import sqlite3
import signal
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tool_executor import ToolExecutor

# Common modules path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common.database import get_db_manager

# Configuration
KOUBOU_HOME = os.environ.get('KOUBOU_HOME', '/home/hama/project/koubou-system/.koubou')
DB_PATH = f"{KOUBOU_HOME}/db/koubou.db"
LOG_DIR = f"{KOUBOU_HOME}/logs/workers"

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Initialize database manager
db = get_db_manager(DB_PATH)

# Worker ID from environment or generate
worker_id_for_log = os.environ.get('WORKER_ID', f"enhanced_worker_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid() % 10}")

# Logging setup
log_file = f"{LOG_DIR}/{worker_id_for_log}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

class EnhancedGeminiWorker:
    def __init__(self):
        # Check if running through Worker Pool Manager (optional for enhanced worker)
        auth_token = os.environ.get('WORKER_AUTH_TOKEN')
        expected_token = os.environ.get('KOUBOU_HOME', '') + '_POOL_MANAGER'
        
        if auth_token and auth_token != expected_token:
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ Enhanced worker running without Worker Pool Manager authentication")
        
        self.worker_id = worker_id_for_log
        self.model = os.environ.get('LOCAL_LLM_MODEL', 'gpt-oss-20b@f16')
        self.timeout = 600  # 10 minutes
        self.max_retries = 3
        self.logger = logging.getLogger(__name__)
        self.tool_executor = ToolExecutor()
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.cleanup_handler)
        signal.signal(signal.SIGINT, self.cleanup_handler)
        
        # Register worker
        self.register_worker()
        
    def register_worker(self):
        """Register worker in database"""
        try:
            # Clean up any existing record first
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workers WHERE worker_id = ?", (self.worker_id,))
            conn.commit()
            conn.close()
        except:
            pass
        
        if db.register_worker(self.worker_id):
            self.logger.info(f"Enhanced worker {self.worker_id} registered in DB.")
        else:
            self.logger.error(f"Failed to register worker {self.worker_id}")
            sys.exit(1)
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """Get next pending task from database"""
        try:
            pending_tasks = db.get_pending_tasks(limit=1)
            if pending_tasks:
                row = pending_tasks[0]
                task_id = row['task_id']
                
                if db.assign_task_to_worker(task_id, self.worker_id):
                    self.logger.info(f"Picked up task {task_id}")
                    db.update_worker_status(self.worker_id, 'busy', task_id)
                    
                    content_str = row["content"] or '{}'
                    context_str = row.get("context", '{}')
                    
                    task = {
                        'task_id': task_id,
                        'content': json.loads(content_str),
                        'context': json.loads(context_str)
                    }
                    return task
                else:
                    return None
        except sqlite3.Error as e:
            self.logger.error(f"Database error while getting task: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
        return None
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task with enhanced capabilities"""
        task_content = task.get('content', {})
        task_type = task_content.get('type', 'general')
        prompt = task_content.get('prompt', '')
        
        self.logger.info(f"Processing task {task['task_id']} of type '{task_type}' with enhanced capabilities")
        
        if not prompt:
            return {'success': False, 'output': '', 'error': 'Prompt is empty'}
        
        # Update status to processing
        db.update_worker_status(self.worker_id, 'processing', task['task_id'])
        
        # First, get the response from Gemini CLI
        result = self.run_gemini_task(prompt)
        
        if result['success']:
            # Parse and execute any tool calls in the output
            enhanced_output = self.tool_executor.parse_and_execute(result['output'])
            
            # If tools were executed, return the enhanced output
            if enhanced_output != result['output']:
                self.logger.info("Tool calls detected and executed")
                result['output'] = enhanced_output
                result['tools_executed'] = True
            else:
                result['tools_executed'] = False
        
        return result
    
    def run_gemini_task(self, prompt: str) -> Dict[str, Any]:
        """Execute task using Gemini CLI"""
        gemini_script = f"{KOUBOU_HOME}/scripts/gemini-exec.sh"
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Executing Gemini CLI script (attempt {attempt + 1}/{self.max_retries})")
                
                # Start subprocess
                start_time = time.time()
                process = subprocess.Popen(
                    [gemini_script, prompt],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid
                )
                
                self.logger.info(f"Subprocess started with PID: {process.pid}")
                
                try:
                    stdout, stderr = process.communicate(timeout=self.timeout)
                    elapsed_time = time.time() - start_time
                    
                    self.logger.info(f"Subprocess completed in {elapsed_time:.2f} seconds")
                    
                    if process.returncode == 0:
                        return {
                            'success': True,
                            'output': stdout.strip(),
                            'error': None
                        }
                    else:
                        self.logger.error(f"Gemini CLI failed with code {process.returncode}")
                        if attempt < self.max_retries - 1:
                            time.sleep(2 ** attempt)
                        else:
                            return {
                                'success': False,
                                'output': stdout,
                                'error': stderr
                            }
                            
                except subprocess.TimeoutExpired:
                    self.logger.error(f"Timeout after {self.timeout} seconds")
                    process.kill()
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                    else:
                        return {'success': False, 'output': '', 'error': 'Timeout'}
                        
            except Exception as e:
                self.logger.exception(f"Unexpected error: {e}")
                return {'success': False, 'output': '', 'error': str(e)}
        
        return {'success': False, 'output': '', 'error': 'Max retries exceeded'}
    
    def update_task_result(self, task_id: str, result: Dict[str, Any]):
        """Update task result in database"""
        try:
            db.complete_task(task_id, json.dumps(result))
            
            if result.get('success'):
                db.increment_worker_completed_tasks(self.worker_id)
            else:
                db.increment_worker_failed_tasks(self.worker_id)
            
            db.update_worker_status(self.worker_id, 'idle', None)
            
            success_indicator = "✅" if result.get('success') else "❌"
            tools_indicator = "🔧" if result.get('tools_executed') else ""
            self.logger.info(f"{success_indicator} {tools_indicator} Task {task_id} completed")
        except sqlite3.Error as e:
            self.logger.error(f"Database error while updating task result: {e}")
    
    def cleanup(self):
        """Clean up on exit"""
        try:
            db.update_worker_status(self.worker_id, 'offline', None)
            self.logger.info(f"Worker {self.worker_id} cleanup completed")
        except:
            pass
    
    def cleanup_handler(self, signum, frame):
        """Signal handler"""
        self.cleanup()
        sys.exit(0)
    
    def run(self):
        """Main worker loop"""
        self.logger.info(f"🚀 Enhanced Gemini worker {self.worker_id} started (model: {self.model})")
        
        try:
            while True:
                task = self.get_next_task()
                if task:
                    result = self.process_task(task)
                    self.update_task_result(task['task_id'], result)
                else:
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            self.logger.info("🛑 Worker interrupted by user")
        except Exception as e:
            self.logger.error(f"💥 Unexpected error: {e}")
        finally:
            self.cleanup()
            self.logger.info(f"👋 Enhanced worker {self.worker_id} stopped")


if __name__ == "__main__":
    worker = EnhancedGeminiWorker()
    worker.run()