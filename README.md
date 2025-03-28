# JMeter MCP Server

This is a Model Context Protocol (MCP) server that allows executing JMeter tests through MCP-compatible clients.

## Features

- Execute JMeter tests in both GUI and non-GUI modes
- Validate JMeter test files before execution
- Capture and return execution output

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure JMeter is installed on your system and accessible via the command line.

## Usage

1. Run the server:
```bash
python jmeter_server.py
```

2. Connect to the server using an MCP-compatible client (e.g., Claude Desktop)

3. Use the available tools:
   - `execute_jmeter_test`: Execute a JMeter test in GUI mode
   - `execute_jmeter_test_non_gui`: Execute a JMeter test in non-GUI mode

## Example

To execute a JMeter test:
```python
# Using execute_jmeter_test_non_gui
result = await execute_jmeter_test_non_gui("/path/to/test.jmx")
```

## Error Handling

The server will:
- Validate that the test file exists
- Check that the file has a .jmx extension
- Capture and return any execution errors
