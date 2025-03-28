from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import os

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("jmeter")

def main():
    print("Starting JMeter MCP server...")
    print(os.getenv('JMETER_HOME'))
    print(os.getenv('JMETER_BIN'))
    print(os.getenv('JMETER_JAVA_OPTS'))
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
