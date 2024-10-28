"""
Main Download Manager class that coordinates all components
"""
import atexit
from typing import Optional, Dict
from .engine import DownloadEngine
from .filesystem import FileSystemManager
from .metadata import MetadataManager
from .error_handler import ErrorHandler

class DownloadManager:
    def __init__(self, max_workers: int = 4, user_agent: Optional[str] = None):
        """
        Initialize the Download Manager with its core components
        
        Args:
            max_workers (int): Maximum number of concurrent download threads
            user_agent (str, optional): Custom User-Agent string for requests
        """
        self.error_handler = ErrorHandler()
        self.filesystem = FileSystemManager()
        self.metadata = MetadataManager()
        self.engine = DownloadEngine(
            max_workers=max_workers,
            error_handler=self.error_handler,
            filesystem=self.filesystem,
            metadata=self.metadata,
            user_agent=user_agent
        )
        self._active_downloads: Dict[str, bool] = {}
        
        # Register cleanup on exit
        atexit.register(self.cleanup)

    def start_download(self, url: str, output_path: str) -> str:
        """
        Start a new download task
        
        Args:
            url (str): URL to download from
            output_path (str): Where to save the downloaded file
            
        Returns:
            str: Download ID for tracking the download
            
        Raises:
            Exception: If the download fails to start or encounters an error
        """
        try:
            download_id = self.engine.start_download(url, output_path)
            self._active_downloads[download_id] = True
            return download_id
        except Exception as e:
            self.error_handler.handle_error("initialization", e)
            raise

    def get_progress(self, download_id: str) -> float:
        """
        Get the progress of a download
        
        Args:
            download_id (str): ID of the download to check
            
        Returns:
            float: Progress percentage (0-100)
        """
        return self.metadata.get_progress(download_id)

    def is_complete(self, download_id: str) -> bool:
        """
        Check if a download is complete
        
        Args:
            download_id (str): ID of the download to check
            
        Returns:
            bool: True if download is complete, False otherwise
        """
        return self.metadata.is_complete(download_id)

    def verify_checksum(self, download_id: str, algorithm: str, expected: str) -> bool:
        """
        Verify the checksum of a downloaded file
        
        Args:
            download_id (str): ID of the download to verify
            algorithm (str): Hash algorithm to use (e.g., 'SHA256')
            expected (str): Expected checksum value
            
        Returns:
            bool: True if checksum matches, False otherwise
        """
        return self.filesystem.verify_checksum(download_id, algorithm, expected)

    def get_download_speed(self, download_id: str) -> float:
        """
        Get the current download speed in bytes per second
        
        Args:
            download_id (str): ID of the download
            
        Returns:
            float: Current download speed in bytes per second
        """
        return self.engine.get_download_speed(download_id)

    def get_bytes_downloaded(self, download_id: str) -> int:
        """
        Get the total bytes downloaded
        
        Args:
            download_id (str): ID of the download
            
        Returns:
            int: Total bytes downloaded
        """
        return self.engine.get_bytes_downloaded(download_id)

    def cancel_download(self, download_id: str) -> None:
        """
        Cancel an active download
        
        Args:
            download_id (str): ID of the download to cancel
        """
        if download_id in self._active_downloads:
            self._active_downloads[download_id] = False
            self.engine.cancel_download(download_id)

    def cancel_all(self) -> None:
        """
        Cancel all active downloads
        """
        for download_id in list(self._active_downloads.keys()):
            self.cancel_download(download_id)

    def cleanup(self) -> None:
        """
        Clean up resources and cancel active downloads
        """
        try:
            self.cancel_all()
            self.engine.shutdown()
        except:
            pass  # Ensure no exceptions during cleanup
