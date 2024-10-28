"""
Metadata Manager component handling download state and progress
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, UTC

class MetadataManager:
    def __init__(self):
        """Initialize the Metadata Manager"""
        self.metadata_dir = Path("downloads_metadata")
        self.metadata_dir.mkdir(exist_ok=True, parents=True)
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

    def create_download(self, download_id: str, url: str, output_path: str) -> None:
        """
        Create metadata for a new download
        
        Args:
            download_id (str): Unique identifier for the download
            url (str): URL being downloaded
            output_path (str): Where the file will be saved
        """
        metadata = {
            "url": url,
            "output_path": output_path,
            "total_size": 0,
            "downloaded_bytes": 0,
            "status": "initializing",
            "segments": [],
            "created_at": datetime.now(UTC).isoformat(),
            "last_updated": datetime.now(UTC).isoformat()
        }
        self._metadata_cache[download_id] = metadata
        self._save_metadata(download_id, metadata)

    def update_total_size(self, download_id: str, size: int) -> None:
        """
        Update the total size of a download
        
        Args:
            download_id (str): Download identifier
            size (int): Total size in bytes
        """
        metadata = self._get_metadata(download_id)
        metadata["total_size"] = size
        metadata["last_updated"] = datetime.now(UTC).isoformat()
        self._save_metadata(download_id, metadata)

    def update_progress(self, download_id: str, start: int, end: int) -> None:
        """
        Update the progress of a download segment
        
        Args:
            download_id (str): Download identifier
            start (int): Start byte of completed segment
            end (int): End byte of completed segment
        """
        try:
            metadata = self._get_metadata(download_id)
            segment_size = end - start + 1
            metadata["downloaded_bytes"] += segment_size
            metadata["last_updated"] = datetime.now(UTC).isoformat()
            self._save_metadata(download_id, metadata)
        except Exception:
            # Ignore errors during progress updates
            pass

    def get_progress(self, download_id: str) -> float:
        """
        Get the current progress of a download
        
        Args:
            download_id (str): Download identifier
            
        Returns:
            float: Progress percentage (0-100)
        """
        metadata = self._get_metadata(download_id)
        if metadata["total_size"] == 0:
            return 0.0
        return min(100.0, (metadata["downloaded_bytes"] / metadata["total_size"]) * 100)

    def is_complete(self, download_id: str) -> bool:
        """
        Check if a download is complete
        
        Args:
            download_id (str): Download identifier
            
        Returns:
            bool: True if download is complete, False otherwise
        """
        metadata = self._get_metadata(download_id)
        return metadata["status"] == "complete"

    def mark_complete(self, download_id: str) -> None:
        """
        Mark a download as complete
        
        Args:
            download_id (str): Download identifier
        """
        metadata = self._get_metadata(download_id)
        metadata["status"] = "complete"
        metadata["last_updated"] = datetime.now(UTC).isoformat()
        self._save_metadata(download_id, metadata)

    def _get_metadata_path(self, download_id: str) -> Path:
        """Get the path to the metadata file for a download"""
        return self.metadata_dir / f"{download_id}.json"

    def _save_metadata(self, download_id: str, metadata: Dict[str, Any]) -> None:
        """Save metadata to disk and cache"""
        try:
            self._metadata_cache[download_id] = metadata.copy()
            metadata_path = self._get_metadata_path(download_id)
            metadata_path.parent.mkdir(exist_ok=True, parents=True)
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception:
            # Ignore errors during metadata saves
            pass

    def _get_metadata(self, download_id: str) -> Dict[str, Any]:
        """Get metadata from cache or load from disk"""
        if download_id not in self._metadata_cache:
            try:
                with open(self._get_metadata_path(download_id), 'r') as f:
                    self._metadata_cache[download_id] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                raise ValueError(f"No metadata found for download {download_id}")
        return self._metadata_cache[download_id]
