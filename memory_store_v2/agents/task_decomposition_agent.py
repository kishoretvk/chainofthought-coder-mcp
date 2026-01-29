"""
Task decomposition agent - intelligently breaks down complex tasks into sub-tasks
Enhanced with LLM-powered analysis and smart subtask generation.
"""
import re
import json
import uuid
from typing import Dict, Any, List, Optional
from .base_agent import AgentBase


class TaskDecompositionAgent(AgentBase):
    """
    Enhanced task decomposition agent.
    
    Features:
    - LLM-powered complexity analysis
    - Smart subtask generation based on task patterns
    - Automatic dependency inference
    - Task type classification
    """
    
    # Task type patterns for classification
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
    
    # Subtask templates based on task type
    SUBTASK_TEMPLATES = {
        'code_review': [
            'Review code structure and architecture',
            'Check for security vulnerabilities',
            'Analyze code complexity and performance',
            'Verify adherence to coding standards',
            'Document findings and recommendations'
        ],
        'code_generation': [
            'Design solution architecture',
            'Create core implementation',
            'Implement error handling',
            'Add unit tests',
            'Update documentation'
        ],
        'testing': [
            'Design test cases',
            'Implement unit tests',
            'Run integration tests',
            'Verify test coverage',
            'Document test results'
        ],
        'refactoring': [
            'Analyze current code structure',
            'Identify refactoring opportunities',
            'Perform incremental refactoring',
            'Verify functionality after changes',
            'Update affected tests'
        ],
        'documentation': [
            'Gather requirements and context',
            'Draft documentation structure',
            'Write detailed content',
            'Review and validate accuracy',
            'Format and publish documentation'
        ],
        'debugging': [
            'Reproduce the issue',
            'Analyze root cause',
            'Identify fix strategy',
            'Implement fix',
            'Verify resolution'
        ],
        'optimization': [
            'Profile current performance',
            'Identify bottlenecks',
            'Implement optimizations',
            'Measure performance improvement',
            'Verify correctness'
        ],
        'integration': [
            'Analyze integration requirements',
            'Set up integration environment',
            'Implement data transformation',
            'Test end-to-end flow',
            'Monitor and validate'
        ],
        'deployment': [
            'Prepare deployment package',
            'Configure deployment environment',
            'Execute deployment',
            'Verify deployment success',
            'Update monitoring'
        ],
        'research': [
            'Define research scope',
            'Gather relevant information',
            'Analyze findings',
            'Synthesize recommendations',
            'Document results'
        ]
    }
    
    def __init__(self, task_manager, llm_provider=None):
        super().__init__("task_decomposer")
        self.task_manager = task_manager
        self.llm_provider = llm_provider  # Optional LLM for advanced decomposition
        self.complexity_threshold = 3.0
        
        # Task classification cache
        self._task_cache = {}
    
    async def handle_message(self, message: Dict[str, Any]):
        """Handle incoming messages."""
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
        """
        Analyze and decompose complex tasks into sub-tasks.
        
        Args:
            session_id: Session ID
            task_id: Task ID to decompose
            auto_dependencies: Whether to automatically infer dependencies
            
        Returns:
            List of created subtask IDs
        """
        task = self.task_manager.get(task_id)
        if not task:
            return []
        
        complexity = self.analyze_complexity(task)
        if complexity < self.complexity_threshold:
            return []
        
        # Classify task type
        task_type = self.classify_task(task)
        
        # Generate subtasks
        subtasks = self.generate_smart_subtasks(task, task_type)
        created_subtasks = []
        
        for subtask in subtasks:
            subtask_id = self.task_manager.create_subtask(
                session_id,
                task_id,
                subtask['name'],
                subtask.get('description', ''),
                subtask.get('priority', 0)
            )
            subtask['_created_id'] = subtask_id
            created_subtasks.append(subtask_id)
            
            # Add explicit dependencies
            if auto_dependencies and subtask.get('depends_on'):
                for dep in subtask['depends_on']:
                    if dep in created_subtasks:
                        self.task_manager.add_dependency(subtask_id, dep)
        
        # Update parent task metadata
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
        """
        Use LLM for advanced task decomposition.
        
        Args:
            session_id: Session ID
            task_id: Task ID
            prompt: Optional custom prompt for decomposition
            
        Returns:
            List of created subtask IDs
        """
        task = self.task_manager.get(task_id)
        if not task:
            return []
        
        # Build decomposition prompt
        default_prompt = f"""
        Decompose the following task into logical sub-tasks:
        
        Task: {task['name']}
        Description: {task['description']}
        
        Please provide a JSON array of subtasks with:
        - name: Subtask name
        - description: Detailed description
        - priority: Priority (0-10)
        - depends_on: Array of dependent subtask names
        
        Return only valid JSON.
        """
        
        decomposition_prompt = prompt or default_prompt
        
        # Call LLM if available
        if self.llm_provider:
            try:
                response = await self.llm_provider.generate(decomposition_prompt)
                subtasks = self._parse_llm_response(response)
            except Exception as e:
                print(f"LLM decomposition failed: {e}")
                subtasks = self.generate_smart_subtasks(task, self.classify_task(task))
        else:
            subtasks = self.generate_smart_subtasks(task, self.classify_task(task))
        
        # Create subtasks
        created_subtasks = []
        for subtask in subtasks:
            subtask_id = self.task_manager.create_subtask(
                session_id,
                task_id,
                subtask['name'],
                subtask.get('description', ''),
                subtask.get('priority', 0)
            )
            created_subtasks.append(subtask_id)
        
        return created_subtasks
    
    def classify_task(self, task: Dict[str, Any]) -> str:
        """
        Classify task type based on keywords.
        
        Args:
            task: Task dictionary
            
        Returns:
            Task type string
        """
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
        """
        Estimate task complexity using enhanced heuristics.
        
        Args:
            task: Task dictionary
            
        Returns:
            Complexity score (higher = more complex)
        """
        complexity = 0.0
        description = task.get('description', '') or ''
        name = task.get('name', '') or ''
        
        # Base complexity from description length
        complexity += len(description) / 200.0
        complexity += len(name) / 50.0
        
        # Multi-step indicators
        step_keywords = ['step', 'phase', 'stage', 'level', 'layer']
        for keyword in step_keywords:
            complexity += description.lower().count(keyword) * 0.5
        
        # Complexity indicators
        complex_indicators = ['comprehensive', 'detailed', 'complex', 'entire', 'full']
        for indicator in complex_indicators:
            if indicator in description.lower():
                complexity += 1.0
        
        # Task type impact
        task_type = self.classify_task(task)
        type_complexity = {
            'code_review': 1.5,
            'code_generation': 2.0,
            'testing': 1.0,
            'refactoring': 1.8,
            'documentation': 0.8,
            'debugging': 1.2,
            'optimization': 1.5,
            'integration': 2.0,
            'deployment': 1.5,
            'research': 1.0,
            'general': 1.0
        }
        complexity += type_complexity.get(task_type, 1.0)
        
        return complexity
    
    def generate_smart_subtasks(self, task: Dict[str, Any], 
                                 task_type: str = None) -> List[Dict[str, Any]]:
        """
        Generate intelligent sub-tasks based on task type.
        
        Args:
            task: Parent task
            task_type: Optional task type override
            
        Returns:
            List of subtask dictionaries
        """
        if task_type is None:
            task_type = self.classify_task(task)
        
        # Get template for task type
        template = self.SUBTASK_TEMPLATES.get(task_type, self.SUBTASK_TEMPLATES['general'])
        
        subtasks = []
        task_name = task.get('name', 'Task')
        
        for i, subtask_name in enumerate(template):
            # Customize subtask name with parent task context
            name = f"{subtask_name} ({task_name})"
            
            subtask = {
                'name': name,
                'description': f"Part of {task_name}: {subtask_name.lower()}",
                'priority': max(0, 5 - i),  # Higher priority for earlier tasks
                'depends_on': [f"Subtask {j+1} for {task_name}" for j in range(i)] if i > 0 else []
            }
            
            subtasks.append(subtask)
        
        return subtasks
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into subtask list."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                subtasks = json.loads(json_match.group())
                return subtasks
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return []
    
    def get_recommended_parallelism(self, task_id: str) -> int:
        """
        Get recommended maximum parallel tasks for a decomposed task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Recommended max parallel tasks
        """
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


# Import time for timestamp
import time
