"""
Tests for the visualization engine.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

from analyzer.models import EndpointMetrics, TimeSeriesMetrics
from analyzer.visualization.engine import VisualizationEngine


class TestVisualizationEngine(unittest.TestCase):
    """Tests for the VisualizationEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for output files
        self.temp_dir = tempfile.mkdtemp()
        self.engine = VisualizationEngine(output_dir=self.temp_dir)
        
        # Create time series metrics
        base_time = datetime(2023, 1, 1, 12, 0, 0)
        self.time_series_metrics = [
            TimeSeriesMetrics(
                timestamp=base_time + timedelta(seconds=i * 5),
                active_threads=i + 1,
                throughput=10.0 + i * 0.5,
                average_response_time=100.0 + i * 20,
                error_rate=0.0 if i < 8 else 5.0
            )
            for i in range(10)
        ]
        
        # Create endpoint metrics
        self.endpoint_metrics = {
            "Endpoint 1": EndpointMetrics(
                endpoint="Endpoint 1",
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
            "Endpoint 2": EndpointMetrics(
                endpoint="Endpoint 2",
                total_samples=100,
                error_count=5,
                error_rate=5.0,
                average_response_time=200.0,
                median_response_time=190.0,
                percentile_90=300.0,
                percentile_95=350.0,
                percentile_99=400.0,
                min_response_time=100.0,
                max_response_time=450.0,
                throughput=8.0,
                test_duration=10.0
            ),
            "Endpoint 3": EndpointMetrics(
                endpoint="Endpoint 3",
                total_samples=100,
                error_count=10,
                error_rate=10.0,
                average_response_time=300.0,
                median_response_time=280.0,
                percentile_90=450.0,
                percentile_95=500.0,
                percentile_99=600.0,
                min_response_time=150.0,
                max_response_time=700.0,
                throughput=5.0,
                test_duration=10.0
            )
        }
        
        # Create response times
        self.response_times = [100, 120, 130, 140, 150, 160, 170, 180, 190, 200, 
                              220, 240, 260, 280, 300, 350, 400, 450, 500, 600]
        
        # Create analysis results
        self.analysis_results = {
            "summary": {
                "total_samples": 300,
                "error_count": 15,
                "error_rate": 5.0,
                "average_response_time": 200.0,
                "median_response_time": 180.0,
                "percentile_90": 350.0,
                "percentile_95": 400.0,
                "percentile_99": 500.0,
                "min_response_time": 100.0,
                "max_response_time": 600.0,
                "throughput": 7.5,
                "start_time": datetime(2023, 1, 1, 12, 0, 0),
                "end_time": datetime(2023, 1, 1, 12, 0, 40),
                "duration": 40.0
            },
            "detailed": {
                "endpoints": {
                    "Endpoint 1": {
                        "total_samples": 100,
                        "error_count": 0,
                        "error_rate": 0.0,
                        "average_response_time": 100.0,
                        "median_response_time": 95.0,
                        "percentile_90": 150.0,
                        "percentile_95": 180.0,
                        "percentile_99": 200.0,
                        "min_response_time": 50.0,
                        "max_response_time": 250.0,
                        "throughput": 10.0
                    },
                    "Endpoint 2": {
                        "total_samples": 100,
                        "error_count": 5,
                        "error_rate": 5.0,
                        "average_response_time": 200.0,
                        "median_response_time": 190.0,
                        "percentile_90": 300.0,
                        "percentile_95": 350.0,
                        "percentile_99": 400.0,
                        "min_response_time": 100.0,
                        "max_response_time": 450.0,
                        "throughput": 8.0
                    },
                    "Endpoint 3": {
                        "total_samples": 100,
                        "error_count": 10,
                        "error_rate": 10.0,
                        "average_response_time": 300.0,
                        "median_response_time": 280.0,
                        "percentile_90": 450.0,
                        "percentile_95": 500.0,
                        "percentile_99": 600.0,
                        "min_response_time": 150.0,
                        "max_response_time": 700.0,
                        "throughput": 5.0
                    }
                },
                "bottlenecks": {
                    "slow_endpoints": [
                        {
                            "endpoint": "Endpoint 3",
                            "response_time": 300.0,
                            "threshold": 200.0,
                            "severity": "high"
                        }
                    ],
                    "error_prone_endpoints": [
                        {
                            "endpoint": "Endpoint 3",
                            "error_rate": 10.0,
                            "threshold": 5.0,
                            "severity": "medium"
                        }
                    ]
                },
                "insights": {
                    "recommendations": [
                        {
                            "issue": "High response time in Endpoint 3",
                            "recommendation": "Optimize database queries",
                            "expected_impact": "Reduced response time",
                            "implementation_difficulty": "medium",
                            "priority_level": "high"
                        }
                    ],
                    "scaling_insights": [
                        {
                            "topic": "Concurrency Impact",
                            "description": "Performance degrades with increasing concurrency"
                        }
                    ]
                }
            }
        }
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)
    
    def test_create_time_series_graph(self):
        """Test creating a time series graph."""
        # Test with default parameters
        graph = self.engine.create_time_series_graph(self.time_series_metrics)
        self.assertIsNotNone(graph)
        self.assertEqual(graph["type"], "time_series")
        
        # Test with output file
        output_file = "time_series.txt"
        output_path = self.engine.create_time_series_graph(
            self.time_series_metrics, output_file=output_file)
        self.assertTrue(os.path.exists(output_path))
        
        # Test with different metric
        graph = self.engine.create_time_series_graph(
            self.time_series_metrics, metric_name="throughput")
        self.assertIsNotNone(graph)
        self.assertEqual(graph["y_label"], "Throughput (requests/second)")
        
        # Test with empty metrics
        with self.assertRaises(ValueError):
            self.engine.create_time_series_graph([])
        
        # Test with invalid metric name
        with self.assertRaises(ValueError):
            self.engine.create_time_series_graph(
                self.time_series_metrics, metric_name="invalid_metric")
    
    def test_create_distribution_graph(self):
        """Test creating a distribution graph."""
        # Test with default parameters
        graph = self.engine.create_distribution_graph(self.response_times)
        self.assertIsNotNone(graph)
        self.assertEqual(graph["type"], "distribution")
        
        # Test with output file
        output_file = "distribution.txt"
        output_path = self.engine.create_distribution_graph(
            self.response_times, output_file=output_file)
        self.assertTrue(os.path.exists(output_path))
        
        # Test with custom percentiles
        graph = self.engine.create_distribution_graph(
            self.response_times, percentiles=[25, 50, 75])
        self.assertIsNotNone(graph)
        self.assertIn(25, graph["percentiles"])
        self.assertIn(50, graph["percentiles"])
        self.assertIn(75, graph["percentiles"])
        
        # Test with empty response times
        with self.assertRaises(ValueError):
            self.engine.create_distribution_graph([])
    
    def test_create_endpoint_comparison_chart(self):
        """Test creating an endpoint comparison chart."""
        # Test with default parameters
        chart = self.engine.create_endpoint_comparison_chart(self.endpoint_metrics)
        self.assertIsNotNone(chart)
        self.assertEqual(chart["type"], "endpoint_comparison")
        
        # Test with output file
        output_file = "comparison.txt"
        output_path = self.engine.create_endpoint_comparison_chart(
            self.endpoint_metrics, output_file=output_file)
        self.assertTrue(os.path.exists(output_path))
        
        # Test with different metric
        chart = self.engine.create_endpoint_comparison_chart(
            self.endpoint_metrics, metric_name="error_rate")
        self.assertIsNotNone(chart)
        self.assertEqual(chart["x_label"], "Error Rate (%)")
        
        # Test with empty metrics
        with self.assertRaises(ValueError):
            self.engine.create_endpoint_comparison_chart({})
        
        # Test with invalid metric name
        with self.assertRaises(ValueError):
            self.engine.create_endpoint_comparison_chart(
                self.endpoint_metrics, metric_name="invalid_metric")
    
    def test_create_html_report(self):
        """Test creating an HTML report."""
        output_file = "report.html"
        output_path = self.engine.create_html_report(
            self.analysis_results, output_file=output_file)
        
        # Check that the file exists
        self.assertTrue(os.path.exists(output_path))
        
        # Check that the file contains expected content
        with open(output_path, 'r') as f:
            content = f.read()
            self.assertIn("JMeter Test Results Analysis", content)
            self.assertIn("Endpoint Analysis", content)
            self.assertIn("Bottleneck Analysis", content)
            self.assertIn("Insights and Recommendations", content)
    
    def test_figure_to_base64(self):
        """Test converting a figure to base64."""
        graph = self.engine.create_time_series_graph(self.time_series_metrics)
        base64_str = self.engine.figure_to_base64(graph)
        
        # Check that the result is a non-empty string
        self.assertIsInstance(base64_str, str)
        self.assertTrue(len(base64_str) > 0)


if __name__ == '__main__':
    unittest.main()