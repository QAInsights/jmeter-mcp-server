"""
XML parser for JMeter test results.

This module provides functionality for parsing JMeter test results
from JTL files in XML format using SAX for efficient processing.
"""

import xml.sax
from datetime import datetime
from pathlib import Path
from typing import Union

from analyzer.models import Sample, TestResults
from analyzer.parser.base import JTLParser


class JMeterXMLHandler(xml.sax.ContentHandler):
    """SAX handler for JMeter XML results."""
    
    def __init__(self, test_results: TestResults):
        """Initialize the handler.
        
        Args:
            test_results: TestResults object to populate
        """
        super().__init__()
        self.test_results = test_results
    
    def startElement(self, tag, attributes):
        """Process start element.
        
        Args:
            tag: Element tag name
            attributes: Element attributes
        """
        # Process httpSample or sample elements
        if tag in ["httpSample", "sample"]:
            try:
                # Parse timestamp
                ts = int(attributes.get("ts", "0")) / 1000  # Convert from ms to seconds
                timestamp = datetime.fromtimestamp(ts)
                
                # Create sample
                sample = Sample(
                    timestamp=timestamp,
                    label=attributes.get("lb", ""),
                    response_time=int(attributes.get("t", "0")),
                    success=attributes.get("s", "true").lower() == "true",
                    response_code=attributes.get("rc", ""),
                    error_message=attributes.get("rm", ""),
                    thread_name=attributes.get("tn", ""),
                    bytes_received=int(attributes.get("by", "0")),
                    bytes_sent=int(attributes.get("sby", "0")),
                    latency=int(attributes.get("lt", "0")),
                    connect_time=int(attributes.get("ct", "0"))
                )
                
                # Add sample to test results
                self.test_results.add_sample(sample)
                
            except (ValueError, KeyError) as e:
                # Log error but continue processing
                print(f"Error parsing sample: {e}")


class XMLJTLParser(JTLParser):
    """Parser for JMeter JTL files in XML format."""
    
    def parse_file(self, file_path: Union[str, Path]) -> TestResults:
        """Parse a JTL file in XML format.
        
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
        if format_name != "xml":
            raise ValueError(f"Invalid file format. Expected XML, got {format_name}")
        
        # Create test results object
        test_results = TestResults()
        
        # Create SAX parser
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_namespaces, 0)
        
        # Create and set content handler
        handler = JMeterXMLHandler(test_results)
        parser.setContentHandler(handler)
        
        try:
            # Parse the file
            parser.parse(str(path))
        except Exception as e:
            raise ValueError(f"Error parsing XML file: {e}")
        
        return test_results