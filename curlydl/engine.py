"""
Download Engine component handling core downloading logic using libcurl
"""
import uuid
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional, Dict, List
import pycurl
import certifi
from io import BytesIO
from .metadata import DownloadState

class DownloadEngine:
    def __init__(self, max_workers: int, error_handler, filesystem, metadata, user_agent: Optional[str] = None):
        """
        Initialize the Download Engine

        Args:
            max_workers (int): Maximum number of concurrent download threads
            error_handler: Error handling component
            filesystem: File system management component
            metadata: Metadata management component
            user_agent (str, optional): Custom User-Agent string for requests
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.error_handler = error_handler
        self.filesystem = filesystem
        self.metadata = metadata
        self.user_agent = user_agent
        self._active_downloads: Dict[str, bool] = {}
        self._futures: Dict[str, List[Future]] = {}
        self._download_speeds: Dict[str, float] = {}  # Track download speeds
        self._bytes_downloaded: Dict[str, int] = {}   # Track bytes downloaded
        self._last_update_time: Dict[str, float] = {} # Track last update time
        self._lock = threading.Lock()

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
            download_id = str(uuid.uuid4())
            with self._lock:
                self._active_downloads[download_id] = True
                self._futures[download_id] = []
                self._download_speeds[download_id] = 0.0
                self._bytes_downloaded[download_id] = 0
                self._last_update_time[download_id] = time.time()

            self.metadata.create_download(download_id, url, output_path)
            self.filesystem.prepare_download(download_id, output_path)

            # Get file size and check for range support
            total_size, supports_range = self._get_file_size(url)
            if total_size <= 0:
                raise Exception("Failed to get file size")

            self.metadata.update_total_size(download_id, total_size)

            # Submit download task to thread pool
            future = self.executor.submit(self._download_task, download_id, url, output_path, total_size, supports_range)
            with self._lock:
                self._futures[download_id].append(future)
            return download_id

        except Exception as e:
            self.error_handler.handle_error(download_id if 'download_id' in locals() else 'initialization', e)
            raise

    def _get_file_size(self, url: str) -> (int, bool):
        buffer = BytesIO()
        headers = {}

        def header_function(header_line):
            header_line = header_line.decode('iso-8859-1')
            if ':' in header_line:
                name, value = header_line.split(':', 1)
                headers[name.strip().lower()] = value.strip()

        c = pycurl.Curl()

        try:
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.NOBODY, 1)
            c.setopt(pycurl.WRITEDATA, buffer)
            c.setopt(pycurl.HEADERFUNCTION, header_function)
            c.setopt(pycurl.CAINFO, certifi.where())
            c.setopt(pycurl.FOLLOWLOCATION, 1)
            c.setopt(pycurl.MAXREDIRS, 5)

            if self.user_agent:
                c.setopt(pycurl.USERAGENT, self.user_agent)

            c.perform()

            response_code = c.getinfo(pycurl.RESPONSE_CODE)
            if response_code not in (200, 206):
                raise Exception(f"Failed to get file size: HTTP {response_code}")

            content_length = c.getinfo(pycurl.CONTENT_LENGTH_DOWNLOAD)

            supports_range = headers.get('accept-ranges', '').lower() != 'none'

            return int(content_length) if content_length > 0 else 0, supports_range

        except Exception as e:
            raise Exception(f"Failed to get file size: {str(e)}")
        finally:
            c.close()

    def _calculate_segment_size(self, total_size: int) -> int:
        """Calculate optimal segment size based on total file size"""
        if total_size <= 1024 * 1024:  # 1MB
            return total_size
        return max(1024 * 1024, total_size // self.executor._max_workers)  # At least 1MB segments

    def _create_segments(self, total_size: int, segment_size: int) -> list:
        """Create download segments based on file size"""
        segments = []
        for start in range(0, total_size, segment_size):
            end = min(start + segment_size - 1, total_size - 1)
            segments.append({'start': start, 'end': end})
        return segments

    def _download_segment(self, download_id: str, url: str, start: int, end: int) -> None:
        """Download a specific segment of the file using libcurl"""
        if not self._active_downloads.get(download_id, False):
            return

        c = None
        try:
            c = pycurl.Curl()
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.RANGE, f'{start}-{end}')
            c.setopt(pycurl.CAINFO, certifi.where())  # SSL certificate verification

            # Set custom User-Agent if provided
            if self.user_agent:
                c.setopt(pycurl.USERAGENT, self.user_agent)

            # Setup write callback
            def write_callback(data: bytes) -> int:
                if not self._active_downloads.get(download_id, False):
                    return -1  # Abort transfer
                try:
                    self.filesystem.write_segment(download_id, start, data)
                    # Update bytes downloaded and progress immediately
                    with self._lock:
                        self._bytes_downloaded[download_id] += len(data)
                        current_time = time.time()
                        time_diff = current_time - self._last_update_time[download_id]
                        if time_diff > 0:  # Update speed on every write
                            speed = len(data) / time_diff
                            self._download_speeds[download_id] = speed
                            self._last_update_time[download_id] = current_time
                        # Update progress immediately
                        self.metadata.update_progress(download_id, self._bytes_downloaded[download_id], end - start + 1)
                    return len(data)
                except Exception as e:
                    raise e  # Properly raise the exception

            c.setopt(pycurl.WRITEFUNCTION, write_callback)

            # Setup progress callback
            def progress_callback(total_downloaded, total_to_download, upload_total, upload_now):
                # Parameters renamed to match PycURL documentation
                # total_downloaded: Total number of bytes downloaded so far
                # total_to_download: Total expected bytes to download
                if not self._active_downloads.get(download_id, False):
                    return 1  # Abort transfer
                try:
                    if total_to_download > 0:
                        self.metadata.update_progress(download_id, self._bytes_downloaded[download_id], total_to_download)
                        # Update download speed
                        with self._lock:
                            current_time = time.time()
                            time_diff = current_time - self._last_update_time[download_id]
                            if time_diff > 0:  # Update speed on every progress callback
                                speed = (self._bytes_downloaded[download_id]) / time_diff
                                self._download_speeds[download_id] = speed
                                self._last_update_time[download_id] = current_time
                except Exception:
                    pass
                return 0  # Continue download

            # Set the appropriate progress function based on availability
            if hasattr(pycurl, 'XFERINFOFUNCTION'):
                c.setopt(pycurl.XFERINFOFUNCTION, progress_callback)
            else:
                c.setopt(pycurl.PROGRESSFUNCTION, progress_callback)
            c.setopt(pycurl.NOPROGRESS, False)

            # Additional options for better performance
            c.setopt(pycurl.FOLLOWLOCATION, 1)  # Follow redirects
            c.setopt(pycurl.MAXREDIRS, 5)  # Maximum number of redirects
            c.setopt(pycurl.CONNECTTIMEOUT, 30)  # Connection timeout
            c.setopt(pycurl.LOW_SPEED_LIMIT, 1000)  # Minimum speed in bytes/second
            c.setopt(pycurl.LOW_SPEED_TIME, 30)  # Time in seconds to be below speed limit

            # Perform the download
            c.perform()

            # Check for errors
            response_code = c.getinfo(pycurl.RESPONSE_CODE)
            if response_code not in (200, 206):  # OK or Partial Content
                raise Exception(f"Unexpected response code: {response_code}")

        except Exception as e:
            if self._active_downloads.get(download_id, False):
                self.error_handler.handle_error(download_id, e)
            raise
        finally:
            if c:
                c.close()

    def _single_threaded_download(self, download_id: str, url: str, output_path: str) -> None:
        """Perform single-threaded download when range requests are not supported"""
        if not self._active_downloads.get(download_id, False):
            return

        c = None
        try:
            c = pycurl.Curl()
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.CAINFO, certifi.where())  # SSL certificate verification

            # Set custom User-Agent if provided
            if self.user_agent:
                c.setopt(pycurl.USERAGENT, self.user_agent)

            # Setup write callback
            def write_callback(data: bytes) -> int:
                if not self._active_downloads.get(download_id, False):
                    return -1  # Abort transfer
                try:
                    self.filesystem.write_full_content(download_id, data)
                    # Update bytes downloaded and progress immediately
                    with self._lock:
                        self._bytes_downloaded[download_id] += len(data)
                        current_time = time.time()
                        time_diff = current_time - self._last_update_time[download_id]
                        if time_diff > 0:  # Update speed on every write
                            speed = len(data) / time_diff
                            self._download_speeds[download_id] = speed
                            self._last_update_time[download_id] = current_time
                        # Update progress immediately
                        self.metadata.update_progress(download_id, self._bytes_downloaded[download_id], len(data))
                    return len(data)
                except Exception as e:
                    raise e  # Properly raise the exception

            c.setopt(pycurl.WRITEFUNCTION, write_callback)

            # Setup progress callback
            def progress_callback(total_downloaded, total_to_download, upload_total, upload_now):
                if not self._active_downloads.get(download_id, False):
                    return 1  # Abort transfer
                try:
                    if total_to_download > 0:
                        self.metadata.update_progress(download_id, self._bytes_downloaded[download_id], total_to_download)
                        # Update download speed
                        with self._lock:
                            current_time = time.time()
                            time_diff = current_time - self._last_update_time[download_id]
                            if time_diff > 0:  # Update speed on every progress callback
                                speed = (self._bytes_downloaded[download_id]) / time_diff
                                self._download_speeds[download_id] = speed
                                self._last_update_time[download_id] = current_time
                except Exception:
                    pass
                return 0  # Continue download

            if hasattr(pycurl, 'XFERINFOFUNCTION'):
                c.setopt(pycurl.XFERINFOFUNCTION, progress_callback)
            else:
                c.setopt(pycurl.PROGRESSFUNCTION, progress_callback)
            c.setopt(pycurl.NOPROGRESS, False)

            # Additional options
            c.setopt(pycurl.FOLLOWLOCATION, 1)
            c.setopt(pycurl.MAXREDIRS, 5)
            c.setopt(pycurl.CONNECTTIMEOUT, 30)
            c.setopt(pycurl.LOW_SPEED_LIMIT, 1000)
            c.setopt(pycurl.LOW_SPEED_TIME, 30)

            # Perform the download
            c.perform()

            # Check for errors
            response_code = c.getinfo(pycurl.RESPONSE_CODE)
            if response_code != 200:  # OK
                raise Exception(f"Unexpected response code: {response_code}")

            # Mark download as complete
            self.filesystem.finalize_full_content(download_id, output_path)
            self.metadata.mark_complete(download_id)

        except Exception as e:
            if self._active_downloads.get(download_id, False):
                self.error_handler.handle_error(download_id, e)
            raise
        finally:
            if c:
                c.close()

    def _download_task(self, download_id: str, url: str, output_path: str, total_size: int, supports_range: bool) -> None:
        """
        Internal method to handle the actual download process

        Args:
            download_id (str): Unique identifier for this download
            url (str): URL to download from
            output_path (str): Where to save the downloaded file
            total_size (int): Total size of the file
            supports_range (bool): Whether the server supports range requests
        """
        segment_futures = []
        try:
            if supports_range:
                # Start segmented download
                segment_size = self._calculate_segment_size(total_size)
                segments = self._create_segments(total_size, segment_size)

                # Submit each segment for download
                for segment in segments:
                    if not self._active_downloads.get(download_id, False):
                        break
                    future = self.executor.submit(
                        self._download_segment,
                        download_id,
                        url,
                        segment['start'],
                        segment['end']
                    )
                    segment_futures.append(future)
                    with self._lock:
                        self._futures[download_id].append(future)

                # Wait for all segments to complete
                try:
                    for future in segment_futures:
                        if not self._active_downloads.get(download_id, False):
                            break
                        future.result()  # This will raise any exceptions that occurred
                except Exception as e:
                    with self._lock:
                        self._active_downloads[download_id] = False
                    raise

                # Assemble final file if download wasn't cancelled
                if self._active_downloads.get(download_id, False):
                    try:
                        # Update state to assembling
                        self.metadata.update_state(download_id, DownloadState.ASSEMBLING)
                        self.filesystem.assemble_file(download_id, output_path)
                        # Update state to complete
                        self.metadata.update_state(download_id, DownloadState.COMPLETE)
                    except Exception as e:
                        with self._lock:
                            self._active_downloads[download_id] = False
                        raise
            else:
                # Perform single-threaded download
                self._single_threaded_download(download_id, url, output_path)

        except Exception as e:
            if self._active_downloads.get(download_id, False):
                self.error_handler.handle_error(download_id, e)
                # Update state to failed
                self.metadata.update_state(download_id, DownloadState.FAILED)
            raise
        finally:
            # Clean up and cancel any pending futures
            with self._lock:
                self._active_downloads.pop(download_id, None)
                self._download_speeds.pop(download_id, None)
                self._bytes_downloaded.pop(download_id, None)
                self._last_update_time.pop(download_id, None)
                futures = self._futures.pop(download_id, [])

            for future in futures:
                future.cancel()

            # Clean up segment futures
            for future in segment_futures:
                future.cancel()

    def cancel_download(self, download_id: str) -> None:
        """
        Cancel an active download

        Args:
            download_id (str): ID of the download to cancel
        """
        with self._lock:
            if download_id in self._active_downloads:
                self._active_downloads[download_id] = False
                futures = self._futures.get(download_id, [])
                for future in futures:
                    future.cancel()
                # Update state to cancelled
                self.metadata.update_state(download_id, DownloadState.CANCELLED)

    def get_download_speed(self, download_id: str) -> float:
        """
        Get the current download speed in bytes per second

        Args:
            download_id (str): ID of the download

        Returns:
            float: Current download speed in bytes per second
        """
        with self._lock:
            return self._download_speeds.get(download_id, 0.0)

    def get_bytes_downloaded(self, download_id: str) -> int:
        """
        Get the total bytes downloaded

        Args:
            download_id (str): ID of the download

        Returns:
            int: Total bytes downloaded
        """
        with self._lock:
            return self._bytes_downloaded.get(download_id, 0)

    def shutdown(self) -> None:
        """
        Shutdown the download engine and cleanup resources
        """
        # Cancel all active downloads
        with self._lock:
            for download_id in list(self._active_downloads.keys()):
                self._active_downloads[download_id] = False
                futures = self._futures.get(download_id, [])
                for future in futures:
                    future.cancel()
                # Update state to cancelled
                self.metadata.update_state(download_id, DownloadState.CANCELLED)

            self._active_downloads.clear()
            self._futures.clear()
            self._download_speeds.clear()
            self._bytes_downloaded.clear()
            self._last_update_time.clear()

        # Shutdown thread pool
        self.executor.shutdown(wait=True, cancel_futures=True)
        
    def cancel_all(self) -> None:
        with self._lock:
            for download_id in list(self._active_downloads.keys()):
                self._active_downloads[download_id] = False
                futures = self._futures.get(download_id, [])
                for future in futures:
                    future.cancel()
                # Update state to cancelled
                self.metadata.update_state(download_id, DownloadState.CANCELLED)
