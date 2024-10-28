"""
Unit tests for the Metadata Manager component
"""
import unittest
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from src.metadata import MetadataManager

class TestMetadataManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.metadata_manager = MetadataManager()
        self.test_download_id = "test_id"
        self.test_url = "https://example.com/file.txt"
        self.test_output = "test_file.txt"

    def tearDown(self):
        """Clean up test environment"""
        if Path("downloads_metadata").exists():
            shutil.rmtree("downloads_metadata")

    def test_create_download(self):
        """Test download metadata creation"""
        self.metadata_manager.create_download(
            self.test_download_id,
            self.test_url,
            self.test_output
        )

        # Verify metadata file exists
        metadata_path = self.metadata_manager._get_metadata_path(self.test_download_id)
        self.assertTrue(metadata_path.exists())

        # Verify metadata content
        metadata = self.metadata_manager._get_metadata(self.test_download_id)
        self.assertEqual(metadata["url"], self.test_url)
        self.assertEqual(metadata["output_path"], self.test_output)
        self.assertEqual(metadata["status"], "initializing")
        self.assertEqual(metadata["downloaded_bytes"], 0)

    def test_update_total_size(self):
        """Test updating total file size"""
        self.metadata_manager.create_download(
            self.test_download_id,
            self.test_url,
            self.test_output
        )

        test_size = 1024
        self.metadata_manager.update_total_size(self.test_download_id, test_size)

        metadata = self.metadata_manager._get_metadata(self.test_download_id)
        self.assertEqual(metadata["total_size"], test_size)

    def test_update_progress(self):
        """Test progress updates"""
        self.metadata_manager.create_download(
            self.test_download_id,
            self.test_url,
            self.test_output
        )

        # Set total size
        self.metadata_manager.update_total_size(self.test_download_id, 1000)

        # Update progress
        self.metadata_manager.update_progress(self.test_download_id, 0, 499)
        progress = self.metadata_manager.get_progress(self.test_download_id)
        self.assertEqual(progress, 50.0)

    def test_is_complete(self):
        """Test completion status"""
        self.metadata_manager.create_download(
            self.test_download_id,
            self.test_url,
            self.test_output
        )

        # Initially not complete
        self.assertFalse(self.metadata_manager.is_complete(self.test_download_id))

        # Mark as complete
        self.metadata_manager.mark_complete(self.test_download_id)
        self.assertTrue(self.metadata_manager.is_complete(self.test_download_id))

    def test_metadata_persistence(self):
        """Test metadata persistence across loads"""
        self.metadata_manager.create_download(
            self.test_download_id,
            self.test_url,
            self.test_output
        )

        # Create new instance to test loading from disk
        new_manager = MetadataManager()
        metadata = new_manager._get_metadata(self.test_download_id)
        
        self.assertEqual(metadata["url"], self.test_url)
        self.assertEqual(metadata["output_path"], self.test_output)

    def test_invalid_download_id(self):
        """Test handling of invalid download ID"""
        with self.assertRaises(ValueError):
            self.metadata_manager.get_progress("invalid_id")

if __name__ == '__main__':
    unittest.main()
