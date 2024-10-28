"""
Unit tests for the Download Manager component
"""
import unittest
import os
from unittest.mock import MagicMock, patch
import pycurl
from src import DownloadManager

class TestDownloadManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.download_manager = DownloadManager(max_workers=4)
        self.test_url = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.11.5.tar.xz"
        self.test_output = "downloads/linux-6.11.5.tar.xz"
        
        # Create downloads directory
        os.makedirs("downloads", exist_ok=True)

    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists("downloads"):
            for file in os.listdir("downloads"):
                try:
                    os.remove(os.path.join("downloads", file))
                except:
                    pass
            os.rmdir("downloads")

    def test_download_initialization(self):
        """Test download initialization"""
        with patch('src.engine.pycurl.Curl') as mock_curl:
            mock_curl_instance = MagicMock()
            mock_curl_instance.getinfo.side_effect = [200, 134217728]  # First for response code, second for content length
            mock_curl.return_value = mock_curl_instance
            
            # Set up pycurl constants
            mock_curl_instance.URL = pycurl.URL
            mock_curl_instance.NOBODY = pycurl.NOBODY
            mock_curl_instance.WRITEDATA = pycurl.WRITEDATA
            mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE
            mock_curl_instance.CONTENT_LENGTH_DOWNLOAD = pycurl.CONTENT_LENGTH_DOWNLOAD
            
            download_id = self.download_manager.start_download(
                self.test_url,
                self.test_output
            )
            
            self.assertIsInstance(download_id, str)
            self.assertTrue(len(download_id) > 0)

    def test_progress_tracking(self):
        """Test progress tracking functionality"""
        with patch('src.engine.pycurl.Curl') as mock_curl:
            mock_curl_instance = MagicMock()
            mock_curl_instance.getinfo.side_effect = [200, 134217728]  # First for response code, second for content length
            mock_curl.return_value = mock_curl_instance
            
            # Set up pycurl constants
            mock_curl_instance.URL = pycurl.URL
            mock_curl_instance.NOBODY = pycurl.NOBODY
            mock_curl_instance.WRITEDATA = pycurl.WRITEDATA
            mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE
            mock_curl_instance.CONTENT_LENGTH_DOWNLOAD = pycurl.CONTENT_LENGTH_DOWNLOAD
            
            download_id = self.download_manager.start_download(
                self.test_url,
                self.test_output
            )
            
            progress = self.download_manager.get_progress(download_id)
            self.assertIsInstance(progress, float)
            self.assertTrue(0 <= progress <= 100)

    def test_completion_status(self):
        """Test completion status check"""
        with patch('src.engine.pycurl.Curl') as mock_curl:
            mock_curl_instance = MagicMock()
            mock_curl_instance.getinfo.side_effect = [200, 134217728]  # First for response code, second for content length
            mock_curl.return_value = mock_curl_instance
            
            # Set up pycurl constants
            mock_curl_instance.URL = pycurl.URL
            mock_curl_instance.NOBODY = pycurl.NOBODY
            mock_curl_instance.WRITEDATA = pycurl.WRITEDATA
            mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE
            mock_curl_instance.CONTENT_LENGTH_DOWNLOAD = pycurl.CONTENT_LENGTH_DOWNLOAD
            
            download_id = self.download_manager.start_download(
                self.test_url,
                self.test_output
            )
            
            status = self.download_manager.is_complete(download_id)
            self.assertIsInstance(status, bool)

    @patch('src.engine.pycurl.Curl')
    def test_error_handling(self, mock_curl):
        """Test error handling"""
        # Mock curl instance
        mock_curl_instance = MagicMock()
        mock_curl.return_value = mock_curl_instance
        
        # Set up pycurl constants
        mock_curl_instance.URL = pycurl.URL
        mock_curl_instance.NOBODY = pycurl.NOBODY
        mock_curl_instance.WRITEDATA = pycurl.WRITEDATA
        mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE
        mock_curl_instance.CONTENT_LENGTH_DOWNLOAD = pycurl.CONTENT_LENGTH_DOWNLOAD
        
        # Make getinfo return error response
        mock_curl_instance.getinfo.side_effect = [404, -1]  # Not Found response

        # Verify that the exception is propagated
        with self.assertRaises(Exception):
            self.download_manager.start_download(
                "https://invalid-url.com/file.txt",
                "downloads/error_file.bin"
            )

    def test_verify_checksum(self):
        """Test checksum verification"""
        with patch('src.engine.pycurl.Curl') as mock_curl:
            mock_curl_instance = MagicMock()
            mock_curl_instance.getinfo.side_effect = [200, 134217728]  # First for response code, second for content length
            mock_curl.return_value = mock_curl_instance
            
            # Set up pycurl constants
            mock_curl_instance.URL = pycurl.URL
            mock_curl_instance.NOBODY = pycurl.NOBODY
            mock_curl_instance.WRITEDATA = pycurl.WRITEDATA
            mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE
            mock_curl_instance.CONTENT_LENGTH_DOWNLOAD = pycurl.CONTENT_LENGTH_DOWNLOAD
            
            # Create test file
            test_data = b"Hello, World!"
            os.makedirs(os.path.dirname(self.test_output), exist_ok=True)
            with open(self.test_output, 'wb') as f:
                f.write(test_data)
            
            # Start a download
            download_id = self.download_manager.start_download(
                self.test_url,
                self.test_output
            )
            
            # Test checksum verification
            expected_sha256 = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
            result = self.download_manager.verify_checksum(
                download_id,
                "sha256",
                expected_sha256
            )
            self.assertTrue(result)
            
            # Test invalid checksum
            result = self.download_manager.verify_checksum(
                download_id,
                "sha256",
                "invalid_hash"
            )
            self.assertFalse(result)
            
            # Test invalid algorithm
            with self.assertRaises(ValueError):
                self.download_manager.verify_checksum(
                    download_id,
                    "invalid_algo",
                    "hash"
                )

if __name__ == '__main__':
    unittest.main()
