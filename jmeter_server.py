from typing import Any
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv

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

        # Build command
        cmd = []
        if java_opts:
            cmd.extend(['java', java_opts])
        cmd.append(jmeter_bin)
        
        if non_gui:
            cmd.extend(['-n'])
        cmd.extend(['-t', str(test_file_path)])

        # Execute JMeter
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        return f"JMeter execution completed successfully:\n{result.stdout}"

    except subprocess.CalledProcessError as e:
        return f"Error executing JMeter test:\n{e.stderr}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"

@mcp.tool()
async def execute_jmeter_test(test_file: str) -> str:
    """Execute a JMeter test.

    Args:
        test_file: Path to the JMeter test file (.jmx)
    """
    return await run_jmeter(test_file)

@mcp.tool()
async def execute_jmeter_test_non_gui(test_file: str) -> str:
    """Execute a JMeter test in non-GUI mode.

    Args:
        test_file: Path to the JMeter test file (.jmx)
    """
    return await run_jmeter(test_file, non_gui=True)

if __name__ == "__main__":
    mcp.run(transport='stdio')
