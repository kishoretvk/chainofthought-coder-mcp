"""
Dependency mapper agent - analyzes and manages task dependencies
Enhanced with smart inference, cycle detection/resolution, and visualization support.
"""
import json
import uuid
from typing import Dict, Any, List, Set, Optional, Tuple
from collections import deque
from .base_agent import AgentBase

try:
    import networkx as nx
    from networkx import DiGraph, Graph
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not installed. Using fallback implementation.")


class DependencyMapperAgent(AgentBase):
    """Enhanced dependency mapper agent."""
    
    DEPENDENCY_PATTERNS = {
        ('testing', 'code_generation'): 'Tests should run after code is generated',
        ('testing', 'refactoring'): 'Tests should verify refactoring',
        ('documentation', 'code_generation'): 'Docs should describe implementation',
        ('debugging', 'testing'): 'Debug issues found in tests',
        ('integration', 'code_generation'): 'Integration after components ready',
        ('integration', 'testing'): 'Integration tests after integration',
        ('deployment', 'testing'): 'Deploy after tests pass',
        ('deployment', 'documentation'): 'Deploy with updated docs',
        ('refactoring', 'testing'): 'Tests validate refactoring',
        ('optimization', 'testing'): 'Tests verify optimizations',
        ('code_review', 'code_generation'): 'Review before finalizing',
        ('documentation', 'debugging'): 'Docs may need updates for fixes'
    }
    
    def __init__(self, task_manager):
        super().__init__("dependency_mapper")
        self.task_manager = task_manager
        
        if HAS_NETWORKX:
            self.dependency_graph = DiGraph()
            self.resource_graph = Graph()
        else:
            self.dependency_graph = {}
            self.resource_graph = {}
        
        self.cycle_resolvers = [
            self._resolve_cycle_by_priority,
            self._resolve_cycle_by_topological_insert,
            self._resolve_cycle_by_merge
        ]
        
        self._dependency_cache = {}
    
    async def handle_message(self, message: Dict[str, Any]):
        msg_type = message['content'].get('type')
        
        if msg_type == 'analyze_dependencies':
            session_id = message['content']['session_id']
            root_task_id = message['content'].get('root_task_id')
            auto_infer = message['content'].get('auto_infer', True)
            await self.analyze_dependencies(session_id, root_task_id, auto_infer)
            
        elif msg_type == 'add_dependency':
            task_id = message['content']['task_id']
            depends_on = message['content']['depends_on']
            self.add_explicit_dependency(task_id, depends_on)
            
        elif msg_type == 'remove_dependency':
            task_id = message['content']['task_id']
            depends_on = message['content']['depends_on']
            self.remove_dependency(task_id, depends_on)
            
        elif msg_type == 'check_circular':
            session_id = message['content']['session_id']
            root_task_id = message['content'].get('root_task_id')
            cycles = self.detect_circular_dependencies(session_id, root_task_id)
            return cycles
    
    async def analyze_dependencies(self, session_id: str, root_task_id: str = None,
                                    auto_infer: bool = True) -> Dict:
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return {'status': 'error', 'message': 'Task tree not found'}
        
        if HAS_NETWORKX:
            self.dependency_graph.clear()
        else:
            self.dependency_graph = {}
        
        self._build_graph_from_tree(task_tree)
        
        if auto_infer:
            inferred = self._infer_implicit_dependencies(task_tree)
            for dep in inferred:
                task_id, depends_on = dep
                self.add_explicit_dependency(task_id, depends_on)
        
        cycles = self.detect_circular_dependencies(session_id, root_task_id)
        if cycles:
            resolved = self._resolve_cycles(cycles)
        
        execution_order = self.get_execution_order()
        critical_path = self.get_critical_path()
        
        result = {
            'status': 'success',
            'task_count': len(self.dependency_graph.nodes) if HAS_NETWORKX else len(self.dependency_graph),
            'execution_order': execution_order,
            'critical_path': critical_path,
            'cycles': cycles,
            'parallelizable_groups': self.get_parallelizable_groups()
        }
        
        if root_task_id:
            metadata = json.loads(self.task_manager.get(root_task_id).get('metadata', '{}') or '{}')
            metadata['dependency_analysis'] = result
            self.task_manager.db.execute(
                "UPDATE tasks SET metadata = ? WHERE task_id = ?",
                (json.dumps(metadata), root_task_id)
            )
        
        return result
    
    def add_explicit_dependency(self, task_id: str, depends_on: str) -> bool:
        if task_id == depends_on:
            return False
        return self.task_manager.add_dependency(task_id, depends_on)
    
    def remove_dependency(self, task_id: str, depends_on: str):
        task = self.task_manager.get(task_id)
        if not task:
            return
        
        deps = json.loads(task.get('dependencies', '[]') or '[]')
        if depends_on in deps:
            deps.remove(depends_on)
            self.task_manager.db.execute(
                "UPDATE tasks SET dependencies = ? WHERE task_id = ?",
                (json.dumps(deps), task_id)
            )
    
    def _build_graph_from_tree(self, task_tree: Dict[str, Any]):
        """Recursively build dependency graph from task tree."""
        task_id = task_tree['task_id']
        
        if HAS_NETWORKX:
            self.dependency_graph.add_node(task_id)
        else:
            if task_id not in self.dependency_graph:
                self.dependency_graph[task_id] = {'incoming': set(), 'outgoing': set()}
        
        # FIX: get_tree already returns dependencies as parsed list, not string
        deps_val = task_tree.get('dependencies')
        if deps_val is None:
            dependencies = []
        elif isinstance(deps_val, list):
            dependencies = deps_val
        else:
            dependencies = json.loads(deps_val) if deps_val else []
        
        for dep in dependencies:
            if HAS_NETWORKX:
                self.dependency_graph.add_edge(dep, task_id)
            else:
                self.dependency_graph[task_id]['incoming'].add(dep)
                if dep not in self.dependency_graph:
                    self.dependency_graph[dep] = {'incoming': set(), 'outgoing': set()}
                self.dependency_graph[dep]['outgoing'].add(task_id)
        
        # Add parent-child dependencies (parent depends on children)
        for subtask in task_tree.get('subtasks', []):
            if HAS_NETWORKX:
                self.dependency_graph.add_edge(subtask['task_id'], task_id)
            else:
                self.dependency_graph[task_id]['incoming'].add(subtask['task_id'])
                if subtask['task_id'] not in self.dependency_graph:
                    self.dependency_graph[subtask['task_id']] = {'incoming': set(), 'outgoing': set()}
                self.dependency_graph[subtask['task_id']]['outgoing'].add(task_id)
            
            self._build_graph_from_tree(subtask)
    
    def _infer_implicit_dependencies(self, task_tree: Dict[str, Any]) -> List[Tuple[str, str]]:
        from .task_decomposition_agent import TaskDecompositionAgent
        classifier = TaskDecompositionAgent(self.task_manager)
        
        inferred = []
        
        def process_task(task, siblings):
            task_id = task['task_id']
            task_type = classifier.classify_task(task)
            
            for sibling in siblings:
                if sibling['task_id'] == task_id:
                    continue
                
                sibling_type = classifier.classify_task(sibling)
                pattern_key = (task_type, sibling_type)
                
                if pattern_key in self.DEPENDENCY_PATTERNS:
                    existing_deps = task.get('dependencies', [])
                    if isinstance(existing_deps, str):
                        existing_deps = json.loads(existing_deps) if existing_deps else []
                    if sibling['task_id'] not in existing_deps:
                        inferred.append((task_id, sibling['task_id']))
                
                reverse_key = (sibling_type, task_type)
                if reverse_key in self.DEPENDENCY_PATTERNS:
                    sibling_deps = sibling.get('dependencies', [])
                    if isinstance(sibling_deps, str):
                        sibling_deps = json.loads(sibling_deps) if sibling_deps else []
                    if task_id not in sibling_deps:
                        inferred.append((sibling['task_id'], task_id))
            
            for subtask in task.get('subtasks', []):
                process_task(subtask, task.get('subtasks', []))
        
        if 'main_tasks' in task_tree:
            for main_task in task_tree['main_tasks']:
                process_task(main_task, task_tree['main_tasks'])
        
        return inferred
    
    def detect_circular_dependencies(self, session_id: str, 
                                      root_task_id: str = None) -> List[List[str]]:
        if not HAS_NETWORKX:
            return self._detect_cycles_fallback()
        
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return []
        
        self._build_graph_from_tree(task_tree)
        
        try:
            cycles = list(nx.simple_cycles(self.dependency_graph))
            return [list(c) for c in cycles]
        except nx.NetworkXUnfeasible:
            return self._find_all_cycles()
        except nx.NetworkXNoCycle:
            return []
    
    def _find_all_cycles(self) -> List[List[str]]:
        if not HAS_NETWORKX:
            return self._detect_cycles_fallback()
        
        cycles = []
        visited = set()
        
        for node in self.dependency_graph.nodes():
            if node in visited:
                continue
            
            path = []
            stack = [(node, iter(self.dependency_graph.successors(node)))]
            
            while stack:
                current, neighbors = stack[-1]
                
                if current not in visited:
                    visited.add(current)
                    path.append(current)
                
                try:
                    next_neighbor = next(neighbors)
                    if next_neighbor in path:
                        cycle_start = path.index(next_neighbor)
                        cycles.append(path[cycle_start:] + [next_neighbor])
                    elif next_neighbor not in visited:
                        stack.append((next_neighbor, iter(self.dependency_graph.successors(next_neighbor))))
                except StopIteration:
                    stack.pop()
                    if path and path[-1] == current:
                        path.pop()
        
        return cycles
    
    def _detect_cycles_fallback(self) -> List[List[str]]:
        if not self.dependency_graph:
            return []
        
        cycles = []
        visited = set()
        recursion_stack = set()
        
        def dfs(node, path):
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)
            
            neighbors = self.dependency_graph.get(node, {}).get('outgoing', set())
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    if dfs(neighbor, path.copy()):
                        return True
                elif neighbor in recursion_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:])
            
            recursion_stack.remove(node)
            return False
        
        for node in self.dependency_graph:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def _resolve_cycles(self, cycles: List[List[str]]) -> Dict:
        resolution_report = {
            'cycles_found': len(cycles),
            'resolutions': [],
            'remaining_cycles': []
        }
        
        for cycle in cycles:
            resolved = False
            
            for resolver in self.cycle_resolvers:
                try:
                    if resolver(cycle):
                        resolution_report['resolutions'].append({
                            'cycle': cycle,
                            'strategy': resolver.__name__,
                            'success': True
                        })
                        resolved = True
                        break
                except Exception as e:
                    resolution_report['resolutions'].append({
                        'cycle': cycle,
                        'strategy': resolver.__name__,
                        'success': False,
                        'error': str(e)
                    })
            
            if not resolved:
                resolution_report['remaining_cycles'].append(cycle)
        
        return resolution_report
    
    def _resolve_cycle_by_priority(self, cycle: List[str]) -> bool:
        if len(cycle) < 2:
            return False
        
        lowest_priority_task = min(cycle, key=lambda t: self.task_manager.get(t).get('priority', 0))
        
        idx = cycle.index(lowest_priority_task)
        next_task = cycle[(idx + 1) % len(cycle)]
        
        self.remove_dependency(lowest_priority_task, next_task)
        return True
    
    def _resolve_cycle_by_topological_insert(self, cycle: List[str]) -> bool:
        if len(cycle) < 2:
            return False
        
        self.remove_dependency(cycle[0], cycle[1])
        return True
    
    def _resolve_cycle_by_merge(self, cycle: List[str]) -> bool:
        return False
    
    def get_execution_order(self) -> List[str]:
        if not HAS_NETWORKX:
            return self._topological_sort_fallback()
        
        try:
            return list(nx.topological_sort(self.dependency_graph))
        except nx.NetworkXUnfeasible:
            if self.dependency_graph.nodes():
                source = next(iter(self.dependency_graph.nodes()))
                return list(nx.bfs_tree(self.dependency_graph, source).nodes())
            return []
    
    def _topological_sort_fallback(self) -> List[str]:
        if not self.dependency_graph:
            return []
        
        in_degree = {}
        for node in self.dependency_graph:
            in_degree[node] = len(self.dependency_graph.get(node, {}).get('incoming', set()))
        
        queue = deque([n for n in in_degree if in_degree[n] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            
            for neighbor in self.dependency_graph.get(node, {}).get('outgoing', set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    def get_critical_path(self) -> Dict:
        if not HAS_NETWORKX or not self.dependency_graph.nodes():
            return {'tasks': [], 'length': 0}
        
        try:
            def longest_path(node, memo):
                if node in memo:
                    return memo[node]
                
                max_length = 0
                max_path = [node]
                
                for successor in self.dependency_graph.successors(node):
                    path_length, path = longest_path(successor, memo)
                    if path_length + 1 > max_length:
                        max_length = path_length + 1
                        max_path = [node] + path
                
                memo[node] = (max_length, max_path)
                return memo[node]
            
            memo = {}
            all_paths = []
            for node in self.dependency_graph.nodes():
                length, path = longest_path(node, memo)
                if length > 0:
                    all_paths.append({'path': path, 'length': length})
            
            if all_paths:
                critical = max(all_paths, key=lambda x: x['length'])
                return {
                    'tasks': critical['path'],
                    'length': critical['length'],
                    'estimated_duration': critical['length'] * 5
                }
            
            return {'tasks': [], 'length': 0}
            
        except Exception as e:
            return {'tasks': [], 'length': 0, 'error': str(e)}
    
    def get_parallelizable_groups(self) -> List[List[str]]:
        if not HAS_NETWORKX:
            return self._find_parallel_groups_fallback()
        
        if not self.dependency_graph.nodes():
            return []
        
        roots = [n for n in self.dependency_graph.nodes() 
                if self.dependency_graph.in_degree(n) == 0]
        
        groups = []
        processed = set()
        
        def get_group(task):
            group = [task]
            processed.add(task)
            
            for successor in self.dependency_graph.successors(task):
                if self.dependency_graph.in_degree(successor) == len(list(
                        self.dependency_graph.predecessors(successor))):
                    if successor not in processed:
                        group.extend(get_group(successor))
            
            return group
        
        for root in roots:
            if root not in processed:
                groups.append(get_group(root))
        
        return groups
    
    def _find_parallel_groups_fallback(self) -> List[List[str]]:
        if not self.dependency_graph:
            return []
        
        roots = [n for n in self.dependency_graph 
                if not self.dependency_graph.get(n, {}).get('incoming')]
        
        groups = []
        for root in roots:
            groups.append([root])
        
        return groups
    
    def get_dependency_graph(self, session_id: str, root_task_id: str = None) -> Dict:
        task_tree = self.task_manager.get_tree(session_id, root_task_id)
        if not task_tree:
            return {'nodes': [], 'edges': []}
        
        self._build_graph_from_tree(task_tree)
        
        nodes = []
        edges = []
        
        if HAS_NETWORKX:
            for node in self.dependency_graph.nodes():
                task = self.task_manager.get(node)
                nodes.append({
                    'id': node,
                    'label': task.get('name', node) if task else node,
                    'status': task.get('status', 'unknown') if task else 'unknown'
                })
            
            for edge in self.dependency_graph.edges():
                edges.append({
                    'from': edge[0],
                    'to': edge[1]
                })
        else:
            for node, data in self.dependency_graph.items():
                task = self.task_manager.get(node)
                nodes.append({
                    'id': node,
                    'label': task.get('name', node) if task else node,
                    'status': task.get('status', 'unknown') if task else 'unknown'
                })
            
            for node, data in self.dependency_graph.items():
                for successor in data.get('outgoing', set()):
                    edges.append({
                        'from': node,
                        'to': successor
                    })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'groups': self.get_parallelizable_groups(),
            'critical_path': self.get_critical_path()['tasks']
        }
    
    def analyze_resource_conflicts(self, session_id: str, 
                                    resource_type: str = 'file') -> List[Dict]:
        return []
