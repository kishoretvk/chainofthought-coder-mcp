"""
Design Planner Agent - Generates High-Level and Low-Level Design documents
"""
import json
import time
from typing import Dict, Any, List, Optional
from .base_agent import AgentBase


class DesignPlannerAgent(AgentBase):
    """
    Agent for generating HLD and LLD for tasks.
    
    Actions:
    - create_hld: Generate High-Level Design
    - create_lld: Generate Low-Level Design  
    - generate: Generate both HLD and LLD
    """
    
    # HLD Template
    HLD_TEMPLATE = {
        "system_overview": "",
        "components": [],
        "data_flow": "",
        "api_surface": [],
        "technology_stack": [],
        "key_decisions": []
    }
    
    # LLD Template
    LLD_TEMPLATE = {
        "class_diagrams": [],
        "database_schema": {},
        "function_signatures": [],
        "edge_cases": [],
        "error_handling": [],
        "testing_strategy": []
    }
    
    def __init__(self, task_manager):
        super().__init__("design_planner")
        self.task_manager = task_manager
    
    async def handle_message(self, message: Dict[str, Any]):
        msg_type = message['content'].get('type')
        
        if msg_type == 'create_hld':
            task_id = message['content']['task_id']
            session_id = message['content']['session_id']
            return await self.create_hld(session_id, task_id)
        
        elif msg_type == 'create_lld':
            task_id = message['content']['task_id']
            session_id = message['content']['session_id']
            return await self.create_lld(session_id, task_id)
        
        elif msg_type == 'generate':
            task_id = message['content']['task_id']
            session_id = message['content']['session_id']
            return await self.generate_design(session_id, task_id)
    
    async def create_hld(self, session_id: str, task_id: str) -> Dict[str, Any]:
        """Generate High-Level Design."""
        task = self.task_manager.get(task_id)
        if not task:
            return {"error": "Task not found"}
        
        hld = {
            "system_overview": f"System to {task.get('name', 'N/A')}: {task.get('description', 'N/A')}",
            "components": self._generate_components(task),
            "data_flow": self._generate_data_flow(task),
            "api_surface": self._generate_api_surface(task),
            "technology_stack": self._suggest_tech_stack(task),
            "key_decisions": self._generate_key_decisions(task),
            "created_at": time.time()
        }
        
        # Store in task metadata
        metadata = json.loads(task.get('metadata', '{}') or '{}')
        metadata['hld'] = hld
        self.task_manager.db.execute(
            "UPDATE tasks SET metadata = ? WHERE task_id = ?",
            (json.dumps(metadata), task_id)
        )
        
        return {"hld": hld, "task_id": task_id}
    
    async def create_lld(self, session_id: str, task_id: str) -> Dict[str, Any]:
        """Generate Low-Level Design."""
        task = self.task_manager.get(task_id)
        if not task:
            return {"error": "Task not found"}
        
        lld = {
            "class_diagrams": self._generate_class_diagrams(task),
            "database_schema": self._generate_db_schema(task),
            "function_signatures": self._generate_functions(task),
            "edge_cases": self._identify_edge_cases(task),
            "error_handling": self._suggest_error_handling(task),
            "testing_strategy": self._suggest_testing(task),
            "created_at": time.time()
        }
        
        # Store in task metadata
        metadata = json.loads(task.get('metadata', '{}') or '{}')
        metadata['lld'] = lld
        self.task_manager.db.execute(
            "UPDATE tasks SET metadata = ? WHERE task_id = ?",
            (json.dumps(metadata), task_id)
        )
        
        return {"lld": lld, "task_id": task_id}
    
    async def generate_design(self, session_id: str, task_id: str) -> Dict[str, Any]:
        """Generate both HLD and LLD."""
        hld_result = await self.create_hld(session_id, task_id)
        lld_result = await self.create_lld(session_id, task_id)
        
        return {
            "hld": hld_result.get("hld"),
            "lld": lld_result.get("lld"),
            "task_id": task_id
        }
    
    # Helper methods for HLD
    def _generate_components(self, task: Dict) -> List[Dict]:
        name = task.get('name', '')
        return [
            {"name": "Core", "description": f"Main component for {name}"},
            {"name": "Storage", "description": "Data persistence layer"},
            {"name": "API", "description": "Interface layer"}
        ]
    
    def _generate_data_flow(self, task: Dict) -> str:
        return f"Input → Processing → Storage → Output"
    
    def _generate_api_surface(self, task: Dict) -> List[Dict]:
        return [
            {"endpoint": "/create", "method": "POST", "description": "Create new item"},
            {"endpoint": "/get/{id}", "method": "GET", "description": "Get item by ID"},
            {"endpoint": "/list", "method": "GET", "description": "List all items"},
            {"endpoint": "/update/{id}", "method": "PUT", "description": "Update item"},
            {"endpoint": "/delete/{id}", "method": "DELETE", "description": "Delete item"}
        ]
    
    def _suggest_tech_stack(self, task: Dict) -> List[str]:
        return ["Python", "SQLite", "REST API", "JSON"]
    
    def _generate_key_decisions(self, task: Dict) -> List[str]:
        return [
            "Use SQLite for simplicity",
            "REST API for interface",
            "JSON for data exchange"
        ]
    
    # Helper methods for LLD
    def _generate_class_diagrams(self, task: Dict) -> List[Dict]:
        return [
            {"class": "MainClass", "attributes": ["id", "name", "data"], "methods": ["create", "read", "update", "delete"]}
        ]
    
    def _generate_db_schema(self, task: Dict) -> Dict:
        return {
            "tables": [
                {"name": "items", "columns": ["id", "name", "data", "created_at", "updated_at"]}
            ]
        }
    
    def _generate_functions(self, task: Dict) -> List[Dict]:
        return [
            {"name": "create_item", "params": ["name", "data"], "returns": "item_id"},
            {"name": "get_item", "params": ["item_id"], "returns": "item"},
            {"name": "update_item", "params": ["item_id", "data"], "returns": "success"},
            {"name": "delete_item", "params": ["item_id"], "returns": "success"}
        ]
    
    def _identify_edge_cases(self, task: Dict) -> List[str]:
        return [
            "Empty input handling",
            "Duplicate detection",
            "Concurrent access",
            "Data validation"
        ]
    
    def _suggest_error_handling(self, task: Dict) -> List[str]:
        return [
            "Try-catch blocks",
            "Error codes",
            "Logging",
            "User-friendly messages"
        ]
    
    def _suggest_testing(self, task: Dict) -> List[str]:
        return [
            "Unit tests",
            "Integration tests",
            "Edge case tests",
            "Performance tests"
        ]
