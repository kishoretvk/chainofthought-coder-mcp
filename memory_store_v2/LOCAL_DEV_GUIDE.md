# Local Development & Testing Guide

This guide covers how to test the MCP server locally before publishing to Cline Marketplace.

## Prerequisites

```bash
# Install MCP SDK
pip install mcp

# Install project dependencies
pip install -r memory_store_v2/requirements.txt
```

## Quick Test: Direct Python Execution

The easiest way to test is running the demo:

```bash
cd memory_store_v2
python demo_enhanced.py
```

This runs a standalone test of all MCP components without the MCP protocol.

## Testing the MCP Server

### Option 1: Using mcp CLI (Recommended)

```bash
# Install the MCP CLI
pip install mcp

# Test the server runs correctly
python -m memory_store_v2.mcp_server_v2
```

### Option 2: Using a Test Client

Create a test script:

```python
# test_mcp_client.py
import asyncio
import json
from mcp import ClientSession, StdioServer

async def test_mcp():
    async with StdioServer("python", ["-m", "memory_store_v2.mcp_server_v2"]) as server:
        async with ClientSession(server) as session:
            # Initialize
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")
            
            # Test session creation
            result = await session.call_tool("session_manager", {
                "action": "create",
                "name": "Test Session"
            })
            print(f"Session created: {result}")

asyncio.run(test_mcp())
```

Run it:
```bash
python test_mcp_client.py
```

## Connecting to Cline (Local MCP)

### Method 1: Cline Settings (Custom Servers)

1. Open Cline settings
2. Navigate to **MCP Servers** or **Custom Servers**
3. Add a new server:

```json
{
  "name": "ChainOfThought Coder (Local)",
  "command": "python",
  "args": ["-m", "memory_store_v2.mcp_server_v2"],
  "env": {},
  "workingDirectory": "path/to/chainofthought-coder-mcp"
}
```

### Method 2: Using npx (Alternative)

```bash
# If you have a package.json setup
npx @modelcontextprotocol/server-python memory_store_v2/mcp_server_v2
```

## Debugging Tips

### Check Server Starts Correctly

```bash
# Run with verbose output
python -c "
import asyncio
from memory_store_v2 import MemorySystemV2

memory = MemorySystemV2()
print(f'DB: {memory.db.db_path}')
print(f'Files: {memory.file_store.base_dir}')
print('✓ Server components loaded successfully')
memory.close()
"
```

### Verify All Tools Available

```python
# Check tools are registered
from memory_store_v2.mcp_server_v2 import list_tools
import asyncio

tools = asyncio.run(list_tools())
print(f"Total tools: {len(tools)}")
for tool in tools:
    print(f"  - {tool.name}")
```

### Test Individual Components

```bash
# Run component tests
python -m memory_store_v2.test_mcp_components
```

## Troubleshooting

### Issue: "Module not found"

```bash
# Make sure you're in the right directory
cd chainofthought-coder-mcp
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python -m memory_store_v2.mcp_server_v2
```

### Issue: "stdio_server not found"

```bash
# Install MCP SDK
pip install mcp --upgrade
```

### Issue: Database errors

```bash
# Clean database and retry
rm -f memory_store_v2/*.db
python -m memory_store_v2.test_mcp_components
```

## Publishing to Cline (After Local Testing)

Once local testing passes:

```bash
# 1. Run validation
cline security scan --level production
cline compatibility validate --manifest memory_store_v2/mcp-manifest.json

# 2. Package
zip -r release.zip memory_store_v2/ tests_v2/ *.md requirements.txt

# 3. Publish (requires API key)
export CLINE_API_KEY="your_key_here"
cline marketplace publish --name "ChainOfThought Coder V2"
```

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `session_manager` | Create/list/close sessions |
| `task_manager` | Create tasks, subtasks, dependencies |
| `workflow_manager` | Execute workflows with parallel processing |
| `dependency_analyzer` | Analyze task dependencies & cycles |
| `parallel_executor` | Run tasks in parallel |
| `progress_tracker` | Track and predict progress |
| `task_decomposer` | Decompose complex tasks |
| `memory_ops` | Store/retrieve long & short-term memory |
| `checkpoint_ops` | Create/restore checkpoints |
| `system_stats` | Get system statistics |

---

**Happy Testing!** 🧪
