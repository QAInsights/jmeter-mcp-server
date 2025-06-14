"""
Tests for the metrics calculator.
"""

import unittest
from datetime import datetime, timedelta

from analyzer.metrics.calculator import MetricsCalculator
from analyzer.models import Sample, TestResults


class TestMetricsCalculator(unittest.TestCase):
    """Tests for the MetricsCalculator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.calculator = MetricsCalculator()
        
        # Create test results with samples
        self.test_results = TestResults()
        
        # Add samples for endpoint 1
        base_time = datetime(2023, 1, 1, 12, 0, 0)
        for i in range(10):
            sample = Sample(
                timestamp=base_time + timedelta(seconds=i),
                label="Endpoint1",
                response_time=100 + i * 10,  # 100, 110, 120, ..., 190
                success=True,
                response_code="200"
            )
            self.test_results.add_sample(sample)
        
        # Add samples for endpoint 2 (including some errors)
        for i in range(5):
            sample = Sample(
                timestamp=base_time + timedelta(seconds=i + 10),
                label="Endpoint2",
                response_time=200 + i * 20,  # 200, 220, 240, 260, 280
                success=i < 4,  # Last one is an error
                response_code="200" if i < 4 else "500",
                error_message="" if i < 4 else "Internal Server Error"
            )
            self.test_results.add_sample(sample)
    
    def test_calculate_overall_metrics(self):
        """Test calculating overall metrics."""
        metrics = self.calculator.calculate_overall_metrics(self.test_results)
        
        # Check basic metrics
        self.assertEqual(metrics.total_samples, 15)
        self.assertEqual(metrics.error_count, 1)
        self.assertAlmostEqual(metrics.error_rate, 100 * 1/15)
        
        # Check response time metrics
        expected_response_times = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 220, 240, 260, 280]
        self.assertAlmostEqual(metrics.average_response_time, sum(expected_response_times) / len(expected_response_times))
        self.assertAlmostEqual(metrics.median_response_time, 170)  # Median of the 15 values
        self.assertAlmostEqual(metrics.min_response_time, 100)
        self.assertAlmostEqual(metrics.max_response_time, 280)
        
        # Check percentiles
        self.assertAlmostEqual(metrics.percentile_90, 260)
        self.assertAlmostEqual(metrics.percentile_95, 270)
        self.assertAlmostEqual(metrics.percentile_99, 278)
        
        # Check throughput and duration
        self.assertEqual(metrics.test_duration, 14)  # 14 seconds from first to last sample
        self.assertAlmostEqual(metrics.throughput, 15 / 14)  # 15 samples over 14 seconds
    
    def test_calculate_endpoint_metrics(self):
        """Test calculating endpoint-specific metrics."""
        endpoint_metrics = self.calculator.calculate_endpoint_metrics(self.test_results)
        
        # Check that we have metrics for both endpoints
        self.assertEqual(len(endpoint_metrics), 2)
        self.assertIn("Endpoint1", endpoint_metrics)
        self.assertIn("Endpoint2", endpoint_metrics)
        
        # Check metrics for endpoint 1
        metrics1 = endpoint_metrics["Endpoint1"]
        self.assertEqual(metrics1.endpoint, "Endpoint1")
        self.assertEqual(metrics1.total_samples, 10)
        self.assertEqual(metrics1.error_count, 0)
        self.assertEqual(metrics1.error_rate, 0)
        self.assertAlmostEqual(metrics1.average_response_time, 145)  # Average of 100, 110, ..., 190
        
        # Check metrics for endpoint 2
        metrics2 = endpoint_metrics["Endpoint2"]
        self.assertEqual(metrics2.endpoint, "Endpoint2")
        self.assertEqual(metrics2.total_samples, 5)
        self.assertEqual(metrics2.error_count, 1)
        self.assertAlmostEqual(metrics2.error_rate, 20)  # 1 error out of 5 samples
        self.assertAlmostEqual(metrics2.average_response_time, 240)  # Average of 200, 220, 240, 260, 280
    
    def test_calculate_time_series_metrics(self):
        """Test calculating time series metrics."""
        # Use a 5-second interval
        time_series = self.calculator.calculate_time_series_metrics(self.test_results, interval_seconds=5)
        
        # We should have 3 intervals: 0-5s, 5-10s, 10-15s
        self.assertEqual(len(time_series), 3)
        
        # Check first interval (0-5s)
        self.assertEqual(time_series[0].timestamp, datetime(2023, 1, 1, 12, 0, 0))
        self.assertEqual(time_series[0].active_threads, 0)  # No thread names in our test data
        self.assertAlmostEqual(time_series[0].throughput, 5 / 5)  # 5 samples over 5 seconds
        self.assertAlmostEqual(time_series[0].average_response_time, (100 + 110 + 120 + 130 + 140) / 5)
        self.assertEqual(time_series[0].error_rate, 0)  # No errors in first interval
        
        # Check third interval (10-15s)
        self.assertEqual(time_series[2].timestamp, datetime(2023, 1, 1, 12, 0, 10))
        self.assertAlmostEqual(time_series[2].throughput, 5 / 5)  # 5 samples over 5 seconds
        self.assertAlmostEqual(time_series[2].average_response_time, (200 + 220 + 240 + 260 + 280) / 5)
        self.assertAlmostEqual(time_series[2].error_rate, 20)  # 1 error out of 5 samples
    
    def test_compare_with_benchmarks(self):
        """Test comparing metrics with benchmarks."""
        # Calculate metrics
        metrics = self.calculator.calculate_overall_metrics(self.test_results)
        
        # Define benchmarks
        benchmarks = {
            "average_response_time": 150,
            "error_rate": 0,
            "throughput": 2
        }
        
        # Compare with benchmarks
        comparison = self.calculator.compare_with_benchmarks(metrics, benchmarks)
        
        # Check comparison results
        self.assertIn("average_response_time", comparison)
        self.assertIn("error_rate", comparison)
        self.assertIn("throughput", comparison)
        
        # Check average_response_time comparison
        avg_rt_comp = comparison["average_response_time"]
        self.assertEqual(avg_rt_comp["benchmark"], 150)
        self.assertAlmostEqual(avg_rt_comp["actual"], metrics.average_response_time)
        self.assertAlmostEqual(avg_rt_comp["difference"], metrics.average_response_time - 150)
        self.assertAlmostEqual(avg_rt_comp["percent_difference"], 
                              (metrics.average_response_time - 150) / 150 * 100)
        
        # Check error_rate comparison
        error_rate_comp = comparison["error_rate"]
        self.assertEqual(error_rate_comp["benchmark"], 0)
        self.assertAlmostEqual(error_rate_comp["actual"], metrics.error_rate)
        self.assertAlmostEqual(error_rate_comp["difference"], metrics.error_rate)
        self.assertEqual(error_rate_comp["percent_difference"], float('inf'))  # Division by zero
        
        # Check throughput comparison
        throughput_comp = comparison["throughput"]
        self.assertEqual(throughput_comp["benchmark"], 2)
        self.assertAlmostEqual(throughput_comp["actual"], metrics.throughput)
        self.assertAlmostEqual(throughput_comp["difference"], metrics.throughput - 2)
        self.assertAlmostEqual(throughput_comp["percent_difference"], 
                              (metrics.throughput - 2) / 2 * 100)
    
    def test_empty_results(self):
        """Test calculating metrics for empty test results."""
        empty_results = TestResults()
        
        with self.assertRaises(ValueError):
            self.calculator.calculate_overall_metrics(empty_results)
        
        with self.assertRaises(ValueError):
            self.calculator.calculate_endpoint_metrics(empty_results)
        
        with self.assertRaises(ValueError):
            self.calculator.calculate_time_series_metrics(empty_results)
    
    def test_invalid_interval(self):
        """Test calculating time series metrics with invalid interval."""
        with self.assertRaises(ValueError):
            self.calculator.calculate_time_series_metrics(self.test_results, interval_seconds=0)
        
        with self.assertRaises(ValueError):
            self.calculator.calculate_time_series_metrics(self.test_results, interval_seconds=-1)


if __name__ == '__main__':
    unittest.main()