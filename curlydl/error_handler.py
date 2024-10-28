"""
Error Handler component for managing exceptions and retries
"""
import logging
import time
from typing import Optional, Any, Callable, TypeVar, Dict, List, Union
from enum import Enum
import traceback
import sys
import random


T = TypeVar('T')

class ErrorCategory(Enum):
    """Categories of errors that can occur during downloads"""
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    PERMISSION = "permission"
    AUTHENTICATION = "authentication"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    VALIDATION = "validation"
    UNKNOWN = "unknown"

class DownloadError(Exception):
    """Custom exception class for download-related errors"""
    def __init__(self, message: str, category: ErrorCategory, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.category = category
        self.original_error = original_error
        self.timestamp = time.time()

class RetryStrategy:
    """Configurable retry strategy"""
    def __init__(
        self,
        max_retries: int,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential: bool = True,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential = exponential
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the current attempt"""
        if self.exponential:
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        else:
            delay = self.base_delay

        if self.jitter:
            delay *= (0.5 + random.random())

        return delay

class ErrorHandler:
    def __init__(
        self,
        max_retries: int = 3,
        log_file: Optional[str] = None,
        custom_handlers: Optional[Dict[ErrorCategory, Callable]] = None
    ):
        """
        Initialize the Error Handler
        
        Args:
            max_retries (int): Maximum number of retry attempts
            log_file (str, optional): Path to log file
            custom_handlers (Dict[ErrorCategory, Callable], optional): Custom error handlers
        """
        self.retry_strategies: Dict[ErrorCategory, RetryStrategy] = {
            ErrorCategory.NETWORK: RetryStrategy(max_retries=5, base_delay=1.0),
            ErrorCategory.TIMEOUT: RetryStrategy(max_retries=3, base_delay=2.0),
            ErrorCategory.RESOURCE: RetryStrategy(max_retries=2, base_delay=5.0),
            ErrorCategory.AUTHENTICATION: RetryStrategy(max_retries=1, base_delay=0.0),  # Don't retry auth errors
            ErrorCategory.UNKNOWN: RetryStrategy(max_retries=max_retries, base_delay=1.0)
        }
        
        self.custom_handlers = custom_handlers or {}
        self.logger = logging.getLogger(__name__)
        self._setup_logging(log_file)
        self.error_history: Dict[str, List[DownloadError]] = {}

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """
        Categorize an error based on its type and message
        
        Args:
            error (Exception): The error to categorize
            
        Returns:
            ErrorCategory: The category of the error
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # Network-related errors
        if any(term in error_type.lower() for term in ['timeout', 'connection', 'network', 'socket']):
            return ErrorCategory.NETWORK
        
        # Filesystem-related errors
        if any(term in error_type.lower() for term in ['io', 'file', 'disk', 'storage']):
            return ErrorCategory.FILESYSTEM
        
        # Permission-related errors
        if any(term in error_msg for term in ['permission', 'access denied', 'forbidden']):
            return ErrorCategory.PERMISSION
        
        # Authentication-related errors
        if any(term in error_msg for term in ['unauthorized', 'authentication', 'login']):
            return ErrorCategory.AUTHENTICATION
        
        # Timeout-related errors
        if 'timeout' in error_msg:
            return ErrorCategory.TIMEOUT
        
        # Resource-related errors
        if any(term in error_msg for term in ['memory', 'disk space', 'quota']):
            return ErrorCategory.RESOURCE
        
        # Validation-related errors
        if any(term in error_msg for term in ['invalid', 'malformed', 'corrupt']):
            return ErrorCategory.VALIDATION

        return ErrorCategory.UNKNOWN

    def handle_error(self, download_id: str, error: Exception) -> None:
        """
        Handle an error that occurred during download
        
        Args:
            download_id (str): ID of the download that encountered the error
            error (Exception): The error that occurred
        """
        category = self.categorize_error(error)
        download_error = DownloadError(str(error), category, error)
        
        # Store error in history
        if download_id not in self.error_history:
            self.error_history[download_id] = []
        self.error_history[download_id].append(download_error)
        
        # Log detailed error information
        self._log_error(download_id, download_error)
        
        # Execute custom handler if available
        if category in self.custom_handlers:
            try:
                self.custom_handlers[category](download_id, download_error)
            except Exception as handler_error:
                self.logger.error(
                    f"Custom error handler for {category.value} failed: {str(handler_error)}",
                    exc_info=True
                )

    def retry_with_backoff(
        self,
        func: Callable[..., T],
        error_category: ErrorCategory,
        *args: Any,
        **kwargs: Any
    ) -> Optional[T]:
        """
        Retry a function with exponential backoff based on error category
        
        Args:
            func: Function to retry
            error_category: Category of error to handle
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Optional[T]: Result of the function if successful
            
        Raises:
            Exception: The last error encountered after all retries
        """
        strategy = self.retry_strategies.get(error_category, self.retry_strategies[ErrorCategory.UNKNOWN])
        last_error = None
        
        for attempt in range(strategy.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < strategy.max_retries - 1:
                    delay = strategy.get_delay(attempt)
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed for {error_category.value} error, "
                        f"retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"All retry attempts failed for function {func.__name__} "
                        f"with {error_category.value} error",
                        exc_info=True
                    )
        
        if last_error:
            raise last_error

    def get_error_history(self, download_id: str) -> List[DownloadError]:
        """
        Get the error history for a specific download
        
        Args:
            download_id (str): ID of the download
            
        Returns:
            List[DownloadError]: List of errors encountered during the download
        """
        return self.error_history.get(download_id, [])

    def clear_error_history(self, download_id: str) -> None:
        """
        Clear the error history for a specific download
        
        Args:
            download_id (str): ID of the download
        """
        self.error_history.pop(download_id, None)

    def _log_error(self, download_id: str, error: DownloadError) -> None:
        """Log detailed error information"""
        error_info = {
            'download_id': download_id,
            'error_category': error.category.value,
            'error_message': str(error),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(error.timestamp)),
            'traceback': ''.join(traceback.format_exception(*sys.exc_info())) if error.original_error else None
        }
        
        self.logger.error(
            "Download Error:\n" + \
            f"Download ID: {error_info['download_id']}\n" + \
            f"Category: {error_info['error_category']}\n" + \
            f"Message: {error_info['error_message']}\n" + \
            f"Time: {error_info['timestamp']}\n" + \
            (f"Traceback:\n{error_info['traceback']}" if error_info['traceback'] else "")
        )

    def _setup_logging(self, log_file: Optional[str] = None) -> None:
        """
        Setup logging configuration
        
        Args:
            log_file (str, optional): Path to log file
        """
        handlers: List[Union[logging.Handler, logging.StreamHandler]] = [
            logging.StreamHandler(sys.stdout)
        ]
        
        if log_file:
            handlers.append(logging.FileHandler(log_file))
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
