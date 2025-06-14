"""
Tests for the analyzer models.
"""

import unittest
from datetime import datetime

from analyzer.models import Sample, TestResults, OverallMetrics, EndpointMetrics


class TestSample(unittest.TestCase):
    """Tests for the Sample class."""
    
    def test_sample_creation(self):
        """Test creating a Sample instance."""
        timestamp = datetime.now()
        sample = Sample(
            timestamp=timestamp,
            label="Test Sample",
            response_time=100,
            success=True,
            response_code="200",
            error_message=None,
            thread_name="Thread Group 1-1",
            bytes_sent=150,
            bytes_received=1024,
            latency=50,
            connect_time=20
        )
        
        self.assertEqual(sample.timestamp, timestamp)
        self.assertEqual(sample.label, "Test Sample")
        self.assertEqual(sample.response_time, 100)
        self.assertTrue(sample.success)
        self.assertEqual(sample.response_code, "200")
        self.assertIsNone(sample.error_message)
        self.assertEqual(sample.thread_name, "Thread Group 1-1")
        self.assertEqual(sample.bytes_sent, 150)
        self.assertEqual(sample.bytes_received, 1024)
        self.assertEqual(sample.latency, 50)
        self.assertEqual(sample.connect_time, 20)


class TestTestResults(unittest.TestCase):
    """Tests for the TestResults class."""
    
    def test_add_sample(self):
        """Test adding samples to TestResults."""
        results = TestResults()
        self.assertEqual(len(results.samples), 0)
        
        # Add a sample
        timestamp1 = datetime(2023, 1, 1, 12, 0, 0)
        sample1 = Sample(
            timestamp=timestamp1,
            label="Sample 1",
            response_time=100,
            success=True,
            response_code="200"
        )
        results.add_sample(sample1)
        
        self.assertEqual(len(results.samples), 1)
        self.assertEqual(results.start_time, timestamp1)
        self.assertEqual(results.end_time, timestamp1)
        
        # Add another sample with earlier timestamp
        timestamp2 = datetime(2023, 1, 1, 11, 0, 0)
        sample2 = Sample(
            timestamp=timestamp2,
            label="Sample 2",
            response_time=200,
            success=True,
            response_code="200"
        )
        results.add_sample(sample2)
        
        self.assertEqual(len(results.samples), 2)
        self.assertEqual(results.start_time, timestamp2)  # Should update to earlier time
        self.assertEqual(results.end_time, timestamp1)
        
        # Add another sample with later timestamp
        timestamp3 = datetime(2023, 1, 1, 13, 0, 0)
        sample3 = Sample(
            timestamp=timestamp3,
            label="Sample 3",
            response_time=300,
            success=True,
            response_code="200"
        )
        results.add_sample(sample3)
        
        self.assertEqual(len(results.samples), 3)
        self.assertEqual(results.start_time, timestamp2)
        self.assertEqual(results.end_time, timestamp3)  # Should update to later time


class TestMetrics(unittest.TestCase):
    """Tests for the metrics classes."""
    
    def test_overall_metrics(self):
        """Test creating OverallMetrics instance."""
        metrics = OverallMetrics(
            total_samples=100,
            error_count=5,
            error_rate=5.0,
            average_response_time=250.5,
            median_response_time=220.0,
            percentile_90=400.0,
            percentile_95=450.0,
            percentile_99=500.0,
            min_response_time=100.0,
            max_response_time=600.0,
            throughput=10.5,
            test_duration=60.0
        )
        
        self.assertEqual(metrics.total_samples, 100)
        self.assertEqual(metrics.error_count, 5)
        self.assertEqual(metrics.error_rate, 5.0)
        self.assertEqual(metrics.average_response_time, 250.5)
        self.assertEqual(metrics.median_response_time, 220.0)
        self.assertEqual(metrics.percentile_90, 400.0)
        self.assertEqual(metrics.percentile_95, 450.0)
        self.assertEqual(metrics.percentile_99, 500.0)
        self.assertEqual(metrics.min_response_time, 100.0)
        self.assertEqual(metrics.max_response_time, 600.0)
        self.assertEqual(metrics.throughput, 10.5)
        self.assertEqual(metrics.test_duration, 60.0)
    
    def test_endpoint_metrics(self):
        """Test creating EndpointMetrics instance."""
        metrics = EndpointMetrics(
            endpoint="Test Endpoint",
            total_samples=50,
            error_count=2,
            error_rate=4.0,
            average_response_time=200.5,
            median_response_time=180.0,
            percentile_90=350.0,
            percentile_95=400.0,
            percentile_99=450.0,
            min_response_time=90.0,
            max_response_time=500.0,
            throughput=8.5,
            test_duration=60.0
        )
        
        self.assertEqual(metrics.endpoint, "Test Endpoint")
        self.assertEqual(metrics.total_samples, 50)
        self.assertEqual(metrics.error_count, 2)
        self.assertEqual(metrics.error_rate, 4.0)
        self.assertEqual(metrics.average_response_time, 200.5)
        self.assertEqual(metrics.median_response_time, 180.0)
        self.assertEqual(metrics.percentile_90, 350.0)
        self.assertEqual(metrics.percentile_95, 400.0)
        self.assertEqual(metrics.percentile_99, 450.0)
        self.assertEqual(metrics.min_response_time, 90.0)
        self.assertEqual(metrics.max_response_time, 500.0)
        self.assertEqual(metrics.throughput, 8.5)
        self.assertEqual(metrics.test_duration, 60.0)


if __name__ == '__main__':
    unittest.main()