"""
Storage handler for metadata persistence and caching
"""
import os
import json
import time
import tempfile
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import contextmanager
from .exceptions import MetadataStorageError, MetadataLoadError

class MetadataStorage:
    """Handles metadata storage operations with caching and atomic writes"""
    
    def __init__(self, base_dir: str = "downloads_metadata", cache_ttl: int = 300):
        """
        Initialize the metadata storage
        
        Args:
            base_dir (str): Base directory for metadata storage
            cache_ttl (int): Cache time-to-live in seconds
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True, parents=True)
        self.cache_ttl = cache_ttl
        
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_times: Dict[str, float] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    @contextmanager
    def get_lock(self, metadata_id: str):
        """
        Get or create a lock for a specific metadata entry
        
        Args:
            metadata_id (str): Identifier for the metadata entry
        """
        with self._global_lock:
            if metadata_id not in self._locks:
                self._locks[metadata_id] = threading.Lock()
        try:
            with self._locks[metadata_id]:
                yield
        finally:
            with self._global_lock:
                if metadata_id in self._locks and not self._locks[metadata_id].locked():
                    self._locks.pop(metadata_id)

    def save(self, metadata_id: str, data: Dict[str, Any]) -> None:
        """
        Save metadata to disk and cache atomically
        
        Args:
            metadata_id (str): Identifier for the metadata
            data (Dict[str, Any]): Metadata to save
            
        Raises:
            MetadataStorageError: If save operation fails
        """
        try:
            metadata_path = self._get_path(metadata_id)
            metadata_path.parent.mkdir(exist_ok=True, parents=True)
            
            # Write to temporary file first
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=str(metadata_path.parent),
                delete=False
            ) as temp_file:
                json.dump(data, temp_file, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            
            # Atomically replace the old file
            os.replace(temp_file.name, metadata_path)
            
            # Update cache
            self._metadata_cache[metadata_id] = data.copy()
            self._cache_times[metadata_id] = time.time()
            
        except Exception as e:
            try:
                os.unlink(temp_file.name)
            except:
                pass
            raise MetadataStorageError(f"Failed to save metadata: {str(e)}")

    def load(self, metadata_id: str) -> Dict[str, Any]:
        """
        Load metadata from cache or disk
        
        Args:
            metadata_id (str): Identifier for the metadata
            
        Returns:
            Dict[str, Any]: Loaded metadata
            
        Raises:
            MetadataLoadError: If load operation fails
        """
        # Check if cache is valid
        cache_time = self._cache_times.get(metadata_id, 0)
        if (
            metadata_id in self._metadata_cache
            and time.time() - cache_time < self.cache_ttl
        ):
            return self._metadata_cache[metadata_id]

        try:
            metadata_path = self._get_path(metadata_id)
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                self._metadata_cache[metadata_id] = metadata
                self._cache_times[metadata_id] = time.time()
                return metadata
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise MetadataLoadError(f"Failed to load metadata: {str(e)}")

    def exists(self, metadata_id: str) -> bool:
        """
        Check if metadata exists
        
        Args:
            metadata_id (str): Identifier for the metadata
            
        Returns:
            bool: True if metadata exists, False otherwise
        """
        return self._get_path(metadata_id).exists()

    def delete(self, metadata_id: str) -> None:
        """
        Delete metadata from disk and cache
        
        Args:
            metadata_id (str): Identifier for the metadata
            
        Raises:
            MetadataStorageError: If delete operation fails
        """
        try:
            metadata_path = self._get_path(metadata_id)
            if metadata_path.exists():
                metadata_path.unlink()
            
            # Clear from cache
            self._metadata_cache.pop(metadata_id, None)
            self._cache_times.pop(metadata_id, None)
            
        except Exception as e:
            raise MetadataStorageError(f"Failed to delete metadata: {str(e)}")

    def cleanup_old_metadata(self, max_age_days: int = 7) -> None:
        """
        Clean up metadata files older than specified days
        
        Args:
            max_age_days (int): Maximum age of metadata files in days
            
        Raises:
            MetadataStorageError: If cleanup operation fails
        """
        try:
            current_time = time.time()
            for metadata_file in self.base_dir.glob("*.json"):
                try:
                    if (current_time - metadata_file.stat().st_mtime) > (max_age_days * 86400):
                        metadata_file.unlink()
                        metadata_id = metadata_file.stem
                        self._metadata_cache.pop(metadata_id, None)
                        self._cache_times.pop(metadata_id, None)
                except Exception:
                    continue
        except Exception as e:
            raise MetadataStorageError(f"Failed to cleanup old metadata: {str(e)}")

    def _get_path(self, metadata_id: str) -> Path:
        """Get the path to the metadata file"""
        return self.base_dir / f"{metadata_id}.json"

    def clear_cache(self) -> None:
        """Clear the metadata cache"""
        self._metadata_cache.clear()
        self._cache_times.clear()

    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.cleanup_old_metadata()
        except:
            pass
