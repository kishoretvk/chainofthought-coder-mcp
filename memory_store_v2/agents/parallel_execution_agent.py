"""
Parallel execution agent - identifies and manages parallelizable tasks
Enhanced with real task execution hooks, dynamic parallelism, and resource management.
"""
import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Set, Optional, Callable
from enum import Enum
from collections import deque
from heapq import heappush, heappop

from .base_agent import AgentBase


class ExecutionState(Enum):
    IDLE = "idle"
    SCHEDULING = "scheduling"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ParallelExecutionAgent(AgentBase):
    """
    Enhanced parallel execution agent.
    
    Features:
    - Dynamic parallelism adjustment based on system load
    - Task execution hooks for custom executors
    - Resource-aware scheduling
    - Deadlock detection and recovery
    - Execution history and statistics
    """
    
    def __init__(self, task_manager, max_parallel: int = 4):
        super().__init__("parallel_executor")
        self.task_manager = task_manager
        self.max_parallel = max_parallel
        self.min_parallel = 1
        
        # Execution state
        self.currently_running: Dict[str, Dict] = {}
        self.task_queue: deque = deque()
        self.execution_history: List[Dict] = []
        self.execution_stats = {
            'total_executed': 0,
            'total_failed': 0,
            'total_time': 0,
            'avg_execution_time': 0
        }
        
        # Execution hooks
        self._task_executor: Optional[Callable] = None
        self._progress_callback: Optional[Callable] = None
        
        # Concurrency control
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._state_lock = asyncio.Lock()
        self._execution_state = ExecutionState.IDLE
        
        # FIX: Track paused state properly
        self._paused_permits_held = 0
        
        # Deadlock detection
        self._deadlock_check_interval = 30
        self._last_deadlock_check = 0
    
    async def handle_message(self, message: Dict[str, Any]):
        """Handle incoming messages."""
        msg_type = message['content'].get('type')
        
        if msg_type == 'schedule_tasks':
            session_id = message['content']['session_id']
            root_task_id = message['content'].get('root_task_id')
            max_parallel = message['content'].get('max_parallel', self.max_parallel)
            await self.schedule_tasks(session_id, root_task_id, max_parallel)
            
        elif msg_type == 'execute_task':
            task_id = message['content']['task_id']
            await self.execute_task(task_id)
            
        elif msg_type == 'pause_execution':
            await self.pause_execution()
            
        elif msg_type == 'resume_execution':
            await self.resume_execution()
            
        elif msg_type == 'cancel_task':
            task_id = message['content']['task_id']
            await self.cancel_task(task_id)
    
    def set_task_executor(self, executor: Callable):
        """
        Set custom task executor.
        
        Args:
            executor: Async function that takes task_id and returns result
        """
        self._task_executor = executor
    
    def set_progress_callback(self, callback: Callable):
        """
        Set progress callback.
        
        Args:
            callback: Async function called on progress updates
        """
        self._progress_callback = callback
    
    async def schedule_tasks(self, session_id: str, root_task_id: str = None,
                              max_parallel: int = None) -> Dict:
        """
        Schedule tasks for parallel execution.
        
        Args:
            session_id: Session ID
            root_task_id: Optional root task ID
            max_parallel: Override max parallel tasks
            
        Returns:
            Schedule result
        """
        if max_parallel:
            self.max_parallel = max_parallel
        
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return {'status': 'error', 'message': 'Task tree not found'}
        
        async with self._state_lock:
            if self._execution_state == ExecutionState.RUNNING:
                return {'status': 'error', 'message': 'Execution already in progress'}
            
            self._execution_state = ExecutionState.SCHEDULING
        
        # Get execution order from metadata or calculate it
        execution_order = self.get_execution_order(task_tree)
        
        # Build task queue with priorities
        self.build_task_queue(execution_order)
        
        # Start execution
        return await self.process_queue()
    
    def get_execution_order(self, task_tree: Dict[str, Any]) -> List[str]:
        """Extract execution order from task metadata."""
        metadata = json.loads(task_tree.get('metadata', '{}') or '{}')
        return metadata.get('execution_order', self._calculate_execution_order(task_tree))
    
    def _calculate_execution_order(self, task_tree: Dict[str, Any]) -> List[str]:
        """Calculate execution order based on dependencies."""
        order = []
        
        def traverse(task):
            task_id = task['task_id']
            order.append(task_id)
            
            for subtask in task.get('subtasks', []):
                traverse(subtask)
        
        traverse(task_tree)
        return order
    
    def build_task_queue(self, execution_order: List[str], 
                          priorities: Dict[str, int] = None):
        """
        Build prioritized task queue.
        
        Args:
            execution_order: List of task IDs in execution order
            priorities: Optional priority dict {task_id: priority}
        """
        self.task_queue.clear()
        
        for task_id in execution_order:
            # Higher priority number = higher priority
            priority = (priorities or {}).get(task_id, 0)
            task = self.task_manager.get(task_id)
            if task:
                priority += task.get('priority', 0)
            
            heappush(self.task_queue, (-priority, task_id))
    
    async def process_queue(self) -> Dict:
        """
        Process tasks with parallel execution limits.
        
        Returns:
            Execution result
        """
        async with self._state_lock:
            self._execution_state = ExecutionState.RUNNING
        
        self._semaphore = asyncio.Semaphore(self.max_parallel)
        self._paused_permits_held = 0
        
        start_time = time.time()
        tasks_to_process = []
        
        # Prepare all tasks
        while self.task_queue:
            _, task_id = heappop(self.task_queue)
            tasks_to_process.append(task_id)
        
        # Create execution tasks
        async def run_with_hooks(task_id: str) -> Dict:
            async with self._semaphore:
                return await self._execute_with_hooks(task_id)
        
        # Execute in batches based on max_parallel
        results = []
        batch_size = self.max_parallel
        
        for i in range(0, len(tasks_to_process), batch_size):
            batch = tasks_to_process[i:i + batch_size]
            batch_tasks = [run_with_hooks(task_id) for task_id in batch]
            
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                results.extend(batch_results)
                
                # Check for failures and apply fail_fast if needed
                if any(isinstance(r, Exception) for r in batch_results):
                    # Log but continue with other batches
                    pass
                    
            except Exception as e:
                results.extend([{'error': str(e)}] * len(batch))
        
        execution_time = time.time() - start_time
        
        # Update statistics
        self._update_stats(results, execution_time)
        
        async with self._state_lock:
            self._execution_state = ExecutionState.COMPLETED
        
        return {
            'status': 'completed',
            'total_tasks': len(tasks_to_process),
            'executed': len([r for r in results if not isinstance(r, dict) or 'error' not in r]),
            'failed': len([r for r in results if isinstance(r, dict) and 'error' in r]),
            'execution_time': execution_time,
            'results': {k: v for k, v in zip(tasks_to_process, results)}
        }
    
    async def _execute_with_hooks(self, task_id: str) -> Dict:
        """
        Execute task with pre/post execution hooks.
        
        Args:
            task_id: Task ID
            
        Returns:
            Execution result
        """
        start_time = time.time()
        
        # Pre-execution hook
        self.currently_running[task_id] = {
            'started_at': start_time,
            'status': 'running'
        }
        
        self.task_manager.update_progress(task_id, 0.0, 'in_progress')
        await self._emit_progress(task_id, 0.0, 'started')
        
        try:
            # Execute task (custom executor or default)
            if self._task_executor:
                result = await self._task_executor(task_id)
            else:
                result = await self.execute_task(task_id)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Post-execution
            self.task_manager.update_progress(task_id, 1.0, 'completed')
            await self._emit_progress(task_id, 1.0, 'completed')
            
            self.execution_history.append({
                'task_id': task_id,
                'started_at': start_time,
                'completed_at': end_time,
                'duration': duration,
                'status': 'completed'
            })
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'duration': duration,
                'result': result
            }
            
        except Exception as e:
            end_time = time.time()
            
            self.task_manager.update_progress(task_id, 0, 'failed')
            await self._emit_progress(task_id, 0, 'failed')
            
            self.execution_history.append({
                'task_id': task_id,
                'started_at': start_time,
                'completed_at': end_time,
                'duration': end_time - start_time,
                'status': 'failed',
                'error': str(e)
            })
            
            return {
                'task_id': task_id,
                'status': 'failed',
                'error': str(e)
            }
    
    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """
        Execute a single task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task execution result
        """
        task = self.task_manager.get(task_id)
        if not task:
            return {'error': 'Task not found'}
        
        # Simulate task execution
        for progress in [0.25, 0.5, 0.75, 1.0]:
            await asyncio.sleep(0.1)
            await self._emit_progress(task_id, progress, 'running')
        
        return {
            'task_id': task_id,
            'name': task['name'],
            'status': 'completed'
        }
    
    async def _emit_progress(self, task_id: str, progress: float, status: str):
        """Emit progress update."""
        if self._progress_callback:
            try:
                await self._progress_callback(task_id, progress, status)
            except Exception as e:
                print(f"Progress callback error: {e}")
    
    async def pause_execution(self):
        """Pause current execution using non-blocking acquire."""
        async with self._state_lock:
            if self._execution_state != ExecutionState.RUNNING:
                return
            
            self._execution_state = ExecutionState.PAUSED
            self._paused_permits_held = 0
        
        # FIX: Use non-blocking acquire to track how many permits we can grab
        if self._semaphore:
            while True:
                try:
                    self._semaphore.acquire_nowait()
                    self._paused_permits_held += 1
                except asyncio.InvalidStateError:
                    # Semaphore is already in a valid state
                    break
                except Exception:
                    break
    
    async def resume_execution(self):
        """Resume paused execution."""
        async with self._state_lock:
            self._execution_state = ExecutionState.RUNNING
        
        # FIX: Release only the permits we actually hold
        if self._semaphore and self._paused_permits_held > 0:
            for _ in range(self._paused_permits_held):
                try:
                    self._semaphore.release()
                except Exception:
                    pass
            self._paused_permits_held = 0
    
    async def cancel_task(self, task_id: str):
        """Cancel a specific task."""
        if task_id in self.currently_running:
            del self.currently_running[task_id]
        
        self.task_manager.update_progress(task_id, 0, 'cancelled')
        await self._emit_progress(task_id, 0, 'cancelled')
    
    def _update_stats(self, results: List[Dict], execution_time: float):
        """Update execution statistics."""
        successful = [r for r in results if isinstance(r, dict) and r.get('status') == 'completed']
        failed = [r for r in results if isinstance(r, dict) and r.get('status') == 'failed']
        
        self.execution_stats['total_executed'] += len(successful)
        self.execution_stats['total_failed'] += len(failed)
        self.execution_stats['total_time'] += execution_time
        
        total = self.execution_stats['total_executed'] + self.execution_stats['total_failed']
        if total > 0:
            self.execution_stats['avg_execution_time'] = (
                self.execution_stats['total_time'] / total
            )
    
    def detect_deadlocks(self) -> List[Dict]:
        """
        Detect potential deadlocks in running tasks.
        
        Returns:
            List of detected deadlocks
        """
        deadlocks = []
        running_tasks = list(self.currently_running.keys())
        
        if len(running_tasks) < 2:
            return deadlocks
        
        # Check for circular waiting
        for i, task1 in enumerate(running_tasks):
            task1_deps = json.loads(
                self.task_manager.get(task1).get('dependencies', '[]') or '[]'
            )
            
            for task2 in running_tasks[i+1:]:
                task2_deps = json.loads(
                    self.task_manager.get(task2).get('dependencies', '[]') or '[]'
                )
                
                # Check if task1 is waiting for task2 and vice versa
                if task1 in task2_deps and task2 in task1_deps:
                    deadlocks.append({
                        'tasks': [task1, task2],
                        'type': 'circular_wait',
                        'description': f'{task1} and {task2} waiting for each other'
                    })
        
        return deadlocks
    
    async def resolve_deadlock(self, deadlock: Dict) -> bool:
        """
        Attempt to resolve a deadlock.
        
        Args:
            deadlock: Deadlock information
            
        Returns:
            True if resolved
        """
        tasks = deadlock.get('tasks', [])
        if len(tasks) < 2:
            return False
        
        # Cancel lower priority task
        task1 = self.task_manager.get(tasks[0])
        task2 = self.task_manager.get(tasks[1])
        
        if task1 and task2:
            if task1.get('priority', 0) < task2.get('priority', 0):
                await self.cancel_task(tasks[0])
            else:
                await self.cancel_task(tasks[1])
            return True
        
        return False
    
    def get_execution_status(self) -> Dict:
        """Get current execution status."""
        return {
            'state': self._execution_state.value,
            'currently_running': list(self.currently_running.keys()),
            'queue_size': len(self.task_queue),
            'stats': self.execution_stats,
            'recent_history': self.execution_history[-10:]
        }
    
    def get_available_parallelism(self) -> int:
        """
        Calculate available parallelism based on ready tasks.
        
        Returns:
            Number of tasks that can run in parallel
        """
        ready_tasks = self._get_ready_tasks()
        return min(len(ready_tasks), self.max_parallel)
    
    def _get_ready_tasks(self) -> List[str]:
        """Get tasks that are ready to run (all dependencies met)."""
        ready = []
        
        while self.task_queue:
            priority, task_id = self.task_queue[0]
            # FIX: Handle NULL dependencies
            task = self.task_manager.get(task_id)
            if not task:
                heappop(self.task_queue)
                continue
                
            deps_str = task.get('dependencies')
            deps = json.loads(deps_str) if deps_str else []
            
            # Check if all dependencies are completed
            all_done = all(
                self.task_manager.get(d).get('status') == 'completed'
                for d in deps
                if self.task_manager.get(d)
            )
            
            if all_done:
                ready.append(task_id)
                heappop(self.task_queue)
            else:
                break
        
        return ready
    
    async def adjust_parallelism(self, load_factor: float = 1.0):
        """
        Dynamically adjust parallelism based on system load.
        
        Args:
            load_factor: Load factor (0.0 to 2.0, where 1.0 is normal)
        """
        new_max = max(
            self.min_parallel,
            min(10, int(self.max_parallel * load_factor))
        )
        
        async with self._state_lock:
            old_max = self.max_parallel
            self.max_parallel = new_max
        
        if new_max != old_max:
            # Reinitialize semaphore with new limit
            if self._semaphore:
                diff = new_max - old_max
                if diff > 0:
                    for _ in range(diff):
                        self._semaphore.release()
                elif diff < 0:
                    for _ in range(-diff):
                        try:
                            self._semaphore.acquire_nowait()
                        except:
                            pass
