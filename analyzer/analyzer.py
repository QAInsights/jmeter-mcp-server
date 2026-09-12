"""
Main analyzer module for JMeter test results.

This module provides the main entry point for analyzing JMeter test results.
It orchestrates the flow of data through the various components of the analyzer.
"""

import copy
from pathlib import Path
from typing import Dict, Optional, Union

from analyzer.cache import AnalysisCache, default_cache
from analyzer.models import TestResults
from analyzer.parser.base import JTLParser
from analyzer.parser.xml_parser import XMLJTLParser
from analyzer.parser.csv_parser import CSVJTLParser
from analyzer.metrics.calculator import MetricsCalculator
from analyzer.metrics.streaming import StreamingAggregator
from analyzer.bottleneck.analyzer import BottleneckAnalyzer
from analyzer.insights.generator import InsightsGenerator


class TestResultsAnalyzer:
    """Main analyzer class for JMeter test results."""
    
    def __init__(self, cache: Optional[AnalysisCache] = None):
        """Initialize the analyzer.
        
        Args:
            cache: AnalysisCache to use for caching file analyses
                   (default: the shared module-level cache)
        """
        self.parsers = {}
        self.metrics_calculator = MetricsCalculator()
        self.bottleneck_analyzer = BottleneckAnalyzer()
        self.insights_generator = InsightsGenerator()
        self.cache = cache if cache is not None else default_cache()
        
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
        
        # Serve from cache if the file is unchanged
        full = self.cache.get(path)
        if full is None:
            # Detect format
            format_name = JTLParser.detect_format(path)
            
            # Get appropriate parser
            if format_name not in self.parsers:
                raise ValueError(f"No parser available for format: {format_name}")
            
            parser = self.parsers[format_name]
            
            # Stream-parse and aggregate in a single pass
            agg = StreamingAggregator().consume(parser.iter_samples(path))
            full = self._build_results(agg)
            self.cache.put(path, full)
        
        result = full if detailed else {"summary": full["summary"]}
        # Deep copy so callers cannot mutate cached results
        return copy.deepcopy(result)
    
    def _analyze_results(self, test_results: TestResults, 
                        detailed: bool = False) -> Dict:
        """Analyze test results and return the analysis (compat wrapper
        that routes in-memory TestResults through the streaming aggregator).
        
        Args:
            test_results: TestResults object
            detailed: Whether to include detailed analysis
            
        Returns:
            Dictionary containing analysis results
        """
        agg = StreamingAggregator().consume(test_results.samples)
        full = self._build_results(agg)
        return full if detailed else {"summary": full["summary"]}
    
    def _build_results(self, agg: StreamingAggregator) -> Dict:
        """Build the full (detailed) analysis dict from a consumed aggregator."""
        # Calculate overall metrics
        overall_metrics = agg.overall_metrics()
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
                "start_time": agg.start_time,
                "end_time": agg.end_time,
                "duration": overall_metrics.test_duration
            }
        }
        
        # Detailed analysis
        # Calculate endpoint metrics
        endpoint_metrics = agg.endpoint_metrics()
        
        # Calculate time series metrics
        try:
            time_series_metrics = agg.time_series_metrics()
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
        error_analysis = agg.error_analysis()
        error_recommendations = self.insights_generator.generate_error_recommendations(error_analysis)
        
        # Generate scaling insights
        scaling_insights = self.insights_generator.generate_scaling_insights(concurrency_impact)
        
        # Prioritize all recommendations
        all_recommendations = bottleneck_recommendations + error_recommendations
        prioritized_recommendations = self.insights_generator.prioritize_recommendations(all_recommendations)
        
        # Add to results
        results["detailed"] = {
            "samples_count": overall_metrics.total_samples,
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
    
