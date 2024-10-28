"""
File System Manager component handling file operations
"""
import os
import shutil
import hashlib
import tempfile
from pathlib import Path
from typing import Union, BinaryIO, Dict, Optional
from contextlib import contextmanager
import threading
import psutil

class FileSystemError(Exception):
    """Custom exception for filesystem-related errors"""
    pass

class FileSystemManager:
    def __init__(self, min_free_space: int = 1024 * 1024 * 100):  # 100MB minimum free space
        """
        Initialize the File System Manager
        
        Args:
            min_free_space (int): Minimum required free space in bytes
        """
        self.temp_dir = Path("downloads_temp")
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        self.min_free_space = min_free_space
        self._output_paths: Dict[str, str] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def _check_disk_space(self, required_space: int) -> None:
        """
        Check if there's enough disk space available
        
        Args:
            required_space (int): Required space in bytes
            
        Raises:
            FileSystemError: If there isn't enough disk space
        """
        try:
            disk_usage = psutil.disk_usage(str(self.temp_dir))
            if disk_usage.free < max(required_space, self.min_free_space):
                raise FileSystemError(
                    f"Not enough disk space. Required: {required_space / 1024 / 1024:.2f}MB, "
                    f"Available: {disk_usage.free / 1024 / 1024:.2f}MB"
                )
        except Exception as e:
            raise FileSystemError(f"Failed to check disk space: {str(e)}")

    def prepare_download(self, download_id: str, output_path: str, expected_size: Optional[int] = None) -> None:
        """
        Prepare the filesystem for a new download
        
        Args:
            download_id (str): Unique identifier for the download
            output_path (str): Final destination path for the file
            expected_size (int, optional): Expected size of the download in bytes
            
        Raises:
            FileSystemError: If filesystem preparation fails
        """
        try:
            # Check disk space if size is known
            if expected_size:
                self._check_disk_space(expected_size)

            # Create temporary directory
            download_temp_dir = self.temp_dir / download_id
            download_temp_dir.mkdir(exist_ok=True, parents=True)

            # Create a thread lock for this download
            with self._lock:
                self._locks[download_id] = threading.Lock()
                self._output_paths[download_id] = output_path

            # Check if partial download exists
            partial_path = download_temp_dir / "partial"
            if partial_path.exists():
                # Validate partial file
                if not self._validate_partial_file(partial_path):
                    partial_path.unlink()

        except Exception as e:
            raise FileSystemError(f"Failed to prepare download: {str(e)}")

    def write_segment(self, download_id: str, offset: int, data: Union[bytes, BinaryIO]) -> None:
        """
        Write a downloaded segment to temporary storage
        
        Args:
            download_id (str): Download identifier
            offset (int): Starting byte offset for the segment
            data: Data to write (either bytes or file-like object)
            
        Raises:
            FileSystemError: If write operation fails
        """
        temp_dir = self.temp_dir / download_id
        segment_path = temp_dir / f"segment_{offset}"

        try:
            # Write to temporary segment file first
            with tempfile.NamedTemporaryFile(dir=str(temp_dir), delete=False) as temp_file:
                if isinstance(data, bytes):
                    temp_file.write(data)
                else:
                    shutil.copyfileobj(data, temp_file)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomically move temporary file to segment file
            os.replace(temp_file.name, segment_path)

        except Exception as e:
            try:
                os.unlink(temp_file.name)
            except:
                pass
            raise FileSystemError(f"Failed to write segment: {str(e)}")

    def write_full_content(self, download_id: str, data: bytes) -> None:
        """
        Write data directly to a file for single-threaded downloads
        
        Args:
            download_id (str): Download identifier
            data: Data to write
            
        Raises:
            FileSystemError: If write operation fails
        """
        temp_dir = self.temp_dir / download_id
        partial_path = temp_dir / "partial"

        try:
            # Write to temporary file first
            with tempfile.NamedTemporaryFile(dir=str(temp_dir), delete=False) as temp_file:
                temp_file.write(data)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomically move temporary file to partial file
            os.replace(temp_file.name, partial_path)

        except Exception as e:
            try:
                os.unlink(temp_file.name)
            except:
                pass
            raise FileSystemError(f"Failed to write content: {str(e)}")

    def assemble_file(self, download_id: str, output_path: str) -> None:
        """
        Assemble all segments into the final file
        
        Args:
            download_id (str): Download identifier
            output_path (str): Path where the final file should be saved
            
        Raises:
            FileSystemError: If file assembly fails
        """
        temp_dir = self.temp_dir / download_id
        assembled_path = temp_dir / "assembled"

        try:
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Assemble segments into temporary file
            with tempfile.NamedTemporaryFile(dir=str(temp_dir), delete=False) as temp_file:
                segment_files = sorted(
                    temp_dir.glob("segment_*"),
                    key=lambda x: int(x.name.split('_')[1])
                )

                for segment_file in segment_files:
                    with open(segment_file, 'rb') as f:
                        shutil.copyfileobj(f, temp_file)

                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomically move assembled file to final location
            os.replace(temp_file.name, output_path)

            # Clean up temporary directory
            self._cleanup_download(download_id)

        except Exception as e:
            try:
                os.unlink(temp_file.name)
            except:
                pass
            raise FileSystemError(f"Failed to assemble file: {str(e)}")

    def finalize_full_content(self, download_id: str, output_path: str) -> None:
        """
        Move the fully downloaded content to its final location
        
        Args:
            download_id (str): Download identifier
            output_path (str): Final destination path
            
        Raises:
            FileSystemError: If finalization fails
        """
        temp_dir = self.temp_dir / download_id
        partial_path = temp_dir / "partial"

        try:
            if not partial_path.exists():
                raise FileSystemError("No downloaded content found")

            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Atomically move file to final location
            os.replace(str(partial_path), output_path)

            # Clean up temporary directory
            self._cleanup_download(download_id)

        except Exception as e:
            raise FileSystemError(f"Failed to finalize download: {str(e)}")

    def verify_checksum(self, download_id: str, algorithm: str, expected: str) -> bool:
        """
        Verify the checksum of a downloaded file
        
        Args:
            download_id (str): Download identifier
            algorithm (str): Hash algorithm to use
            expected (str): Expected checksum value
            
        Returns:
            bool: True if checksum matches, False otherwise
            
        Raises:
            FileSystemError: If verification fails
        """
        if download_id not in self._output_paths:
            raise FileSystemError(f"No output path found for download {download_id}")

        try:
            hash_func = getattr(hashlib, algorithm.lower())()
        except AttributeError:
            raise FileSystemError(f"Unsupported hash algorithm: {algorithm}")

        output_path = self._output_paths[download_id]
        if not os.path.exists(output_path):
            raise FileSystemError(f"Output file not found: {output_path}")

        try:
            with open(output_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest().lower() == expected.lower()
        except Exception as e:
            raise FileSystemError(f"Failed to verify checksum: {str(e)}")

    def get_partial_size(self, download_id: str) -> Optional[int]:
        """
        Get the size of partially downloaded content
        
        Args:
            download_id (str): Download identifier
            
        Returns:
            Optional[int]: Size of partial download in bytes, or None if no partial download exists
        """
        partial_path = self.temp_dir / download_id / "partial"
        try:
            return partial_path.stat().st_size if partial_path.exists() else None
        except Exception:
            return None

    def _validate_partial_file(self, path: Path) -> bool:
        """
        Validate a partial download file
        
        Args:
            path: Path to the partial file
            
        Returns:
            bool: True if file is valid, False otherwise
        """
        try:
            with open(path, 'rb') as f:
                # Read a small chunk to verify file is readable
                f.read(1)
            return True
        except Exception:
            return False

    def _cleanup_download(self, download_id: str) -> None:
        """
        Clean up temporary files for a download
        
        Args:
            download_id (str): Download identifier
        """
        temp_dir = self.temp_dir / download_id
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors

        with self._lock:
            self._locks.pop(download_id, None)
            self._output_paths.pop(download_id, None)

    def cleanup(self) -> None:
        """Clean up all temporary files and resources"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass

        with self._lock:
            self._locks.clear()
            self._output_paths.clear()

    def __del__(self):
        """Cleanup on deletion"""
        self.cleanup()
