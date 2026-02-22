"""
SQLite database wrapper for the hybrid memory system.
Production-ready with proper connection pooling and transaction management.
"""
import sqlite3
import json
import os
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """Custom database error."""
    pass

class Database:
    """
    SQLite database wrapper with connection pooling and schema management.
    
    Features:
    - Thread-safe connection pooling with max limit
    - Transaction support with rollback on failure
    - WAL mode for concurrent reads
    - Automatic connection cleanup
    """
    
    def __init__(self, db_path: str = "./memory_store_v2/memory.db", max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._connections = {}
        self._lock = threading.Lock()
        self._connection_count = 0
        self._semaphore = threading.Semaphore(max_connections)
        self._is_memory = db_path == ":memory:" or db_path.startswith("file:")
        self._closed = False
        self._init_database()
    
    def _init_database(self):
        """Initialize database with schema."""
        if not self._is_memory and self.db_path:
            dir_path = os.path.dirname(self.db_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
        
        # Enable WAL mode with initial connection
        conn = sqlite3.connect(
            self.db_path if self.db_path else ":memory:",
            timeout=30.0
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA busy_timeout=30000")
        conn.commit()
        
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                mode TEXT DEFAULT 'plan',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                metadata TEXT
            )
        """)
        
        # Tasks table
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
                plan_session_id TEXT,
                act_session_id TEXT,
                is_planned INTEGER DEFAULT 0,
                is_executed INTEGER DEFAULT 0,
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
        
        # Checkpoints table
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
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_longterm_session ON long_term_memory(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_longterm_type ON long_term_memory(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_longterm_tags ON long_term_memory(tags)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_level ON checkpoints(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_timestamp ON checkpoints(timestamp)")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database initialized at: {self.db_path}")
    
    @contextmanager
    def get_connection(self) -> sqlite3.Connection:
        """
        Get thread-safe connection with semaphore control.
        
        Yields:
            sqlite3.Connection: Database connection
            
        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """
        if self._closed:
            raise DatabaseError("Database connection pool has been closed")
        
        thread_id = threading.current_thread().ident
        conn = None
        
        # Try to acquire semaphore with timeout
        if not self._semaphore.acquire(timeout=30.0):
            raise DatabaseError("Could not acquire database connection within timeout")
        
        try:
            with self._lock:
                if thread_id in self._connections:
                    conn = self._connections[thread_id]
                else:
                    conn = sqlite3.connect(
                        self.db_path if self.db_path else ":memory:",
                        timeout=30.0,
                        check_same_thread=False,
                        isolation_level=None  # Let us control transactions
                    )
                    conn.row_factory = sqlite3.Row
                    if not self._is_memory:
                        conn.execute("PRAGMA journal_mode=WAL")
                        conn.execute("PRAGMA busy_timeout=30000")
                    self._connections[thread_id] = conn
                    self._connection_count += 1
            
            yield conn
        finally:
            self._semaphore.release()
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute query and return cursor."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row as dictionary."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    @contextmanager
    def transaction(self):
        """
        Transaction context manager with automatic rollback on error.
        
        Usage:
            with db.transaction():
                db.execute("INSERT INTO ...")
                db.execute("UPDATE ...")
                # Automatically committed if no exception
        """
        with self.get_connection() as conn:
            conn.execute("BEGIN")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def close(self):
        """Close all connections and cleanup."""
        with self._lock:
            self._closed = True
            for thread_id, conn in list(self._connections.items()):
                try:
                    conn.close()
                    logger.debug(f"Closed connection for thread {thread_id}")
                except Exception as e:
                    logger.warning(f"Error closing connection for thread {thread_id}: {e}")
            self._connections.clear()
            self._connection_count = 0
            logger.info("Database connection pool closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "path": self.db_path,
            "is_memory": self._is_memory,
            "max_connections": self.max_connections,
            "active_connections": self._connection_count,
            "closed": self._closed
        }
    
    def exec_atomic(self, queries: List[tuple], description: str = "") -> bool:
        """
        Execute multiple queries atomically.
        
        Args:
            queries: List of (query, params) tuples
            description: Description of the operation
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If transaction fails
        """
        with self.transaction():
            for query, params in queries:
                cursor = self.execute(query, params)
                cursor.close()
            if description:
                logger.debug(f"Executed atomic transaction: {description}")
            return True


# Backward compatibility - keep old method names
Database.fetchone = Database.fetch_one
Database.fetchall = Database.fetch_all
