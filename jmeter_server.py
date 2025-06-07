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
