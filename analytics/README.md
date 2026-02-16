# MCP Analytics

Tools for analyzing the ChainOfThought Coder MCP usage.

## Files

- `analyze_db.py` - Main analysis script
- `find_db.py` - Database finder utility  
- `check_tables.py` - Quick table check

## Usage

### Find Databases
```bash
python analytics/find_db.py
```

### Analyze Local Database
```bash
python analytics/analyze_db.py
```

### Check Tables
```bash
python analytics/check_tables.py
```

## Output Files

After running `analyze_db.py`, these JSON files are created in `analytics/`:

- `sessions.json` - All sessions
- `tasks.json` - All tasks
- `summary.json` - Quick stats
- `dependencies.json` - Tasks with dependencies
- `status_counts.json` - Tasks by status
- `parent_tasks.json` - Parent tasks with subtask counts
- `recent_activity.json` - Recent tasks (24h)
- `complex_tasks.json` - Complex tasks

## Note on Cline MCP

The MCP running inside Cline uses its own database which is not accessible from outside. To analyze Cline's MCP data:

1. **Option A**: Use the MCP tools directly in Cline to query data
2. **Option B**: Modify the MCP to log/save to a shared location
3. **Option C**: Run the MCP locally (outside Cline) to populate local database

## Testing the Local MCP

To test locally and populate the database:

```bash
# Run the component tests (creates test data)
python -m memory_store_v2.test_mcp_components

# Then analyze
python analytics/analyze_db.py

# Or run the demo
python memory_store_v2/demo_enhanced.py
```
