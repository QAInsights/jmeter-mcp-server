"""
Tests for the analyzer parser module.
"""

import os
import tempfile
import unittest
from pathlib import Path

from analyzer.parser.base import JTLParser


class TestJTLParserBase(unittest.TestCase):
    """Tests for the base JTLParser class."""
    
    def test_validate_file_exists(self):
        """Test validating that a file exists."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.jtl') as tmp:
            self.assertTrue(JTLParser.validate_file(tmp.name))
    
    def test_validate_file_not_exists(self):
        """Test validating a non-existent file."""
        self.assertFalse(JTLParser.validate_file('/path/to/nonexistent/file.jtl'))
    
    def test_validate_file_extension(self):
        """Test validating file extensions."""
        # Create temporary files with different extensions
        with tempfile.NamedTemporaryFile(suffix='.jtl') as jtl_file, \
             tempfile.NamedTemporaryFile(suffix='.xml') as xml_file, \
             tempfile.NamedTemporaryFile(suffix='.csv') as csv_file, \
             tempfile.NamedTemporaryFile(suffix='.txt') as txt_file:
            
            self.assertTrue(JTLParser.validate_file(jtl_file.name))
            self.assertTrue(JTLParser.validate_file(xml_file.name))
            self.assertTrue(JTLParser.validate_file(csv_file.name))
            self.assertFalse(JTLParser.validate_file(txt_file.name))
    
    def test_detect_format_xml(self):
        """Test detecting XML format."""
        # Create a temporary XML file
        with tempfile.NamedTemporaryFile(suffix='.xml', mode='w', delete=False) as tmp:
            tmp.write('<?xml version="1.0" encoding="UTF-8"?>\n<testResults>\n</testResults>')
        
        try:
            self.assertEqual(JTLParser.detect_format(tmp.name), 'xml')
        finally:
            os.unlink(tmp.name)
    
    def test_detect_format_csv(self):
        """Test detecting CSV format."""
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as tmp:
            tmp.write('timeStamp,elapsed,label,responseCode,success\n')
            tmp.write('1625097600000,100,Test,200,true\n')
        
        try:
            self.assertEqual(JTLParser.detect_format(tmp.name), 'csv')
        finally:
            os.unlink(tmp.name)
    
    def test_detect_format_jtl_xml(self):
        """Test detecting XML format in a .jtl file."""
        # Create a temporary JTL file with XML content
        with tempfile.NamedTemporaryFile(suffix='.jtl', mode='w', delete=False) as tmp:
            tmp.write('<?xml version="1.0" encoding="UTF-8"?>\n<testResults>\n</testResults>')
        
        try:
            self.assertEqual(JTLParser.detect_format(tmp.name), 'xml')
        finally:
            os.unlink(tmp.name)
    
    def test_detect_format_jtl_csv(self):
        """Test detecting CSV format in a .jtl file."""
        # Create a temporary JTL file with CSV content
        with tempfile.NamedTemporaryFile(suffix='.jtl', mode='w', delete=False) as tmp:
            tmp.write('timeStamp,elapsed,label,responseCode,success\n')
            tmp.write('1625097600000,100,Test,200,true\n')
        
        try:
            self.assertEqual(JTLParser.detect_format(tmp.name), 'csv')
        finally:
            os.unlink(tmp.name)
    
    def test_detect_format_file_not_found(self):
        """Test detecting format of a non-existent file."""
        with self.assertRaises(FileNotFoundError):
            JTLParser.detect_format('/path/to/nonexistent/file.jtl')
    
    def test_detect_format_unknown(self):
        """Test detecting format of a file with unknown format."""
        # Create a temporary file with unknown content
        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', delete=False) as tmp:
            tmp.write('This is not a JTL file\n')
        
        try:
            with self.assertRaises(ValueError):
                JTLParser.detect_format(tmp.name)
        finally:
            os.unlink(tmp.name)


if __name__ == '__main__':
    unittest.main()