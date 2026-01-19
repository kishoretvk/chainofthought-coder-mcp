"""
File store for managing JSON snapshot files.
Handles atomic writes, loading, and cleanup of checkpoint snapshots.
"""
import json
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional


class FileStore:
    """Manages JSON snapshot files for checkpoints."""
    
    def __init__(self, base_dir: str = "./memory_store_v2/snapshots"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_snapshot(self, data: Dict[str, Any], checkpoint_id: str) -> str:
        """
        Save snapshot data to JSON file atomically.
        
        Args:
            data: Dictionary to save as JSON
            checkpoint_id: ID for the checkpoint
            
        Returns:
            Path to saved file
        """
        file_path = self.base_dir / f"{checkpoint_id}.json"
        
        # Serialize with proper formatting
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        
        # Write atomically using temp file
        temp_path = file_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        
        # Atomic rename
        temp_path.rename(file_path)
        
        return str(file_path)
    
    def load_snapshot(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load snapshot from JSON file.
        
        Args:
            checkpoint_id: ID of the checkpoint to load
            
        Returns:
            Dictionary or None if not found
        """
        file_path = self.base_dir / f"{checkpoint_id}.json"
        
        if not file_path.exists():
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def delete_snapshot(self, checkpoint_id: str) -> bool:
        """
        Delete a snapshot file.
        
        Args:
            checkpoint_id: ID of the checkpoint to delete
            
        Returns:
            True if deleted, False if not found
        """
        file_path = self.base_dir / f"{checkpoint_id}.json"
        
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def get_file_info(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata.
        
        Args:
            checkpoint_id: ID of the checkpoint
            
        Returns:
            Dictionary with size, modified time, and hash
        """
        file_path = self.base_dir / f"{checkpoint_id}.json"
        
        if not file_path.exists():
            return None
        
        stat = file_path.stat()
        
        # Calculate hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        return {
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "hash": file_hash
        }
    
    def cleanup_orphaned(self, valid_checkpoint_ids: set) -> int:
        """
        Remove snapshot files not in the valid set.
        
        Args:
            valid_checkpoint_ids: Set of valid checkpoint IDs
            
        Returns:
            Number of files deleted
        """
        deleted = 0
        
        for file_path in self.base_dir.glob("*.json"):
            checkpoint_id = file_path.stem
            if checkpoint_id not in valid_checkpoint_ids:
                file_path.unlink()
                deleted += 1
        
        return deleted
    
    def list_snapshots(self) -> list:
        """List all snapshot files."""
        return [f.stem for f in self.base_dir.glob("*.json")]
