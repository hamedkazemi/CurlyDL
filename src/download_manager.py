"""
Main Download Manager class that coordinates all components
"""
import atexit
import logging
from typing import Optional, Dict, Any
from .engine import DownloadEngine
from .filesystem import FileSystemManager, FileSystemError
from .metadata import MetadataManager, DownloadState, MetadataError
from .error_handler import ErrorHandler, ErrorCategory

class DownloadManager:
    def __init__(
        self,
        max_workers: int = 4,
        user_agent: Optional[str] = None,
        min_free_space: int = 1024 * 1024 * 100,  # 100MB
        log_file: Optional[str] = None
    ):
        """
        Initialize the Download Manager with its core components
        
        Args:
            max_workers (int): Maximum number of concurrent download threads
            user_agent (str, optional): Custom User-Agent string for requests
            min_free_space (int): Minimum required free space in bytes
            log_file (str, optional): Path to log file
        """
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

        # Initialize components with custom error handlers
        self.error_handler = ErrorHandler(
            max_retries=3,
            log_file=log_file,
            custom_handlers={
                ErrorCategory.FILESYSTEM: self._handle_filesystem_error,
                ErrorCategory.NETWORK: self._handle_network_error,
                ErrorCategory.RESOURCE: self._handle_resource_error
            }
        )
        
        self.filesystem = FileSystemManager(min_free_space=min_free_space)
        self.metadata = MetadataManager()
        self.engine = DownloadEngine(
            max_workers=max_workers,
            error_handler=self.error_handler,
            filesystem=self.filesystem,
            metadata=self.metadata,
            user_agent=user_agent
        )
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
        
        self.logger.info("Download Manager initialized successfully")

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
            self.logger.info(f"Starting download from {url} to {output_path}")
            
            # Start the download
            download_id = self.engine.start_download(url, output_path)
            
            self.logger.info(f"Download started successfully with ID: {download_id}")
            return download_id
            
        except Exception as e:
            self.logger.error(f"Failed to start download: {str(e)}", exc_info=True)
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
        try:
            return self.metadata.get_progress(download_id)
        except MetadataError as e:
            self.logger.warning(f"Failed to get progress for download {download_id}: {str(e)}")
            return 0.0

    def get_download_state(self, download_id: str) -> DownloadState:
        """
        Get the current state of a download
        
        Args:
            download_id (str): ID of the download to check
            
        Returns:
            DownloadState: Current state of the download
        """
        try:
            return self.metadata.get_state(download_id)
        except MetadataError as e:
            self.logger.warning(f"Failed to get state for download {download_id}: {str(e)}")
            return DownloadState.FAILED

    def get_download_stats(self, download_id: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a download
        
        Args:
            download_id (str): ID of the download
            
        Returns:
            Dict[str, Any]: Dictionary containing download statistics
        """
        try:
            return {
                "progress": self.get_progress(download_id),
                "state": self.get_download_state(download_id),
                "speed": self.metadata.get_speed_stats(download_id),
                "bytes_downloaded": self.engine.get_bytes_downloaded(download_id)
            }
        except Exception as e:
            self.logger.warning(f"Failed to get stats for download {download_id}: {str(e)}")
            return {
                "progress": 0.0,
                "state": DownloadState.FAILED,
                "speed": {"current_speed": 0.0, "average_speed": 0.0, "peak_speed": 0.0},
                "bytes_downloaded": 0
            }

    def is_complete(self, download_id: str) -> bool:
        """
        Check if a download is complete
        
        Args:
            download_id (str): ID of the download to check
            
        Returns:
            bool: True if download is complete, False otherwise
        """
        try:
            return self.metadata.is_complete(download_id)
        except MetadataError as e:
            self.logger.warning(f"Failed to check completion status for download {download_id}: {str(e)}")
            return False

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
        try:
            return self.filesystem.verify_checksum(download_id, algorithm, expected)
        except FileSystemError as e:
            self.logger.error(f"Failed to verify checksum for download {download_id}: {str(e)}")
            return False

    def cancel_download(self, download_id: str) -> None:
        """
        Cancel an active download
        
        Args:
            download_id (str): ID of the download to cancel
        """
        try:
            self.logger.info(f"Cancelling download {download_id}")
            self.engine.cancel_download(download_id)
            self.metadata.update_state(download_id, DownloadState.CANCELLED)
        except Exception as e:
            self.logger.error(f"Failed to cancel download {download_id}: {str(e)}")

    def cancel_all(self) -> None:
        """
        Cancel all active downloads
        """
        self.logger.info("Cancelling all active downloads")
        self.engine.cancel_all()

    def cleanup(self) -> None:
        """
        Clean up resources and cancel active downloads
        """
        try:
            self.logger.info("Cleaning up Download Manager resources")
            self.cancel_all()
            self.engine.shutdown()
            self.metadata.cleanup_old_metadata()
            self.filesystem.cleanup()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")

    def _handle_filesystem_error(self, download_id: str, error: Exception) -> None:
        """Handle filesystem-related errors"""
        self.logger.error(f"Filesystem error for download {download_id}: {str(error)}")
        self.metadata.record_error(download_id, str(error))
        self.metadata.update_state(download_id, DownloadState.FAILED)

    def _handle_network_error(self, download_id: str, error: Exception) -> None:
        """Handle network-related errors"""
        self.logger.error(f"Network error for download {download_id}: {str(error)}")
        self.metadata.record_error(download_id, str(error))
        # Network errors might be temporary, so don't mark as failed immediately

    def _handle_resource_error(self, download_id: str, error: Exception) -> None:
        """Handle resource-related errors"""
        self.logger.error(f"Resource error for download {download_id}: {str(error)}")
        self.metadata.record_error(download_id, str(error))
        self.metadata.update_state(download_id, DownloadState.FAILED)

    def __del__(self):
        """Cleanup on deletion"""
        self.cleanup()
