"""
Progress tracker - Real-time progress monitoring and history tracking.
"""
import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum


class ProgressStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class ProgressTracker:
    """
    Real-time progress tracking with history and callbacks.
    
    Features:
    - Progress history with timestamps
    - Real-time callbacks
    - Progress prediction
    - Aggregated progress for parent tasks
    """
    
    def __init__(self, task_manager):
        self.task_manager = task_manager
        self._history: Dict[str, List[Dict]] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
    
    async def update_progress(self, task_id: str, progress: float, 
                               status: str = None, metadata: Dict = None):
        """
        Update task progress.
        
        Args:
            task_id: Task ID
            progress: Progress value (0.0 to 1.0)
            status: Optional status override
            metadata: Optional additional metadata
        """
        task = self.task_manager.get(task_id)
        if not task:
            return
        
        # Determine status from progress
        if status is None:
            if progress >= 1.0:
                status = 'completed'
            elif progress > 0:
                status = 'in_progress'
            else:
                status = 'pending'
        
        # Update task in database
        self.task_manager.update_progress(task_id, progress, status, metadata)
        
        # Record history
        await self._record_history(task_id, progress, status, metadata)
        
        # Emit callback
        await self._emit_callback(task_id, progress, status)
        
        # Update parent progress
        self.task_manager._update_parent_progress(task_id)
    
    async def _record_history(self, task_id: str, progress: float, 
                               status: str, metadata: Dict = None):
        """Record progress update in history."""
        async with self._lock:
            if task_id not in self._history:
                self._history[task_id] = []
            
            self._history[task_id].append({
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'progress': progress,
                'status': status,
                'metadata': metadata or {}
            })
    
    async def _emit_callback(self, task_id: str, progress: float, status: str):
        """Emit progress to registered callbacks."""
        callbacks = self._callbacks.get(task_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task_id, progress, status)
                else:
                    callback(task_id, progress, status)
            except Exception as e:
                print(f"Progress callback error: {e}")
    
    def on_progress(self, task_id: str, callback: Callable):
        """Register progress callback for a task."""
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        self._callbacks[task_id].append(callback)
    
    def get_history(self, task_id: str, limit: int = 100) -> List[Dict]:
        """Get progress history for a task."""
        history = self._history.get(task_id, [])
        return history[-limit:]
    
    def get_current_progress(self, task_id: str) -> Optional[Dict]:
        """Get current progress for a task."""
        history = self.get_history(task_id, 1)
        if history:
            return history[-1]
        return None
    
    def get_progress_summary(self, session_id: str, root_task_id: str = None) -> Dict:
        """
        Get progress summary for a session or task tree.
        
        Args:
            session_id: Session ID
            root_task_id: Optional root task ID
            
        Returns:
            Progress summary
        """
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return {'status': 'error', 'message': 'Task tree not found'}
        
        stats = {'total': 0, 'completed': 0, 'in_progress': 0, 'pending': 0, 'failed': 0}
        
        def traverse(task):
            stats['total'] += 1
            status = task.get('status', 'pending')
            stats[status] = stats.get(status, 0) + 1
            
            for subtask in task.get('subtasks', []):
                traverse(subtask)
        
        if 'main_tasks' in task_tree:
            for task in task_tree['main_tasks']:
                traverse(task)
        else:
            traverse(task_tree)
        
        stats['progress'] = (
            stats['completed'] / stats['total'] if stats['total'] > 0 else 0.0
        )
        
        return stats
    
    def predict_completion(self, session_id: str, root_task_id: str = None) -> Dict:
        """
        Predict task completion based on current progress.
        
        Args:
            session_id: Session ID
            root_task_id: Optional root task ID
            
        Returns:
            Prediction data
        """
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return {'status': 'error', 'message': 'Task tree not found'}
        
        # Calculate average time per task type
        time_per_task = {}
        task_counts = {}
        
        for task_id, history in self._history.items():
            if len(history) >= 2:
                task = self.task_manager.get(task_id)
                if task and task.get('parent_id'):
                    task_type = task.get('name', 'unknown')[:20]
                    
                    duration = history[-1]['timestamp'] - history[0]['timestamp']
                    if task_type not in time_per_task:
                        time_per_task[task_type] = []
                    time_per_task[task_type].append(duration)
        
        # Calculate averages
        avg_times = {}
        for task_type, times in time_per_task.items():
            avg_times[task_type] = sum(times) / len(times)
        
        # Estimate remaining time
        remaining_tasks = 0
        estimated_time = 0
        
        def traverse(task):
            nonlocal remaining_tasks, estimated_time
            
            if task.get('status') not in ['completed', 'failed']:
                remaining_tasks += 1
                task_type = task.get('name', 'unknown')[:20]
                estimated_time += avg_times.get(task_type, 300)  # Default 5 min
        
        if 'main_tasks' in task_tree:
            for task in task_tree['main_tasks']:
                traverse(task)
        else:
            traverse(task_tree)
        
        return {
            'remaining_tasks': remaining_tasks,
            'estimated_seconds': estimated_time,
            'estimated_minutes': estimated_time / 60,
            'average_task_time': sum(avg_times.values()) / len(avg_times) if avg_times else 300,
            'completion_percentage': self.get_progress_summary(session_id, root_task_id)['progress'] * 100
        }
