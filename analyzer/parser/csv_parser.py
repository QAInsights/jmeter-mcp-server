"""
CSV parser for JMeter test results.

This module provides functionality for parsing JMeter test results
from JTL files in CSV format using streaming for efficient processing.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

from analyzer.models import Sample, TestResults
from analyzer.parser.base import JTLParser


class CSVJTLParser(JTLParser):
    """Parser for JMeter JTL files in CSV format."""
    
    # Default column mappings for JMeter CSV output
    DEFAULT_COLUMN_MAPPINGS = {
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
    
    def __init__(self, column_mappings: Dict[str, str] = None):
        """Initialize the parser.
        
        Args:
            column_mappings: Custom column mappings (default: None)
        """
        self.column_mappings = column_mappings or self.DEFAULT_COLUMN_MAPPINGS
    
    def parse_file(self, file_path: Union[str, Path]) -> TestResults:
        """Parse a JTL file in CSV format.
        
        Args:
            file_path: Path to the JTL file
            
        Returns:
            TestResults object containing parsed data
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is invalid
        """
        path = Path(file_path)
        
        # Validate file
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Detect format
        format_name = self.detect_format(path)
        if format_name != "csv":
            raise ValueError(f"Invalid file format. Expected CSV, got {format_name}")
        
        # Create test results object
        test_results = TestResults()
        
        try:
            # Open and parse the CSV file
            with open(path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Validate that required columns are present
                if not reader.fieldnames:
                    raise ValueError("CSV file has no header row")
                
                # Check if we can map all required columns
                missing_columns = []
                column_indices = {}
                
                for model_field, csv_field in self.column_mappings.items():
                    if csv_field not in reader.fieldnames:
                        missing_columns.append(csv_field)
                    else:
                        column_indices[model_field] = reader.fieldnames.index(csv_field)
                
                if missing_columns:
                    raise ValueError(f"CSV file is missing required columns: {', '.join(missing_columns)}")
                
                # Process each row
                for row in reader:
                    try:
                        # Parse timestamp (convert from milliseconds to seconds)
                        ts = int(row[self.column_mappings['timestamp']]) / 1000
                        timestamp = datetime.fromtimestamp(ts)
                        
                        # Parse success (convert string to boolean)
                        success_str = row[self.column_mappings['success']].lower()
                        success = success_str == "true" or success_str == "1"
                        
                        # Create sample
                        sample = Sample(
                            timestamp=timestamp,
                            label=row[self.column_mappings['label']],
                            response_time=int(row[self.column_mappings['response_time']]),
                            success=success,
                            response_code=row[self.column_mappings['response_code']],
                            error_message=row.get(self.column_mappings['error_message'], ""),
                            thread_name=row.get(self.column_mappings['thread_name'], ""),
                            bytes_received=int(row.get(self.column_mappings['bytes_received'], 0)),
                            bytes_sent=int(row.get(self.column_mappings['bytes_sent'], 0)),
                            latency=int(row.get(self.column_mappings['latency'], 0)),
                            connect_time=int(row.get(self.column_mappings['connect_time'], 0))
                        )
                        
                        # Add sample to test results
                        test_results.add_sample(sample)
                        
                    except (ValueError, KeyError) as e:
                        # Log error but continue processing
                        print(f"Error parsing row: {e}")
                        continue
        
        except Exception as e:
            raise ValueError(f"Error parsing CSV file: {e}")
        
        return test_results