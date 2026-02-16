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
        
        Args:
            session_id: Session ID
            name: Task name
            description: Task description
            priority: Priority level
            tags: List of tags
            
        Returns:
            Task ID
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        now = time.time()
        
        # FIX: Added dependencies column with default '[]' instead of NULL
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
        
        Args:
            session_id: Session ID
            parent_id: Parent task ID
            name: Sub-task name
            description: Sub-task description
            priority: Priority level
            
        Returns:
            Task ID
        """
        task_id = f"subtask_{uuid.uuid4().hex[:8]}"
        now = time.time()
        
        # FIX: Added dependencies column with default '[]' instead of NULL
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
        """
        Update task progress and status.
        
        Args:
            task_id: Task ID
            progress: Progress (0.0 to 1.0)
            status: New status
            metadata: Additional metadata
        """
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
        
        # Calculate average progress
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
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task dictionary or None
        """
        return self.db.fetch_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    
    def get_subtasks(self, parent_id: str) -> List[Dict[str, Any]]:
        """
        Get all sub-tasks of a task.
        
        Args:
            parent_id: Parent task ID
            
        Returns:
            List of sub-task dictionaries
        """
        return self.db.fetch_all(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at",
            (parent_id,)
        )
    
    def get_tree(self, session_id: str, root_task_id: str = None) -> Dict[str, Any]:
        """
        Get hierarchical task tree.
        
        Args:
            session_id: Session ID
            root_task_id: Optional root task ID
            
        Returns:
            Task tree structure
        """
        if root_task_id:
            root = self.get(root_task_id)
            if not root:
                return None
            return self._build_tree(root)
        else:
            # Get all main tasks
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
        
        # FIX: Handle NULL dependencies gracefully
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
            "subtasks": [self._build_tree(st) for st in subtasks]
        }
    
    def add_dependency(self, task_id: str, depends_on: str) -> bool:
        """
        Add dependency between tasks.
        
        Args:
            task_id: Task ID
            depends_on: Task ID that must complete first
            
        Returns:
            True if successful
        """
        task = self.get(task_id)
        if not task:
            return False
        
        # FIX: Handle NULL dependencies gracefully
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
        """
        Get all tasks with specific status.
        
        Args:
            session_id: Session ID
            status: Task status
            
        Returns:
            List of task dictionaries
        """
        return self.db.fetch_all(
            "SELECT * FROM tasks WHERE session_id = ? AND status = ?",
            (session_id, status)
        )
