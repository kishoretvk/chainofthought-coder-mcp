"""
Task manager for hierarchical task management.
Supports main tasks and sub-tasks with automatic progress aggregation.
"""
import time
import uuid
import json
from typing import Optional, List, Dict, Any
from ..core.database import Database


class TaskManager:
    """Manages hierarchical tasks."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_main_task(self, session_id: str, name: str, description: str = "",
                        priority: int = 0, tags: List[str] = None) -> str:
        """
        Create main task (no parent).
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        now = time.time()
        
        self.db.execute("""
            INSERT INTO tasks 
            (task_id, session_id, parent_id, name, description, status, progress,
             priority, dependencies, tags, metadata, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?, 'pending', 0.0, ?, ?, ?, ?, ?, ?)
        """, (task_id, session_id, name, description, priority,
              json.dumps([]), json.dumps(tags or []), json.dumps({}), now, now))
        
        return task_id
    
    def create_subtask(self, session_id: str, parent_id: str, name: str,
                      description: str = "", priority: int = 0) -> str:
        """
        Create sub-task under parent.
        """
        task_id = f"subtask_{uuid.uuid4().hex[:8]}"
        now = time.time()
        
        self.db.execute("""
            INSERT INTO tasks 
            (task_id, session_id, parent_id, name, description, status, progress,
             priority, dependencies, tags, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', 0.0, ?, ?, ?, ?, ?, ?)
        """, (task_id, session_id, parent_id, name, description, priority,
              json.dumps([]), json.dumps([]), json.dumps({}), now, now))
        
        return task_id
    
    def update_progress(self, task_id: str, progress: float, status: str = None,
                       metadata: Dict = None):
        """Update task progress and status."""
        updates = ["progress = ?", "updated_at = ?"]
        params = [progress, time.time()]
        
        if status:
            updates.append("status = ?")
            params.append(status)
        
        if metadata:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        
        params.append(task_id)
        
        self.db.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
            params
        )
        
        # Auto-update parent
        self._update_parent_progress(task_id)
    
    def _update_parent_progress(self, task_id: str):
        """Recalculate parent progress from sub-tasks."""
        result = self.db.fetch_one(
            "SELECT parent_id FROM tasks WHERE task_id = ?", (task_id,)
        )
        
        if not result or not result['parent_id']:
            return
        
        parent_id = result['parent_id']
        
        stats = self.db.fetch_one("""
            SELECT 
                AVG(progress) as avg_progress,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM tasks WHERE parent_id = ?
        """, (parent_id,))
        
        if stats:
            avg_progress = stats['avg_progress'] or 0.0
            total = stats['total']
            completed = stats['completed']
            
            new_status = "completed" if completed == total else "in_progress"
            
            self.db.execute("""
                UPDATE tasks 
                SET progress = ?, status = ?, updated_at = ?
                WHERE task_id = ?
            """, (avg_progress, new_status, time.time(), parent_id))
    
    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID."""
        return self.db.fetch_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    
    def get_subtasks(self, parent_id: str) -> List[Dict[str, Any]]:
        """Get all sub-tasks of a task."""
        return self.db.fetch_all(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at",
            (parent_id,)
        )
    
    def get_tree(self, session_id: str, root_task_id: str = None) -> Dict[str, Any]:
        """Get hierarchical task tree."""
        if root_task_id:
            root = self.get(root_task_id)
            if not root:
                return None
            return self._build_tree(root)
        else:
            main_tasks = self.db.fetch_all(
                "SELECT * FROM tasks WHERE session_id = ? AND parent_id IS NULL ORDER BY created_at",
                (session_id,)
            )
            return {
                "session_id": session_id,
                "main_tasks": [self._build_tree(task) for task in main_tasks]
            }
    
    def _build_tree(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively build task tree."""
        task_id = task['task_id']
        subtasks = self.get_subtasks(task_id)
        
        dependencies = task.get('dependencies')
        if dependencies is None:
            dependencies = '[]'
        
        return {
            "task_id": task_id,
            "session_id": task['session_id'],
            "name": task['name'],
            "description": task['description'],
            "status": task['status'],
            "progress": task['progress'],
            "priority": task['priority'],
            "dependencies": json.loads(dependencies) if dependencies else [],
            "tags": json.loads(task['tags']) if task['tags'] else [],
            "is_planned": task.get('is_planned', 0),
            "is_executed": task.get('is_executed', 0),
            "plan_session_id": task.get('plan_session_id'),
            "act_session_id": task.get('act_session_id'),
            "subtasks": [self._build_tree(st) for st in subtasks]
        }
    
    def add_dependency(self, task_id: str, depends_on: str) -> bool:
        """Add dependency between tasks."""
        task = self.get(task_id)
        if not task:
            return False
        
        deps_str = task.get('dependencies')
        deps = json.loads(deps_str) if deps_str else []
        
        if depends_on not in deps:
            deps.append(depends_on)
        
        self.db.execute(
            "UPDATE tasks SET dependencies = ? WHERE task_id = ?",
            (json.dumps(deps), task_id)
        )
        return True
    
    def list_by_status(self, session_id: str, status: str) -> List[Dict[str, Any]]:
        """Get all tasks with specific status."""
        return self.db.fetch_all(
            "SELECT * FROM tasks WHERE session_id = ? AND status = ?",
            (session_id, status)
        )
    
    # ==================== Plan/Act Tracking ====================
    
    def mark_as_planned(self, task_id: str, plan_session_id: str):
        """Mark task as planned in a specific session."""
        self.db.execute("""
            UPDATE tasks 
            SET is_planned = 1, plan_session_id = ?, updated_at = ?
            WHERE task_id = ?
        """, (plan_session_id, time.time(), task_id))
        
        # Also mark all subtasks
        self._mark_subtasks_as_planned(task_id, plan_session_id)
    
    def _mark_subtasks_as_planned(self, parent_id: str, plan_session_id: str):
        """Mark all subtasks as planned."""
        subtasks = self.get_subtasks(parent_id)
        for subtask in subtasks:
            self.db.execute("""
                UPDATE tasks 
                SET is_planned = 1, plan_session_id = ?, updated_at = ?
                WHERE task_id = ?
            """, (plan_session_id, time.time(), subtask['task_id']))
            self._mark_subtasks_as_planned(subtask['task_id'], plan_session_id)
    
    def mark_as_executed(self, task_id: str, act_session_id: str):
        """Mark task as executed in a specific session."""
        self.db.execute("""
            UPDATE tasks 
            SET is_executed = 1, act_session_id = ?, updated_at = ?
            WHERE task_id = ?
        """, (act_session_id, time.time(), task_id))
        
        # Also mark all subtasks
        self._mark_subtasks_as_executed(task_id, act_session_id)
    
    def _mark_subtasks_as_executed(self, parent_id: str, act_session_id: str):
        """Mark all subtasks as executed."""
        subtasks = self.get_subtasks(parent_id)
        for subtask in subtasks:
            self.db.execute("""
                UPDATE tasks 
                SET is_executed = 1, act_session_id = ?, updated_at = ?
                WHERE task_id = ?
            """, (act_session_id, time.time(), subtask['task_id']))
            self._mark_subtasks_as_executed(subtask['task_id'], act_session_id)
    
    def get_planned_tasks(self, plan_session_id: str = None) -> List[Dict[str, Any]]:
        """Get all planned tasks."""
        if plan_session_id:
            return self.db.fetch_all(
                "SELECT * FROM tasks WHERE is_planned = 1 AND plan_session_id = ?",
                (plan_session_id,)
            )
        return self.db.fetch_all("SELECT * FROM tasks WHERE is_planned = 1")
    
    def get_executed_tasks(self, act_session_id: str = None) -> List[Dict[str, Any]]:
        """Get all executed tasks."""
        if act_session_id:
            return self.db.fetch_all(
                "SELECT * FROM tasks WHERE is_executed = 1 AND act_session_id = ?",
                (act_session_id,)
            )
        return self.db.fetch_all("SELECT * FROM tasks WHERE is_executed = 1")
    
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks that are planned but not executed."""
        return self.db.fetch_all("""
            SELECT * FROM tasks 
            WHERE is_planned = 1 AND is_executed = 0
            ORDER BY created_at
        """)
    
    def get_plan_act_summary(self, session_id: str = None) -> Dict[str, Any]:
        """Get summary of planned vs executed tasks."""
        if session_id:
            planned = len(self.db.fetch_all(
                "SELECT * FROM tasks WHERE plan_session_id = ?", (session_id,)
            ))
            executed = len(self.db.fetch_all(
                "SELECT * FROM tasks WHERE act_session_id = ?", (session_id,)
            ))
        else:
            planned = len(self.db.fetch_all("SELECT * FROM tasks WHERE is_planned = 1"))
            executed = len(self.db.fetch_all("SELECT * FROM tasks WHERE is_executed = 1"))
        
        pending = len(self.db.fetch_all("SELECT * FROM tasks WHERE is_planned = 1 AND is_executed = 0"))
        
        return {
            "planned": planned,
            "executed": executed,
            "pending": pending,
            "total": planned + executed
        }
