"""
MCP Server v2 - Production-ready with all tools implemented.
Fixed: Missing tool handlers, input validation, connection cleanup
"""
import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from memory_store_v2 import MemorySystemV2
from memory_store_v2.agents.orchestration_engine import OrchestrationEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chainofthought-coder-v2")

# Global instance with proper initialization
memory: Optional[MemorySystemV2] = None
orchestration: Optional[OrchestrationEngine] = None

def init_memory_system():
    """Initialize memory system with proper error handling."""
    global memory, orchestration
    base_dir = os.environ.get("MEMORY_STORE_DIR", "./memory_store_v2")
    memory = MemorySystemV2(base_dir)
    orchestration = OrchestrationEngine(memory.tasks, max_parallel=4)
    logger.info(f"Memory system initialized at: {base_dir}")
    return memory, orchestration

def get_memory() -> MemorySystemV2:
    """Get memory instance with lazy initialization."""
    global memory
    if memory is None:
        init_memory_system()
    return memory

def get_orchestration() -> OrchestrationEngine:
    """Get orchestration instance with lazy initialization."""
    global orchestration
    if orchestration is None:
        init_memory_system()
    return orchestration

app = Server("chainofthought-coder-v2")

@app.list_tools()
async def list_tools():
    """List all available tools with proper schemas."""
    return [
        # Session Management
        Tool(
            name="session_manager",
            description="Manage thinking sessions - create, list, get, close, archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "get", "close", "archive", "set_mode", "get_mode", "update"],
                        "description": "Action to perform"
                    },
                    "name": {"type": "string", "description": "Session name (for create)"},
                    "session_id": {"type": "string", "description": "Session ID (for get/update/close)"},
                    "status": {"type": "string", "enum": ["active", "paused", "completed", "archived"]},
                    "mode": {"type": "string", "enum": ["plan", "act"], "description": "Plan or Act mode"},
                    "metadata": {"type": "object", "description": "Additional session metadata"}
                },
                "required": ["action"],
                "dependencies": {
                    "create": ["name"],
                    "get": ["session_id"],
                    "close": ["session_id"],
                    "archive": ["session_id"],
                    "set_mode": ["session_id", "mode"],
                    "get_mode": ["session_id"],
                    "update": ["session_id", "status"]
                }
            }
        ),
        # Task Management
        Tool(
            name="task_manager",
            description="Manage tasks with hierarchical structure and Plan/Act tracking",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create_main", "create_subtask", "update", "get_tree", "add_dependency", 
                                  "mark_planned", "mark_executed", "get_plan_summary", "get", "list"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "task_id": {"type": "string", "description": "Task ID"},
                    "parent_id": {"type": "string", "description": "Parent task ID (for subtask)"},
                    "name": {"type": "string", "description": "Task name"},
                    "description": {"type": "string", "description": "Task description"},
                    "progress": {"type": "number", "minimum": 0, "maximum": 1, "description": "Progress 0-1"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed", "blocked"]},
                    "priority": {"type": "integer", "minimum": 0, "description": "Task priority"},
                    "depends_on": {"type": "string", "description": "Task ID this task depends on"},
                    "plan_session_id": {"type": "string"},
                    "act_session_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["action"],
                "dependencies": {
                    "create_main": ["session_id", "name"],
                    "create_subtask": ["session_id", "parent_id", "name"],
                    "update": ["task_id", "progress"],
                    "get_tree": ["session_id"],
                    "get": ["task_id"],
                    "list": ["session_id"],
                    "add_dependency": ["task_id", "depends_on"],
                    "mark_planned": ["task_id"],
                    "mark_executed": ["task_id"],
                    "get_plan_summary": ["session_id"]
                }
            }
        ),
        # Workflow Manager
        Tool(
            name="workflow_manager",
            description="Manage task workflows with parallel execution and dependency tracking",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "execute", "status", "cancel", "get_graph"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "workflow_id": {"type": "string", "description": "Workflow ID"},
                    "name": {"type": "string", "description": "Workflow name"},
                    "description": {"type": "string", "description": "Workflow description"},
                    "root_task_id": {"type": "string", "description": "Root task ID"},
                    "max_parallel": {"type": "integer", "minimum": 1, "maximum": 16, "default": 4}
                },
                "required": ["action"],
                "dependencies": {
                    "create": ["session_id", "name"],
                    "execute": ["workflow_id"],
                    "status": ["workflow_id"],
                    "cancel": ["workflow_id"],
                    "get_graph": ["session_id", "root_task_id"]
                }
            }
        ),
        # Dependency Analyzer
        Tool(
            name="dependency_analyzer",
            description="Analyze and visualize task dependencies, detect cycles, get execution order",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["analyze", "get_order", "get_graph", "detect_cycles", "critical_path"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "root_task_id": {"type": "string", "description": "Root task ID"},
                    "task_id": {"type": "string", "description": "Specific task ID"},
                    "auto_infer": {"type": "boolean", "default": True, "description": "Auto-infer dependencies"}
                },
                "required": ["action"],
                "dependencies": {
                    "analyze": ["session_id", "root_task_id"],
                    "get_order": ["session_id", "root_task_id"],
                    "get_graph": ["session_id"],
                    "detect_cycles": ["session_id", "root_task_id"],
                    "critical_path": ["session_id", "root_task_id"]
                }
            }
        ),
        # Parallel Executor
        Tool(
            name="parallel_executor",
            description="Execute tasks in parallel with dependency awareness and progress monitoring",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["schedule", "status", "pause", "resume", "cancel"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "root_task_id": {"type": "string", "description": "Root task ID"},
                    "task_id": {"type": "string", "description": "Task ID (for cancel)"},
                    "max_parallel": {"type": "integer", "minimum": 1, "maximum": 16, "default": 4}
                },
                "required": ["action"],
                "dependencies": {
                    "schedule": ["session_id", "root_task_id"],
                    "status": ["session_id", "root_task_id"],
                    "cancel": ["task_id"]
                }
            }
        ),
        # Progress Tracker
        Tool(
            name="progress_tracker",
            description="Track task progress with history, predictions, and analytics",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get", "history", "summary", "predict"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "root_task_id": {"type": "string", "description": "Root task ID"},
                    "task_id": {"type": "string", "description": "Task ID"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100}
                },
                "required": ["action"],
                "dependencies": {
                    "get": ["task_id"],
                    "history": ["task_id"],
                    "summary": ["session_id"],
                    "predict": ["session_id", "root_task_id"]
                }
            }
        ),
        # Task Decomposer
        Tool(
            name="task_decomposer",
            description="Decompose complex tasks into subtasks with intelligent analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["decompose", "analyze_complexity", "classify", "get_templates"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "task_id": {"type": "string", "description": "Task ID"},
                    "auto_dependencies": {"type": "boolean", "default": True, "description": "Auto-infer dependencies"}
                },
                "required": ["action"],
                "dependencies": {
                    "decompose": ["session_id", "task_id"],
                    "analyze_complexity": ["task_id"],
                    "classify": ["task_id"]
                }
            }
        ),
        # Design Planner (Refactored - LLM-based)
        Tool(
            name="design_planner",
            description="Generate High-Level Design (HLD) and Low-Level Design (LLD) using AI",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create_hld", "create_lld", "generate", "get_design"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "task_id": {"type": "string", "description": "Task ID"},
                    "model": {"type": "string", "enum": ["auto", "gpt-4", "claude", "local"], "default": "auto",
                              "description": "AI model to use (auto = best available)"},
                    "detail_level": {"type": "string", "enum": ["high", "medium", "low"], "default": "medium"},
                    "include_diagrams": {"type": "boolean", "default": True}
                },
                "required": ["action", "session_id", "task_id"]
            }
        ),
        # Memory Operations
        Tool(
            name="memory_ops",
            description="Store and retrieve long-term and short-term memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["store_long", "retrieve_long", "store_short", "get_short", 
                                  "push_context", "push_action", "clear_short"],
                        "description": "Action to perform"
                    },
                    "session_id": {"type": "string", "description": "Session ID"},
                    "memory_type": {"type": "string", "enum": ["knowledge", "insight", "pattern", "context"]},
                    "content": {"type": "object", "description": "Memory content"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0},
                    "query": {"type": "string", "description": "Search query for retrieval"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                    "action_data": {"type": "object", "description": "Action data to push"},
                    "active_context": {"type": "object"},
                    "recent_actions": {"type": "array"},
                    "focus_area": {"type": "string"},
                    "temporary_state": {"type": "object"}
                },
                "required": ["action", "session_id"],
                "dependencies": {
                    "store_long": ["session_id", "memory_type", "content"],
                    "retrieve_long": ["session_id", "query"],
                    "store_short": ["session_id"],
                    "push_context": ["session_id"],
                    "push_action": ["session_id"],
                    "clear_short": ["session_id"]
                }
            }
        ),
        # Checkpoint Operations
        Tool(
            name="checkpoint_ops",
            description="Create and manage multi-level checkpoints with diff and restore",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "get", "restore", "diff", "cleanup"],
                        "description": "Action to perform"
                    },
                    "level": {"type": "string", "enum": ["overall", "subtask", "stage"]},
                    "session_id": {"type": "string", "description": "Session ID"},
                    "task_id": {"type": "string", "description": "Task ID (for subtask/stage)"},
                    "checkpoint_id": {"type": "string", "description": "Checkpoint ID"},
                    "checkpoint_id_2": {"type": "string", "description": "Second checkpoint for diff"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "metadata": {"type": "object"},
                    "stage_name": {"type": "string", "description": "Stage name (for stage level)"},
                    "keep_last": {"type": "integer", "minimum": 1, "default": 10},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}
                },
                "required": ["action"],
                "dependencies": {
                    "create": ["level", "session_id"],
                    "get": ["checkpoint_id"],
                    "restore": ["session_id", "checkpoint_id"]
                }
            }
        ),
        # System Stats
        Tool(
            name="system_stats",
            description="Get comprehensive system statistics and health metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_health": {"type": "boolean", "default": True, "description": "Include health check"},
                    "include_storage": {"type": "boolean", "default": True, "description": "Include storage metrics"}
                }
            }
        )
    ]

async def validate_input(action: str, arguments: Dict[str, Any], required: List[str]) -> Optional[str]:
    """Validate required arguments."""
    missing = [r for r in required if r not in arguments or arguments[r] is None]
    if missing:
        return f"Missing required arguments for action '{action}': {', '.join(missing)}"
    return None

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]):
    """Handle tool calls with proper error handling and validation."""
    mem = get_memory()
    orch = get_orchestration()
    
    try:
        # Session Manager
        if name == "session_manager":
            action = arguments["action"]
            
            if action == "create":
                error = await validate_input(action, arguments, ["name"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                session_id = mem.sessions.create(
                    arguments["name"],
                    arguments.get("metadata"),
                    arguments.get("mode", "plan")
                )
                return [TextContent(type="text", text=json.dumps({"session_id": session_id, "status": "created"}))]
            
            elif action == "list":
                sessions = mem.sessions.list(arguments.get("status"))
                return [TextContent(type="text", text=json.dumps({"sessions": sessions, "count": len(sessions)}))]
            
            elif action == "get":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                session = mem.sessions.get(arguments["session_id"])
                if not session:
                    return [TextContent(type="text", text=json.dumps({"error": "Session not found"}))]
                return [TextContent(type="text", text=json.dumps(session))]
            
            elif action == "update":
                error = await validate_input(action, arguments, ["session_id", "status"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                success = mem.sessions.update(arguments["session_id"], arguments["status"])
                return [TextContent(type="text", text=json.dumps({"success": success}))]
            
            elif action in ["close", "archive"]:
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                success = mem.sessions.archive(arguments["session_id"])
                return [TextContent(type="text", text=json.dumps({"success": success}))]
            
            elif action == "set_mode":
                error = await validate_input(action, arguments, ["session_id", "mode"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.sessions.set_mode(arguments["session_id"], arguments["mode"])
                return [TextContent(type="text", text=json.dumps({"success": True, "mode": arguments["mode"]}))]
            
            elif action == "get_mode":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mode = mem.sessions.get_mode(arguments["session_id"])
                return [TextContent(type="text", text=json.dumps({"mode": mode}))]
        
        # Task Manager
        elif name == "task_manager":
            action = arguments["action"]
            
            if action == "create_main":
                error = await validate_input(action, arguments, ["session_id", "name"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                task_id = mem.tasks.create_main_task(
                    arguments["session_id"],
                    arguments["name"],
                    arguments.get("description", ""),
                    arguments.get("priority", 0),
                    arguments.get("tags", [])
                )
                return [TextContent(type="text", text=json.dumps({"task_id": task_id, "status": "created"}))]
            
            elif action == "create_subtask":
                error = await validate_input(action, arguments, ["session_id", "parent_id", "name"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                task_id = mem.tasks.create_subtask(
                    arguments["session_id"],
                    arguments["parent_id"],
                    arguments["name"],
                    arguments.get("description", ""),
                    arguments.get("priority", 0)
                )
                return [TextContent(type="text", text=json.dumps({"task_id": task_id, "status": "created"}))]
            
            elif action == "update":
                error = await validate_input(action, arguments, ["task_id", "progress"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.tasks.update_progress(
                    arguments["task_id"],
                    arguments["progress"],
                    arguments.get("status")
                )
                return [TextContent(type="text", text=json.dumps({"success": True, "task_id": arguments["task_id"]}))]
            
            elif action == "get_tree":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                tree = mem.tasks.get_tree(arguments["session_id"], arguments.get("root_task_id"))
                return [TextContent(type="text", text=json.dumps(tree or {}))]
            
            elif action == "get":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                task = mem.tasks.get(arguments["task_id"])
                if not task:
                    return [TextContent(type="text", text=json.dumps({"error": "Task not found"}))]
                return [TextContent(type="text", text=json.dumps(task))]
            
            elif action == "add_dependency":
                error = await validate_input(action, arguments, ["task_id", "depends_on"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                success = mem.tasks.add_dependency(arguments["task_id"], arguments["depends_on"])
                return [TextContent(type="text", text=json.dumps({"success": success}))]
            
            elif action == "mark_planned":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.tasks.mark_as_planned(
                    arguments["task_id"],
                    arguments.get("plan_session_id", arguments.get("session_id"))
                )
                return [TextContent(type="text", text=json.dumps({"success": True, "planned": True}))]
            
            elif action == "mark_executed":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.tasks.mark_as_executed(
                    arguments["task_id"],
                    arguments.get("act_session_id", arguments.get("session_id"))
                )
                return [TextContent(type="text", text=json.dumps({"success": True, "executed": True}))]
            
            elif action == "get_plan_summary":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                summary = mem.tasks.get_plan_act_summary(arguments["session_id"])
                return [TextContent(type="text", text=json.dumps(summary))]
        
        # Workflow Manager
        elif name == "workflow_manager":
            action = arguments["action"]
            
            if action == "create":
                error = await validate_input(action, arguments, ["session_id", "name"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                workflow_id = await orch.create_workflow(
                    arguments["session_id"],
                    arguments["name"],
                    arguments.get("description", "")
                )
                return [TextContent(type="text", text=json.dumps({"workflow_id": workflow_id, "status": "created"}))]
            
            elif action == "execute":
                error = await validate_input(action, arguments, ["workflow_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                result = await orch.execute_workflow(arguments["workflow_id"])
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "status":
                error = await validate_input(action, arguments, ["workflow_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                status = orch.get_workflow_status(arguments["workflow_id"])
                return [TextContent(type="text", text=json.dumps(status or {"error": "Workflow not found"}))]
            
            elif action == "cancel":
                error = await validate_input(action, arguments, ["workflow_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                await orch.cancel_workflow(arguments["workflow_id"])
                return [TextContent(type="text", text=json.dumps({"success": True, "status": "cancelled"}))]
            
            elif action == "get_graph":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                graph = orch.get_dependency_graph(arguments["session_id"], arguments.get("root_task_id"))
                return [TextContent(type="text", text=json.dumps(graph))]
        
        # Dependency Analyzer
        elif name == "dependency_analyzer":
            action = arguments["action"]
            
            if action == "analyze":
                error = await validate_input(action, arguments, ["session_id", "root_task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                result = await orch.dependency_agent.analyze_dependencies(
                    arguments["session_id"],
                    arguments["root_task_id"],
                    arguments.get("auto_infer", True)
                )
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "get_order":
                error = await validate_input(action, arguments, ["session_id", "root_task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                order = orch.dependency_agent.get_execution_order()
                return [TextContent(type="text", text=json.dumps({"execution_order": order}))]
            
            elif action == "get_graph":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                graph = orch.dependency_agent.get_dependency_graph(
                    arguments["session_id"],
                    arguments.get("root_task_id")
                )
                return [TextContent(type="text", text=json.dumps(graph))]
            
            elif action == "detect_cycles":
                error = await validate_input(action, arguments, ["session_id", "root_task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                cycles = orch.dependency_agent.detect_circular_dependencies(
                    arguments["session_id"],
                    arguments["root_task_id"]
                )
                return [TextContent(type="text", text=json.dumps({"cycles": cycles, "has_cycles": len(cycles) > 0}))]
            
            elif action == "critical_path":
                error = await validate_input(action, arguments, ["session_id", "root_task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                critical = orch.dependency_agent.get_critical_path()
                return [TextContent(type="text", text=json.dumps(critical))]
        
        # Parallel Executor
        elif name == "parallel_executor":
            action = arguments["action"]
            executor = orch.execution_agent
            
            if action == "schedule":
                error = await validate_input(action, arguments, ["session_id", "root_task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                result = await executor.schedule_tasks(
                    arguments["session_id"],
                    arguments.get("root_task_id"),
                    arguments.get("max_parallel", 4)
                )
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "status":
                status = executor.get_execution_status()
                return [TextContent(type="text", text=json.dumps(status))]
            
            elif action == "pause":
                await executor.pause_execution()
                return [TextContent(type="text", text=json.dumps({"success": True, "status": "paused"}))]
            
            elif action == "resume":
                await executor.resume_execution()
                return [TextContent(type="text", text=json.dumps({"success": True, "status": "resumed"}))]
            
            elif action == "cancel":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                await executor.cancel_task(arguments["task_id"])
                return [TextContent(type="text", text=json.dumps({"success": True, "task_id": arguments["task_id"]}))]
        
        # Progress Tracker
        elif name == "progress_tracker":
            action = arguments["action"]
            tracker = mem.progress_tracker
            
            if action == "get":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                progress = tracker.get_current_progress(arguments["task_id"])
                return [TextContent(type="text", text=json.dumps(progress or {"task_id": arguments["task_id"], "progress": 0}))]
            
            elif action == "history":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                history = tracker.get_history(arguments["task_id"], arguments.get("limit", 100))
                return [TextContent(type="text", text=json.dumps({"history": history, "count": len(history)}))]
            
            elif action == "summary":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                summary = tracker.get_progress_summary(arguments["session_id"], arguments.get("root_task_id"))
                return [TextContent(type="text", text=json.dumps(summary))]
            
            elif action == "predict":
                error = await validate_input(action, arguments, ["session_id", "root_task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                prediction = tracker.predict_completion(arguments["session_id"], arguments["root_task_id"])
                return [TextContent(type="text", text=json.dumps(prediction))]
        
        # Task Decomposer
        elif name == "task_decomposer":
            action = arguments["action"]
            decomp = orch.decomposition_agent
            
            if action == "decompose":
                error = await validate_input(action, arguments, ["session_id", "task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                subtask_ids = await decomp.decompose_task(
                    arguments["session_id"],
                    arguments["task_id"],
                    arguments.get("auto_dependencies", True)
                )
                return [TextContent(type="text", text=json.dumps({"subtasks": subtask_ids, "count": len(subtask_ids)}))]
            
            elif action == "analyze_complexity":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                task = mem.tasks.get(arguments["task_id"])
                if not task:
                    return [TextContent(type="text", text=json.dumps({"error": "Task not found"}))]
                complexity = decomp.analyze_complexity(task)
                return [TextContent(type="text", text=json.dumps({"complexity": complexity}))]
            
            elif action == "classify":
                error = await validate_input(action, arguments, ["task_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                task = mem.tasks.get(arguments["task_id"])
                if not task:
                    return [TextContent(type="text", text=json.dumps({"error": "Task not found"}))]
                task_type = decomp.classify_task(task)
                return [TextContent(type="text", text=json.dumps({"task_type": task_type}))]
            
            elif action == "get_templates":
                templates = decomp.SUBTASK_TEMPLATES
                return [TextContent(type="text", text=json.dumps({"templates": templates}))]
        
        # Design Planner (Refactored)
        elif name == "design_planner":
            action = arguments["action"]
            session_id = arguments.get("session_id")
            task_id = arguments.get("task_id")
            
            error = await validate_input(action, arguments, ["session_id", "task_id"])
            if error:
                return [TextContent(type="text", text=json.dumps({"error": error}))]
            
            task = mem.tasks.get(task_id)
            if not task:
                return [TextContent(type="text", text=json.dumps({"error": "Task not found"}))]
            
            # Get configuration
            detail_level = arguments.get("detail_level", "medium")
            include_diagrams = arguments.get("include_diagrams", True)
            
            if action == "create_hld":
                from memory_store_v2.agents.design_planner_agent import DesignPlannerAgent
                agent = DesignPlannerAgent(mem.tasks)
                result = await agent.create_hld(session_id, task_id, detail_level, include_diagrams)
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "create_lld":
                from memory_store_v2.agents.design_planner_agent import DesignPlannerAgent
                agent = DesignPlannerAgent(mem.tasks)
                result = await agent.create_lld(session_id, task_id, detail_level, include_diagrams)
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "generate":
                from memory_store_v2.agents.design_planner_agent import DesignPlannerAgent
                agent = DesignPlannerAgent(mem.tasks)
                result = await agent.generate_complete_design(session_id, task_id, detail_level, include_diagrams)
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "get_design":
                metadata = json.loads(task.get('metadata', '{}') or '{}')
                hld = metadata.get('hld')
                lld = metadata.get('lld')
                return [TextContent(type="text", text=json.dumps({
                    "has_hld": hld is not None,
                    "has_lld": lld is not None,
                    "hld": hld,
                    "lld": lld
                }))]
        
        # Memory Operations
        elif name == "memory_ops":
            action = arguments["action"]
            session_id = arguments["session_id"]
            
            if action == "store_long":
                error = await validate_input(action, arguments, ["session_id", "memory_type", "content"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                memory_id = mem.memory.store_long_term(
                    session_id,
                    arguments["memory_type"],
                    arguments["content"],
                    arguments.get("tags"),
                    arguments.get("confidence", 1.0)
                )
                return [TextContent(type="text", text=json.dumps({"memory_id": memory_id, "status": "stored"}))]
            
            elif action == "retrieve_long":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                results = mem.memory.retrieve_long_term(
                    session_id,
                    arguments.get("query"),
                    arguments.get("memory_type"),
                    arguments.get("limit", 10)
                )
                return [TextContent(type="text", text=json.dumps({"results": results, "count": len(results)}))]
            
            elif action == "store_short":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.memory.store_short_term(
                    session_id,
                    arguments.get("active_context"),
                    arguments.get("recent_actions"),
                    arguments.get("focus_area"),
                    arguments.get("temporary_state")
                )
                return [TextContent(type="text", text=json.dumps({"success": True, "stored": "short_term"}))]
            
            elif action == "get_short":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                result = mem.memory.get_short_term(session_id)
                return [TextContent(type="text", text=json.dumps(result or {}))]
            
            elif action == "push_context":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.memory.push_context(session_id, arguments.get("content", {}))
                return [TextContent(type="text", text=json.dumps({"success": True}))]
            
            elif action == "push_action":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.memory.push_action(session_id, arguments.get("action_data", {}))
                return [TextContent(type="text", text=json.dumps({"success": True}))]
            
            elif action == "clear_short":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                mem.memory.clear_short_term(session_id)
                return [TextContent(type="text", text=json.dumps({"success": True}))]
        
        # Checkpoint Operations
        elif name == "checkpoint_ops":
            action = arguments["action"]
            
            if action == "create":
                error = await validate_input(action, arguments, ["level", "session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                
                level = arguments["level"]
                session_id = arguments["session_id"]
                
                if level == "overall":
                    cp_id = mem.checkpoints.create_overall(
                        session_id,
                        arguments.get("tags"),
                        arguments.get("metadata")
                    )
                elif level == "subtask":
                    if not arguments.get("task_id"):
                        return [TextContent(type="text", text=json.dumps({"error": "task_id required for subtask checkpoint"}))]
                    cp_id = mem.checkpoints.create_subtask(
                        arguments["task_id"],
                        arguments.get("tags"),
                        arguments.get("metadata")
                    )
                elif level == "stage":
                    if not arguments.get("task_id") or not arguments.get("stage_name"):
                        return [TextContent(type="text", text=json.dumps({"error": "task_id and stage_name required for stage checkpoint"}))]
                    cp_id = mem.checkpoints.create_stage(
                        arguments["task_id"],
                        arguments["stage_name"],
                        arguments.get("tags"),
                        arguments.get("metadata")
                    )
                else:
                    return [TextContent(type="text", text=json.dumps({"error": f"Unknown level: {level}"}))]
                
                return [TextContent(type="text", text=json.dumps({"checkpoint_id": cp_id, "level": level}))]
            
            elif action == "list":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                checkpoints = mem.checkpoints.list(
                    arguments["session_id"],
                    arguments.get("task_id"),
                    arguments.get("level"),
                    arguments.get("tags"),
                    arguments.get("limit", 50)
                )
                return [TextContent(type="text", text=json.dumps({"checkpoints": checkpoints, "count": len(checkpoints)}))]
            
            elif action == "get":
                error = await validate_input(action, arguments, ["checkpoint_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                checkpoint = mem.checkpoints.get(arguments["checkpoint_id"])
                if not checkpoint:
                    return [TextContent(type="text", text=json.dumps({"error": "Checkpoint not found"}))]
                return [TextContent(type="text", text=json.dumps(checkpoint))]
            
            elif action == "restore":
                error = await validate_input(action, arguments, ["session_id", "checkpoint_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                level = arguments.get("level", "overall")
                success = mem.checkpoints.restore(arguments["session_id"], arguments["checkpoint_id"], level)
                return [TextContent(type="text", text=json.dumps({"success": success, "restored": success}))]
            
            elif action == "diff":
                error = await validate_input(action, arguments, ["checkpoint_id", "checkpoint_id_2"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                diff = mem.checkpoints.diff(arguments["checkpoint_id"], arguments["checkpoint_id_2"])
                return [TextContent(type="text", text=json.dumps(diff))]
            
            elif action == "cleanup":
                error = await validate_input(action, arguments, ["session_id"])
                if error:
                    return [TextContent(type="text", text=json.dumps({"error": error}))]
                deleted = mem.checkpoints.cleanup_old(arguments["session_id"], arguments.get("keep_last", 10))
                return [TextContent(type="text", text=json.dumps({"deleted": deleted, "remaining": arguments.get("keep_last", 10)}))]
        
        # System Stats
        elif name == "system_stats":
            stats = mem.get_stats()
            include_health = arguments.get("include_health", True)
            include_storage = arguments.get("include_storage", True)
            
            if include_health:
                stats["health"] = {
                    "status": "healthy",
                    "memory_initialized": memory is not None,
                    "orchestration_initialized": orchestration is not None
                }
            
            if include_storage:
                import os
                base_dir = os.environ.get("MEMORY_STORE_DIR", "./memory_store_v2")
                db_path = os.path.join(base_dir, "memory.db")
                if os.path.exists(db_path):
                    stats["storage"] = {
                        "db_size_bytes": os.path.getsize(db_path),
                        "snapshots_count": len([f for f in os.listdir(f"{base_dir}/snapshots") if f.endswith('.json')] if os.path.exists(f"{base_dir}/snapshots") else [])
                    }
            
            return [TextContent(type="text", text=json.dumps(stats, indent=2))]
        
        # Unknown tool
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    
    except ValueError as e:
        logger.warning(f"Validation error in {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e), "type": "validation"}))]
    
    except Exception as e:
        logger.error(f"Error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({
            "error": str(e),
            "type": "internal",
            "tool": name,
            "action": arguments.get("action") if isinstance(arguments, dict) else None
        }))]

async def main():
    """Main entry point with graceful shutdown handling."""
    global memory, orchestration
    
    # Initialize memory system
    init_memory_system()
    
    logger.info("=" * 60)
    logger.info("ChainOfThought Coder v2 - MCP Server")
    logger.info(f"Storage: {memory.db.db_path if memory else 'N/A'}")
    logger.info("Ready to accept connections...")
    logger.info("=" * 60)
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    except asyncio.CancelledError:
        logger.info("Server shutdown requested...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        # Cleanup
        if memory:
            logger.info("Closing memory system...")
            memory.close()
            memory = None
            orchestration = None
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
