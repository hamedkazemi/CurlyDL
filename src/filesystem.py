"""
File System Manager component handling file operations
"""
import os
import shutil
import hashlib
from pathlib import Path
from typing import Union, BinaryIO, Dict, Optional

class FileSystemManager:
    def __init__(self):
        """Initialize the File System Manager"""
        self.temp_dir = Path("downloads_temp")
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        self._segment_files: Dict[str, BinaryIO] = {}
        self._output_paths: Dict[str, str] = {}

    def prepare_download(self, download_id: str, output_path: str) -> None:
        """
        Prepare the filesystem for a new download
        
        Args:
            download_id (str): Unique identifier for the download
            output_path (str): Final destination path for the file
        """
        # Create temporary directory
        download_temp_dir = self.temp_dir / download_id
        download_temp_dir.mkdir(exist_ok=True, parents=True)
        
        # Store output path for later use
        self._output_paths[download_id] = output_path
        
        # Initialize segment file in read/write mode
        segment_path = download_temp_dir / "data"
        self._segment_files[download_id] = open(segment_path, 'w+b')

    def write_segment(self, download_id: str, offset: int, data: Union[bytes, BinaryIO]) -> None:
        """
        Write a downloaded segment to temporary storage
        
        Args:
            download_id (str): Download identifier
            offset (int): Starting byte offset for the segment
            data: Data to write (either bytes or file-like object)
        """
        if download_id not in self._segment_files:
            raise Exception(f"No open file for download {download_id}")
            
        f = self._segment_files[download_id]
        f.seek(offset)
        
        if isinstance(data, bytes):
            f.write(data)
        else:
            shutil.copyfileobj(data, f)
        
        f.flush()

    def assemble_file(self, download_id: str, output_path: str) -> None:
        """
        Assemble all segments into the final file
        
        Args:
            download_id (str): Download identifier
            output_path (str): Path where the final file should be saved
        """
        if download_id in self._segment_files:
            f = self._segment_files[download_id]
            f.flush()
            f.close()
            del self._segment_files[download_id]

        temp_dir = self.temp_dir / download_id
        temp_file = temp_dir / "data"

        if not temp_file.exists():
            raise Exception(f"No data file found for download {download_id}")

        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Move assembled file to final location
        try:
            shutil.move(str(temp_file), output_path)
        except Exception as e:
            raise Exception(f"Failed to move file to {output_path}: {str(e)}")

        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors

        # Store final output path
        self._output_paths[download_id] = output_path

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
            ValueError: If the download ID is not found or algorithm is not supported
        """
        if download_id not in self._output_paths:
            raise ValueError(f"No output path found for download {download_id}")
            
        try:
            hash_func = getattr(hashlib, algorithm.lower())()
        except AttributeError:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        output_path = self._output_paths[download_id]
        if not os.path.exists(output_path):
            raise ValueError(f"Output file not found: {output_path}")
            
        with open(output_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_func.update(chunk)
                
        return hash_func.hexdigest().lower() == expected.lower()

    def _get_output_path(self, download_id: str) -> str:
        """Get the output path for a download"""
        if download_id not in self._output_paths:
            raise ValueError(f"No output path found for download {download_id}")
        return self._output_paths[download_id]

    def __del__(self):
        """Cleanup any open files"""
        for f in self._segment_files.values():
            try:
                f.close()
            except:
                pass
