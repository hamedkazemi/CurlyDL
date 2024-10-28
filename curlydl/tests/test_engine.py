"""
Unit tests for the Download Engine component
"""
import unittest
from unittest.mock import MagicMock, patch, call
import pycurl
from concurrent.futures import Future
from src.engine import DownloadEngine

class TestDownloadEngine(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.error_handler = MagicMock()
        self.filesystem = MagicMock()
        self.metadata = MagicMock()
        self.engine = DownloadEngine(
            max_workers=2,
            error_handler=self.error_handler,
            filesystem=self.filesystem,
            metadata=self.metadata
        )

    @patch('src.engine.pycurl.Curl')
    def test_get_file_size(self, mock_curl):
        """Test file size retrieval"""
        # Mock curl response
        mock_curl_instance = MagicMock()
        mock_curl_instance.getinfo.side_effect = [200, 1024]  # First for response code, second for content length
        mock_curl.return_value = mock_curl_instance

        # Set up pycurl constants
        mock_curl_instance.URL = pycurl.URL
        mock_curl_instance.NOBODY = pycurl.NOBODY
        mock_curl_instance.WRITEDATA = pycurl.WRITEDATA
        mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE
        mock_curl_instance.CONTENT_LENGTH_DOWNLOAD = pycurl.CONTENT_LENGTH_DOWNLOAD

        size = self.engine._get_file_size("https://example.com/file.txt")
        self.assertEqual(size, 1024)
        
        # Verify curl options were set correctly
        mock_curl_instance.setopt.assert_any_call(pycurl.URL, "https://example.com/file.txt")

        # Test error handling
        mock_curl_instance.perform.side_effect = pycurl.error("Test error")
        with self.assertRaises(Exception):
            self.engine._get_file_size("https://example.com/file.txt")

        # Test zero content length
        mock_curl_instance.perform.side_effect = None
        mock_curl_instance.getinfo.side_effect = [200, 0]
        size = self.engine._get_file_size("https://example.com/file.txt")
        self.assertEqual(size, 0)

    def test_calculate_segment_size(self):
        """Test segment size calculation"""
        # Test small file (< 1MB)
        small_size = self.engine._calculate_segment_size(500_000)
        self.assertEqual(small_size, 500_000)

        # Test medium file
        medium_size = self.engine._calculate_segment_size(10_000_000)
        self.assertEqual(medium_size, 1_250_000)  # 10MB / 8

        # Test large file
        large_size = self.engine._calculate_segment_size(1_000_000_000)
        self.assertEqual(large_size, 125_000_000)  # 1GB / 8

    def test_create_segments(self):
        """Test segment creation"""
        total_size = 1000
        segment_size = 400
        segments = self.engine._create_segments(total_size, segment_size)

        # Should create 3 segments: 0-399, 400-799, 800-999
        expected_segments = [
            {'start': 0, 'end': 399},
            {'start': 400, 'end': 799},
            {'start': 800, 'end': 999}
        ]
        self.assertEqual(segments, expected_segments)

        # Test single segment
        segments = self.engine._create_segments(100, 200)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0], {'start': 0, 'end': 99})

    @patch('src.engine.pycurl.Curl')
    def test_download_segment(self, mock_curl):
        """Test segment download"""
        mock_curl_instance = MagicMock()
        mock_curl.return_value = mock_curl_instance

        # Set up pycurl constants
        mock_curl_instance.URL = pycurl.URL
        mock_curl_instance.RANGE = pycurl.RANGE
        mock_curl_instance.CAINFO = pycurl.CAINFO
        mock_curl_instance.WRITEFUNCTION = pycurl.WRITEFUNCTION
        mock_curl_instance.NOPROGRESS = pycurl.NOPROGRESS
        mock_curl_instance.XFERINFOFUNCTION = pycurl.XFERINFOFUNCTION
        mock_curl_instance.FOLLOWLOCATION = pycurl.FOLLOWLOCATION
        mock_curl_instance.MAXREDIRS = pycurl.MAXREDIRS
        mock_curl_instance.CONNECTTIMEOUT = pycurl.CONNECTTIMEOUT
        mock_curl_instance.LOW_SPEED_LIMIT = pycurl.LOW_SPEED_LIMIT
        mock_curl_instance.LOW_SPEED_TIME = pycurl.LOW_SPEED_TIME
        mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE

        # Add download to active downloads
        self.engine._active_downloads["test_id"] = True

        # Test successful download
        mock_curl_instance.getinfo.return_value = 206
        self.engine._download_segment(
            "test_id",
            "https://example.com/file.txt",
            0,
            999
        )

        # Verify curl options
        mock_curl_instance.setopt.assert_any_call(pycurl.RANGE, '0-999')
        mock_curl_instance.perform.assert_called_once()

        # Test error response
        mock_curl_instance.getinfo.return_value = 404  # Not Found response
        with self.assertRaises(Exception):
            self.engine._download_segment(
                "test_id",
                "https://example.com/file.txt",
                0,
                999
            )

        # Test inactive download
        self.engine._active_downloads["test_id"] = False
        result = self.engine._download_segment(
            "test_id",
            "https://example.com/file.txt",
            0,
            999
        )
        self.assertIsNone(result)

        # Test write callback error
        self.engine._active_downloads["test_id"] = True
        mock_curl_instance.getinfo.return_value = 206
        self.filesystem.write_segment.side_effect = Exception("Write error")

        # Simulate write callback error using pycurl.error
        mock_curl_instance.perform.side_effect = pycurl.error(42, "Callback aborted")

        with self.assertRaises(Exception):
            self.engine._download_segment(
                "test_id",
                "https://example.com/file.txt",
                0,
                999
            )

    @patch('src.engine.pycurl.Curl')
    def test_start_download(self, mock_curl):
        """Test download initialization"""
        mock_curl_instance = MagicMock()
        mock_curl_instance.getinfo.side_effect = [200, 1024]  # First for response code, second for content length
        mock_curl.return_value = mock_curl_instance

        # Set up pycurl constants
        mock_curl_instance.URL = pycurl.URL
        mock_curl_instance.NOBODY = pycurl.NOBODY
        mock_curl_instance.WRITEDATA = pycurl.WRITEDATA
        mock_curl_instance.RESPONSE_CODE = pycurl.RESPONSE_CODE
        mock_curl_instance.CONTENT_LENGTH_DOWNLOAD = pycurl.CONTENT_LENGTH_DOWNLOAD

        download_id = self.engine.start_download(
            "https://example.com/file.txt",
            "output.txt"
        )

        # Verify download ID is created
        self.assertIsInstance(download_id, str)
        self.assertTrue(len(download_id) > 0)

        # Verify metadata is created
        self.metadata.create_download.assert_called_with(
            download_id,
            "https://example.com/file.txt",
            "output.txt"
        )

        # Test error in metadata creation
        self.metadata.create_download.side_effect = Exception("Metadata error")
        with self.assertRaises(Exception):
            self.engine.start_download(
                "https://example.com/file.txt",
                "output.txt"
            )

    @patch('src.engine.pycurl.Curl')
    @patch('concurrent.futures.ThreadPoolExecutor.submit')
    def test_download_task(self, mock_submit, mock_curl):
        """Test download task execution"""
        # Set up mock curl instances
        mock_curl_instance = MagicMock()
        mock_curl.return_value = mock_curl_instance

        # Set up pycurl constants
        for attr in dir(pycurl):
            if attr.isupper():
                setattr(mock_curl_instance, attr, getattr(pycurl, attr))

        # Set up responses for file size check and segment downloads
        mock_curl_instance.getinfo.side_effect = [
            200,  # Response code for file size check
            1024,  # Content length for file size check
            206,  # Response code for first segment
            206   # Response code for second segment
        ]

        # Add download to active downloads
        download_id = "test_id"
        self.engine._active_downloads[download_id] = True

        # Mock future result
        future = Future()
        future.set_result(None)
        mock_submit.return_value = future

        # Test successful download task
        self.engine._download_task(
            download_id,
            "https://example.com/file.txt",
            "output.txt"
        )

        # Verify file assembly and completion
        self.filesystem.assemble_file.assert_called_once()
        self.metadata.mark_complete.assert_called_once()

        # Test file assembly error
        self.filesystem.assemble_file.side_effect = Exception("Assembly error")
        with self.assertRaises(Exception):
            self.engine._download_task(
                download_id,
                "https://example.com/file.txt",
                "output.txt"
            )

        # Test download cancellation
        mock_curl_instance.getinfo.side_effect = None
        mock_curl_instance.getinfo.return_value = 200
        self.engine._active_downloads[download_id] = False
        self.engine._download_task(
            download_id,
            "https://example.com/file.txt",
            "output.txt"
        )
        self.assertFalse(download_id in self.engine._active_downloads)

if __name__ == '__main__':
    unittest.main()
