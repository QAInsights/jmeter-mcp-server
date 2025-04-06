from typing import Any
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import os
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

async def run_jmeter(test_file: str, non_gui: bool = True) -> str:
    """Run a JMeter test.

    Args:
        test_file: Path to the JMeter test file (.jmx)
        non_gui: Run in non-GUI mode (default: True)

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
async def execute_jmeter_test(test_file: str, gui_mode: bool = False) -> str:
    """Execute a JMeter test.

    Args:
        test_file: Path to the JMeter test file (.jmx)
        gui_mode: Whether to run in GUI mode (default: False)
    """
    return await run_jmeter(test_file, non_gui=not gui_mode)  # Run in non-GUI mode by default

@mcp.tool()
async def execute_jmeter_test_non_gui(test_file: str) -> str:
    """Execute a JMeter test in non-GUI mode.

    Args:
        test_file: Path to the JMeter test file (.jmx)
    """
    return await run_jmeter(test_file, non_gui=True)

if __name__ == "__main__":
    mcp.run(transport='stdio')
