"""
Integration agent - manages task integration points and data contracts
"""
from .base_agent import AgentBase
from typing import Dict, Any, List, Optional
import json
import jsonschema
from jsonschema import validate

class IntegrationAgent(AgentBase):
    def __init__(self, task_manager):
        super().__init__("integration_manager")
        self.task_manager = task_manager
        self.contract_registry = {}
        
    async def handle_message(self, message: Dict[str, Any]):
        msg_type = message['content'].get('type')
        
        if msg_type == 'register_contract':
            await self.register_contract(
                message['content']['task_id'],
                message['content']['contract']
            )
        elif msg_type == 'validate_integration':
            await self.validate_integration(
                message['content']['source_task'],
                message['content']['target_task'],
                message['content']['data']
            )
            
    async def register_contract(self, task_id: str, contract: Dict[str, Any]):
        """Register input/output contract for a task"""
        self.contract_registry[task_id] = contract
        metadata = json.loads(self.task_manager.get(task_id).get('metadata', '{}'))
        metadata['data_contract'] = contract
        self.task_manager.db.execute(
            "UPDATE tasks SET metadata = ? WHERE task_id = ?",
            (json.dumps(metadata), task_id)
        )
        
    async def validate_integration(self, source_task: str, target_task: str, data: Dict):
        """Validate data against both tasks' contracts"""
        # Validate against source task's output contract
        source_contract = self.contract_registry.get(source_task, {}).get('output')
        if source_contract:
            try:
                validate(instance=data, schema=source_contract)
            except jsonschema.ValidationError as e:
                raise ValueError(f"Source contract violation: {str(e)}")
                
        # Validate against target task's input contract
        target_contract = self.contract_registry.get(target_task, {}).get('input')
        if target_contract:
            try:
                validate(instance=data, schema=target_contract)
            except jsonschema.ValidationError as e:
                raise ValueError(f"Target contract violation: {str(e)}")
                
        return True
        
    def map_integration_points(self, session_id: str):
        """Discover and map all integration points in a session"""
        tasks = self.task_manager.db.fetch_all(
            "SELECT * FROM tasks WHERE session_id = ?",
            (session_id,)
        )
        
        integration_map = {}
        for task in tasks:
            metadata = json.loads(task['metadata'] or '{}')
            if 'data_contract' in metadata:
                integration_map[task['task_id']] = {
                    'inputs': metadata['data_contract'].get('input', {}),
                    'outputs': metadata['data_contract'].get('output', {})
                }
                
        return integration_map
        
    def detect_breaking_changes(self, old_contract: Dict, new_contract: Dict) -> List[str]:
        """Detect breaking changes between contract versions"""
        breaking_changes = []
        
        # Check input contract changes
        old_input = old_contract.get('input', {})
        new_input = new_contract.get('input', {})
        breaking_changes.extend(self._compare_schemas(old_input, new_input, "input"))
        
        # Check output contract changes
        old_output = old_contract.get('output', {})
        new_output = new_contract.get('output', {})
        breaking_changes.extend(self._compare_schemas(old_output, new_output, "output"))
        
        return breaking_changes
        
    def _compare_schemas(self, old: Dict, new: Dict, contract_type: str) -> List[str]:
        changes = []
        if not old and new:
            return changes
            
        # Check required fields
        old_required = set(old.get('required', []))
        new_required = set(new.get('required', []))
        added_required = new_required - old_required
        if added_required:
            changes.append(f"Added required {contract_type} fields: {', '.join(added_required)}")
            
        # Check type changes
        for prop, old_def in old.get('properties', {}).items():
            new_def = new.get('properties', {}).get(prop)
            if new_def and old_def.get('type') != new_def.get('type'):
                changes.append(f"{contract_type} field '{prop}' type changed from {old_def.get('type')} to {new_def.get('type')}")
                
        return changes