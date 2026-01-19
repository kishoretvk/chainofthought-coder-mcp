"""
Unified Memory System V2 - Hybrid SQLite + JSON approach.
Combines all managers into a single interface.
"""
from typing import Dict, Any
from .core.database import Database
from .core.file_store import FileStore
from .managers.session_manager import SessionManager
from .managers.task_manager import TaskManager
from .managers.memory_manager import MemoryManager
from .managers.checkpoint_manager import CheckpointManager


class MemorySystemV2:
    """Unified memory system with hierarchical management."""
    
    def __init__(self, base_dir: str = "./memory_store_v2"):
        """
        Initialize the memory system.
        
        Args:
            base_dir: Base directory for storage
        """
        self.db = Database(f"{base_dir}/memory.db")
        self.file_store = FileStore(f"{base_dir}/snapshots")
        
        # Initialize managers
        self.sessions = SessionManager(self.db)
        self.tasks = TaskManager(self.db)
        self.memory = MemoryManager(self.db)
        self.checkpoints = CheckpointManager(
            self.db, self.file_store, self.tasks, self.memory
        )
    
    def close(self):
        """Close all connections."""
        self.db.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get system statistics.
        
        Returns:
            Dictionary with stats
        """
        sessions = self.db.fetch_all("SELECT COUNT(*) as count FROM sessions")[0]['count']
        tasks = self.db.fetch_all("SELECT COUNT(*) as count FROM tasks")[0]['count']
        checkpoints = self.db.fetch_all("SELECT COUNT(*) as count FROM checkpoints")[0]['count']
        long_term = self.db.fetch_all("SELECT COUNT(*) as count FROM long_term_memory")[0]['count']
        
        return {
            "sessions": sessions,
            "tasks": tasks,
            "checkpoints": checkpoints,
            "long_term_memory": long_term
        }
