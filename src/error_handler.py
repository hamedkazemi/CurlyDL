"""
Error Handler component for managing exceptions and retries
"""
import logging
import time
from typing import Optional, Any, Callable, TypeVar

T = TypeVar('T')

class ErrorHandler:
    def __init__(self, max_retries: int = 3):
        """
        Initialize the Error Handler
        
        Args:
            max_retries (int): Maximum number of retry attempts
        """
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

    def handle_error(self, download_id: str, error: Exception) -> None:
        """
        Handle an error that occurred during download
        
        Args:
            download_id (str): ID of the download that encountered the error
            error (Exception): The error that occurred
        """
        self.logger.error(
            f"Download {download_id} encountered error: {str(error)}",
            exc_info=True
        )

    def retry_with_backoff(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Optional[T]:
        """
        Retry a function with exponential backoff
        
        Args:
            func: Function to retry
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Optional[T]: Result of the function if successful
            
        Raises:
            Exception: The last error encountered after all retries
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) + 1  # Exponential backoff
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(
                        f"All retry attempts failed for function {func.__name__}",
                        exc_info=True
                    )
        
        if last_error:
            raise last_error

    def _setup_logging(self) -> None:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
