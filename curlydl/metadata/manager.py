"""
Main metadata manager coordinating metadata operations
"""
import time
from typing import Dict, Any
from datetime import datetime, timezone

from .models import (
    DownloadState,
    SegmentInfo,
    SpeedStats,
    DownloadMetadata
)
from .storage import MetadataStorage
from .exceptions import (
    MetadataError,
    MetadataStateError,
    MetadataValidationError
)

class MetadataManager:
    """Coordinates metadata operations for downloads"""
    
    def __init__(self, base_dir: str = "downloads_metadata", cache_ttl: int = 300):
        """
        Initialize the Metadata Manager
        
        Args:
            base_dir (str): Base directory for metadata storage
            cache_ttl (int): Cache time-to-live in seconds
        """
        self.storage = MetadataStorage(base_dir, cache_ttl)

    def create_download(self, download_id: str, url: str, output_path: str, resume_supported: bool = False) -> None:
        """
        Create metadata for a new download
        
        Args:
            download_id (str): Unique identifier for the download
            url (str): URL being downloaded
            output_path (str): Where the file will be saved
            resume_supported (bool): Whether the server supports resume
        """
        metadata = DownloadMetadata(
            url=url,
            output_path=output_path,
            total_size=0,
            downloaded_bytes=0,
            state=DownloadState.INITIALIZING,
            resume_supported=resume_supported
        )
        
        with self.storage.get_lock(download_id):
            self.storage.save(download_id, metadata.to_dict())

    def update_total_size(self, download_id: str, size: int) -> None:
        """
        Update the total size of a download
        
        Args:
            download_id (str): Download identifier
            size (int): Total size in bytes
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            metadata.total_size = size
            metadata.state = DownloadState.DOWNLOADING
            metadata.last_updated = datetime.now(timezone.utc).isoformat()
            self.storage.save(download_id, metadata.to_dict())

    def add_segment(self, download_id: str, start: int, end: int) -> None:
        """
        Add a new segment to track
        
        Args:
            download_id (str): Download identifier
            start (int): Start byte of segment
            end (int): End byte of segment
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            segment = SegmentInfo(start=start, end=end, status="pending")
            metadata.segments.append(segment)
            self.storage.save(download_id, metadata.to_dict())

    def update_segment(self, download_id: str, start: int, end: int, status: str) -> None:
        """
        Update the status of a segment
        
        Args:
            download_id (str): Download identifier
            start (int): Start byte of segment
            end (int): End byte of segment
            status (str): New status of segment
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            for segment in metadata.segments:
                if segment.start == start and segment.end == end:
                    segment.status = status
                    if status == "complete":
                        segment.completed_at = datetime.now(timezone.utc).isoformat()
                    break
            self.storage.save(download_id, metadata.to_dict())

    def update_progress(self, download_id: str, bytes_downloaded: int, total_bytes: int) -> None:
        """
        Update the progress of a download
        
        Args:
            download_id (str): Download identifier
            bytes_downloaded (int): Total bytes downloaded
            total_bytes (int): Total bytes to download
        """
        with self.storage.get_lock(download_id):
            try:
                metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
                
                # Update downloaded bytes
                metadata.downloaded_bytes = bytes_downloaded
                
                # Update speed statistics
                current_time = time.time()
                time_diff = current_time - metadata.speed_stats.last_update
                
                if time_diff >= 1.0:  # Update speed every second
                    bytes_diff = bytes_downloaded - metadata.speed_stats.last_bytes
                    current_speed = bytes_diff / time_diff if time_diff > 0 else 0
                    
                    # Update speed history
                    metadata.speed_stats.add_speed(current_speed)
                    metadata.speed_stats.last_update = current_time
                    metadata.speed_stats.last_bytes = bytes_downloaded
                
                metadata.last_updated = datetime.now(timezone.utc).isoformat()
                self.storage.save(download_id, metadata.to_dict())
                
            except Exception as e:
                raise MetadataError(f"Failed to update progress: {str(e)}")

    def get_progress(self, download_id: str) -> float:
        """
        Get the current progress of a download
        
        Args:
            download_id (str): Download identifier
                
        Returns:
            float: Progress percentage (0-100)
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            if metadata.total_size == 0:
                return 0.0
            return min(100.0, (metadata.downloaded_bytes / metadata.total_size) * 100)

    def get_speed_stats(self, download_id: str) -> Dict[str, float]:
        """
        Get speed statistics for a download
        
        Args:
            download_id (str): Download identifier
                
        Returns:
            Dict[str, float]: Dictionary containing current, average, and peak speeds
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            return {
                "current_speed": metadata.speed_stats.current_speed,
                "average_speed": metadata.speed_stats.average_speed,
                "peak_speed": metadata.speed_stats.peak_speed
            }

    def get_state(self, download_id: str) -> DownloadState:
        """
        Get the current state of a download
        
        Args:
            download_id (str): Download identifier
                
        Returns:
            DownloadState: Current state of the download
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            return metadata.state

    def update_state(self, download_id: str, state: DownloadState) -> None:
        """
        Update the state of a download
        
        Args:
            download_id (str): Download identifier
            state (DownloadState): New state
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            
            # Validate state transition
            if not self._is_valid_state_transition(metadata.state, state):
                raise MetadataStateError(
                    f"Invalid state transition from {metadata.state.value} to {state.value}"
                )
            
            metadata.state = state
            metadata.last_updated = datetime.now(timezone.utc).isoformat()
            self.storage.save(download_id, metadata.to_dict())

    def record_error(self, download_id: str, error: str) -> None:
        """
        Record an error for a download
        
        Args:
            download_id (str): Download identifier
            error (str): Error message
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            metadata.error_count += 1
            metadata.last_error = error
            metadata.last_updated = datetime.now(timezone.utc).isoformat()
            self.storage.save(download_id, metadata.to_dict())

    def is_complete(self, download_id: str) -> bool:
        """
        Check if a download is complete
        
        Args:
            download_id (str): Download identifier
                
        Returns:
            bool: True if download is complete, False otherwise
        """
        with self.storage.get_lock(download_id):
            metadata = DownloadMetadata.from_dict(self.storage.load(download_id))
            return metadata.state == DownloadState.COMPLETE

    def mark_complete(self, download_id: str) -> None:
        """
        Mark a download as complete
        
        Args:
            download_id (str): Download identifier
        """
        self.update_state(download_id, DownloadState.COMPLETE)

    def cleanup_old_metadata(self, max_age_days: int = 7) -> None:
        """
        Clean up metadata files older than specified days
        
        Args:
            max_age_days (int): Maximum age of metadata files in days
        """
        self.storage.cleanup_old_metadata(max_age_days)

    def _is_valid_state_transition(self, current: DownloadState, new: DownloadState) -> bool:
        """
        Check if a state transition is valid
        
        Args:
            current (DownloadState): Current state
            new (DownloadState): New state
            
        Returns:
            bool: True if transition is valid, False otherwise
        """
        # Define valid state transitions
        valid_transitions = {
            DownloadState.INITIALIZING: {
                DownloadState.DOWNLOADING,
                DownloadState.FAILED,
                DownloadState.CANCELLED
            },
            DownloadState.DOWNLOADING: {
                DownloadState.PAUSED,
                DownloadState.ASSEMBLING,
                DownloadState.FAILED,
                DownloadState.CANCELLED
            },
            DownloadState.PAUSED: {
                DownloadState.DOWNLOADING,
                DownloadState.FAILED,
                DownloadState.CANCELLED
            },
            DownloadState.ASSEMBLING: {
                DownloadState.COMPLETE,
                DownloadState.FAILED,
                DownloadState.CANCELLED
            },
            # Terminal states
            DownloadState.COMPLETE: set(),
            DownloadState.FAILED: {DownloadState.DOWNLOADING},  # Allow retry
            DownloadState.CANCELLED: {DownloadState.DOWNLOADING}  # Allow restart
        }
        
        return new in valid_transitions.get(current, set())

    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.cleanup_old_metadata()
        except:
            pass
