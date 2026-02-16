"""
Orchestration Engine - Central coordinator for all agents
Manages task workflow with parallel execution, dependency tracking, and progress monitoring.
"""
import asyncio
import uuid
import json
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum

from .base_agent import AgentBase
from .task_decomposition_agent import TaskDecompositionAgent
from .dependency_mapper_agent import DependencyMapperAgent
from .parallel_execution_agent import ParallelExecutionAgent
from .integration_agent import IntegrationAgent


class TaskStatus(Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowEvent(Enum):
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    PROGRESS_UPDATED = "progress_updated"
    DEPENDENCY_RESOLVED = "dependency_resolved"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


class OrchestrationEngine:
    """
    Central orchestration engine for managing task workflows.
    Provides:
    - Parallel execution with dependency tracking
    - Real-time progress monitoring
    - Event-driven architecture
    - Workflow visualization
    """
    
    def __init__(self, task_manager, max_parallel: int = 4):
        self.task_manager = task_manager
        self.max_parallel = max_parallel
        
        # Initialize agents
        self.decomposition_agent = TaskDecompositionAgent(task_manager)
        self.dependency_agent = DependencyMapperAgent(task_manager)
        self.execution_agent = ParallelExecutionAgent(task_manager, max_parallel)
        self.integration_agent = IntegrationAgent(task_manager)
        
        # Workflow state
        self.workflows: Dict[str, Dict] = {}
        self.task_status: Dict[str, TaskStatus] = {}
        self.task_results: Dict[str, Any] = {}
        
        # FIX: Event-based task completion tracking
        self._task_events: Dict[str, asyncio.Event] = {}
        
        # Event system
        self.event_handlers: Dict[WorkflowEvent, List[Callable]] = {}
        self.progress_callbacks: Dict[str, List[Callable]] = {}
        
        # Execution tracking
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.execution_history: List[Dict] = []
        
        # Concurrency control
        self._execution_lock = asyncio.Lock()
        self._status_lock = asyncio.Lock()
    
    # ==================== Event System ====================
    
    def on_event(self, event: WorkflowEvent, handler: Callable):
        """Register event handler."""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    def on_progress(self, task_id: str, callback: Callable):
        """Register progress callback for a specific task."""
        if task_id not in self.progress_callbacks:
            self.progress_callbacks[task_id] = []
        self.progress_callbacks[task_id].append(callback)
    
    async def _emit_event(self, event: WorkflowEvent, data: Dict):
        """Emit event to all handlers."""
        handlers = self.event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    async def _emit_progress(self, task_id: str, progress: float, status: TaskStatus):
        """Emit progress update."""
        callbacks = self.progress_callbacks.get(task_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task_id, progress, status)
                else:
                    callback(task_id, progress, status)
            except Exception as e:
                print(f"Progress callback error: {e}")
    
    # ==================== Workflow Management ====================
    
    async def create_workflow(self, session_id: str, name: str, 
                               description: str = "", 
                               root_task_data: Dict = None) -> str:
        """
        Create a new workflow with initial task.
        
        Args:
            session_id: Session ID
            name: Workflow name
            description: Description
            root_task_data: Optional pre-defined task data
            
        Returns:
            Workflow ID
        """
        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"
        
        # Create root task
        task_id = self.task_manager.create_main_task(
            session_id, name, description
        )
        
        workflow = {
            'workflow_id': workflow_id,
            'session_id': session_id,
            'root_task_id': task_id,
            'name': name,
            'status': 'pending',
            'created_at': time.time(),
            'updated_at': time.time(),
            'config': {
                'max_parallel': self.max_parallel,
                'auto_decompose': True,
                'fail_fast': False
            }
        }
        
        self.workflows[workflow_id] = workflow
        
        await self._emit_event(WorkflowEvent.TASK_CREATED, {
            'workflow_id': workflow_id,
            'task_id': task_id,
            'parent_id': None,
            'task_data': root_task_data
        })
        
        return workflow_id
    
    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Execute a workflow with parallel execution and dependency tracking.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Execution result
        """
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        root_task_id = workflow['root_task_id']
        session_id = workflow['session_id']
        
        workflow['status'] = 'running'
        workflow['started_at'] = time.time()
        
        await self._emit_event(WorkflowEvent.WORKFLOW_STARTED, {
            'workflow_id': workflow_id,
            'root_task_id': root_task_id
        })
        
        try:
            # Step 1: Decompose tasks
            if workflow['config'].get('auto_decompose', True):
                await self._decompose_all_tasks(session_id, root_task_id)
            
            # Step 2: Build dependency graph
            await self.dependency_agent.analyze_dependencies(session_id, root_task_id)
            
            # Step 3: Execute with parallel execution
            result = await self._execute_with_dependencies(session_id, root_task_id)
            
            workflow['status'] = 'completed'
            workflow['completed_at'] = time.time()
            workflow['result'] = result
            
            await self._emit_event(WorkflowEvent.WORKFLOW_COMPLETED, {
                'workflow_id': workflow_id,
                'result': result
            })
            
            return result
            
        except Exception as e:
            workflow['status'] = 'failed'
            workflow['failed_at'] = time.time()
            workflow['error'] = str(e)
            
            await self._emit_event(WorkflowEvent.WORKFLOW_FAILED, {
                'workflow_id': workflow_id,
                'error': str(e)
            })
            
            raise
    
    async def _decompose_all_tasks(self, session_id: str, root_task_id: str):
        """Recursively decompose all complex tasks."""
        task = self.task_manager.get(root_task_id)
        if not task:
            return
        
        # Decompose this task
        await self.decomposition_agent.decompose_task(session_id, root_task_id)
        
        # Get subtasks and decompose them
        subtasks = self.task_manager.get_subtasks(root_task_id)
        for subtask in subtasks:
            await self._decompose_all_tasks(session_id, subtask['task_id'])
    
    async def _execute_with_dependencies(self, session_id: str, 
                                         root_task_id: str) -> Dict[str, Any]:
        """
        Execute tasks respecting dependencies using parallel execution.
        
        Args:
            session_id: Session ID
            root_task_id: Root task ID
            
        Returns:
            Execution result
        """
        # Get task tree
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return {'status': 'error', 'message': 'Task tree not found'}
        
        # Get all tasks and their dependencies
        all_tasks = self._flatten_tasks(task_tree)
        
        # Initialize task events for signaling
        for task in all_tasks:
            task_id = task['task_id']
            if task_id not in self._task_events:
                self._task_events[task_id] = asyncio.Event()
        
        # Build dependency map
        dependency_map = self._build_dependency_map(all_tasks)
        
        # Track execution state
        completed = set()
        failed = set()
        results = {}
        
        # Semaphore for parallel execution control
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        async def execute_task(task_id: str) -> Any:
            """Execute a single task with its dependencies."""
            async with semaphore:
                # Wait for dependencies using events instead of polling
                deps = dependency_map.get(task_id, [])
                for dep in deps:
                    if dep not in completed:
                        await wait_for_task(dep)
                
                # Update status to in_progress
                async with self._status_lock:
                    self.task_status[task_id] = TaskStatus.IN_PROGRESS
                    self.task_results[task_id] = {'status': 'running'}
                
                await self._emit_event(WorkflowEvent.TASK_STARTED, {
                    'task_id': task_id,
                    'dependencies_met': len([d for d in deps if d in completed])
                })
                
                try:
                    # Execute the task (placeholder - integrate with actual execution)
                    result = await self._run_task(task_id)
                    
                    async with self._status_lock:
                        self.task_status[task_id] = TaskStatus.COMPLETED
                        self.task_results[task_id] = result
                        completed.add(task_id)
                    
                    # FIX: Signal task completion
                    if task_id in self._task_events:
                        self._task_events[task_id].set()
                    
                    await self._emit_event(WorkflowEvent.TASK_COMPLETED, {
                        'task_id': task_id,
                        'result': result
                    })
                    
                    # Update progress in task manager
                    self.task_manager.update_progress(task_id, 1.0, 'completed')
                    
                    await self._emit_progress(task_id, 1.0, TaskStatus.COMPLETED)
                    
                    return result
                    
                except Exception as e:
                    async with self._status_lock:
                        self.task_status[task_id] = TaskStatus.FAILED
                        self.task_results[task_id] = {'error': str(e)}
                        failed.add(task_id)
                    
                    # FIX: Signal task failure
                    if task_id in self._task_events:
                        self._task_events[task_id].set()
                    
                    await self._emit_event(WorkflowEvent.TASK_FAILED, {
                        'task_id': task_id,
                        'error': str(e)
                    })
                    
                    raise
        
        async def wait_for_task(task_id: str):
            """Wait for a task to complete using events (no polling)."""
            max_wait = 300  # 5 minutes timeout
            
            if task_id not in self._task_events:
                # Task event doesn't exist - might already be completed
                return
            
            event = self._task_events[task_id]
            try:
                await asyncio.wait_for(event.wait(), timeout=max_wait)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Task {task_id} did not complete in time")
            
            if task_id in failed:
                raise RuntimeError(f"Dependency task {task_id} failed")
        
        # Execute all tasks in parallel respecting dependencies
        tasks = [execute_task(t['task_id']) for t in all_tasks]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return {
                'status': 'completed',
                'total_tasks': len(all_tasks),
                'completed': len(completed),
                'failed': len(failed),
                'results': {t['task_id']: r for t, r in zip(all_tasks, results)}
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'completed': len(completed),
                'failed': len(failed)
            }
    
    async def _run_task(self, task_id: str) -> Dict[str, Any]:
        """
        Run a single task.
        This is a placeholder - in production, integrate with actual task execution.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task result
        """
        task = self.task_manager.get(task_id)
        if not task:
            return {'error': 'Task not found'}
        
        # Simulate task execution with progress updates
        for progress in [0.25, 0.5, 0.75, 1.0]:
            await asyncio.sleep(0.1)
            self.task_manager.update_progress(task_id, progress, 'in_progress')
            await self._emit_progress(task_id, progress, TaskStatus.IN_PROGRESS)
        
        return {
            'task_id': task_id,
            'name': task['name'],
            'status': 'completed',
            'completed_at': time.time()
        }
    
    # ==================== Utility Methods ====================
    
    def _flatten_tasks(self, task_tree: Dict, result: List[Dict] = None) -> List[Dict]:
        """Flatten task tree into list."""
        if result is None:
            result = []
        
        result.append({
            'task_id': task_tree['task_id'],
            'name': task_tree['name'],
            'status': task_tree['status'],
            'priority': task_tree.get('priority', 0)
        })
        
        for subtask in task_tree.get('subtasks', []):
            self._flatten_tasks(subtask, result)
        
        return result
    
    def _build_dependency_map(self, tasks: List[Dict]) -> Dict[str, List[str]]:
        """Build dependency map from tasks."""
        dependency_map = {}
        task_ids = {t['task_id'] for t in tasks}
        
        for task in tasks:
            task_id = task['task_id']
            db_task = self.task_manager.get(task_id)
            # FIX: Handle NULL dependencies gracefully
            deps_str = db_task.get('dependencies')
            deps = json.loads(deps_str) if deps_str else []
            
            # Filter to only tasks in our workflow
            valid_deps = [d for d in deps if d in task_ids]
            dependency_map[task_id] = valid_deps
        
        return dependency_map
    
    # ==================== Progress & Status ====================
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get current workflow status."""
        if workflow_id not in self.workflows:
            return None
        
        workflow = self.workflows[workflow_id]
        root_task_id = workflow['root_task_id']
        
        # Get task tree with current status
        task_tree = self.task_manager.get_tree(workflow['session_id'], root_task_id)
        
        return {
            'workflow': workflow,
            'task_tree': task_tree,
            'active_tasks': list(self.active_tasks.keys()),
            'execution_history': self.execution_history[-100:]  # Last 100 events
        }
    
    def get_dependency_graph(self, session_id: str, root_task_id: str = None) -> Dict:
        """Get dependency graph for visualization."""
        return self.dependency_agent.get_dependency_graph(session_id, root_task_id)
    
    def get_parallel_ready_tasks(self, session_id: str, root_task_id: str) -> List[Dict]:
        """Get tasks that are ready for parallel execution."""
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return []
        
        all_tasks = self._flatten_tasks(task_tree)
        dependency_map = self._build_dependency_map(all_tasks)
        
        completed = set()
        for task in all_tasks:
            if self.task_status.get(task['task_id']) == TaskStatus.COMPLETED:
                completed.add(task['task_id'])
        
        ready_tasks = []
        for task in all_tasks:
            task_id = task['task_id']
            deps = dependency_map.get(task_id, [])
            
            # Task is ready if all dependencies are completed
            if all(d in completed for d in deps):
                if self.task_status.get(task_id) not in [TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS]:
                    ready_tasks.append(task)
        
        # Sort by priority (higher priority first)
        ready_tasks.sort(key=lambda t: t.get('priority', 0), reverse=True)
        
        return ready_tasks
    
    # ==================== Lifecycle ====================
    
    async def cancel_workflow(self, workflow_id: str):
        """Cancel a running workflow."""
        if workflow_id not in self.workflows:
            return
        
        workflow = self.workflows[workflow_id]
        workflow['status'] = 'cancelled'
        workflow['cancelled_at'] = time.time()
        
        # Cancel active tasks
        for task_id, task in list(self.active_tasks.items()):
            if not task.done():
                task.cancel()
                self.task_status[task_id] = TaskStatus.CANCELLED
                self.task_manager.update_progress(task_id, 0, 'cancelled')
                
                # Signal cancelled tasks
                if task_id in self._task_events:
                    self._task_events[task_id].set()
        
        await self._emit_event(WorkflowEvent.WORKFLOW_FAILED, {
            'workflow_id': workflow_id,
            'error': 'Workflow cancelled'
        })
