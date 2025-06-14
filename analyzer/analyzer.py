"""
Main analyzer module for JMeter test results.

This module provides the main entry point for analyzing JMeter test results.
It orchestrates the flow of data through the various components of the analyzer.
"""

from pathlib import Path
from datetime import timedelta
from typing import Dict, List, Optional, Union

from analyzer.models import TestResults, OverallMetrics, Bottleneck
from analyzer.parser.base import JTLParser
from analyzer.parser.xml_parser import XMLJTLParser
from analyzer.parser.csv_parser import CSVJTLParser
from analyzer.metrics.calculator import MetricsCalculator
from analyzer.bottleneck.analyzer import BottleneckAnalyzer
from analyzer.insights.generator import InsightsGenerator


class TestResultsAnalyzer:
    """Main analyzer class for JMeter test results."""
    
    def __init__(self):
        """Initialize the analyzer."""
        self.parsers = {}
        self.metrics_calculator = MetricsCalculator()
        self.bottleneck_analyzer = BottleneckAnalyzer()
        self.insights_generator = InsightsGenerator()
        
        # Register default parsers
        self.register_parser('xml', XMLJTLParser())
        self.register_parser('csv', CSVJTLParser())
    
    def register_parser(self, format_name: str, parser: JTLParser) -> None:
        """Register a parser for a specific format.
        
        Args:
            format_name: Name of the format (e.g., 'xml', 'csv')
            parser: Parser instance
        """
        self.parsers[format_name] = parser
    
    def analyze_file(self, file_path: Union[str, Path], 
                    detailed: bool = False) -> Dict:
        """Analyze a JTL file and return the results.
        
        Args:
            file_path: Path to the JTL file
            detailed: Whether to include detailed analysis
            
        Returns:
            Dictionary containing analysis results
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is invalid or unsupported
        """
        path = Path(file_path)
        
        # Validate file
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Detect format
        format_name = JTLParser.detect_format(path)
        
        # Get appropriate parser
        if format_name not in self.parsers:
            raise ValueError(f"No parser available for format: {format_name}")
        
        parser = self.parsers[format_name]
        
        # Parse file
        test_results = parser.parse_file(path)
        
        # Perform analysis
        analysis_results = self._analyze_results(test_results, detailed)
        
        return analysis_results
    
    def _analyze_results(self, test_results: TestResults, 
                        detailed: bool = False) -> Dict:
        """Analyze test results and return the analysis.
        
        Args:
            test_results: TestResults object
            detailed: Whether to include detailed analysis
            
        Returns:
            Dictionary containing analysis results
        """
        # Calculate overall metrics
        overall_metrics = self.metrics_calculator.calculate_overall_metrics(test_results)
        
        # Create basic results structure
        results = {
            "summary": {
                "total_samples": overall_metrics.total_samples,
                "error_count": overall_metrics.error_count,
                "error_rate": overall_metrics.error_rate,
                "average_response_time": overall_metrics.average_response_time,
                "median_response_time": overall_metrics.median_response_time,
                "percentile_90": overall_metrics.percentile_90,
                "percentile_95": overall_metrics.percentile_95,
                "percentile_99": overall_metrics.percentile_99,
                "min_response_time": overall_metrics.min_response_time,
                "max_response_time": overall_metrics.max_response_time,
                "throughput": overall_metrics.throughput,
                "start_time": test_results.start_time,
                "end_time": test_results.end_time,
                "duration": overall_metrics.test_duration
            }
        }
        
        # Add detailed analysis if requested
        if detailed:
            # Calculate endpoint metrics
            endpoint_metrics = self.metrics_calculator.calculate_endpoint_metrics(test_results)
            
            # Calculate time series metrics (5-second intervals)
            try:
                time_series_metrics = self.metrics_calculator.calculate_time_series_metrics(
                    test_results, interval_seconds=5)
            except ValueError:
                time_series_metrics = []
            
            # Identify bottlenecks
            slow_endpoints = self.bottleneck_analyzer.identify_slow_endpoints(endpoint_metrics)
            error_prone_endpoints = self.bottleneck_analyzer.identify_error_prone_endpoints(endpoint_metrics)
            anomalies = self.bottleneck_analyzer.detect_anomalies(time_series_metrics)
            concurrency_impact = self.bottleneck_analyzer.analyze_concurrency_impact(time_series_metrics)
            
            # Generate insights and recommendations
            all_bottlenecks = slow_endpoints + error_prone_endpoints
            bottleneck_recommendations = self.insights_generator.generate_bottleneck_recommendations(all_bottlenecks)
            
            # Create error analysis
            error_analysis = self._create_error_analysis(test_results)
            error_recommendations = self.insights_generator.generate_error_recommendations(error_analysis)
            
            # Generate scaling insights
            scaling_insights = self.insights_generator.generate_scaling_insights(concurrency_impact)
            
            # Prioritize all recommendations
            all_recommendations = bottleneck_recommendations + error_recommendations
            prioritized_recommendations = self.insights_generator.prioritize_recommendations(all_recommendations)
            
            # Add to results
            results["detailed"] = {
                "samples_count": len(test_results.samples),
                "endpoints": {
                    endpoint: {
                        "total_samples": metrics.total_samples,
                        "error_count": metrics.error_count,
                        "error_rate": metrics.error_rate,
                        "average_response_time": metrics.average_response_time,
                        "median_response_time": metrics.median_response_time,
                        "percentile_90": metrics.percentile_90,
                        "percentile_95": metrics.percentile_95,
                        "percentile_99": metrics.percentile_99,
                        "min_response_time": metrics.min_response_time,
                        "max_response_time": metrics.max_response_time,
                        "throughput": metrics.throughput
                    }
                    for endpoint, metrics in endpoint_metrics.items()
                },
                "time_series": [
                    {
                        "timestamp": metrics.timestamp.isoformat(),
                        "active_threads": metrics.active_threads,
                        "throughput": metrics.throughput,
                        "average_response_time": metrics.average_response_time,
                        "error_rate": metrics.error_rate
                    }
                    for metrics in time_series_metrics
                ],
                "bottlenecks": {
                    "slow_endpoints": [
                        {
                            "endpoint": bottleneck.endpoint,
                            "response_time": bottleneck.value,
                            "threshold": bottleneck.threshold,
                            "severity": bottleneck.severity
                        }
                        for bottleneck in slow_endpoints
                    ],
                    "error_prone_endpoints": [
                        {
                            "endpoint": bottleneck.endpoint,
                            "error_rate": bottleneck.value,
                            "threshold": bottleneck.threshold,
                            "severity": bottleneck.severity
                        }
                        for bottleneck in error_prone_endpoints
                    ],
                    "anomalies": [
                        {
                            "timestamp": anomaly.timestamp.isoformat(),
                            "expected_value": anomaly.expected_value,
                            "actual_value": anomaly.actual_value,
                            "deviation_percentage": anomaly.deviation_percentage
                        }
                        for anomaly in anomalies
                    ],
                    "concurrency_impact": concurrency_impact
                },
                "insights": {
                    "recommendations": [
                        {
                            "issue": rec["recommendation"].issue,
                            "recommendation": rec["recommendation"].recommendation,
                            "expected_impact": rec["recommendation"].expected_impact,
                            "implementation_difficulty": rec["recommendation"].implementation_difficulty,
                            "priority_level": rec["priority_level"]
                        }
                        for rec in prioritized_recommendations
                    ],
                    "scaling_insights": [
                        {
                            "topic": insight.topic,
                            "description": insight.description
                        }
                        for insight in scaling_insights
                    ]
                }
            }
        
        return results
    
    def _create_error_analysis(self, test_results: TestResults) -> Dict:
        """Create error analysis from test results.
        
        Args:
            test_results: TestResults object
            
        Returns:
            Dictionary containing error analysis
        """
        # Extract error samples
        error_samples = [sample for sample in test_results.samples if not sample.success]
        
        if not error_samples:
            return {"error_types": {}, "error_patterns": []}
        
        # Count error types
        error_types = {}
        for sample in error_samples:
            error_message = sample.error_message or f"HTTP {sample.response_code}"
            if error_message in error_types:
                error_types[error_message] += 1
            else:
                error_types[error_message] = 1
        
        # Detect error patterns
        error_patterns = []
        
        # Check for error spikes
        if test_results.start_time and test_results.end_time:
            # Group errors by time intervals (5-second intervals)
            interval_seconds = 5
            duration = (test_results.end_time - test_results.start_time).total_seconds()
            num_intervals = int(duration / interval_seconds) + 1
            
            # Count errors in each interval
            interval_errors = [0] * num_intervals
            for sample in error_samples:
                interval_index = int((sample.timestamp - test_results.start_time).total_seconds() / interval_seconds)
                if 0 <= interval_index < num_intervals:
                    interval_errors[interval_index] += 1
            
            # Calculate average errors per interval
            avg_errors = sum(interval_errors) / len(interval_errors) if interval_errors else 0
            
            # Detect spikes (intervals with errors > 2 * average)
            for i, error_count in enumerate(interval_errors):
                if error_count > 2 * avg_errors and error_count > 1:
                    spike_time = test_results.start_time + timedelta(seconds=i * interval_seconds)
                    error_patterns.append({
                        "type": "spike",
                        "timestamp": spike_time.isoformat(),
                        "error_count": error_count
                    })
        
        return {
            "error_types": error_types,
            "error_patterns": error_patterns
        }