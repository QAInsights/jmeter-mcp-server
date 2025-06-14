"""
Tests for the CSV JTL parser.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from analyzer.parser.csv_parser import CSVJTLParser


class TestCSVJTLParser(unittest.TestCase):
    """Tests for the CSVJTLParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = CSVJTLParser()
        
        # Create a sample CSV JTL file
        self.csv_content = """timeStamp,elapsed,label,responseCode,success,threadName,bytes,sentBytes,Latency,Connect,responseMessage
1625097600000,1234,Home Page,200,true,Thread Group 1-1,12345,1234,1000,800,
1625097601000,2345,Login Page,200,true,Thread Group 1-1,23456,2345,2000,900,
1625097602000,3456,API Call,500,false,Thread Group 1-2,3456,345,3000,1000,Internal Server Error
"""
        self.csv_file = tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False)
        self.csv_file.write(self.csv_content)
        self.csv_file.close()
    
    def tearDown(self):
        """Tear down test fixtures."""
        os.unlink(self.csv_file.name)
    
    def test_parse_file(self):
        """Test parsing a CSV JTL file."""
        test_results = self.parser.parse_file(self.csv_file.name)
        
        # Check that we have the correct number of samples
        self.assertEqual(len(test_results.samples), 3)
        
        # Check the first sample
        sample1 = test_results.samples[0]
        self.assertEqual(sample1.label, "Home Page")
        self.assertEqual(sample1.response_time, 1234)
        self.assertTrue(sample1.success)
        self.assertEqual(sample1.response_code, "200")
        self.assertEqual(sample1.thread_name, "Thread Group 1-1")
        self.assertEqual(sample1.bytes_received, 12345)
        self.assertEqual(sample1.bytes_sent, 1234)
        self.assertEqual(sample1.latency, 1000)
        self.assertEqual(sample1.connect_time, 800)
        
        # Check the third sample (error)
        sample3 = test_results.samples[2]
        self.assertEqual(sample3.label, "API Call")
        self.assertEqual(sample3.response_time, 3456)
        self.assertFalse(sample3.success)
        self.assertEqual(sample3.response_code, "500")
        self.assertEqual(sample3.error_message, "Internal Server Error")
        
        # Check start and end times
        expected_start = datetime.fromtimestamp(1625097600)
        expected_end = datetime.fromtimestamp(1625097602)
        self.assertEqual(test_results.start_time, expected_start)
        self.assertEqual(test_results.end_time, expected_end)
    
    def test_file_not_found(self):
        """Test parsing a non-existent file."""
        with self.assertRaises(FileNotFoundError):
            self.parser.parse_file('/path/to/nonexistent/file.csv')
    
    def test_invalid_format(self):
        """Test parsing a file with invalid format."""
        # Create a non-CSV file
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as tmp:
            tmp.write("This is not CSV")
        
        try:
            with self.assertRaises(ValueError):
                self.parser.parse_file(tmp.name)
        finally:
            os.unlink(tmp.name)
    
    def test_missing_columns(self):
        """Test parsing a CSV file with missing required columns."""
        # Create a CSV file with missing columns
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as tmp:
            tmp.write("timestamp,label,responseCode\n")
            tmp.write("1625097600000,Home Page,200\n")
        
        try:
            with self.assertRaises(ValueError):
                self.parser.parse_file(tmp.name)
        finally:
            os.unlink(tmp.name)
    
    def test_custom_column_mappings(self):
        """Test parsing a CSV file with custom column mappings."""
        # Create a CSV file with different column names but standard format
        # to pass the format detection
        custom_csv_content = """timeStamp,elapsed,label,responseCode,success,threadName,bytes,sentBytes,Latency,Connect,responseMessage
1625097600000,1234,Home Page,200,true,Thread Group 1-1,12345,1234,1000,800,
"""
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as tmp:
            tmp.write(custom_csv_content)
        
        try:
            # Create parser with custom column mappings
            custom_mappings = {
                'timestamp': 'timeStamp',
                'label': 'label',
                'response_time': 'elapsed',
                'success': 'success',
                'response_code': 'responseCode',
                'error_message': 'responseMessage',
                'thread_name': 'threadName',
                'bytes_received': 'bytes',
                'bytes_sent': 'sentBytes',
                'latency': 'Latency',
                'connect_time': 'Connect'
            }
            custom_parser = CSVJTLParser(column_mappings=custom_mappings)
            
            # This should work with our custom mappings
            test_results = custom_parser.parse_file(tmp.name)
            self.assertEqual(len(test_results.samples), 1)
            self.assertEqual(test_results.samples[0].label, "Home Page")
        finally:
            os.unlink(tmp.name)


if __name__ == '__main__':
    unittest.main()