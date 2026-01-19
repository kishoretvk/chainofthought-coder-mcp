"""
Memory manager for long-term and short-term memory operations.
"""
import time
import hashlib
import json
from typing import Optional, List, Dict, Any
from ..core.database import Database


class MemoryManager:
    """Manages long-term and short-term memory."""
    
    def __init__(self, db: Database):
        self.db = db
    
    # Long-term Memory
    def store_long_term(self, session_id: str, memory_type: str,
                       content: Dict[str, Any], tags: List[str] = None,
                       confidence: float = 1.0, source: str = "") -> int:
        """
        Store long-term memory.
        
        Args:
            session_id: Session ID (None for global)
            memory_type: Type of memory (knowledge, pattern, insight, context)
            content: Memory content dictionary
            tags: Optional tags for search
            confidence: Confidence score (0.0 to 1.0)
            source: Source of the memory
            
        Returns:
            Memory ID
        """
        content_str = json.dumps(content, sort_keys=True)
        content_hash = hashlib.md5(content_str.encode()).hexdigest()
        
        # Check for duplicates
        existing = self.db.fetch_one("""
            SELECT id FROM long_term_memory 
            WHERE session_id = ? AND content_hash = ?
        """, (session_id, content_hash))
        
        if existing:
            return existing['id']
        
        now = time.time()
        
        cursor = self.db.execute("""
            INSERT INTO long_term_memory 
            (session_id, memory_type, content_hash, content, tags, confidence, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, memory_type, content_hash, content_str,
              json.dumps(tags or []), confidence, source, now))
        
        return cursor.lastrowid
    
    def retrieve_long_term(self, session_id: str, query: str = None,
                          memory_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve long-term memory with optional filters.
        
        Args:
            session_id: Session ID
            query: Text search query
            memory_type: Filter by memory type
            limit: Maximum results
            
        Returns:
            List of memory dictionaries
        """
        sql = "SELECT * FROM long_term_memory WHERE session_id = ?"
        params = [session_id]
        
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        
        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")
        
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        results = self.db.fetch_all(sql, params)
        
        # Parse JSON content back to dict
        for result in results:
            result['content'] = json.loads(result['content'])
            result['tags'] = json.loads(result['tags']) if result['tags'] else []
        
        return results
    
    def get_patterns(self, session_id: str, pattern_type: str) -> List[Dict[str, Any]]:
        """
        Get recurring patterns.
        
        Args:
            session_id: Session ID
            pattern_type: Type of pattern
            
        Returns:
            List of patterns with counts
        """
        return self.db.fetch_all("""
            SELECT content, COUNT(*) as count, AVG(confidence) as avg_confidence
            FROM long_term_memory
            WHERE session_id = ? AND memory_type = ?
            GROUP BY content_hash
            HAVING count > 1
            ORDER BY count DESC
        """, (session_id, pattern_type))
    
    # Short-term Memory
    def store_short_term(self, session_id: str, active_context: Dict = None,
                        recent_actions: List[Dict] = None, focus_area: str = None,
                        temporary_state: Dict = None):
        """
        Store short-term (working) memory.
        
        Args:
            session_id: Session ID
            active_context: Current working context
            recent_actions: Recent actions taken
            focus_area: Current focus
            temporary_state: Temporary data
        """
        now = time.time()
        
        # Check if exists
        existing = self.db.fetch_one(
            "SELECT session_id FROM short_term_memory WHERE session_id = ?",
            (session_id,)
        )
        
        if existing:
            self.db.execute("""
                UPDATE short_term_memory 
                SET active_context = ?, recent_actions = ?, focus_area = ?, 
                    temporary_state = ?, updated_at = ?
                WHERE session_id = ?
            """, (
                json.dumps(active_context or {}),
                json.dumps(recent_actions or []),
                focus_area,
                json.dumps(temporary_state or {}),
                now,
                session_id
            ))
        else:
            self.db.execute("""
                INSERT INTO short_term_memory 
                (session_id, active_context, recent_actions, focus_area, temporary_state, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                json.dumps(active_context or {}),
                json.dumps(recent_actions or []),
                focus_area,
                json.dumps(temporary_state or {}),
                now
            ))
    
    def get_short_term(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve short-term memory.
        
        Args:
            session_id: Session ID
            
        Returns:
            Short-term memory dictionary or None
        """
        result = self.db.fetch_one(
            "SELECT * FROM short_term_memory WHERE session_id = ?",
            (session_id,)
        )
        
        if result:
            result['active_context'] = json.loads(result['active_context'] or "{}")
            result['recent_actions'] = json.loads(result['recent_actions'] or "[]")
            result['temporary_state'] = json.loads(result['temporary_state'] or "{}")
        
        return result
    
    def push_context(self, session_id: str, context: Dict[str, Any]):
        """
        Add to working context.
        
        Args:
            session_id: Session ID
            context: Context to add
        """
        short_term = self.get_short_term(session_id) or {}
        contexts = short_term.get('active_context', {})
        
        # Merge new context
        contexts.update(context)
        
        # Store with all existing data preserved
        self.store_short_term(
            session_id,
            active_context=contexts,
            recent_actions=short_term.get('recent_actions'),
            focus_area=short_term.get('focus_area'),
            temporary_state=short_term.get('temporary_state')
        )
    
    def push_action(self, session_id: str, action: Dict[str, Any]):
        """
        Add recent action.
        
        Args:
            session_id: Session ID
            action: Action to add
        """
        # Get current state
        short_term = self.get_short_term(session_id)
        
        if short_term is None:
            # No existing short-term memory, create with just the action
            self.store_short_term(
                session_id,
                recent_actions=[action]
            )
        else:
            # Get existing actions
            actions = short_term.get('recent_actions', [])
            
            # Keep last 10 actions
            actions.append(action)
            actions = actions[-10:]
            
            # Store with other existing data
            self.store_short_term(
                session_id,
                active_context=short_term.get('active_context'),
                recent_actions=actions,
                focus_area=short_term.get('focus_area'),
                temporary_state=short_term.get('temporary_state')
            )
    
    def clear_short_term(self, session_id: str):
        """
        Clear working memory.
        
        Args:
            session_id: Session ID
        """
        self.db.execute(
            "DELETE FROM short_term_memory WHERE session_id = ?",
            (session_id,)
        )
