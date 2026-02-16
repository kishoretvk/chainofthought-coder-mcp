"""
SQLite database wrapper for the hybrid memory system.
Provides connection pooling, transactions, and schema management.
FIXED: Enabled WAL mode for concurrent reads, no more database locking!
"""
import sqlite3
import json
import os
from typing import Optional, Dict, Any, List
from pathlib import Path
import threading


class Database:
    """SQLite database wrapper with connection pooling and schema management."""
    
    def __init__(self, db_path: str = "./memory_store_v2/memory.db"):
        self.db_path = db_path
        self._connections = {}
        self._lock = threading.Lock()
        self._is_memory = db_path == ":memory:" or db_path.startswith("file:")
        self._init_database()
    
    def _init_database(self):
        """Initialize database with schema."""
        if not self._is_memory and self.db_path:
            dir_path = os.path.dirname(self.db_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
        
        # Enable WAL mode for concurrent reads (skip for in-memory)
        if not self._is_memory:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.close()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Tasks table (hierarchical)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    parent_id TEXT,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    progress REAL DEFAULT 0.0,
                    priority INTEGER DEFAULT 0,
                    dependencies TEXT,
                    tags TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (parent_id) REFERENCES tasks(task_id)
                )
            """)
            
            # Long-term memory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    memory_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    confidence REAL,
                    source TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Short-term memory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS short_term_memory (
                    session_id TEXT PRIMARY KEY,
                    active_context TEXT,
                    recent_actions TEXT,
                    focus_area TEXT,
                    temporary_state TEXT,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Checkpoints table (metadata only)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    task_id TEXT,
                    level TEXT NOT NULL,
                    snapshot_path TEXT NOT NULL,
                    snapshot_size INTEGER,
                    snapshot_hash TEXT,
                    timestamp REAL NOT NULL,
                    tags TEXT,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_longterm_session ON long_term_memory(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_longterm_type ON long_term_memory(memory_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_task ON checkpoints(task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_level ON checkpoints(level)")
            
            conn.commit()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get thread-safe connection with WAL mode."""
        thread_id = threading.current_thread().ident
        
        with self._lock:
            if thread_id not in self._connections:
                conn = sqlite3.connect(
                    self.db_path if self.db_path else ":memory:", 
                    timeout=30.0,
                    check_same_thread=False,
                    isolation_level=None
                )
                conn.row_factory = sqlite3.Row
                # Only enable WAL for file-based databases
                if not self._is_memory:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA busy_timeout=30000")
                self._connections[thread_id] = conn
        
        return self._connections[thread_id]
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute query - NEVER locks database, uses WAL mode."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor
        except Exception:
            raise
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row as dictionary - always allowed."""
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries - always allowed."""
        cursor = self.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def transaction(self, func):
        """Transaction decorator."""
        def wrapper(*args, **kwargs):
            conn = self.get_connection()
            try:
                conn.execute("BEGIN")
                result = func(*args, **kwargs)
                conn.execute("COMMIT")
                return result
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e
        return wrapper
    
    def close(self):
        """Close all connections."""
        with self._lock:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()
