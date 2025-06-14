"""
Bottleneck analyzer for JMeter test results.

This module provides functionality for identifying performance bottlenecks
in JMeter test results, including slow endpoints, error-prone endpoints,
response time anomalies, and concurrency impact analysis.
"""

import statistics
from typing import Dict, List, Optional, Tuple

from analyzer.models import (Anomaly, Bottleneck, EndpointMetrics,
                           OverallMetrics, Sample, TestResults,
                           TimeSeriesMetrics)


class BottleneckAnalyzer:
    """Analyzer for identifying performance bottlenecks."""
    
    def identify_slow_endpoints(self, endpoint_metrics: Dict[str, EndpointMetrics], 
                               threshold_percentile: float = 95,
                               threshold_factor: float = 1.5) -> List[Bottleneck]:
        """Identify endpoints with the highest response times.
        
        Args:
            endpoint_metrics: Dictionary mapping endpoint names to EndpointMetrics objects
            threshold_percentile: Percentile to use for response time threshold (default: 95)
            threshold_factor: Factor to multiply the average response time by (default: 1.5)
            
        Returns:
            List of Bottleneck objects for slow endpoints
        """
        if not endpoint_metrics:
            return []
        
        # Calculate average response time across all endpoints
        avg_response_times = [metrics.average_response_time for metrics in endpoint_metrics.values()]
        overall_avg_response_time = statistics.mean(avg_response_times) if avg_response_times else 0
        
        # Calculate threshold
        threshold = overall_avg_response_time * threshold_factor
        
        # Identify slow endpoints
        bottlenecks = []
        for endpoint, metrics in endpoint_metrics.items():
            # Get the response time at the specified percentile
            percentile_rt = getattr(metrics, f"percentile_{int(threshold_percentile)}", metrics.average_response_time)
            
            # Check if the endpoint is slow
            if percentile_rt > threshold:
                # Determine severity based on how much it exceeds the threshold
                if percentile_rt > threshold * 2:
                    severity = "high"
                elif percentile_rt > threshold * 1.5:
                    severity = "medium"
                else:
                    severity = "low"
                
                bottleneck = Bottleneck(
                    endpoint=endpoint,
                    metric_type="response_time",
                    value=percentile_rt,
                    threshold=threshold,
                    severity=severity
                )
                
                bottlenecks.append(bottleneck)
        
        # Sort bottlenecks by severity and then by value (descending)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        bottlenecks.sort(key=lambda b: (severity_order.get(b.severity, 3), -b.value))
        
        return bottlenecks
    
    def identify_error_prone_endpoints(self, endpoint_metrics: Dict[str, EndpointMetrics], 
                                      threshold_error_rate: float = 1.0) -> List[Bottleneck]:
        """Identify endpoints with the highest error rates.
        
        Args:
            endpoint_metrics: Dictionary mapping endpoint names to EndpointMetrics objects
            threshold_error_rate: Minimum error rate to consider as a bottleneck (default: 1.0%)
            
        Returns:
            List of Bottleneck objects for error-prone endpoints
        """
        if not endpoint_metrics:
            return []
        
        # Identify error-prone endpoints
        bottlenecks = []
        for endpoint, metrics in endpoint_metrics.items():
            # Skip endpoints with no errors
            if metrics.error_count == 0:
                continue
            
            # Check if the endpoint has a high error rate
            if metrics.error_rate >= threshold_error_rate:
                # Determine severity based on error rate
                if metrics.error_rate >= 10.0:
                    severity = "high"
                elif metrics.error_rate >= 5.0:
                    severity = "medium"
                else:
                    severity = "low"
                
                bottleneck = Bottleneck(
                    endpoint=endpoint,
                    metric_type="error_rate",
                    value=metrics.error_rate,
                    threshold=threshold_error_rate,
                    severity=severity
                )
                
                bottlenecks.append(bottleneck)
        
        # Sort bottlenecks by severity and then by value (descending)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        bottlenecks.sort(key=lambda b: (severity_order.get(b.severity, 3), -b.value))
        
        return bottlenecks
    
    def detect_anomalies(self, time_series_metrics: List[TimeSeriesMetrics], 
                        z_score_threshold: float = 2.0) -> List[Anomaly]:
        """Detect response time anomalies and outliers.
        
        Args:
            time_series_metrics: List of TimeSeriesMetrics objects
            z_score_threshold: Z-score threshold for anomaly detection (default: 2.0)
            
        Returns:
            List of Anomaly objects
        """
        if not time_series_metrics:
            return []
        
        # Extract response times
        response_times = [metrics.average_response_time for metrics in time_series_metrics]
        
        # Calculate mean and standard deviation
        mean_rt = statistics.mean(response_times)
        stdev_rt = statistics.stdev(response_times) if len(response_times) > 1 else 0
        
        # Detect anomalies
        anomalies = []
        for metrics in time_series_metrics:
            # Skip if standard deviation is zero (all values are the same)
            if stdev_rt == 0:
                continue
            
            # Calculate z-score
            z_score = (metrics.average_response_time - mean_rt) / stdev_rt
            
            # Check if the response time is an anomaly
            if abs(z_score) >= z_score_threshold:
                # Calculate deviation percentage
                deviation_percentage = ((metrics.average_response_time - mean_rt) / mean_rt) * 100
                
                anomaly = Anomaly(
                    timestamp=metrics.timestamp,
                    endpoint="overall",  # Overall anomaly, not endpoint-specific
                    expected_value=mean_rt,
                    actual_value=metrics.average_response_time,
                    deviation_percentage=deviation_percentage
                )
                
                anomalies.append(anomaly)
        
        # Sort anomalies by deviation percentage (descending)
        anomalies.sort(key=lambda a: abs(a.deviation_percentage), reverse=True)
        
        return anomalies
    
    def analyze_concurrency_impact(self, time_series_metrics: List[TimeSeriesMetrics]) -> Dict:
        """Analyze the impact of concurrency on performance.
        
        Args:
            time_series_metrics: List of TimeSeriesMetrics objects
            
        Returns:
            Dictionary containing concurrency analysis results
        """
        if not time_series_metrics:
            return {"correlation": 0, "degradation_threshold": 0, "has_degradation": False}
        
        # Extract thread counts and response times
        thread_counts = [metrics.active_threads for metrics in time_series_metrics]
        response_times = [metrics.average_response_time for metrics in time_series_metrics]
        
        # Skip if there's no variation in thread counts
        if len(set(thread_counts)) <= 1:
            return {"correlation": 0, "degradation_threshold": 0, "has_degradation": False}
        
        # Calculate correlation between thread count and response time
        try:
            correlation = self._calculate_correlation(thread_counts, response_times)
        except (ValueError, ZeroDivisionError):
            correlation = 0
        
        # Identify potential degradation threshold
        degradation_threshold = 0
        has_degradation = False
        
        if correlation > 0.5:  # Strong positive correlation
            # Group by thread count
            thread_rt_map = {}
            for metrics in time_series_metrics:
                if metrics.active_threads not in thread_rt_map:
                    thread_rt_map[metrics.active_threads] = []
                thread_rt_map[metrics.active_threads].append(metrics.average_response_time)
            
            # Calculate average response time for each thread count
            thread_avg_rt = {
                threads: statistics.mean(rts)
                for threads, rts in thread_rt_map.items()
            }
            
            # Sort by thread count
            sorted_threads = sorted(thread_avg_rt.keys())
            
            # Look for significant increases in response time
            for i in range(1, len(sorted_threads)):
                prev_threads = sorted_threads[i-1]
                curr_threads = sorted_threads[i]
                prev_rt = thread_avg_rt[prev_threads]
                curr_rt = thread_avg_rt[curr_threads]
                
                # Check if response time increased by more than 50%
                if curr_rt > prev_rt * 1.5:
                    degradation_threshold = curr_threads
                    has_degradation = True
                    break
        
        return {
            "correlation": correlation,
            "degradation_threshold": degradation_threshold,
            "has_degradation": has_degradation
        }
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient between two lists.
        
        Args:
            x: First list of values
            y: Second list of values
            
        Returns:
            Correlation coefficient (-1 to 1)
        """
        if len(x) != len(y) or len(x) < 2:
            return 0
        
        # Calculate means
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)
        
        # Calculate numerator and denominators
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denom_x = sum((xi - mean_x) ** 2 for xi in x)
        denom_y = sum((yi - mean_y) ** 2 for yi in y)
        
        # Calculate correlation
        if denom_x == 0 or denom_y == 0:
            return 0
        
        return numerator / ((denom_x ** 0.5) * (denom_y ** 0.5))