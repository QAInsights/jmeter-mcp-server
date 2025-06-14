"""
Tests for the XML JTL parser.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from analyzer.parser.xml_parser import XMLJTLParser


class TestXMLJTLParser(unittest.TestCase):
    """Tests for the XMLJTLParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = XMLJTLParser()
        
        # Create a sample XML JTL file
        self.xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testResults version="1.2">
<httpSample t="1234" lt="1000" ts="1625097600000" s="true" lb="Home Page" rc="200" rm="" tn="Thread Group 1-1" by="1234" sby="1234" ct="800"/>
<httpSample t="2345" lt="2000" ts="1625097601000" s="true" lb="Login Page" rc="200" rm="" tn="Thread Group 1-1" by="2345" sby="2345" ct="900"/>
<httpSample t="3456" lt="3000" ts="1625097602000" s="false" lb="API Call" rc="500" rm="Internal Server Error" tn="Thread Group 1-2" by="3456" sby="345" ct="1000"/>
</testResults>
"""
        self.xml_file = tempfile.NamedTemporaryFile(suffix='.xml', mode='w', delete=False)
        self.xml_file.write(self.xml_content)
        self.xml_file.close()
    
    def tearDown(self):
        """Tear down test fixtures."""
        os.unlink(self.xml_file.name)
    
    def test_parse_file(self):
        """Test parsing an XML JTL file."""
        test_results = self.parser.parse_file(self.xml_file.name)
        
        # Check that we have the correct number of samples
        self.assertEqual(len(test_results.samples), 3)
        
        # Check the first sample
        sample1 = test_results.samples[0]
        self.assertEqual(sample1.label, "Home Page")
        self.assertEqual(sample1.response_time, 1234)
        self.assertTrue(sample1.success)
        self.assertEqual(sample1.response_code, "200")
        self.assertEqual(sample1.thread_name, "Thread Group 1-1")
        self.assertEqual(sample1.bytes_received, 1234)
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
            self.parser.parse_file('/path/to/nonexistent/file.xml')
    
    def test_invalid_format(self):
        """Test parsing a file with invalid format."""
        # Create a non-XML file
        with tempfile.NamedTemporaryFile(suffix='.xml', mode='w', delete=False) as tmp:
            tmp.write("This is not XML")
        
        try:
            with self.assertRaises(ValueError):
                self.parser.parse_file(tmp.name)
        finally:
            os.unlink(tmp.name)


if __name__ == '__main__':
    unittest.main()