"""
XML parser for JMeter test results.

This module provides functionality for parsing JMeter test results
from JTL files in XML format using ElementTree.iterparse for
memory-efficient streaming.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Iterator, Union

from analyzer.models import Sample
from analyzer.parser.base import JTLParser

logger = logging.getLogger(__name__)

_SAMPLE_TAGS = ("httpSample", "sample")


class XMLJTLParser(JTLParser):
    """Parser for JMeter JTL files in XML format."""
    
    def iter_samples(self, file_path: Union[str, Path]) -> Iterator[Sample]:
        """Iterate over samples in an XML JTL file, one element at a time.
        
        Args:
            file_path: Path to the JTL file
            
        Yields:
            Sample objects, one per httpSample/sample element
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is invalid or cannot be parsed
        """
        path = Path(file_path)
        
        # Validate file
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Detect format
        format_name = self.detect_format(path)
        if format_name != "xml":
            raise ValueError(f"Invalid file format. Expected XML, got {format_name}")
        
        try:
            for _event, elem in ET.iterparse(str(path), events=("end",)):
                if elem.tag in _SAMPLE_TAGS:
                    attributes = elem.attrib
                    try:
                        # Parse timestamp (convert from ms to seconds)
                        ts = int(attributes.get("ts", "0")) / 1000
                        timestamp = datetime.fromtimestamp(ts)
                        
                        yield Sample(
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
                    except (ValueError, KeyError) as e:
                        # Log error but continue processing
                        logger.warning(f"Error parsing sample: {e}")
                    finally:
                        elem.clear()
        except ET.ParseError as e:
            raise ValueError(f"Error parsing XML file: {e}")
