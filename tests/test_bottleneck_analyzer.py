"""
Tests for the bottleneck analyzer.
"""

import unittest
from datetime import datetime, timedelta

from analyzer.bottleneck.analyzer import BottleneckAnalyzer
from analyzer.models import EndpointMetrics, TimeSeriesMetrics


class TestBottleneckAnalyzer(unittest.TestCase):
    """Tests for the BottleneckAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = BottleneckAnalyzer()
        
        # Create endpoint metrics
        self.endpoint_metrics = {
            "Fast Endpoint": EndpointMetrics(
                endpoint="Fast Endpoint",
                total_samples=100,
                error_count=0,
                error_rate=0.0,
                average_response_time=100.0,
                median_response_time=95.0,
                percentile_90=150.0,
                percentile_95=180.0,
                percentile_99=200.0,
                min_response_time=50.0,
                max_response_time=250.0,
                throughput=10.0,
                test_duration=10.0
            ),
            "Medium Endpoint": EndpointMetrics(
                endpoint="Medium Endpoint",
                total_samples=100,
                error_count=2,
                error_rate=2.0,
                average_response_time=200.0,
                median_response_time=190.0,
                percentile_90=300.0,
                percentile_95=350.0,
                percentile_99=400.0,
                min_response_time=100.0,
                max_response_time=450.0,
                throughput=10.0,
                test_duration=10.0
            ),
            "Slow Endpoint": EndpointMetrics(
                endpoint="Slow Endpoint",
                total_samples=100,
                error_count=5,
                error_rate=5.0,
                average_response_time=500.0,
                median_response_time=450.0,
                percentile_90=800.0,
                percentile_95=900.0,
                percentile_99=1000.0,
                min_response_time=200.0,
                max_response_time=1200.0,
                throughput=10.0,
                test_duration=10.0
            ),
            "Error Endpoint": EndpointMetrics(
                endpoint="Error Endpoint",
                total_samples=100,
                error_count=15,
                error_rate=15.0,
                average_response_time=300.0,
                median_response_time=280.0,
                percentile_90=450.0,
                percentile_95=500.0,
                percentile_99=600.0,
                min_response_time=150.0,
                max_response_time=700.0,
                throughput=10.0,
                test_duration=10.0
            )
        }
        
        # Create time series metrics
        base_time = datetime(2023, 1, 1, 12, 0, 0)
        self.time_series_metrics = [
            TimeSeriesMetrics(
                timestamp=base_time + timedelta(seconds=i * 5),
                active_threads=i + 1,
                throughput=10.0,
                average_response_time=100.0 + i * 20,
                error_rate=0.0 if i < 8 else 5.0
            )
            for i in range(10)
        ]
        
        # Add an anomaly
        self.time_series_metrics[5].average_response_time = 500.0  # Spike in the middle
    
    def test_identify_slow_endpoints(self):
        """Test identifying slow endpoints."""
        # Use a higher threshold factor to get only the Slow Endpoint
        bottlenecks = self.analyzer.identify_slow_endpoints(self.endpoint_metrics, threshold_factor=2.0)
        
        # We should have identified the slow endpoint
        self.assertEqual(len(bottlenecks), 1)
        self.assertEqual(bottlenecks[0].endpoint, "Slow Endpoint")
        self.assertEqual(bottlenecks[0].metric_type, "response_time")
        # With threshold_factor=2.0, the severity should be medium or high
        self.assertIn(bottlenecks[0].severity, ["medium", "high"])
        
        # Test with a lower threshold factor to catch more endpoints
        bottlenecks = self.analyzer.identify_slow_endpoints(self.endpoint_metrics, threshold_factor=0.8)
        self.assertGreaterEqual(len(bottlenecks), 2)
        self.assertEqual(bottlenecks[0].endpoint, "Slow Endpoint")  # Should still be first
    
    def test_identify_error_prone_endpoints(self):
        """Test identifying error-prone endpoints."""
        bottlenecks = self.analyzer.identify_error_prone_endpoints(self.endpoint_metrics, threshold_error_rate=3.0)
        
        # We should have identified both error-prone endpoints
        self.assertEqual(len(bottlenecks), 2)
        self.assertEqual(bottlenecks[0].endpoint, "Error Endpoint")  # Higher error rate should be first
        self.assertEqual(bottlenecks[0].metric_type, "error_rate")
        self.assertEqual(bottlenecks[0].severity, "high")
        
        self.assertEqual(bottlenecks[1].endpoint, "Slow Endpoint")
        self.assertEqual(bottlenecks[1].metric_type, "error_rate")
        self.assertEqual(bottlenecks[1].severity, "medium")
        
        # Test with a higher threshold to catch fewer endpoints
        bottlenecks = self.analyzer.identify_error_prone_endpoints(self.endpoint_metrics, threshold_error_rate=10.0)
        self.assertEqual(len(bottlenecks), 1)
        self.assertEqual(bottlenecks[0].endpoint, "Error Endpoint")
    
    def test_detect_anomalies(self):
        """Test detecting response time anomalies."""
        anomalies = self.analyzer.detect_anomalies(self.time_series_metrics)
        
        # We should have detected the spike
        self.assertGreaterEqual(len(anomalies), 1)
        
        # The spike should be the first anomaly
        spike_anomaly = anomalies[0]
        self.assertEqual(spike_anomaly.timestamp, datetime(2023, 1, 1, 12, 0, 25))  # 5th interval
        self.assertGreater(abs(spike_anomaly.deviation_percentage), 50)  # Should be a significant deviation
    
    def test_analyze_concurrency_impact(self):
        """Test analyzing concurrency impact."""
        # Our time series has increasing thread counts and response times
        analysis = self.analyzer.analyze_concurrency_impact(self.time_series_metrics)
        
        # There should be a positive correlation
        self.assertGreater(analysis["correlation"], 0.5)
        
        # Create a new time series with no correlation
        no_correlation_series = [
            TimeSeriesMetrics(
                timestamp=datetime(2023, 1, 1, 12, 0, 0) + timedelta(seconds=i * 5),
                active_threads=i + 1,
                throughput=10.0,
                average_response_time=200.0,  # Constant response time
                error_rate=0.0
            )
            for i in range(10)
        ]
        
        analysis = self.analyzer.analyze_concurrency_impact(no_correlation_series)
        self.assertLess(analysis["correlation"], 0.5)
        self.assertFalse(analysis["has_degradation"])
    
    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        self.assertEqual(len(self.analyzer.identify_slow_endpoints({})), 0)
        self.assertEqual(len(self.analyzer.identify_error_prone_endpoints({})), 0)
        self.assertEqual(len(self.analyzer.detect_anomalies([])), 0)
        
        analysis = self.analyzer.analyze_concurrency_impact([])
        self.assertEqual(analysis["correlation"], 0)
        self.assertFalse(analysis["has_degradation"])


if __name__ == '__main__':
    unittest.main()