"""
Unit tests for the File System Manager component
"""
import unittest
import os
import shutil
from pathlib import Path
from io import BytesIO
from unittest.mock import mock_open, patch, MagicMock
from src.filesystem import FileSystemManager

class TestFileSystemManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.fs_manager = FileSystemManager()
        self.test_dir = Path("test_downloads")
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test environment"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        if Path("downloads_temp").exists():
            shutil.rmtree("downloads_temp")

    def test_prepare_download(self):
        """Test download preparation"""
        download_id = "test_id"
        output_path = str(self.test_dir / "test_file.txt")

        self.fs_manager.prepare_download(download_id, output_path)

        # Verify temp directory is created
        temp_dir = self.fs_manager.temp_dir / download_id
        self.assertTrue(temp_dir.exists())
        self.assertTrue(temp_dir.is_dir())

        # Verify output path is stored
        self.assertEqual(self.fs_manager._output_paths[download_id], output_path)

    def test_write_segment(self):
        """Test segment writing"""
        download_id = "test_id"
        output_path = str(self.test_dir / "test_file.txt")
        test_data = b"Hello, World!"

        # Prepare download
        self.fs_manager.prepare_download(download_id, output_path)

        # Write segment
        self.fs_manager.write_segment(download_id, 0, test_data)

        # Verify segment file exists and contains correct data
        segment_file = self.fs_manager._segment_files[download_id]
        segment_file.flush()
        segment_file.seek(0)
        written_data = segment_file.read()
        self.assertEqual(written_data, test_data)

        # Test writing file-like object
        file_like = BytesIO(test_data)
        self.fs_manager.write_segment(download_id, len(test_data), file_like)
        segment_file.flush()
        segment_file.seek(0)
        written_data = segment_file.read()
        self.assertEqual(len(written_data), len(test_data) * 2)

    def test_assemble_file(self):
        """Test file assembly"""
        download_id = "test_id"
        output_path = str(self.test_dir / "test_file.txt")
        test_data = b"Hello, World!"

        # Prepare and write data
        self.fs_manager.prepare_download(download_id, output_path)
        self.fs_manager.write_segment(download_id, 0, test_data)

        # Assemble file
        self.fs_manager.assemble_file(download_id, output_path)

        # Verify output file
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, 'rb') as f:
            assembled_data = f.read()
        self.assertEqual(assembled_data, test_data)

        # Verify cleanup
        temp_dir = self.fs_manager.temp_dir / download_id
        self.assertFalse(temp_dir.exists())

        # Test error handling
        with self.assertRaises(Exception):
            self.fs_manager.assemble_file("invalid_id", output_path)

    def test_verify_checksum(self):
        """Test checksum verification"""
        download_id = "test_id"
        output_path = str(self.test_dir / "test_file.txt")
        test_data = b"Hello, World!"

        # Write test file and prepare download
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(test_data)
        
        self.fs_manager.prepare_download(download_id, output_path)
        self.fs_manager._output_paths[download_id] = output_path

        # Test MD5 checksum
        expected_md5 = "65a8e27d8879283831b664bd8b7f0ad4"
        self.assertTrue(
            self.fs_manager.verify_checksum(download_id, "md5", expected_md5)
        )

        # Test SHA256 checksum
        expected_sha256 = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        self.assertTrue(
            self.fs_manager.verify_checksum(download_id, "sha256", expected_sha256)
        )

        # Test invalid algorithm
        with self.assertRaises(ValueError):
            self.fs_manager.verify_checksum(download_id, "invalid_algo", "hash")

        # Test missing file
        os.remove(output_path)
        with self.assertRaises(ValueError):
            self.fs_manager.verify_checksum(download_id, "md5", expected_md5)

    def test_invalid_download_id(self):
        """Test handling of invalid download ID"""
        with self.assertRaises(Exception):
            self.fs_manager.write_segment("invalid_id", 0, b"test")

    def test_cleanup_on_delete(self):
        """Test cleanup when object is deleted"""
        download_id = "test_id"
        output_path = str(self.test_dir / "test_file.txt")
        
        # Create a file
        self.fs_manager.prepare_download(download_id, output_path)
        
        # Mock the file's close method
        self.fs_manager._segment_files[download_id].close = MagicMock()
        
        # Trigger cleanup
        self.fs_manager.__del__()
        
        # Verify close was called
        self.fs_manager._segment_files[download_id].close.assert_called_once()

    def test_cleanup_error_handling(self):
        """Test error handling during cleanup"""
        download_id = "test_id"
        output_path = str(self.test_dir / "test_file.txt")
        
        # Create a file
        self.fs_manager.prepare_download(download_id, output_path)
        
        # Make close raise an exception
        self.fs_manager._segment_files[download_id].close = MagicMock(
            side_effect=Exception("Test error")
        )
        
        # Cleanup should not raise exception
        try:
            self.fs_manager.__del__()
        except:
            self.fail("Cleanup should not raise exceptions")

if __name__ == '__main__':
    unittest.main()
