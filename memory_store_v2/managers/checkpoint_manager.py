"""
Checkpoint manager for multi-level checkpointing.
Handles overall, subtask, and stage checkpoints with file-based snapshots.
"""
import time
import uuid
import json
import os
import hashlib
from typing import Optional, List, Dict, Any
from ..core.database import Database
from ..core.file_store import FileStore
from .task_manager import TaskManager
from .memory_manager import MemoryManager


class CheckpointManager:
    """Multi-level checkpoint management."""
    
    def __init__(self, db: Database, file_store: FileStore,
                 task_manager: TaskManager, memory_manager: MemoryManager):
        self.db = db
        self.file_store = file_store
        self.task_manager = task_manager
        self.memory_manager = memory_manager
    
    def create_overall(self, session_id: str, tags: List[str] = None,
                      metadata: Dict = None) -> str:
        """
        Create overall session checkpoint.
        
        Args:
            session_id: Session ID
            tags: Optional tags
            metadata: Optional metadata
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"cp_{uuid.uuid4().hex[:8]}"
        
        # Build snapshot
        snapshot = {
            "type": "overall",
            "session_id": session_id,
            "timestamp": time.time(),
            "tasks": self.task_manager.get_tree(session_id),
            "long_term_memory": self.memory_manager.retrieve_long_term(session_id, limit=50),
            "short_term_memory": self.memory_manager.get_short_term(session_id),
            "metadata": metadata or {}
        }
        
        # Save to file
        snapshot_path = self.file_store.save_snapshot(snapshot, checkpoint_id)
        file_info = self.file_store.get_file_info(checkpoint_id)
        
        # Store metadata in DB
        self.db.execute("""
            INSERT INTO checkpoints 
            (checkpoint_id, session_id, task_id, level, snapshot_path, 
             snapshot_size, snapshot_hash, timestamp, tags, metadata)
            VALUES (?, ?, NULL, 'overall', ?, ?, ?, ?, ?, ?)
        """, (checkpoint_id, session_id, snapshot_path, file_info['size'],
              file_info['hash'], snapshot['timestamp'], json.dumps(tags or []),
              json.dumps(metadata or {})))
        
        return checkpoint_id
    
    def create_subtask(self, task_id: str, tags: List[str] = None,
                      metadata: Dict = None) -> str:
        """
        Create sub-task checkpoint.
        
        Args:
            task_id: Task ID
            tags: Optional tags
            metadata: Optional metadata
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"cp_{uuid.uuid4().hex[:8]}"
        
        # Get task info
        task = self.task_manager.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        session_id = task['session_id']
        
        # Get task with subtasks
        task_with_subtasks = self.task_manager.get_tree(session_id, task_id)
        
        # Build snapshot
        snapshot = {
            "type": "subtask",
            "task_id": task_id,
            "session_id": session_id,
            "timestamp": time.time(),
            "task_details": task_with_subtasks,
            "subtasks": task_with_subtasks.get('subtasks', []) if isinstance(task_with_subtasks, dict) else [],
            "metadata": metadata or {}
        }
        
        # Save to file
        snapshot_path = self.file_store.save_snapshot(snapshot, checkpoint_id)
        file_info = self.file_store.get_file_info(checkpoint_id)
        
        # Store metadata
        self.db.execute("""
            INSERT INTO checkpoints 
            (checkpoint_id, session_id, task_id, level, snapshot_path, 
             snapshot_size, snapshot_hash, timestamp, tags, metadata)
            VALUES (?, ?, ?, 'subtask', ?, ?, ?, ?, ?, ?)
        """, (checkpoint_id, session_id, task_id, snapshot_path, file_info['size'],
              file_info['hash'], snapshot['timestamp'], json.dumps(tags or []),
              json.dumps(metadata or {})))
        
        return checkpoint_id
    
    def create_stage(self, task_id: str, stage_name: str, tags: List[str] = None,
                    metadata: Dict = None) -> str:
        """
        Create stage checkpoint within a task.
        
        Args:
            task_id: Task ID
            stage_name: Stage name
            tags: Optional tags
            metadata: Optional metadata
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"cp_{uuid.uuid4().hex[:8]}"
        
        task = self.task_manager.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        session_id = task['session_id']
        
        # Build snapshot
        snapshot = {
            "type": "stage",
            "task_id": task_id,
            "session_id": session_id,
            "stage_name": stage_name,
            "timestamp": time.time(),
            "current_state": {
                "task": task,
                "subtasks": self.task_manager.get_subtasks(task_id),
                "short_term_memory": self.memory_manager.get_short_term(session_id)
            },
            "metadata": metadata or {}
        }
        
        # Save to file
        snapshot_path = self.file_store.save_snapshot(snapshot, checkpoint_id)
        file_info = self.file_store.get_file_info(checkpoint_id)
        
        # Store metadata
        self.db.execute("""
            INSERT INTO checkpoints 
            (checkpoint_id, session_id, task_id, level, snapshot_path, 
             snapshot_size, snapshot_hash, timestamp, tags, metadata)
            VALUES (?, ?, ?, 'stage', ?, ?, ?, ?, ?, ?)
        """, (checkpoint_id, session_id, task_id, snapshot_path, file_info['size'],
              file_info['hash'], snapshot['timestamp'], json.dumps(tags or []),
              json.dumps(metadata or {})))
        
        return checkpoint_id
    
    def get(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get checkpoint with full snapshot.
        
        Args:
            checkpoint_id: Checkpoint ID
            
        Returns:
            Checkpoint dictionary or None
        """
        metadata = self.db.fetch_one(
            "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,)
        )
        
        if not metadata:
            return None
        
        # Load snapshot from file
        snapshot = self.file_store.load_snapshot(checkpoint_id)
        
        return {
            **metadata,
            "snapshot": snapshot
        }
    
    def list(self, session_id: str, task_id: str = None, level: str = None,
             tags: List[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List checkpoints with filters.
        
        Args:
            session_id: Session ID
            task_id: Filter by task
            level: Filter by level (overall, subtask, stage)
            tags: Filter by tags
            limit: Maximum results
            
        Returns:
            List of checkpoint metadata
        """
        sql = "SELECT * FROM checkpoints WHERE session_id = ?"
        params = [session_id]
        
        if task_id:
            sql += " AND task_id = ?"
            params.append(task_id)
        
        if level:
            sql += " AND level = ?"
            params.append(level)
        
        if tags:
            # JSON array contains check (simplified)
            sql += " AND tags LIKE ?"
            params.append(f'%"{tags[0]}"%')
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        return self.db.fetch_all(sql, params)
    
    def restore(self, session_id: str, checkpoint_id: str, level: str = 'overall'):
        """
        Restore from checkpoint.
        
        Args:
            session_id: Session ID
            checkpoint_id: Checkpoint ID
            level: Restore level
            
        Returns:
            True if successful
        """
        checkpoint = self.get(checkpoint_id)
        if not checkpoint:
            return False
        
        snapshot = checkpoint['snapshot']
        
        if level == 'overall':
            # Restore tasks
            if 'tasks' in snapshot and snapshot['tasks']:
                self._restore_tasks(session_id, snapshot['tasks'])
            
            # Restore memory - clear existing first to avoid duplicates
            if 'long_term_memory' in snapshot:
                # Clear existing session memories
                self.db.execute(
                    "DELETE FROM long_term_memory WHERE session_id = ?",
                    (session_id,)
                )
                # Add checkpoint memories
                for memory in snapshot['long_term_memory']:
                    self.memory_manager.store_long_term(
                        session_id,
                        memory['memory_type'],
                        memory['content'],
                        memory.get('tags'),
                        memory.get('confidence', 1.0),
                        memory.get('source', '')
                    )
            
            if 'short_term_memory' in snapshot:
                stm = snapshot['short_term_memory']
                if stm:
                    # Clear and restore short-term memory
                    self.db.execute(
                        "DELETE FROM short_term_memory WHERE session_id = ?",
                        (session_id,)
                    )
                    self.memory_manager.store_short_term(
                        session_id,
                        active_context=stm.get('active_context'),
                        recent_actions=stm.get('recent_actions'),
                        focus_area=stm.get('focus_area'),
                        temporary_state=stm.get('temporary_state')
                    )
        
        elif level == 'subtask':
            if 'task_details' in snapshot:
                self._restore_tasks(session_id, snapshot['task_details'])
        
        elif level == 'stage':
            # Restore specific state
            if 'current_state' in snapshot:
                state = snapshot['current_state']
                if 'task' in state:
                    task = state['task']
                    self.task_manager.update_progress(
                        task['task_id'],
                        task['progress'],
                        task['status']
                    )
        
        return True
    
    def _restore_tasks(self, session_id: str, task_tree: Dict[str, Any]):
        """Recursively restore tasks from tree."""
        # Handle the tree structure from get_tree()
        if 'main_tasks' in task_tree:
            tasks = task_tree['main_tasks']
        elif isinstance(task_tree, list):
            tasks = task_tree
        else:
            # Single task
            tasks = [task_tree]
        
        for task in tasks:
            task_id = task.get('task_id')
            
            # Skip if no task_id (might be tree wrapper)
            if not task_id:
                continue
            
            # Check if task exists
            existing = self.task_manager.get(task_id)
            
            if existing:
                # Update existing
                self.task_manager.update_progress(
                    task_id,
                    task['progress'],
                    task['status']
                )
            else:
                # Create new
                parent_id = task.get('parent_id')
                if parent_id:
                    self.task_manager.create_subtask(
                        session_id,
                        parent_id,
                        task['name'],
                        task['description'],
                        task.get('priority', 0)
                    )
                else:
                    self.task_manager.create_main_task(
                        session_id,
                        task['name'],
                        task['description'],
                        task.get('priority', 0),
                        task.get('tags', [])
                    )
            
            # Restore sub-tasks
            if 'subtasks' in task and task['subtasks']:
                self._restore_tasks(session_id, task['subtasks'])
    
    def diff(self, checkpoint_id_1: str, checkpoint_id_2: str) -> Dict[str, Any]:
        """
        Compare two checkpoints.
        
        Args:
            checkpoint_id_1: First checkpoint
            checkpoint_id_2: Second checkpoint
            
        Returns:
            Difference dictionary
        """
        cp1 = self.get(checkpoint_id_1)
        cp2 = self.get(checkpoint_id_2)
        
        if not cp1 or not cp2:
            return {"error": "One or both checkpoints not found"}
        
        diff = {
            "checkpoint_1": checkpoint_id_1,
            "checkpoint_2": checkpoint_id_2,
            "timestamp_diff": cp2['timestamp'] - cp1['timestamp'],
            "changes": {}
        }
        
        # Compare task progress
        if 'snapshot' in cp1 and 'snapshot' in cp2:
            tasks1 = self._extract_task_progress(cp1['snapshot'])
            tasks2 = self._extract_task_progress(cp2['snapshot'])
            
            changes = []
            for task_id in set(tasks1.keys()) | set(tasks2.keys()):
                if task_id not in tasks1:
                    changes.append(f"NEW: {task_id}")
                elif task_id not in tasks2:
                    changes.append(f"REMOVED: {task_id}")
                elif tasks1[task_id] != tasks2[task_id]:
                    changes.append(
                        f"CHANGED: {task_id} {tasks1[task_id]} → {tasks2[task_id]}"
                    )
            
            diff['changes']['tasks'] = changes
        
        return diff
    
    def _extract_task_progress(self, snapshot: Dict[str, Any]) -> Dict[str, float]:
        """Extract task progress from snapshot."""
        progress = {}
        
        def extract(tasks):
            if not tasks:
                return
            
            # Handle tree structure from get_tree()
            if isinstance(tasks, dict):
                if 'main_tasks' in tasks:
                    tasks = tasks['main_tasks']
                else:
                    tasks = [tasks]
            
            for task in tasks:
                if 'task_id' in task:
                    progress[task['task_id']] = task['progress']
                if 'subtasks' in task and task['subtasks']:
                    extract(task['subtasks'])
        
        if 'tasks' in snapshot:
            extract(snapshot['tasks'])
        
        return progress
    
    def cleanup_old(self, session_id: str, keep_last: int = 10) -> int:
        """
        Keep only last N checkpoints per session.
        
        Args:
            session_id: Session ID
            keep_last: Number of checkpoints to keep
            
        Returns:
            Number of checkpoints deleted
        """
        checkpoints = self.list(session_id, limit=1000)
        
        if len(checkpoints) <= keep_last:
            return 0
        
        # Get checkpoints to delete
        to_delete = checkpoints[keep_last:]
        deleted = 0
        
        for cp in to_delete:
            # Delete file
            self.file_store.delete_snapshot(cp['checkpoint_id'])
            
            # Delete DB record
            self.db.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (cp['checkpoint_id'],)
            )
            deleted += 1
        
        return deleted
