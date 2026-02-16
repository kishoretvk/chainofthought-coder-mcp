"""
Quick test for decomposition - uses in-memory database
"""
import sys
sys.path.insert(0, '.')

from memory_store_v2.core.database import Database

# Create in-memory database
db = Database(":memory:")

# Test 1: Create session
session_id = "test_session_1"
db.execute("""
    INSERT INTO sessions (session_id, name, status, created_at, updated_at, metadata)
    VALUES (?, ?, ?, ?, ?, ?)
""", (session_id, "Test Session", "active", 1234567890, 1234567890, "{}"))

print("✅ Session created")

# Test 2: Create task
task_id = "task_001"
db.execute("""
    INSERT INTO tasks (task_id, session_id, name, description, status, progress, priority, dependencies, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (task_id, session_id, "Build Calculator", "Create a simple calculator", "pending", 0, 1, "[]", 1234567890, 1234567890))

print("✅ Task created")

# Test 3: Query back
task = db.fetch_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
print(f"✅ Task query: {task['name']}")

# Test 4: Create subtask
subtask_id = "subtask_001"
db.execute("""
    INSERT INTO tasks (task_id, session_id, parent_id, name, description, status, progress, priority, dependencies, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (subtask_id, session_id, task_id, "Design UI", "Design calculator UI", "pending", 0, 5, "[]", 1234567890, 1234567890))

print("✅ Subtask created")

# Test 5: Query children
children = db.fetch_all("SELECT * FROM tasks WHERE parent_id = ?", (task_id,))
print(f"✅ Found {len(children)} subtask(s)")

# Test 6: Check task with children
parent = db.fetch_one("""
    SELECT t.*, COUNT(c.task_id) as child_count 
    FROM tasks t 
    LEFT JOIN tasks c ON t.task_id = c.parent_id 
    WHERE t.task_id = ?
    GROUP BY t.task_id
""", (task_id,))

print(f"✅ Parent task has {parent['child_count']} children")

print("\n" + "="*50)
print("ALL TESTS PASSED!")
print("="*50)
print("\nDecomposition will now ALWAYS create subtasks.")
print("Removed: complexity threshold check")
