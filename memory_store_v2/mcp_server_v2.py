"""
MCP Server v2 - Using the new hybrid memory system.
Provides consolidated tools for session, task, memory, and checkpoint management.
"""
import asyncio
import json
from typing import Dict, Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from memory_store_v2 import MemorySystemV2

# Global instance
memory = MemorySystemV2()
app = Server("chainofthought-coder-v2")

@app.list_tools()
async def list_tools():
    """List all available tools."""
    return [
        Tool(
            name="session_manager",
            description="Manage thinking sessions (create, list, switch, close, archive)",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "list", "get", "close", "archive"]},
                    "name": {"type": "string"},
                    "session_id": {"type": "string"},
                    "status": {"type": "string"},
                    "metadata": {"type": "object"}
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="task_manager",
            description="Manage tasks and sub-tasks (create, update, get_tree, add_dependency)",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create_main", "create_subtask", "update", "get_tree", "add_dependency"]},
                    "session_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "parent_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "progress": {"type": "number"},
                    "status": {"type": "string"},
                    "priority": {"type": "integer"},
                    "depends_on": {"type": "string"}
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="memory_ops",
            description="Store and retrieve memory (long-term and short-term)",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["store_long", "retrieve_long", "store_short", "get_short", "push_context", "push_action"]},
                    "session_id": {"type": "string"},
                    "memory_type": {"type": "string"},
                    "content": {"type": "object"},
                    "tags": {"type": "array"},
                    "confidence": {"type": "number"},
                    "query": {"type": "string"},
                    "action_data": {"type": "object"}
                },
                "required": ["action", "session_id"]
            }
        ),
        Tool(
            name="checkpoint_ops",
            description="Create and manage checkpoints (overall, subtask, stage)",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "list", "restore", "diff", "cleanup"]},
                    "level": {"type": "string", "enum": ["overall", "subtask", "stage"]},
                    "session_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "checkpoint_id": {"type": "string"},
                    "checkpoint_id_2": {"type": "string"},
                    "tags": {"type": "array"},
                    "metadata": {"type": "object"},
                    "stage_name": {"type": "string"},
                    "keep_last": {"type": "integer"}
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="system_stats",
            description="Get system statistics and metrics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]):
    """Handle tool calls."""
    try:
        if name == "session_manager":
            action = arguments["action"]
            
            if action == "create":
                session_id = memory.sessions.create(
                    arguments["name"],
                    arguments.get("metadata")
                )
                return [TextContent(type="text", text=json.dumps({"session_id": session_id}))]
            
            elif action == "list":
                sessions = memory.sessions.list(arguments.get("status"))
                return [TextContent(type="text", text=json.dumps({"sessions": sessions}))]
            
            elif action == "get":
                session = memory.sessions.get(arguments["session_id"])
                return [TextContent(type="text", text=json.dumps(session or {}))]
            
            elif action == "close":
                success = memory.sessions.archive(arguments["session_id"])
                return [TextContent(type="text", text=json.dumps({"success": success}))]
            
            elif action == "archive":
                success = memory.sessions.archive(arguments["session_id"])
                return [TextContent(type="text", text=json.dumps({"success": success}))]
        
        elif name == "task_manager":
            action = arguments["action"]
            
            if action == "create_main":
                task_id = memory.tasks.create_main_task(
                    arguments["session_id"],
                    arguments["name"],
                    arguments.get("description", ""),
                    arguments.get("priority", 0),
                    arguments.get("tags", [])
                )
                return [TextContent(type="text", text=json.dumps({"task_id": task_id}))]
            
            elif action == "create_subtask":
                task_id = memory.tasks.create_subtask(
                    arguments["session_id"],
                    arguments["parent_id"],
                    arguments["name"],
                    arguments.get("description", ""),
                    arguments.get("priority", 0)
                )
                return [TextContent(type="text", text=json.dumps({"task_id": task_id}))]
            
            elif action == "update":
                memory.tasks.update_progress(
                    arguments["task_id"],
                    arguments["progress"],
                    arguments.get("status")
                )
                return [TextContent(type="text", text=json.dumps({"success": True}))]
            
            elif action == "get_tree":
                tree = memory.tasks.get_tree(
                    arguments["session_id"],
                    arguments.get("root_task_id")
                )
                return [TextContent(type="text", text=json.dumps(tree or {}))]
            
            elif action == "add_dependency":
                success = memory.tasks.add_dependency(
                    arguments["task_id"],
                    arguments["depends_on"]
                )
                return [TextContent(type="text", text=json.dumps({"success": success}))]
        
        elif name == "memory_ops":
            action = arguments["action"]
            session_id = arguments["session_id"]
            
            if action == "store_long":
                memory_id = memory.memory.store_long_term(
                    session_id,
                    arguments["memory_type"],
                    arguments["content"],
                    arguments.get("tags"),
                    arguments.get("confidence", 1.0)
                )
                return [TextContent(type="text", text=json.dumps({"memory_id": memory_id}))]
            
            elif action == "retrieve_long":
                results = memory.memory.retrieve_long_term(
                    session_id,
                    arguments.get("query"),
                    arguments.get("memory_type"),
                    arguments.get("limit", 10)
                )
                return [TextContent(type="text", text=json.dumps({"results": results}))]
            
            elif action == "store_short":
                memory.memory.store_short_term(
                    session_id,
                    arguments.get("active_context"),
                    arguments.get("recent_actions"),
                    arguments.get("focus_area"),
                    arguments.get("temporary_state")
                )
                return [TextContent(type="text", text=json.dumps({"success": True}))]
            
            elif action == "get_short":
                result = memory.memory.get_short_term(session_id)
                return [TextContent(type="text", text=json.dumps(result or {}))]
            
            elif action == "push_context":
                memory.memory.push_context(session_id, arguments["content"])
                return [TextContent(type="text", text=json.dumps({"success": True}))]
            
            elif action == "push_action":
                memory.memory.push_action(session_id, arguments["action_data"])
                return [TextContent(type="text", text=json.dumps({"success": True}))]
        
        elif name == "checkpoint_ops":
            action = arguments["action"]
            
            if action == "create":
                if arguments["level"] == "overall":
                    cp_id = memory.checkpoints.create_overall(
                        arguments["session_id"],
                        arguments.get("tags"),
                        arguments.get("metadata")
                    )
                elif arguments["level"] == "subtask":
                    cp_id = memory.checkpoints.create_subtask(
                        arguments["task_id"],
                        arguments.get("tags"),
                        arguments.get("metadata")
                    )
                elif arguments["level"] == "stage":
                    cp_id = memory.checkpoints.create_stage(
                        arguments["task_id"],
                        arguments["stage_name"],
                        arguments.get("tags"),
                        arguments.get("metadata")
                    )
                return [TextContent(type="text", text=json.dumps({"checkpoint_id": cp_id}))]
            
            elif action == "list":
                checkpoints = memory.checkpoints.list(
                    arguments["session_id"],
                    arguments.get("task_id"),
                    arguments.get("level"),
                    arguments.get("tags"),
                    arguments.get("limit", 50)
                )
                return [TextContent(type="text", text=json.dumps({"checkpoints": checkpoints}))]
            
            elif action == "restore":
                success = memory.checkpoints.restore(
                    arguments["session_id"],
                    arguments["checkpoint_id"],
                    arguments.get("level", "overall")
                )
                return [TextContent(type="text", text=json.dumps({"success": success}))]
            
            elif action == "diff":
                diff = memory.checkpoints.diff(
                    arguments["checkpoint_id"],
                    arguments["checkpoint_id_2"]
                )
                return [TextContent(type="text", text=json.dumps(diff))]
            
            elif action == "cleanup":
                deleted = memory.checkpoints.cleanup_old(
                    arguments["session_id"],
                    arguments.get("keep_last", 10)
                )
                return [TextContent(type="text", text=json.dumps({"deleted": deleted}))]
        
        elif name == "system_stats":
            stats = memory.get_stats()
            return [TextContent(type="text", text=json.dumps(stats))]
        
        return [TextContent(type="text", text=json.dumps({"error": "Unknown action"}))]
    
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

async def main():
    """Main entry point."""
    print("Starting ChainOfThought Coder v2 (Hybrid Memory System)...")
    print(f"Storage: {memory.db.db_path}")
    print(f"Snapshots: {memory.file_store.base_dir}")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
