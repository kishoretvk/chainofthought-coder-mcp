"""
Task decomposition agent - intelligently breaks down complex tasks into sub-tasks
Enhanced with LLM-powered analysis and smart subtask generation.
FIXED: Removed complexity threshold - tool always attempts decomposition
"""
import re
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from .base_agent import AgentBase


class TaskDecompositionAgent(AgentBase):
    """
    Enhanced task decomposition agent.
    """
    
    TASK_PATTERNS = {
        'code_review': ['review', 'analyze', 'examine', 'audit'],
        'code_generation': ['create', 'implement', 'write', 'build', 'develop'],
        'testing': ['test', 'verify', 'validate', 'check', 'ensure'],
        'refactoring': ['refactor', 'restructure', 'rewrite', 'improve'],
        'documentation': ['document', 'write docs', 'explain', 'describe'],
        'debugging': ['debug', 'fix', 'resolve', 'troubleshoot'],
        'optimization': ['optimize', 'improve', 'enhance', 'performance'],
        'integration': ['integrate', 'connect', 'combine', 'merge'],
        'deployment': ['deploy', 'release', 'publish', 'ship'],
        'research': ['research', 'investigate', 'explore', 'learn']
    }
    
    SUBTASK_TEMPLATES = {
        'general': ['Analyze requirements', 'Plan implementation approach', 'Execute main task', 'Verify results', 'Complete and document'],
        'code_review': ['Review code structure', 'Check security', 'Analyze complexity', 'Verify standards', 'Document findings'],
        'code_generation': ['Design architecture', 'Create implementation', 'Handle errors', 'Add tests', 'Update docs'],
        'testing': ['Design cases', 'Implement tests', 'Run integration', 'Verify coverage', 'Document results'],
        'refactoring': ['Analyze structure', 'Find opportunities', 'Refactor incrementally', 'Verify functionality', 'Update tests'],
        'documentation': ['Gather context', 'Draft structure', 'Write content', 'Review accuracy', 'Publish'],
        'debugging': ['Reproduce issue', 'Analyze cause', 'Strategy fix', 'Implement fix', 'Verify resolution'],
        'optimization': ['Profile performance', 'Identify bottlenecks', 'Optimize', 'Measure improvement', 'Verify correctness'],
        'integration': ['Analyze requirements', 'Setup environment', 'Transform data', 'Test flow', 'Validate'],
        'deployment': ['Prepare package', 'Configure env', 'Execute', 'Verify success', 'Update monitoring'],
        'research': ['Define scope', 'Gather info', 'Analyze', 'Synthesize', 'Document']
    }
    
    def __init__(self, task_manager, llm_provider=None):
        super().__init__("task_decomposer")
        self.task_manager = task_manager
        self.llm_provider = llm_provider
        self._task_cache = {}
    
    async def handle_message(self, message: Dict[str, Any]):
        msg_type = message['content'].get('type')
        
        if msg_type == 'decompose_task':
            task_id = message['content']['task_id']
            session_id = message['content']['session_id']
            auto_deps = message['content'].get('auto_dependencies', True)
            await self.decompose_task(session_id, task_id, auto_dependencies=auto_deps)
            
        elif msg_type == 'decompose_with_llm':
            task_id = message['content']['task_id']
            session_id = message['content']['session_id']
            prompt = message['content'].get('prompt', '')
            await self.decompose_with_llm(session_id, task_id, prompt)
    
    async def decompose_task(self, session_id: str, task_id: str,
                             auto_dependencies: bool = True) -> List[str]:
        """Decompose task - NO threshold, always attempts."""
        task = self.task_manager.get(task_id)
        if not task:
            return []
        
        task_type = self.classify_task(task)
        complexity = self.analyze_complexity(task)
        subtasks = self.generate_smart_subtasks(task, task_type)
        created_subtasks = []
        
        for subtask in subtasks:
            subtask_id = self.task_manager.create_subtask(
                session_id, task_id, subtask['name'],
                subtask.get('description', ''), subtask.get('priority', 0)
            )
            created_subtasks.append(subtask_id)
            
            if auto_dependencies and subtask.get('depends_on'):
                for dep in subtask['depends_on']:
                    if dep in created_subtasks:
                        self.task_manager.add_dependency(subtask_id, dep)
        
        metadata = json.loads(task.get('metadata', '{}') or '{}')
        metadata['decomposed'] = True
        metadata['decomposed_at'] = time.time()
        metadata['task_type'] = task_type
        metadata['complexity_score'] = complexity
        metadata['subtasks'] = created_subtasks
        
        self.task_manager.db.execute(
            "UPDATE tasks SET metadata = ? WHERE task_id = ?",
            (json.dumps(metadata), task_id)
        )
        
        return created_subtasks
    
    async def decompose_with_llm(self, session_id: str, task_id: str,
                                  prompt: str = "") -> List[str]:
        task = self.task_manager.get(task_id)
        if not task:
            return []
        
        default_prompt = f"Decompose: {task['name']} - {task['description']}"
        decomposition_prompt = prompt or default_prompt
        
        if self.llm_provider:
            try:
                response = await self.llm_provider.generate(decomposition_prompt)
                subtasks = self._parse_llm_response(response)
            except Exception:
                subtasks = self.generate_smart_subtasks(task, self.classify_task(task))
        else:
            subtasks = self.generate_smart_subtasks(task, self.classify_task(task))
        
        created_subtasks = []
        for subtask in subtasks:
            subtask_id = self.task_manager.create_subtask(
                session_id, task_id, subtask['name'],
                subtask.get('description', ''), subtask.get('priority', 0)
            )
            created_subtasks.append(subtask_id)
        
        return created_subtasks
    
    def classify_task(self, task: Dict[str, Any]) -> str:
        text = f"{task.get('name', '')} {task.get('description', '')}".lower()
        
        scores = {}
        for task_type, patterns in self.TASK_PATTERNS.items():
            score = sum(1 for pattern in patterns if pattern in text)
            if score > 0:
                scores[task_type] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return 'general'
    
    def analyze_complexity(self, task: Dict[str, Any]) -> float:
        complexity = 0.0
        description = task.get('description', '') or ''
        name = task.get('name', '') or ''
        
        complexity += len(description) / 200.0
        complexity += len(name) / 50.0
        
        step_keywords = ['step', 'phase', 'stage', 'level', 'layer']
        for keyword in step_keywords:
            complexity += description.lower().count(keyword) * 0.5
        
        complex_indicators = ['comprehensive', 'detailed', 'complex', 'entire', 'full']
        for indicator in complex_indicators:
            if indicator in description.lower():
                complexity += 1.0
        
        task_type = self.classify_task(task)
        type_complexity = {
            'code_review': 1.5, 'code_generation': 2.0, 'testing': 1.0,
            'refactoring': 1.8, 'documentation': 0.8, 'debugging': 1.2,
            'optimization': 1.5, 'integration': 2.0, 'deployment': 1.5,
            'research': 1.0, 'general': 1.0
        }
        complexity += type_complexity.get(task_type, 1.0)
        
        return complexity
    
    def generate_smart_subtasks(self, task: Dict[str, Any], 
                                 task_type: str = None) -> List[Dict[str, Any]]:
        """Generate sub-tasks - ALWAYS runs, no threshold."""
        if task_type is None:
            task_type = self.classify_task(task)
        
        template = self.SUBTASK_TEMPLATES.get(task_type, self.SUBTASK_TEMPLATES['general'])
        
        subtasks = []
        for i, subtask_name in enumerate(template):
            name = f"{subtask_name} ({task.get('name', 'Task')})"
            
            subtask = {
                'name': name,
                'description': f"Part of {task.get('name', 'Task')}: {subtask_name.lower()}",
                'priority': max(0, 5 - i),
                'depends_on': []
            }
            subtasks.append(subtask)
        
        for i in range(1, len(subtasks)):
            subtasks[i]['depends_on'] = [i - 1]
        
        return subtasks
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                subtasks = json.loads(json_match.group())
                return subtasks
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return []
    
    def get_recommended_parallelism(self, task_id: str) -> int:
        task = self.task_manager.get(task_id)
        if not task:
            return 1
        
        metadata = json.loads(task.get('metadata', '{}') or '{}')
        subtasks = metadata.get('subtasks', [])
        
        if len(subtasks) <= 2:
            return 1
        elif len(subtasks) <= 5:
            return 2
        elif len(subtasks) <= 10:
            return 3
        else:
            return 4
