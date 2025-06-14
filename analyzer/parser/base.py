"""
Base parser interface for JMeter test results.

This module defines the base interface for JTL parsers.
"""

import abc
from pathlib import Path
from typing import Union

from analyzer.models import TestResults


class JTLParser(abc.ABC):
    """Base class for JTL parsers."""
    
    @abc.abstractmethod
    def parse_file(self, file_path: Union[str, Path]) -> TestResults:
        """Parse a JTL file and return structured test results.
        
        Args:
            file_path: Path to the JTL file
            
        Returns:
            TestResults object containing parsed data
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is invalid
        """
        pass
    
    @staticmethod
    def validate_file(file_path: Union[str, Path]) -> bool:
        """Validate that the file exists and has a valid extension.
        
        Args:
            file_path: Path to the JTL file
            
        Returns:
            True if the file is valid, False otherwise
        """
        path = Path(file_path)
        
        # Check if file exists
        if not path.exists():
            return False
        
        # Check if file has a valid extension
        valid_extensions = ['.jtl', '.xml', '.csv']
        if path.suffix.lower() not in valid_extensions:
            return False
        
        return True
    
    @staticmethod
    def detect_format(file_path: Union[str, Path]) -> str:
        """Detect whether the JTL file is in XML or CSV format.
        
        Args:
            file_path: Path to the JTL file
            
        Returns:
            'xml' or 'csv'
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the format cannot be determined
        """
        path = Path(file_path)
        
        # Check if file exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Try to determine format based on content
        with open(path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            
            # Check for XML declaration
            if first_line.startswith('<?xml'):
                return 'xml'
            
            # Check for CSV header
            if ',' in first_line and ('timeStamp' in first_line or 'elapsed' in first_line):
                return 'csv'
            
            # If we can't determine from the first line, check file extension
            if path.suffix.lower() == '.xml':
                return 'xml'
            if path.suffix.lower() == '.csv':
                return 'csv'
            if path.suffix.lower() == '.jtl':
                # For .jtl files, we need to look at more content
                f.seek(0)
                content = f.read(1000)  # Read first 1000 chars
                if '<?xml' in content:
                    return 'xml'
                if ',' in content and ('timeStamp' in content or 'elapsed' in content):
                    return 'csv'
        
        raise ValueError(f"Could not determine format of file: {file_path}")