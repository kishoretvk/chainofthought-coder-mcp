"""
MCP Analytics - Database Analysis Script
Analyzes the memory store database and exports results to JSON
"""
import sqlite3
import json
import os
from datetime import datetime

# Database path
DB_PATH = "memory_store_v2/memory.db"
OUTPUT_DIR = "analytics"


def connect_db():
    """Connect to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_sessions(conn):
    """Get all sessions."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_tasks(conn):
    """Get all tasks with details."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT task_id, session_id, parent_id, name, description, 
               status, progress, priority, dependencies, tags, 
               metadata, created_at, updated_at 
        FROM tasks ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_task_summary(conn):
    """Get task statistics summary."""
    cursor = conn.cursor()
    
    # Total counts
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM sessions) as total_sessions,
            (SELECT COUNT(*) FROM tasks) as total_tasks,
            (SELECT COUNT(*) FROM tasks WHERE parent_id IS NOT NULL) as subtasks,
            (SELECT COUNT(*) FROM tasks WHERE status = 'completed') as completed,
            (SELECT COUNT(*) FROM tasks WHERE status = 'in_progress') as in_progress,
            (SELECT COUNT(*) FROM tasks WHERE status = 'pending') as pending,
            (SELECT COUNT(*) FROM tasks WHERE parent_id IS NULL) as main_tasks
    """)
    row = cursor.fetchone()
    return dict(row)


def get_tasks_with_dependencies(conn):
    """Get tasks that have dependencies."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT task_id, name, dependencies 
        FROM tasks 
        WHERE dependencies != '[]' AND dependencies IS NOT NULL
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_tasks_by_status(conn):
    """Get task counts by status."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM tasks 
        GROUP BY status
    """)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_parent_tasks_with_subtasks(conn):
    """Get parent tasks and their subtask counts."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            t.task_id,
            t.name,
            t.status,
            t.progress,
            COUNT(st.task_id) as subtask_count
        FROM tasks t
        LEFT JOIN tasks st ON t.task_id = st.parent_id
        WHERE t.parent_id IS NULL
        GROUP BY t.task_id
        ORDER BY t.created_at DESC
    """)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_recent_activity(conn, hours=24):
    """Get recent activity in the last N hours."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT * FROM tasks 
        WHERE created_at > datetime('now', '-{hours} hours')
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_complex_tasks(conn, min_desc_length=50):
    """Get tasks with detailed descriptions (complex tasks)."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT task_id, name, LENGTH(description) as desc_length, 
               priority, status
        FROM tasks 
        WHERE LENGTH(description) >= {min_desc_length}
        ORDER BY LENGTH(description) DESC
    """)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def export_to_json(data, filename):
    """Export data to JSON file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"✓ Exported: {filepath}")
    return filepath


def main():
    """Main function to run all analyses."""
    print("=" * 60)
    print("  MCP Analytics - Database Analysis")
    print("=" * 60)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Output: {OUTPUT_DIR}/")
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Connect to database
    conn = connect_db()
    
    try:
        # Run all queries
        print("\n--- Running Queries ---\n")
        
        # 1. Sessions
        sessions = get_sessions(conn)
        export_to_json(sessions, "sessions.json")
        print(f"  Sessions: {len(sessions)}")
        
        # 2. Tasks
        tasks = get_tasks(conn)
        export_to_json(tasks, "tasks.json")
        print(f"  Tasks: {len(tasks)}")
        
        # 3. Summary
        summary = get_task_summary(conn)
        export_to_json(summary, "summary.json")
        print(f"  Summary: {summary}")
        
        # 4. Tasks with dependencies
        task_deps = get_tasks_with_dependencies(conn)
        export_to_json(task_deps, "dependencies.json")
        print(f"  Tasks with dependencies: {len(task_deps)}")
        
        # 5. Tasks by status
        status_counts = get_tasks_by_status(conn)
        export_to_json(status_counts, "status_counts.json")
        print(f"  Status breakdown: {status_counts}")
        
        # 6. Parent tasks with subtasks
        parent_tasks = get_parent_tasks_with_subtasks(conn)
        export_to_json(parent_tasks, "parent_tasks.json")
        print(f"  Parent tasks: {len(parent_tasks)}")
        
        # 7. Recent activity (last 24 hours)
        recent = get_recent_activity(conn, 24)
        export_to_json(recent, "recent_activity.json")
        print(f"  Recent tasks (24h): {len(recent)}")
        
        # 8. Complex tasks
        complex_tasks = get_complex_tasks(conn, 50)
        export_to_json(complex_tasks, "complex_tasks.json")
        print(f"  Complex tasks: {len(complex_tasks)}")
        
        print("\n" + "=" * 60)
        print("  Analysis Complete!")
        print("=" * 60)
        print(f"\nAll files saved to: {OUTPUT_DIR}/")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
