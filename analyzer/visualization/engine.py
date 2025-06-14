"""
Visualization engine for JMeter test results.

This module provides functionality for creating visual representations
of JMeter test results analysis, including time series graphs, distribution
graphs, endpoint comparison charts, and visualization output formats.
"""

import base64
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Note: In a real implementation, we would use matplotlib for visualization.
# However, for the purpose of this implementation, we'll create a simplified version
# that doesn't rely on external libraries.

class VisualizationEngine:
    """Engine for creating visual representations of test results analysis."""
    
    def __init__(self, output_dir: Optional[str] = None):
        """Initialize the visualization engine.
        
        Args:
            output_dir: Directory to save visualization files (default: None)
        """
        self.output_dir = output_dir
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
    
    def create_time_series_graph(self, time_series_metrics: List,
                                metric_name: str = "average_response_time",
                                title: Optional[str] = None,
                                output_file: Optional[str] = None) -> Union[str, Dict]:
        """Create a time-series graph showing performance over the test duration.
        
        Args:
            time_series_metrics: List of TimeSeriesMetrics objects
            metric_name: Name of the metric to plot (default: "average_response_time")
            title: Graph title (default: None)
            output_file: Path to save the graph (default: None)
            
        Returns:
            Path to the saved graph file or Figure object
        """
        if not time_series_metrics:
            raise ValueError("No time series metrics provided")
        
        # Extract data
        timestamps = [metrics.timestamp for metrics in time_series_metrics]
        
        if metric_name == "average_response_time":
            values = [metrics.average_response_time for metrics in time_series_metrics]
            y_label = "Response Time (ms)"
            graph_title = title or "Response Time Over Time"
        elif metric_name == "throughput":
            values = [metrics.throughput for metrics in time_series_metrics]
            y_label = "Throughput (requests/second)"
            graph_title = title or "Throughput Over Time"
        elif metric_name == "error_rate":
            values = [metrics.error_rate for metrics in time_series_metrics]
            y_label = "Error Rate (%)"
            graph_title = title or "Error Rate Over Time"
        elif metric_name == "active_threads":
            values = [metrics.active_threads for metrics in time_series_metrics]
            y_label = "Active Threads"
            graph_title = title or "Active Threads Over Time"
        else:
            raise ValueError(f"Unknown metric name: {metric_name}")
        
        # Create a simple representation of the graph
        graph = {
            "type": "time_series",
            "title": graph_title,
            "x_label": "Time",
            "y_label": y_label,
            "timestamps": [ts.isoformat() for ts in timestamps],
            "values": values
        }
        
        # Save or return
        if output_file:
            output_path = self._get_output_path(output_file)
            with open(output_path, 'w') as f:
                f.write(f"Time Series Graph: {graph_title}\n")
                f.write(f"X-axis: Time\n")
                f.write(f"Y-axis: {y_label}\n")
                f.write("Data:\n")
                for ts, val in zip(timestamps, values):
                    f.write(f"{ts.isoformat()}: {val}\n")
            return output_path
        else:
            return graph
    
    def create_distribution_graph(self, response_times: List[float],
                                percentiles: List[int] = [50, 90, 95, 99],
                                title: Optional[str] = None,
                                output_file: Optional[str] = None) -> Union[str, Dict]:
        """Create a distribution graph showing response time distributions.
        
        Args:
            response_times: List of response times
            percentiles: List of percentiles to mark (default: [50, 90, 95, 99])
            title: Graph title (default: None)
            output_file: Path to save the graph (default: None)
            
        Returns:
            Path to the saved graph file or Figure object
        """
        if not response_times:
            raise ValueError("No response times provided")
        
        # Calculate percentile values
        percentile_values = {}
        for p in percentiles:
            percentile_values[p] = self._calculate_percentile(response_times, p)
        
        # Create a simple representation of the graph
        graph_title = title or "Response Time Distribution"
        graph = {
            "type": "distribution",
            "title": graph_title,
            "x_label": "Response Time (ms)",
            "y_label": "Frequency",
            "response_times": response_times,
            "percentiles": percentile_values
        }
        
        # Save or return
        if output_file:
            output_path = self._get_output_path(output_file)
            with open(output_path, 'w') as f:
                f.write(f"Distribution Graph: {graph_title}\n")
                f.write(f"X-axis: Response Time (ms)\n")
                f.write(f"Y-axis: Frequency\n")
                f.write("Percentiles:\n")
                for p, val in percentile_values.items():
                    f.write(f"{p}th Percentile: {val:.2f} ms\n")
            return output_path
        else:
            return graph
    
    def create_endpoint_comparison_chart(self, endpoint_metrics: Dict,
                                        metric_name: str = "average_response_time",
                                        top_n: int = 10,
                                        title: Optional[str] = None,
                                        output_file: Optional[str] = None) -> Union[str, Dict]:
        """Create a comparison chart for different endpoints.
        
        Args:
            endpoint_metrics: Dictionary mapping endpoint names to EndpointMetrics objects
            metric_name: Name of the metric to compare (default: "average_response_time")
            top_n: Number of top endpoints to include (default: 10)
            title: Chart title (default: None)
            output_file: Path to save the chart (default: None)
            
        Returns:
            Path to the saved chart file or Figure object
        """
        if not endpoint_metrics:
            raise ValueError("No endpoint metrics provided")
        
        # Extract data
        if metric_name == "average_response_time":
            values = {endpoint: metrics.average_response_time for endpoint, metrics in endpoint_metrics.items()}
            y_label = "Average Response Time (ms)"
            chart_title = title or "Endpoint Response Time Comparison"
        elif metric_name == "error_rate":
            values = {endpoint: metrics.error_rate for endpoint, metrics in endpoint_metrics.items()}
            y_label = "Error Rate (%)"
            chart_title = title or "Endpoint Error Rate Comparison"
        elif metric_name == "throughput":
            values = {endpoint: metrics.throughput for endpoint, metrics in endpoint_metrics.items()}
            y_label = "Throughput (requests/second)"
            chart_title = title or "Endpoint Throughput Comparison"
        else:
            raise ValueError(f"Unknown metric name: {metric_name}")
        
        # Sort endpoints by value (descending) and take top N
        sorted_endpoints = sorted(values.items(), key=lambda x: x[1], reverse=True)[:top_n]
        endpoints = [item[0] for item in sorted_endpoints]
        values_list = [item[1] for item in sorted_endpoints]
        
        # Create a simple representation of the chart
        chart = {
            "type": "endpoint_comparison",
            "title": chart_title,
            "x_label": y_label,
            "y_label": "Endpoint",
            "endpoints": endpoints,
            "values": values_list
        }
        
        # Save or return
        if output_file:
            output_path = self._get_output_path(output_file)
            with open(output_path, 'w') as f:
                f.write(f"Endpoint Comparison Chart: {chart_title}\n")
                f.write(f"X-axis: {y_label}\n")
                f.write(f"Y-axis: Endpoint\n")
                f.write("Data:\n")
                for endpoint, value in zip(endpoints, values_list):
                    f.write(f"{endpoint}: {value:.2f}\n")
            return output_path
        else:
            return chart
    
    def create_html_report(self, analysis_results: Dict, output_file: str) -> str:
        """Create an HTML report from analysis results.
        
        Args:
            analysis_results: Dictionary containing analysis results
            output_file: Path to save the HTML report
            
        Returns:
            Path to the saved HTML report
        """
        # Extract data
        summary = analysis_results.get("summary", {})
        detailed = analysis_results.get("detailed", {})
        
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>JMeter Test Results Analysis</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .chart {{ margin: 20px 0; max-width: 100%; }}
                .section {{ margin-bottom: 30px; }}
                .severity-high {{ color: #d9534f; }}
                .severity-medium {{ color: #f0ad4e; }}
                .severity-low {{ color: #5bc0de; }}
            </style>
        </head>
        <body>
            <h1>JMeter Test Results Analysis</h1>
            
            <div class="section">
                <h2>Summary</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Samples</td><td>{summary.get('total_samples', 'N/A')}</td></tr>
                    <tr><td>Error Count</td><td>{summary.get('error_count', 'N/A')}</td></tr>
                    <tr><td>Error Rate</td><td>{summary.get('error_rate', 'N/A'):.2f}%</td></tr>
                    <tr><td>Average Response Time</td><td>{summary.get('average_response_time', 'N/A'):.2f} ms</td></tr>
                    <tr><td>Median Response Time</td><td>{summary.get('median_response_time', 'N/A'):.2f} ms</td></tr>
                    <tr><td>90th Percentile</td><td>{summary.get('percentile_90', 'N/A'):.2f} ms</td></tr>
                    <tr><td>95th Percentile</td><td>{summary.get('percentile_95', 'N/A'):.2f} ms</td></tr>
                    <tr><td>99th Percentile</td><td>{summary.get('percentile_99', 'N/A'):.2f} ms</td></tr>
                    <tr><td>Min Response Time</td><td>{summary.get('min_response_time', 'N/A'):.2f} ms</td></tr>
                    <tr><td>Max Response Time</td><td>{summary.get('max_response_time', 'N/A'):.2f} ms</td></tr>
                    <tr><td>Throughput</td><td>{summary.get('throughput', 'N/A'):.2f} requests/second</td></tr>
                    <tr><td>Start Time</td><td>{summary.get('start_time', 'N/A')}</td></tr>
                    <tr><td>End Time</td><td>{summary.get('end_time', 'N/A')}</td></tr>
                    <tr><td>Duration</td><td>{summary.get('duration', 'N/A'):.2f} seconds</td></tr>
                </table>
            </div>
        """
        
        # Add detailed information if available
        if detailed:
            # Add endpoint information
            endpoints = detailed.get("endpoints", {})
            if endpoints:
                html_content += """
                <div class="section">
                    <h2>Endpoint Analysis</h2>
                    <table>
                        <tr>
                            <th>Endpoint</th>
                            <th>Samples</th>
                            <th>Errors</th>
                            <th>Error Rate</th>
                            <th>Avg Response Time</th>
                            <th>95th Percentile</th>
                            <th>Throughput</th>
                        </tr>
                """
                
                for endpoint, metrics in endpoints.items():
                    html_content += f"""
                        <tr>
                            <td>{endpoint}</td>
                            <td>{metrics['total_samples']}</td>
                            <td>{metrics['error_count']}</td>
                            <td>{metrics['error_rate']:.2f}%</td>
                            <td>{metrics['average_response_time']:.2f} ms</td>
                            <td>{metrics['percentile_95']:.2f} ms</td>
                            <td>{metrics['throughput']:.2f} req/s</td>
                        </tr>
                    """
                
                html_content += """
                    </table>
                </div>
                """
            
            # Add bottleneck information
            bottlenecks = detailed.get("bottlenecks", {})
            if bottlenecks:
                html_content += """
                <div class="section">
                    <h2>Bottleneck Analysis</h2>
                """
                
                # Slow endpoints
                slow_endpoints = bottlenecks.get("slow_endpoints", [])
                if slow_endpoints:
                    html_content += """
                    <h3>Slow Endpoints</h3>
                    <table>
                        <tr>
                            <th>Endpoint</th>
                            <th>Response Time</th>
                            <th>Threshold</th>
                            <th>Severity</th>
                        </tr>
                    """
                    
                    for endpoint in slow_endpoints:
                        severity_class = f"severity-{endpoint.get('severity', 'medium')}"
                        html_content += f"""
                            <tr>
                                <td>{endpoint.get('endpoint')}</td>
                                <td>{endpoint.get('response_time', 'N/A'):.2f} ms</td>
                                <td>{endpoint.get('threshold', 'N/A'):.2f} ms</td>
                                <td class="{severity_class}">{endpoint.get('severity', 'N/A').upper()}</td>
                            </tr>
                        """
                    
                    html_content += """
                    </table>
                    """
                
                # Error-prone endpoints
                error_endpoints = bottlenecks.get("error_prone_endpoints", [])
                if error_endpoints:
                    html_content += """
                    <h3>Error-Prone Endpoints</h3>
                    <table>
                        <tr>
                            <th>Endpoint</th>
                            <th>Error Rate</th>
                            <th>Threshold</th>
                            <th>Severity</th>
                        </tr>
                    """
                    
                    for endpoint in error_endpoints:
                        severity_class = f"severity-{endpoint.get('severity', 'medium')}"
                        html_content += f"""
                            <tr>
                                <td>{endpoint.get('endpoint')}</td>
                                <td>{endpoint.get('error_rate', 'N/A'):.2f}%</td>
                                <td>{endpoint.get('threshold', 'N/A'):.2f}%</td>
                                <td class="{severity_class}">{endpoint.get('severity', 'N/A').upper()}</td>
                            </tr>
                        """
                    
                    html_content += """
                    </table>
                    """
                
                html_content += """
                </div>
                """
            
            # Add insights and recommendations
            insights = detailed.get("insights", {})
            if insights:
                html_content += """
                <div class="section">
                    <h2>Insights and Recommendations</h2>
                """
                
                # Recommendations
                recommendations = insights.get("recommendations", [])
                if recommendations:
                    html_content += """
                    <h3>Recommendations</h3>
                    <table>
                        <tr>
                            <th>Priority</th>
                            <th>Issue</th>
                            <th>Recommendation</th>
                            <th>Expected Impact</th>
                        </tr>
                    """
                    
                    for rec in recommendations:
                        priority_level = rec.get('priority_level', 'medium')
                        severity_class = f"severity-{priority_level}"
                        html_content += f"""
                            <tr>
                                <td class="{severity_class}">{priority_level.upper()}</td>
                                <td>{rec.get('issue')}</td>
                                <td>{rec.get('recommendation')}</td>
                                <td>{rec.get('expected_impact')}</td>
                            </tr>
                        """
                    
                    html_content += """
                    </table>
                    """
                
                # Scaling insights
                scaling_insights = insights.get("scaling_insights", [])
                if scaling_insights:
                    html_content += """
                    <h3>Scaling Insights</h3>
                    <table>
                        <tr>
                            <th>Topic</th>
                            <th>Description</th>
                        </tr>
                    """
                    
                    for insight in scaling_insights:
                        html_content += f"""
                            <tr>
                                <td>{insight.get('topic')}</td>
                                <td>{insight.get('description')}</td>
                            </tr>
                        """
                    
                    html_content += """
                    </table>
                    """
                
                html_content += """
                </div>
                """
        
        # Close HTML
        html_content += """
        </body>
        </html>
        """
        
        # Save HTML report
        output_path = self._get_output_path(output_file)
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        return output_path
    
    def figure_to_base64(self, fig) -> str:
        """Convert a figure to a base64-encoded string.
        
        Args:
            fig: Figure object
            
        Returns:
            Base64-encoded string
        """
        # In a real implementation, this would convert a matplotlib figure to base64
        # For this simplified version, we'll just return a placeholder
        return "base64_encoded_image_placeholder"
    
    def _get_output_path(self, output_file: str) -> str:
        """Get the full path for an output file.
        
        Args:
            output_file: Output file name or path
            
        Returns:
            Full path to the output file
        """
        if self.output_dir:
            return os.path.join(self.output_dir, output_file)
        else:
            return output_file
    
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate a percentile from values.
        
        Args:
            values: List of values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        if not values:
            return 0
        
        # Sort values
        sorted_values = sorted(values)
        
        # Calculate index
        index = (percentile / 100) * (len(sorted_values) - 1)
        
        # If index is an integer, return the value at that index
        if index.is_integer():
            return sorted_values[int(index)]
        
        # Otherwise, interpolate between the two nearest values
        lower_index = int(index)
        upper_index = lower_index + 1
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]
        fraction = index - lower_index
        
        return lower_value + (upper_value - lower_value) * fraction