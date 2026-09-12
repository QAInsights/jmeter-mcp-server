from jmeter_server import mcp, logger


def main():
    logger.info("Starting JMeter MCP server...")
    mcp.run(transport='stdio')


if __name__ == "__main__":
    main()
