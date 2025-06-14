"""
Data models for the JMeter Test Results Analyzer.

This module defines the core data structures used throughout the analyzer,
including TestResults, Sample, and various metrics classes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Sample:
    """Represents a single sample/request in a JMeter test."""
    
    timestamp: datetime
    label: str
    response_time: int  # in milliseconds
    success: bool
    response_code: str
    error_message: Optional[str] = None
    thread_name: Optional[str] = None
    bytes_sent: Optional[int] = None
    bytes_received: Optional[int] = None
    latency: Optional[int] = None  # in milliseconds
    connect_time: Optional[int] = None  # in milliseconds


@dataclass
class TestResults:
    """Represents the results of a JMeter test."""
    
    samples: List[Sample] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def add_sample(self, sample: Sample) -> None:
        """Add a sample to the test results."""
        self.samples.append(sample)
        
        # Update start and end times
        if self.start_time is None or sample.timestamp < self.start_time:
            self.start_time = sample.timestamp
        if self.end_time is None or sample.timestamp > self.end_time:
            self.end_time = sample.timestamp


@dataclass
class OverallMetrics:
    """Represents overall metrics for a test or endpoint."""
    
    total_samples: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    average_response_time: float = 0.0
    median_response_time: float = 0.0
    percentile_90: float = 0.0
    percentile_95: float = 0.0
    percentile_99: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    throughput: float = 0.0  # requests per second
    test_duration: float = 0.0  # in seconds


@dataclass
class EndpointMetrics(OverallMetrics):
    """Represents metrics for a specific endpoint/sampler."""
    
    endpoint: str = ""


@dataclass
class TimeSeriesMetrics:
    """Represents metrics for a specific time interval."""
    
    timestamp: datetime
    active_threads: int = 0
    throughput: float = 0.0
    average_response_time: float = 0.0
    error_rate: float = 0.0


@dataclass
class Bottleneck:
    """Represents a performance bottleneck."""
    
    endpoint: str
    metric_type: str  # response_time, error_rate, etc.
    value: float
    threshold: float
    severity: str  # high, medium, low


@dataclass
class Anomaly:
    """Represents a performance anomaly."""
    
    timestamp: datetime
    endpoint: str
    expected_value: float
    actual_value: float
    deviation_percentage: float


@dataclass
class Recommendation:
    """Represents a performance improvement recommendation."""
    
    issue: str
    recommendation: str
    expected_impact: str
    implementation_difficulty: str  # high, medium, low


@dataclass
class Insight:
    """Represents a performance insight."""
    
    topic: str
    description: str
    supporting_data: Dict = field(default_factory=dict)