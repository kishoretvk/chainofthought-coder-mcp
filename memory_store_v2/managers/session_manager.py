"""
Session manager for creating and managing thinking sessions.
"""
import time
import uuid
import json
from typing import Optional, List, Dict, Any
from ..core.database import Database


class SessionManager:
    """Manages thinking sessions."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, name: str, metadata: Dict[str, Any] = None) -> str:
        """
        Create a new session.
        
        Args:
            name: Session name
            metadata: Optional metadata dictionary
            
        Returns:
            Session ID
        """
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        now = time.time()
        
        self.db.execute("""
            INSERT INTO sessions 
            (session_id, name, status, created_at, updated_at, metadata)
            VALUES (?, ?, 'active', ?, ?, ?)
        """, (session_id, name, now, now, json.dumps(metadata or {})))
        
        return session_id
    
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session dictionary or None
        """
        return self.db.fetch_one(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,)
        )
    
    def list(self, status: str = None) -> List[Dict[str, Any]]:
        """
        List sessions with optional status filter.
        
        Args:
            status: Filter by status (active, paused, archived)
            
        Returns:
            List of session dictionaries
        """
        if status:
            return self.db.fetch_all(
                "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC",
                (status,)
            )
        return self.db.fetch_all("SELECT * FROM sessions ORDER BY created_at DESC")
    
    def update(self, session_id: str, status: str = None, metadata: Dict = None):
        """
        Update session.
        
        Args:
            session_id: Session ID
            status: New status
            metadata: New metadata
        """
        updates = []
        params = []
        
        if status:
            updates.append("status = ?")
            params.append(status)
        
        if metadata:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        
        if updates:
            updates.append("updated_at = ?")
            params.append(time.time())
            params.append(session_id)
            
            self.db.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?",
                params
            )
    
    def delete(self, session_id: str) -> bool:
        """
        Delete session and all related data.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful
        """
        try:
            # Use transaction
            with self.db.get_connection() as conn:
                conn.execute("BEGIN")
                
                # Delete in correct order to avoid FK issues
                conn.execute("DELETE FROM checkpoints WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM short_term_memory WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM long_term_memory WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM tasks WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                
                conn.commit()
            return True
        except Exception:
            return False
    
    def archive(self, session_id: str) -> bool:
        """
        Archive session (soft delete).
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful
        """
        self.update(session_id, status="archived")
        return True
