"""
Unit tests for the Error Handler component
"""
import unittest
import logging
from unittest.mock import MagicMock, patch
from src.error_handler import ErrorHandler

class TestErrorHandler(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.error_handler = ErrorHandler(max_retries=3)
        self.test_download_id = "test_id"

    def test_handle_error(self):
        """Test error handling"""
        test_error = Exception("Test error")
        
        with self.assertLogs(level='ERROR') as log:
            self.error_handler.handle_error(self.test_download_id, test_error)
            
        self.assertTrue(any(
            f"Download {self.test_download_id} encountered error" in record.message
            for record in log.records
        ))

    def test_retry_with_backoff_success(self):
        """Test successful retry with backoff"""
        mock_func = MagicMock()
        mock_func.side_effect = [Exception(), Exception(), "success"]

        result = self.error_handler.retry_with_backoff(mock_func)
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)

    def test_retry_with_backoff_failure(self):
        """Test retry failure after max attempts"""
        mock_func = MagicMock()
        mock_func.side_effect = Exception("Persistent error")

        with self.assertRaises(Exception):
            self.error_handler.retry_with_backoff(mock_func)
            
        self.assertEqual(mock_func.call_count, self.error_handler.max_retries)

    def test_retry_with_backoff_immediate_success(self):
        """Test immediate success without retries"""
        mock_func = MagicMock(return_value="success")

        result = self.error_handler.retry_with_backoff(mock_func)
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 1)

    @patch('time.sleep')
    def test_backoff_timing(self, mock_sleep):
        """Test exponential backoff timing"""
        mock_func = MagicMock()
        mock_func.side_effect = [Exception(), Exception(), Exception()]

        try:
            self.error_handler.retry_with_backoff(mock_func)
        except Exception:
            pass

        # Verify exponential backoff timing
        mock_sleep.assert_any_call(2)  # First retry
        mock_sleep.assert_any_call(3)  # Second retry

    def test_custom_max_retries(self):
        """Test custom maximum retry count"""
        custom_handler = ErrorHandler(max_retries=5)
        mock_func = MagicMock(side_effect=Exception("Error"))

        with self.assertRaises(Exception):
            custom_handler.retry_with_backoff(mock_func)
            
        self.assertEqual(mock_func.call_count, 5)

if __name__ == '__main__':
    unittest.main()
