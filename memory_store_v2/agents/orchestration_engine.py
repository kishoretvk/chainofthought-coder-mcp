"""
Orchestration Engine - Central coordinator for all agents
Manages task workflow with parallel execution, dependency tracking, and progress monitoring.
FIXED: _flatten_tasks now only executes leaf nodes, not parent containers
"""
import asyncio
import uuid
import json
import time
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

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
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


class OrchestrationEngine:
    """Central orchestration engine for managing task workflows."""
    
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
        
        # Event-based task completion tracking
        self._task_events: Dict[str, asyncio.Event] = {}
        
        # Event system
        self.event_handlers: Dict[WorkflowEvent, List[Callable]] = {}
        self.progress_callbacks: Dict[str, List[Callable]] = {}
        
        # Concurrency control
        self._execution_lock = asyncio.Lock()
        self._status_lock = asyncio.Lock()
    
    def on_event(self, event: WorkflowEvent, handler: Callable):
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    def on_progress(self, task_id: str, callback: Callable):
        if task_id not in self.progress_callbacks:
            self.progress_callbacks[task_id] = []
        self.progress_callbacks[task_id].append(callback)
    
    async def create_workflow(self, session_id: str, name: str, description: str = "", root_task_data: Dict = None) -> str:
        """Create a new workflow with initial task."""
        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"
        task_id = self.task_manager.create_main_task(session_id, name, description)
        
        workflow = {
            'workflow_id': workflow_id,
            'session_id': session_id,
            'root_task_id': task_id,
            'name': name,
            'status': 'pending',
            'created_at': time.time(),
            'config': {
                'max_parallel': self.max_parallel,
                'auto_decompose': True,
            }
        }
        self.workflows[workflow_id] = workflow
        return workflow_id
    
    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Execute a workflow with parallel execution and dependency tracking."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        root_task_id = workflow['root_task_id']
        session_id = workflow['session_id']
        workflow['status'] = 'running'
        workflow['started_at'] = time.time()
        
        try:
            # Auto-mark as planned when decomposing
            if workflow['config'].get('auto_decompose', True):
                await self.decomposition_agent.decompose_task(session_id, root_task_id)
            
            # Mark as planned
            self.task_manager.mark_as_planned(root_task_id, session_id)
            
            # Build dependency graph
            await self.dependency_agent.analyze_dependencies(session_id, root_task_id)
            
            # Execute with parallel execution
            result = await self._execute_with_dependencies(session_id, root_task_id)
            
            # Auto-mark as executed after completion
            self.task_manager.mark_as_executed(root_task_id, session_id)
            
            workflow['status'] = 'completed'
            workflow['completed_at'] = time.time()
            workflow['result'] = result
            return result
            
        except Exception as e:
            workflow['status'] = 'failed'
            workflow['failed_at'] = time.time()
            workflow['error'] = str(e)
            raise
    
    async def _execute_with_dependencies(self, session_id: str, root_task_id: str) -> Dict[str, Any]:
        """Execute tasks respecting dependencies using parallel execution."""
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return {'status': 'error', 'message': 'Task tree not found'}
        
        # FIX: Only get leaf tasks (actual work units), not parent containers
        all_tasks = self._flatten_tasks(task_tree, include_parent=False)
        
        for task in all_tasks:
            task_id = task['task_id']
            if task_id not in self._task_events:
                self._task_events[task_id] = asyncio.Event()
        
        dependency_map = self._build_dependency_map(all_tasks)
        completed = set()
        failed = set()
        
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        async def execute_task(task_id: str) -> Any:
            async with semaphore:
                deps = dependency_map.get(task_id, [])
                for dep in deps:
                    if dep not in completed:
                        await self._wait_for_task(dep)
                
                async with self._status_lock:
                    self.task_status[task_id] = TaskStatus.IN_PROGRESS
                
                try:
                    result = await self._run_task(task_id)
                    async with self._status_lock:
                        self.task_status[task_id] = TaskStatus.COMPLETED
                    completed.add(task_id)
                    if task_id in self._task_events:
                        self._task_events[task_id].set()
                    self.task_manager.update_progress(task_id, 1.0, 'completed')
                    return result
                except Exception as e:
                    async with self._status_lock:
                        self.task_status[task_id] = TaskStatus.FAILED
                    failed.add(task_id)
                    if task_id in self._task_events:
                        self._task_events[task_id].set()
                    raise
        
        async def _wait_for_task(task_id: str):
            max_wait = 300
            if task_id not in self._task_events:
                return
            event = self._task_events[task_id]
            try:
                await asyncio.wait_for(event.wait(), timeout=max_wait)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Task {task_id} did not complete in time")
            if task_id in failed:
                raise RuntimeError(f"Dependency task {task_id} failed")
        
        # FIXED: Only schedule leaf tasks for execution
        leaf_tasks = [t for t in all_tasks if t.get('is_leaf', True)]
        tasks = [execute_task(t['task_id']) for t in leaf_tasks]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return {
                'status': 'completed',
                'total_tasks': len(leaf_tasks),
                'completed': len(completed),
                'failed': len(failed),
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'completed': len(completed),
                'failed': len(failed)
            }
    
    async def _run_task(self, task_id: str) -> Dict[str, Any]:
        """Run a single task."""
        task = self.task_manager.get(task_id)
        if not task:
            return {'error': 'Task not found'}
        
        for progress in [0.25, 0.5, 0.75, 1.0]:
            await asyncio.sleep(0.1)
            self.task_manager.update_progress(task_id, progress, 'in_progress')
        
        return {
            'task_id': task_id,
            'name': task['name'],
            'status': 'completed',
            'completed_at': time.time()
        }
    
    def _flatten_tasks(self, task_tree: Dict, result: List[Dict] = None, include_parent: bool = False) -> List[Dict]:
        """
        Flatten task tree to list of executable tasks.
        
        By default, only leaf nodes (actual work tasks) are included.
        Parent tasks are containers for tracking - they shouldn't be executed directly.
        
        Args:
            task_tree: The task tree to flatten
            result: Accumulator list (internal use)
            include_parent: Whether to include parent tasks (default False)
            
        Returns:
            List of executable tasks
        """
        if result is None:
            result = []
        
        subtasks = task_tree.get('subtasks', [])
        has_subtasks = len(subtasks) > 0
        
        # Only add parent if include_parent=True OR if it has no subtasks (leaf node)
        if include_parent or not has_subtasks:
            result.append({
                'task_id': task_tree['task_id'],
                'name': task_tree['name'],
                'status': task_tree['status'],
                'priority': task_tree.get('priority', 0),
                'is_leaf': not has_subtasks
            })
        
        # Recursively process subtasks
        for subtask in subtasks:
            self._flatten_tasks(subtask, result, include_parent)
        
        return result
    
    def _build_dependency_map(self, tasks: List[Dict]) -> Dict[str, List[str]]:
        dependency_map = {}
        task_ids = {t['task_id'] for t in tasks}
        
        for task in tasks:
            task_id = task['task_id']
            db_task = self.task_manager.get(task_id)
            deps_str = db_task.get('dependencies')
            deps = json.loads(deps_str) if deps_str else []
            valid_deps = [d for d in deps if d in task_ids]
            dependency_map[task_id] = valid_deps
        
        return dependency_map
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        if workflow_id not in self.workflows:
            return None
        
        workflow = self.workflows[workflow_id]
        root_task_id = workflow['root_task_id']
        task_tree = self.task_manager.get_tree(workflow['session_id'], root_task_id)
        
        return {
            'workflow': workflow,
            'task_tree': task_tree,
        }
    
    def get_dependency_graph(self, session_id: str, root_task_id: str = None) -> Dict:
        return self.dependency_agent.get_dependency_graph(session_id, root_task_id)
    
    async def cancel_workflow(self, workflow_id: str):
        if workflow_id not in self.workflows:
            return
        
        workflow = self.workflows[workflow_id]
        workflow['status'] = 'cancelled'
        workflow['cancelled_at'] = time.time()
        
        for task_id, event in self._task_events.items():
            if not event.is_set():
                event.set()
        
        await self._emit_event(WorkflowEvent.WORKFLOW_FAILED, {
            'workflow_id': workflow_id,
            'error': 'Workflow cancelled'
        })
    
    async def _emit_event(self, event: WorkflowEvent, data: Dict):
        handlers = self.event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                print(f"Event handler error: {e}")
