from typing import Optional
import asyncio
import signal
import subprocess
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import os
import datetime
import logging
from dotenv import load_dotenv

from analyzer.models import TimeSeriesMetrics, EndpointMetrics
from analyzer.analyzer import TestResultsAnalyzer
from analyzer.visualization.engine import VisualizationEngine
from runs.util import (build_jmeter_command, kill_process_tree,
                       truncate_output)
from runs.manager import get_run_manager
from runs.live_metrics import read_live_metrics
from output.formatting import json_error, json_ok, normalize_format, to_json
from output import prompts as _prompts

# Configure logging (stderr only; stdout is reserved for the MCP stdio channel)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("jmeter")

DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_OUTPUT_MAX_LINES = 200

# Re-export for backward compatibility (lives in runs.util now)
_truncate_output = truncate_output


def _get_timeout_seconds() -> Optional[float]:
    """Return the JMeter run timeout in seconds.

    Reads JMETER_TIMEOUT_SECONDS (default 3600). A value <= 0 means no
    timeout (returns None); an invalid value logs a warning and uses the default.
    """
    raw = os.getenv('JMETER_TIMEOUT_SECONDS')
    if raw is None:
        return float(DEFAULT_TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except ValueError:
        logger.warning(f"Invalid JMETER_TIMEOUT_SECONDS value '{raw}'; using default {DEFAULT_TIMEOUT_SECONDS}")
        return float(DEFAULT_TIMEOUT_SECONDS)
    if value <= 0:
        return None
    return value


def _kill_process_tree(proc) -> None:
    """Kill a subprocess and its whole process group (the jmeter launcher
    shell script only forwards signals inconsistently, so killing the
    wrapper alone leaves the Java child running)."""
    kill_process_tree(proc.pid, signal.SIGKILL)


def _err(message: str, fmt: str) -> str:
    """Return an error string in the requested output format."""
    return json_error(message) if fmt == 'json' else f"Error: {message}"


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
        logger.debug(f"JMeter binary path: {jmeter_bin}")
        logger.debug(f"Java options: {java_opts}")

        # Build command
        cmd, log_file, report_output_dir = build_jmeter_command(
            test_file_path, jmeter_bin, non_gui=non_gui, properties=properties,
            generate_report=generate_report, report_output_dir=report_output_dir,
            log_file=log_file)

        # Log the full command for debugging
        logger.debug(f"Executing command: {' '.join(cmd)}")
        
        if non_gui:
            # For non-GUI mode, capture output asynchronously with a timeout
            timeout = _get_timeout_seconds()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                _kill_process_tree(proc)
                await proc.wait()
                return (f"Error: JMeter test timed out after {timeout} seconds and was terminated. "
                        f"Increase JMETER_TIMEOUT_SECONDS if the test legitimately needs longer.")

            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")

            # Log output for debugging
            logger.debug("Command output:")
            logger.debug(f"Return code: {proc.returncode}")
            logger.debug(f"Stdout: {stdout}")
            logger.debug(f"Stderr: {stderr}")

            if proc.returncode != 0:
                return f"Error executing JMeter test (exit code {proc.returncode}):\n{_truncate_output(stderr or stdout)}"

            return _truncate_output(stdout)
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

@mcp.tool()
async def analyze_jmeter_results(jtl_file: str, detailed: bool = False, format: str = "markdown") -> str:
    """Analyze JMeter test results and provide a summary of key metrics and insights.
    
    Args:
        jtl_file: Path to the JTL file containing test results
        detailed: Whether to include detailed analysis (default: False)
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
        
    Returns:
        str: Analysis results in a formatted string
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        analyzer = TestResultsAnalyzer()
        
        # Validate file exists
        file_path = Path(jtl_file)
        if not file_path.exists():
            return _err(f"JTL file not found: {jtl_file}", fmt)
        
        try:
            # Analyze the file
            analysis_results = analyzer.analyze_file(file_path, detailed=detailed)
            
            if fmt == 'json':
                payload = dict(analysis_results)
                payload["file"] = str(file_path)
                return json_ok(payload)
            
            # Format the results as a string
            result_str = f"Analysis of {jtl_file}:\n\n"
            
            # Add summary information
            summary = analysis_results.get("summary", {})
            result_str += "Summary:\n"
            result_str += f"- Total samples: {summary.get('total_samples', 'N/A')}\n"
            result_str += f"- Error count: {summary.get('error_count', 'N/A')} ({summary.get('error_rate', 'N/A'):.2f}%)\n"
            result_str += "- Response times (ms):\n"
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
                    result_str += "- Interval duration: 5 seconds\n"
                    
                    # Calculate average throughput and response time over intervals
                    avg_throughput = sum(ts.get('throughput', 0) for ts in time_series) / len(time_series)
                    avg_response_time = sum(ts.get('average_response_time', 0) for ts in time_series) / len(time_series)
                    
                    result_str += f"- Average throughput over intervals: {avg_throughput:.2f} requests/second\n"
                    result_str += f"- Average response time over intervals: {avg_response_time:.2f} ms\n\n"
            
            return result_str
            
        except ValueError as e:
            return _err(f"analyzing JTL file: {str(e)}", fmt)
        
    except Exception as e:
        return _err(f"analyzing JMeter results: {str(e)}", fmt)

@mcp.tool()
async def identify_performance_bottlenecks(jtl_file: str, format: str = "markdown") -> str:
    """Identify performance bottlenecks in JMeter test results.
    
    Args:
        jtl_file: Path to the JTL file containing test results
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
        
    Returns:
        str: Bottleneck analysis results in a formatted string
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        analyzer = TestResultsAnalyzer()
        
        # Validate file exists
        file_path = Path(jtl_file)
        if not file_path.exists():
            return _err(f"JTL file not found: {jtl_file}", fmt)
        
        try:
            # Analyze the file with detailed analysis
            analysis_results = analyzer.analyze_file(file_path, detailed=True)
            
            if fmt == 'json':
                return json_ok({
                    "file": str(file_path),
                    "bottlenecks": analysis_results.get("detailed", {}).get("bottlenecks", {}),
                    "summary": analysis_results.get("summary", {})
                })
            
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
            return _err(f"analyzing JTL file: {str(e)}", fmt)
        
    except Exception as e:
        return _err(f"identifying performance bottlenecks: {str(e)}", fmt)

@mcp.tool()
async def get_performance_insights(jtl_file: str, format: str = "markdown") -> str:
    """Get insights and recommendations for improving performance based on JMeter test results.
    
    Args:
        jtl_file: Path to the JTL file containing test results
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
        
    Returns:
        str: Performance insights and recommendations in a formatted string
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        analyzer = TestResultsAnalyzer()
        
        # Validate file exists
        file_path = Path(jtl_file)
        if not file_path.exists():
            return _err(f"JTL file not found: {jtl_file}", fmt)
        
        try:
            # Analyze the file with detailed analysis
            analysis_results = analyzer.analyze_file(file_path, detailed=True)
            
            if fmt == 'json':
                return json_ok({
                    "file": str(file_path),
                    "insights": analysis_results.get("detailed", {}).get("insights", {}),
                    "summary": analysis_results.get("summary", {})
                })
            
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
            return _err(f"analyzing JTL file: {str(e)}", fmt)
        
    except Exception as e:
        return _err(f"getting performance insights: {str(e)}", fmt)

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

def _status_dict(record) -> dict:
    """Build the status payload for a run record (shared by markdown and
    JSON renderers so both formats can't drift)."""
    start = datetime.datetime.fromisoformat(record.start_time)
    end = (datetime.datetime.fromisoformat(record.end_time)
           if record.end_time else datetime.datetime.now())
    elapsed = (end - start).total_seconds()

    live_metrics = None
    if record.jtl_path and Path(record.jtl_path).exists():
        metrics = read_live_metrics(record.jtl_path)
        live_metrics = metrics if metrics.get("supported") else None

    data = record.to_dict()
    data["elapsed_seconds"] = elapsed
    data["live_metrics"] = live_metrics
    return data


@mcp.tool()
async def start_jmeter_test(test_file: str, properties: dict = None, generate_report: bool = False, report_output_dir: str = None, log_file: str = None, format: str = "markdown") -> str:
    """Start a JMeter test in the background and return a run id for polling.

    Args:
        test_file: Path to the JMeter test file (.jmx)
        properties: Dictionary of JMeter properties to pass with -J (default: None)
        generate_report: Whether to generate report dashboard after load test (default: False)
        report_output_dir: Output folder for report dashboard (default: None)
        log_file: Path of JTL file to log sample results to (default: <run_dir>/results.jtl)
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        record = await get_run_manager().start(
            test_file, properties=properties, generate_report=generate_report,
            report_output_dir=report_output_dir, log_file=log_file)
        if fmt == 'json':
            return json_ok(record.to_dict())
        lines = [f"Started JMeter run {record.run_id}",
                 f"- PID: {record.pid}",
                 f"- JTL: {record.jtl_path}"]
        if record.report_dir:
            lines.append(f"- Report dir: {record.report_dir}")
        lines.append(f"- stdout log: {record.stdout_path}")
        lines.append(f"Use get_test_status('{record.run_id}') to poll.")
        return "\n".join(lines)
    except ValueError as e:
        return _err(str(e).removeprefix("Error: "), fmt)
    except Exception as e:
        return _err(str(e), fmt)


@mcp.tool()
async def get_test_status(run_id: str, format: str = "markdown") -> str:
    """Get the status and live metrics of a background JMeter run.

    Args:
        run_id: Run identifier returned by start_jmeter_test
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        manager = get_run_manager()
        record = manager.status(run_id)
        if record is None:
            return _err("Unknown run id", fmt)

        data = _status_dict(record)
        if fmt == 'json':
            return json_ok(data)

        lines = [f"Run {record.run_id}",
                 f"- Status: {record.status}",
                 f"- Elapsed: {data['elapsed_seconds']:.1f} seconds",
                 f"- PID: {record.pid}",
                 f"- Exit code: {record.exit_code}",
                 f"- Test file: {record.test_file}",
                 f"- JTL: {record.jtl_path}",
                 f"- stdout log: {record.stdout_path}",
                 f"- stderr log: {record.stderr_path}"]
        if record.report_dir:
            lines.append(f"- Report dir: {record.report_dir}")
        if record.error:
            lines.append(f"- Error: {record.error}")

        metrics = data['live_metrics']
        if metrics is not None:
            lines.append("Live metrics:")
            lines.append(f"- Total samples so far: {metrics['total_samples']}")
            lines.append(f"- Recent window: {metrics['recent_samples']} samples, "
                         f"{metrics['recent_error_rate_pct']:.1f}% errors")
            lines.append(f"- Recent avg response: {metrics['recent_avg_response_ms']:.1f} ms")
            lines.append(f"- Recent p95 response: {metrics['recent_p95_response_ms']:.1f} ms")
            if metrics.get('active_threads') is not None:
                lines.append(f"- Active threads (last sample): {metrics['active_threads']}")
            if metrics.get('last_sample_time'):
                lines.append(f"- Last sample time: {metrics['last_sample_time']}")
        elif record.jtl_path and Path(record.jtl_path).exists():
            lines.append(f"Live metrics unavailable: {read_live_metrics(record.jtl_path).get('reason')}")
        return "\n".join(lines)
    except Exception as e:
        return _err(str(e), fmt)


@mcp.tool()
async def stop_jmeter_test(run_id: str, graceful: bool = True, timeout_seconds: float = 30.0, format: str = "markdown") -> str:
    """Stop a background JMeter run.

    Args:
        run_id: Run identifier returned by start_jmeter_test
        graceful: Use JMeter's shutdown listener first, escalating to signals (default: True)
        timeout_seconds: Seconds to wait for graceful shutdown before escalating (default: 30)
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        manager = get_run_manager()
        record = manager.status(run_id)
        if record is None:
            return _err("Unknown run id", fmt)
        if record.status not in ("starting", "running"):
            if fmt == 'json':
                return json_error(f"Run {run_id} is not running (status: {record.status})")
            return f"Run {run_id} is not running (status: {record.status})"
        record = await manager.stop(run_id, graceful=graceful, timeout_seconds=timeout_seconds)
        if fmt == 'json':
            return json_ok(record.to_dict())
        return f"Run {run_id} stopped (status: {record.status}, exit code: {record.exit_code})"
    except Exception as e:
        return _err(str(e), fmt)


@mcp.tool()
async def get_test_output(run_id: str, tail_lines: int = 100, format: str = "markdown") -> str:
    """Get the tail of a run's stdout/stderr logs.

    Args:
        run_id: Run identifier returned by start_jmeter_test
        tail_lines: Number of lines to return per stream (default: 100)
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        manager = get_run_manager()
        if manager.status(run_id) is None:
            return _err("Unknown run id", fmt)
        out = manager.output(run_id, tail_lines=tail_lines)
        if fmt == 'json':
            return json_ok({"run_id": run_id, "stdout": out['stdout'], "stderr": out['stderr']})
        return f"stdout (last {tail_lines} lines):\n{out['stdout']}\n\nstderr (last {tail_lines} lines):\n{out['stderr']}"
    except Exception as e:
        return _err(str(e), fmt)


@mcp.tool()
async def list_test_runs(limit: int = 20, format: str = "markdown") -> str:
    """List recent JMeter runs.

    Args:
        limit: Maximum number of runs to return, newest first (default: 20)
        format: "markdown" (default, human-readable) or "json" (machine-readable {"ok", "data"} envelope)
    """
    try:
        fmt = normalize_format(format)
    except ValueError as e:
        return f"Error: {e}"
    try:
        records = get_run_manager().list(limit=limit)
        if fmt == 'json':
            return json_ok({"runs": [r.to_dict() for r in records]})
        if not records:
            return "No runs found."
        lines = []
        for record in records:
            lines.append(f"{record.run_id} | {record.status} | {record.start_time} | "
                         f"{Path(record.test_file).name}")
        return "\n".join(lines)
    except Exception as e:
        return _err(str(e), fmt)


@mcp.resource("jmeter://runs", mime_type="application/json")
def list_runs_resource() -> str:
    """JSON list of recent JMeter run records."""
    records = get_run_manager().list(limit=50)
    return to_json([r.to_dict() for r in records])


@mcp.resource("jmeter://runs/{run_id}", mime_type="application/json")
def run_resource(run_id: str) -> str:
    """JSON status dict for a single run (same shape as get_test_status)."""
    record = get_run_manager().status(run_id)
    if record is None:
        raise ValueError(f"Unknown run id: {run_id}")
    return to_json(_status_dict(record))


@mcp.resource("jmeter://runs/{run_id}/output")
def run_output_resource(run_id: str) -> str:
    """Text: last 200 lines of stdout then stderr for a run."""
    manager = get_run_manager()
    if manager.status(run_id) is None:
        raise ValueError(f"Unknown run id: {run_id}")
    out = manager.output(run_id, tail_lines=200)
    return f"{out['stdout']}\n--- stderr ---\n{out['stderr']}"


@mcp.resource("jmeter://runs/{run_id}/analysis", mime_type="application/json")
def run_analysis_resource(run_id: str) -> str:
    """JSON full analysis of a run's JTL file."""
    record = get_run_manager().status(run_id)
    if record is None:
        raise ValueError(f"Unknown run id: {run_id}")
    jtl = record.jtl_path
    if not jtl or not Path(jtl).exists() or Path(jtl).stat().st_size == 0:
        return json_error("JTL file missing or empty", run_id=run_id)
    try:
        results = TestResultsAnalyzer().analyze_file(jtl, detailed=True)
    except Exception as e:
        return json_error(str(e), run_id=run_id)
    return json_ok(results)


@mcp.prompt()
def analyze_latest_run() -> str:
    """Analyze the most recent JMeter run (metrics, bottlenecks, recommendations)."""
    return _prompts.ANALYZE_LATEST_RUN


@mcp.prompt()
def compare_last_two_runs() -> str:
    """Compare the two most recent JMeter runs and flag regressions."""
    return _prompts.COMPARE_LAST_TWO_RUNS


@mcp.prompt()
def run_and_monitor_test(test_file: str) -> str:
    """Start a JMeter test in the background, monitor it, then analyze."""
    return _prompts.run_and_monitor_test(test_file)


if __name__ == "__main__":
    mcp.run(transport='stdio')