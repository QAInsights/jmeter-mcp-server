# 🚀 JMeter MCP Server

This is a Model Context Protocol (MCP) server that allows executing JMeter tests through MCP-compatible clients.

> [!IMPORTANT]
> 📢 Looking for an AI Assistant inside JMeter? 🚀
> Check out [Feather Wand](https://jmeter.ai)

![Anthropic](./images/Anthropic-MCP.png)
![Cursor](./images/Cursor.png)
![Windsurf](./images/Windsurf.png)

## 📋 Features

📊 Execute JMeter tests in non-GUI modes
🖥️ Launch JMeter in GUI mode
📝 Capture and return execution output

## 🛠️ Installation

### Local Installation

📦 1. Install [`uv`](https://github.com/astral-sh/uv):

💻 2. Ensure JMeter is installed on your system and accessible via the command line.

⚠️ **Important**: Make sure JMeter is executable. You can do this by running:

```bash
chmod +x /path/to/jmeter/bin/jmeter
```

## 🚀 Usage

🔗 1. Connect to the server using an MCP-compatible client (e.g., Claude Desktop, Cursor, Windsurf)

📝 2. Send a prompt to the server:

```
Run JMeter test /path/to/test.jmx
```

🔧 3. MCP compatible client will use the available tools:
   - 🖥️ `execute_jmeter_test`: Launches JMeter in GUI mode, but doesn't execute test as per the JMeter design
   - 🚀 `execute_jmeter_test_non_gui`: Execute a JMeter test in non-GUI mode (default mode for better performance)

## 🛑 Error Handling

The server will:

- Validate that the test file exists
- Check that the file has a .jmx extension
- Capture and return any execution errors
