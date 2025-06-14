from typing import Any
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import os
import datetime
import uuid
import logging
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("jmeter")

async def run_jmeter(test_file: str, non_gui: bool = True, properties: dict = None, generate_report: bool = False, report_output_dir: str = None, log_file: str = None) -> str:
    """Run a JMeter test.

    Args:
        test_file: Path to the JMeter test file (.jmx)
        non_gui: Run in non-GUI mode (default: True)
        properties: Dictionary of JMeter properties to pass with -J (default: None)
        generate_report: Whether to generate report dashboard after load test (default: False)
        report_output_dir: Output folder for report dashboard (default: None)
        log_file: Name of JTL file to log sample results to (default: None)

    Returns:
        str: JMeter execution output
    """
    try:
        # Convert to absolute path
        test_file_path = Path(test_file).resolve()
        
        # Validate file exists and is a .jmx file
        if not test_file_path.exists():
            return f"Error: Test file not found: {test_file}"
        if not test_file_path.suffix == '.jmx':
            return f"Error: Invalid file type. Expected .jmx file: {test_file}"

        # Get JMeter binary path from environment
        jmeter_bin = os.getenv('JMETER_BIN', 'jmeter')
        java_opts = os.getenv('JMETER_JAVA_OPTS', '')

        # Log the JMeter binary path and Java options
        logger.info(f"JMeter binary path: {jmeter_bin}")
        logger.debug(f"Java options: {java_opts}")

        # Build command
        cmd = [str(Path(jmeter_bin).resolve())]
        
        if non_gui:
            cmd.extend(['-n'])
        cmd.extend(['-t', str(test_file_path)])
        
        # Add JMeter properties if provided∑
        if properties:
            for prop_name, prop_value in properties.items():
                cmd.extend([f'-J{prop_name}={prop_value}'])
                logger.debug(f"Adding property: -J{prop_name}={prop_value}")
        
        # Add report generation options if requested
        if generate_report and non_gui:
            if log_file is None:
                # Generate unique log file name if not specified
                unique_id = generate_unique_id()
                log_file = f"{test_file_path.stem}_{unique_id}_results.jtl"
                logger.debug(f"Using generated unique log file: {log_file}")
            
            cmd.extend(['-l', log_file])
            cmd.extend(['-e'])
            
            # Always ensure report_output_dir is unique
            unique_id = unique_id if 'unique_id' in locals() else generate_unique_id()
            
            if report_output_dir:
                # Append unique identifier to user-provided report directory
                original_dir = report_output_dir
                report_output_dir = f"{original_dir}_{unique_id}"
                logger.debug(f"Making user-provided report directory unique: {original_dir} -> {report_output_dir}")
            else:
                # Generate unique report output directory if not specified
                report_output_dir = f"{test_file_path.stem}_{unique_id}_report"
                logger.debug(f"Using generated unique report output directory: {report_output_dir}")
                
            cmd.extend(['-o', report_output_dir])

        # Log the full command for debugging
        logger.debug(f"Executing command: {' '.join(cmd)}")
        
        if non_gui:
            # For non-GUI mode, capture output
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Log output for debugging
            logger.debug("Command output:")
            logger.debug(f"Return code: {result.returncode}")
            logger.debug(f"Stdout: {result.stdout}")
            logger.debug(f"Stderr: {result.stderr}")

            if result.returncode != 0:
                return f"Error executing JMeter test:\n{result.stderr}"
            
            return result.stdout
        else:
            # For GUI mode, start process without capturing output
            subprocess.Popen(cmd)
            return "JMeter GUI launched successfully"

    except Exception as e:
        return f"Unexpected error: {str(e)}"

@mcp.tool()
async def execute_jmeter_test(test_file: str, gui_mode: bool = False, properties: dict = None) -> str:
    """Execute a JMeter test.

    Args:
        test_file: Path to the JMeter test file (.jmx)
        gui_mode: Whether to run in GUI mode (default: False)
        properties: Dictionary of JMeter properties to pass with -J (default: None)
    """
    return await run_jmeter(test_file, non_gui=not gui_mode, properties=properties)  # Run in non-GUI mode by default

@mcp.tool()
async def execute_jmeter_test_non_gui(test_file: str, properties: dict = None, generate_report: bool = False, report_output_dir: str = None, log_file: str = None) -> str:
    """Execute a JMeter test in non-GUI mode - supports JMeter properties.

    Args:
        test_file: Path to the JMeter test file (.jmx)
        properties: Dictionary of JMeter properties to pass with -J (default: None)
        generate_report: Whether to generate report dashboard after load test (default: False)
        report_output_dir: Output folder for report dashboard (default: None)
        log_file: Name of JTL file to log sample results to (default: None)
    """
    return await run_jmeter(test_file, non_gui=True, properties=properties, generate_report=generate_report, report_output_dir=report_output_dir, log_file=log_file)

# Import the analyzer module
from analyzer.models import TestResults
from analyzer.analyzer import TestResultsAnalyzer
from analyzer.visualization.engine import VisualizationEngine

@mcp.tool()
async def analyze_jmeter_results(jtl_file: str, detailed: bool = False) -> str:
    """Analyze JMeter test results and provide a summary of key metrics and insights.
    
    Args:
        jtl_file: Path to the JTL file containing test results
        detailed: Whether to include detailed analysis (default: False)
        
    Returns:
        str: Analysis results in a formatted string
    """
    try:
        analyzer = TestResultsAnalyzer()
        
        # Validate file exists
        file_path = Path(jtl_file)
        if not file_path.exists():
            return f"Error: JTL file not found: {jtl_file}"
        
        try:
            # Analyze the file
            analysis_results = analyzer.analyze_file(file_path, detailed=detailed)
            
            # Format the results as a string
            result_str = f"Analysis of {jtl_file}:\n\n"
            
            # Add summary information
            summary = analysis_results.get("summary", {})
            result_str += "Summary:\n"
            result_str += f"- Total samples: {summary.get('total_samples', 'N/A')}\n"
            result_str += f"- Error count: {summary.get('error_count', 'N/A')} ({summary.get('error_rate', 'N/A'):.2f}%)\n"
            result_str += f"- Response times (ms):\n"
            result_str += f"  - Average: {summary.get('average_response_time', 'N/A'):.2f}\n"
            result_str += f"  - Median: {summary.get('median_response_time', 'N/A'):.2f}\n"
            result_str += f"  - 90th percentile: {summary.get('percentile_90', 'N/A'):.2f}\n"
            result_str += f"  - 95th percentile: {summary.get('percentile_95', 'N/A'):.2f}\n"
            result_str += f"  - 99th percentile: {summary.get('percentile_99', 'N/A'):.2f}\n"
            result_str += f"  - Min: {summary.get('min_response_time', 'N/A'):.2f}\n"
            result_str += f"  - Max: {summary.get('max_response_time', 'N/A'):.2f}\n"
            result_str += f"- Throughput: {summary.get('throughput', 'N/A'):.2f} requests/second\n"
            result_str += f"- Start time: {summary.get('start_time', 'N/A')}\n"
            result_str += f"- End time: {summary.get('end_time', 'N/A')}\n"
            result_str += f"- Duration: {summary.get('duration', 'N/A'):.2f} seconds\n\n"
            
            # Add detailed information if requested
            if detailed and "detailed" in analysis_results:
                detailed_info = analysis_results["detailed"]
                
                # Add endpoint information
                endpoints = detailed_info.get("endpoints", {})
                if endpoints:
                    result_str += "Endpoint Analysis:\n"
                    for endpoint, metrics in endpoints.items():
                        result_str += f"- {endpoint}:\n"
                        result_str += f"  - Samples: {metrics.get('total_samples', 'N/A')}\n"
                        result_str += f"  - Errors: {metrics.get('error_count', 'N/A')} ({metrics.get('error_rate', 'N/A'):.2f}%)\n"
                        result_str += f"  - Average response time: {metrics.get('average_response_time', 'N/A'):.2f} ms\n"
                        result_str += f"  - 95th percentile: {metrics.get('percentile_95', 'N/A'):.2f} ms\n"
                        result_str += f"  - Throughput: {metrics.get('throughput', 'N/A'):.2f} requests/second\n"
                    result_str += "\n"
                
                # Add bottleneck information
                bottlenecks = detailed_info.get("bottlenecks", {})
                if bottlenecks:
                    result_str += "Bottleneck Analysis:\n"
                    
                    # Slow endpoints
                    slow_endpoints = bottlenecks.get("slow_endpoints", [])
                    if slow_endpoints:
                        result_str += "- Slow Endpoints:\n"
                        for endpoint in slow_endpoints:
                            result_str += f"  - {endpoint.get('endpoint')}: {endpoint.get('response_time'):.2f} ms "
                            result_str += f"(Severity: {endpoint.get('severity')})\n"
                        result_str += "\n"
                    
                    # Error-prone endpoints
                    error_endpoints = bottlenecks.get("error_prone_endpoints", [])
                    if error_endpoints:
                        result_str += "- Error-Prone Endpoints:\n"
                        for endpoint in error_endpoints:
                            result_str += f"  - {endpoint.get('endpoint')}: {endpoint.get('error_rate'):.2f}% "
                            result_str += f"(Severity: {endpoint.get('severity')})\n"
                        result_str += "\n"
                    
                    # Anomalies
                    anomalies = bottlenecks.get("anomalies", [])
                    if anomalies:
                        result_str += "- Response Time Anomalies:\n"
                        for anomaly in anomalies[:3]:  # Show only top 3 anomalies
                            result_str += f"  - At {anomaly.get('timestamp')}: "
                            result_str += f"Expected {anomaly.get('expected_value'):.2f} ms, "
                            result_str += f"Got {anomaly.get('actual_value'):.2f} ms "
                            result_str += f"({anomaly.get('deviation_percentage'):.2f}% deviation)\n"
                        result_str += "\n"
                    
                    # Concurrency impact
                    concurrency = bottlenecks.get("concurrency_impact", {})
                    if concurrency:
                        result_str += "- Concurrency Impact:\n"
                        correlation = concurrency.get("correlation", 0)
                        result_str += f"  - Correlation between threads and response time: {correlation:.2f}\n"
                        
                        if concurrency.get("has_degradation", False):
                            result_str += f"  - Performance degradation detected at {concurrency.get('degradation_threshold')} threads\n"
                        else:
                            result_str += "  - No significant performance degradation detected with increasing threads\n"
                        result_str += "\n"
                
                # Add insights and recommendations
                insights = detailed_info.get("insights", {})
                if insights:
                    result_str += "Insights and Recommendations:\n"
                    
                    # Recommendations
                    recommendations = insights.get("recommendations", [])
                    if recommendations:
                        result_str += "- Top Recommendations:\n"
                        for rec in recommendations[:3]:  # Show only top 3 recommendations
                            result_str += f"  - [{rec.get('priority_level', 'medium').upper()}] {rec.get('issue')}\n"
                            result_str += f"    Recommendation: {rec.get('recommendation')}\n"
                            result_str += f"    Expected Impact: {rec.get('expected_impact')}\n"
                        result_str += "\n"
                    
                    # Scaling insights
                    scaling_insights = insights.get("scaling_insights", [])
                    if scaling_insights:
                        result_str += "- Scaling Insights:\n"
                        for insight in scaling_insights[:2]:  # Show only top 2 insights
                            result_str += f"  - {insight.get('topic')}: {insight.get('description')}\n"
                        result_str += "\n"
                
                # Add time series information (just a summary)
                time_series = detailed_info.get("time_series", [])
                if time_series:
                    result_str += "Time Series Analysis:\n"
                    result_str += f"- Intervals: {len(time_series)}\n"
                    result_str += f"- Interval duration: 5 seconds\n"
                    
                    # Calculate average throughput and response time over intervals
                    avg_throughput = sum(ts.get('throughput', 0) for ts in time_series) / len(time_series)
                    avg_response_time = sum(ts.get('average_response_time', 0) for ts in time_series) / len(time_series)
                    
                    result_str += f"- Average throughput over intervals: {avg_throughput:.2f} requests/second\n"
                    result_str += f"- Average response time over intervals: {avg_response_time:.2f} ms\n\n"
            
            return result_str
            
        except ValueError as e:
            return f"Error analyzing JTL file: {str(e)}"
        
    except Exception as e:
        return f"Error analyzing JMeter results: {str(e)}"

@mcp.tool()
async def identify_performance_bottlenecks(jtl_file: str) -> str:
    """Identify performance bottlenecks in JMeter test results.
    
    Args:
        jtl_file: Path to the JTL file containing test results
        
    Returns:
        str: Bottleneck analysis results in a formatted string
    """
    try:
        analyzer = TestResultsAnalyzer()
        
        # Validate file exists
        file_path = Path(jtl_file)
        if not file_path.exists():
            return f"Error: JTL file not found: {jtl_file}"
        
        try:
            # Analyze the file with detailed analysis
            analysis_results = analyzer.analyze_file(file_path, detailed=True)
            
            # Format the results as a string
            result_str = f"Performance Bottleneck Analysis of {jtl_file}:\n\n"
            
            # Add bottleneck information
            detailed_info = analysis_results.get("detailed", {})
            bottlenecks = detailed_info.get("bottlenecks", {})
            
            if not bottlenecks:
                return f"No bottlenecks identified in {jtl_file}."
            
            # Slow endpoints
            slow_endpoints = bottlenecks.get("slow_endpoints", [])
            if slow_endpoints:
                result_str += "Slow Endpoints:\n"
                for endpoint in slow_endpoints:
                    result_str += f"- {endpoint.get('endpoint')}: {endpoint.get('response_time'):.2f} ms "
                    result_str += f"(Severity: {endpoint.get('severity')})\n"
                result_str += "\n"
            else:
                result_str += "No slow endpoints identified.\n\n"
            
            # Error-prone endpoints
            error_endpoints = bottlenecks.get("error_prone_endpoints", [])
            if error_endpoints:
                result_str += "Error-Prone Endpoints:\n"
                for endpoint in error_endpoints:
                    result_str += f"- {endpoint.get('endpoint')}: {endpoint.get('error_rate'):.2f}% "
                    result_str += f"(Severity: {endpoint.get('severity')})\n"
                result_str += "\n"
            else:
                result_str += "No error-prone endpoints identified.\n\n"
            
            # Anomalies
            anomalies = bottlenecks.get("anomalies", [])
            if anomalies:
                result_str += "Response Time Anomalies:\n"
                for anomaly in anomalies:
                    result_str += f"- At {anomaly.get('timestamp')}: "
                    result_str += f"Expected {anomaly.get('expected_value'):.2f} ms, "
                    result_str += f"Got {anomaly.get('actual_value'):.2f} ms "
                    result_str += f"({anomaly.get('deviation_percentage'):.2f}% deviation)\n"
                result_str += "\n"
            else:
                result_str += "No response time anomalies detected.\n\n"
            
            # Concurrency impact
            concurrency = bottlenecks.get("concurrency_impact", {})
            if concurrency:
                result_str += "Concurrency Impact:\n"
                correlation = concurrency.get("correlation", 0)
                result_str += f"- Correlation between threads and response time: {correlation:.2f}\n"
                
                if concurrency.get("has_degradation", False):
                    result_str += f"- Performance degradation detected at {concurrency.get('degradation_threshold')} threads\n"
                else:
                    result_str += "- No significant performance degradation detected with increasing threads\n"
                result_str += "\n"
            
            # Add recommendations
            insights = detailed_info.get("insights", {})
            recommendations = insights.get("recommendations", [])
            
            if recommendations:
                result_str += "Recommendations:\n"
                for rec in recommendations[:5]:  # Show top 5 recommendations
                    result_str += f"- [{rec.get('priority_level', 'medium').upper()}] {rec.get('recommendation')}\n"
            else:
                result_str += "No specific recommendations available.\n"
            
            return result_str
            
        except ValueError as e:
            return f"Error analyzing JTL file: {str(e)}"
        
    except Exception as e:
        return f"Error identifying performance bottlenecks: {str(e)}"

@mcp.tool()
async def get_performance_insights(jtl_file: str) -> str:
    """Get insights and recommendations for improving performance based on JMeter test results.
    
    Args:
        jtl_file: Path to the JTL file containing test results
        
    Returns:
        str: Performance insights and recommendations in a formatted string
    """
    try:
        analyzer = TestResultsAnalyzer()
        
        # Validate file exists
        file_path = Path(jtl_file)
        if not file_path.exists():
            return f"Error: JTL file not found: {jtl_file}"
        
        try:
            # Analyze the file with detailed analysis
            analysis_results = analyzer.analyze_file(file_path, detailed=True)
            
            # Format the results as a string
            result_str = f"Performance Insights for {jtl_file}:\n\n"
            
            # Add insights information
            detailed_info = analysis_results.get("detailed", {})
            insights = detailed_info.get("insights", {})
            
            if not insights:
                return f"No insights available for {jtl_file}."
            
            # Recommendations
            recommendations = insights.get("recommendations", [])
            if recommendations:
                result_str += "Recommendations:\n"
                for i, rec in enumerate(recommendations[:5], 1):  # Show top 5 recommendations
                    result_str += f"{i}. [{rec.get('priority_level', 'medium').upper()}] {rec.get('issue')}\n"
                    result_str += f"   - Recommendation: {rec.get('recommendation')}\n"
                    result_str += f"   - Expected Impact: {rec.get('expected_impact')}\n"
                    result_str += f"   - Implementation Difficulty: {rec.get('implementation_difficulty')}\n\n"
            else:
                result_str += "No specific recommendations available.\n\n"
            
            # Scaling insights
            scaling_insights = insights.get("scaling_insights", [])
            if scaling_insights:
                result_str += "Scaling Insights:\n"
                for i, insight in enumerate(scaling_insights, 1):
                    result_str += f"{i}. {insight.get('topic')}\n"
                    result_str += f"   {insight.get('description')}\n\n"
            else:
                result_str += "No scaling insights available.\n\n"
            
            # Add summary metrics for context
            summary = analysis_results.get("summary", {})
            result_str += "Test Summary:\n"
            result_str += f"- Total samples: {summary.get('total_samples', 'N/A')}\n"
            result_str += f"- Error rate: {summary.get('error_rate', 'N/A'):.2f}%\n"
            result_str += f"- Average response time: {summary.get('average_response_time', 'N/A'):.2f} ms\n"
            result_str += f"- 95th percentile: {summary.get('percentile_95', 'N/A'):.2f} ms\n"
            result_str += f"- Throughput: {summary.get('throughput', 'N/A'):.2f} requests/second\n"
            
            return result_str
            
        except ValueError as e:
            return f"Error analyzing JTL file: {str(e)}"
        
    except Exception as e:
        return f"Error getting performance insights: {str(e)}"

@mcp.tool()
async def generate_visualization(jtl_file: str, visualization_type: str, output_file: str) -> str:
    """Generate visualizations of JMeter test results.
    
    Args:
        jtl_file: Path to the JTL file containing test results
        visualization_type: Type of visualization to generate (time_series, distribution, comparison, html_report)
        output_file: Path to save the visualization
        
    Returns:
        str: Path to the generated visualization file
    """
    try:
        analyzer = TestResultsAnalyzer()
        
        # Validate file exists
        file_path = Path(jtl_file)
        if not file_path.exists():
            return f"Error: JTL file not found: {jtl_file}"
        
        try:
            # Analyze the file with detailed analysis
            analysis_results = analyzer.analyze_file(file_path, detailed=True)
            
            # Create visualization engine
            output_dir = os.path.dirname(output_file) if output_file else None
            engine = VisualizationEngine(output_dir=output_dir)
            
            # Generate visualization based on type
            if visualization_type == "time_series":
                # Extract time series metrics
                time_series = analysis_results.get("detailed", {}).get("time_series", [])
                if not time_series:
                    return "No time series data available for visualization."
                
                # Convert to TimeSeriesMetrics objects
                metrics = []
                for ts_data in time_series:
                    metrics.append(TimeSeriesMetrics(
                        timestamp=datetime.datetime.fromisoformat(ts_data["timestamp"]),
                        active_threads=ts_data["active_threads"],
                        throughput=ts_data["throughput"],
                        average_response_time=ts_data["average_response_time"],
                        error_rate=ts_data["error_rate"]
                    ))
                
                # Create visualization
                output_path = engine.create_time_series_graph(
                    metrics, metric_name="average_response_time", output_file=output_file)
                return f"Time series graph generated: {output_path}"
                
            elif visualization_type == "distribution":
                # Extract response times
                samples = []
                for endpoint, metrics in analysis_results.get("detailed", {}).get("endpoints", {}).items():
                    samples.extend([metrics["average_response_time"]] * metrics["total_samples"])
                
                if not samples:
                    return "No response time data available for visualization."
                
                # Create visualization
                output_path = engine.create_distribution_graph(samples, output_file=output_file)
                return f"Distribution graph generated: {output_path}"
                
            elif visualization_type == "comparison":
                # Extract endpoint metrics
                endpoints = analysis_results.get("detailed", {}).get("endpoints", {})
                if not endpoints:
                    return "No endpoint data available for visualization."
                
                # Convert to EndpointMetrics objects
                endpoint_metrics = {}
                for endpoint, metrics_data in endpoints.items():
                    endpoint_metrics[endpoint] = EndpointMetrics(
                        endpoint=endpoint,
                        total_samples=metrics_data["total_samples"],
                        error_count=metrics_data["error_count"],
                        error_rate=metrics_data["error_rate"],
                        average_response_time=metrics_data["average_response_time"],
                        median_response_time=metrics_data["median_response_time"],
                        percentile_90=metrics_data["percentile_90"],
                        percentile_95=metrics_data["percentile_95"],
                        percentile_99=metrics_data["percentile_99"],
                        min_response_time=metrics_data["min_response_time"],
                        max_response_time=metrics_data["max_response_time"],
                        throughput=metrics_data["throughput"],
                        test_duration=analysis_results["summary"]["duration"]
                    )
                
                # Create visualization
                output_path = engine.create_endpoint_comparison_chart(
                    endpoint_metrics, metric_name="average_response_time", output_file=output_file)
                return f"Endpoint comparison chart generated: {output_path}"
                
            elif visualization_type == "html_report":
                # Create HTML report
                output_path = engine.create_html_report(analysis_results, output_file)
                return f"HTML report generated: {output_path}"
                
            else:
                return f"Unknown visualization type: {visualization_type}. " \
                       f"Supported types: time_series, distribution, comparison, html_report"
            
        except ValueError as e:
            return f"Error generating visualization: {str(e)}"
        
    except Exception as e:
        return f"Error generating visualization: {str(e)}"

def generate_unique_id():
    """
    Generate a unique identifier using timestamp and UUID.
    
    Returns:
        str: A unique identifier string
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    random_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for brevity
    return f"{timestamp}_{random_id}"


if __name__ == "__main__":
    mcp.run(transport='stdio')