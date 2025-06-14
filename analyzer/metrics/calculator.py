"""
Metrics calculator for JMeter test results.

This module provides functionality for calculating performance metrics
from JMeter test results, including overall metrics, endpoint-specific metrics,
and time series metrics.
"""

import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from analyzer.models import (EndpointMetrics, OverallMetrics, Sample,
                           TestResults, TimeSeriesMetrics)


class MetricsCalculator:
    """Calculator for performance metrics from test results."""
    
    def calculate_overall_metrics(self, test_results: TestResults) -> OverallMetrics:
        """Calculate overall metrics for the entire test.
        
        Args:
            test_results: TestResults object containing samples
            
        Returns:
            OverallMetrics object with calculated metrics
            
        Raises:
            ValueError: If test_results contains no samples
        """
        if not test_results.samples:
            raise ValueError("Cannot calculate metrics for empty test results")
        
        # Extract response times and success status
        response_times = [sample.response_time for sample in test_results.samples]
        success_count = sum(1 for sample in test_results.samples if sample.success)
        error_count = len(test_results.samples) - success_count
        
        # Calculate duration
        if test_results.start_time and test_results.end_time:
            duration = (test_results.end_time - test_results.start_time).total_seconds()
        else:
            duration = 0
        
        # Calculate throughput (requests per second)
        throughput = len(test_results.samples) / duration if duration > 0 else 0
        
        # Calculate percentiles
        response_times_sorted = sorted(response_times)
        
        # Create metrics object
        metrics = OverallMetrics(
            total_samples=len(test_results.samples),
            error_count=error_count,
            error_rate=(error_count / len(test_results.samples)) * 100 if test_results.samples else 0,
            average_response_time=statistics.mean(response_times) if response_times else 0,
            median_response_time=statistics.median(response_times) if response_times else 0,
            percentile_90=self._calculate_percentile(response_times_sorted, 90),
            percentile_95=self._calculate_percentile(response_times_sorted, 95),
            percentile_99=self._calculate_percentile(response_times_sorted, 99),
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            throughput=throughput,
            test_duration=duration
        )
        
        return metrics
    
    def calculate_endpoint_metrics(self, test_results: TestResults) -> Dict[str, EndpointMetrics]:
        """Calculate metrics broken down by endpoint/sampler.
        
        Args:
            test_results: TestResults object containing samples
            
        Returns:
            Dictionary mapping endpoint names to EndpointMetrics objects
            
        Raises:
            ValueError: If test_results contains no samples
        """
        if not test_results.samples:
            raise ValueError("Cannot calculate metrics for empty test results")
        
        # Group samples by endpoint
        endpoints = defaultdict(list)
        for sample in test_results.samples:
            endpoints[sample.label].append(sample)
        
        # Calculate metrics for each endpoint
        endpoint_metrics = {}
        for endpoint, samples in endpoints.items():
            # Create a temporary TestResults object with only samples for this endpoint
            temp_results = TestResults()
            for sample in samples:
                temp_results.add_sample(sample)
            
            # Calculate overall metrics for this endpoint
            overall_metrics = self.calculate_overall_metrics(temp_results)
            
            # Create endpoint metrics
            metrics = EndpointMetrics(
                endpoint=endpoint,
                total_samples=overall_metrics.total_samples,
                error_count=overall_metrics.error_count,
                error_rate=overall_metrics.error_rate,
                average_response_time=overall_metrics.average_response_time,
                median_response_time=overall_metrics.median_response_time,
                percentile_90=overall_metrics.percentile_90,
                percentile_95=overall_metrics.percentile_95,
                percentile_99=overall_metrics.percentile_99,
                min_response_time=overall_metrics.min_response_time,
                max_response_time=overall_metrics.max_response_time,
                throughput=overall_metrics.throughput,
                test_duration=overall_metrics.test_duration
            )
            
            endpoint_metrics[endpoint] = metrics
        
        return endpoint_metrics
    
    def calculate_time_series_metrics(self, test_results: TestResults, 
                                     interval_seconds: int = 5) -> List[TimeSeriesMetrics]:
        """Calculate metrics over time using the specified interval.
        
        Args:
            test_results: TestResults object containing samples
            interval_seconds: Time interval in seconds (default: 5)
            
        Returns:
            List of TimeSeriesMetrics objects, one for each interval
            
        Raises:
            ValueError: If test_results contains no samples or if interval_seconds <= 0
        """
        if not test_results.samples:
            raise ValueError("Cannot calculate metrics for empty test results")
        
        if interval_seconds <= 0:
            raise ValueError("Interval must be positive")
        
        if not test_results.start_time or not test_results.end_time:
            raise ValueError("Test results must have start and end times")
        
        # Create time intervals
        start_time = test_results.start_time
        end_time = test_results.end_time
        
        # Ensure we have at least one interval
        if (end_time - start_time).total_seconds() < interval_seconds:
            end_time = start_time + timedelta(seconds=interval_seconds)
        
        intervals = []
        current_time = start_time
        while current_time < end_time:
            next_time = current_time + timedelta(seconds=interval_seconds)
            intervals.append((current_time, next_time))
            current_time = next_time
        
        # Group samples by interval
        interval_samples = [[] for _ in range(len(intervals))]
        for sample in test_results.samples:
            for i, (start, end) in enumerate(intervals):
                if start <= sample.timestamp < end:
                    interval_samples[i].append(sample)
                    break
        
        # Calculate metrics for each interval
        time_series_metrics = []
        for i, (start, end) in enumerate(intervals):
            samples = interval_samples[i]
            
            # Skip intervals with no samples
            if not samples:
                continue
            
            # Calculate metrics for this interval
            response_times = [sample.response_time for sample in samples]
            error_count = sum(1 for sample in samples if not sample.success)
            
            # Count active threads (approximation based on unique thread names)
            thread_names = set(sample.thread_name for sample in samples if sample.thread_name)
            active_threads = len(thread_names)
            
            # Calculate throughput for this interval
            interval_duration = (end - start).total_seconds()
            throughput = len(samples) / interval_duration if interval_duration > 0 else 0
            
            # Create metrics object
            metrics = TimeSeriesMetrics(
                timestamp=start,
                active_threads=active_threads,
                throughput=throughput,
                average_response_time=statistics.mean(response_times) if response_times else 0,
                error_rate=(error_count / len(samples)) * 100 if samples else 0
            )
            
            time_series_metrics.append(metrics)
        
        return time_series_metrics
    
    def compare_with_benchmarks(self, metrics: OverallMetrics, 
                               benchmarks: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        """Compare metrics with benchmarks.
        
        Args:
            metrics: OverallMetrics object
            benchmarks: Dictionary mapping metric names to benchmark values
            
        Returns:
            Dictionary with comparison results
        """
        comparison = {}
        
        for metric_name, benchmark_value in benchmarks.items():
            if hasattr(metrics, metric_name):
                actual_value = getattr(metrics, metric_name)
                difference = actual_value - benchmark_value
                percent_difference = (difference / benchmark_value) * 100 if benchmark_value != 0 else float('inf')
                
                comparison[metric_name] = {
                    'benchmark': benchmark_value,
                    'actual': actual_value,
                    'difference': difference,
                    'percent_difference': percent_difference
                }
        
        return comparison
    
    def _calculate_percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate a percentile from sorted values.
        
        Args:
            sorted_values: List of values, sorted in ascending order
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        if not sorted_values:
            return 0
        
        # Calculate percentile index
        index = (percentile / 100) * (len(sorted_values) - 1)
        
        # If index is an integer, return the value at that index
        if index.is_integer():
            return sorted_values[int(index)]
        
        # Otherwise, interpolate between the two nearest values
        lower_index = math.floor(index)
        upper_index = math.ceil(index)
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]
        fraction = index - lower_index
        
        return lower_value + (upper_value - lower_value) * fraction