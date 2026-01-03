Yes, you can absolutely develop an MCP (Model Context Protocol) server in Python. In fact, Python is one of the two primary languages (along with TypeScript) officially supported by Anthropic and the open-source community for this purpose.

The easiest way to get started is using the **FastMCP** interface provided by the official SDK, which handles the complex protocol details (JSON-RPC, transport, etc.) for you.

Here is a step-by-step guide to building your first MCP server in Python.

### 1. Prerequisites

You need Python installed. Then, install the official MCP SDK:

```bash
pip install mcp

```

### 2. Create a Simple MCP Server

Create a file named `server.py`. We will create a simple server that provides a "calculator" tool and a "weather" tool.

```python
from mcp.server.fastmcp import FastMCP

# 1. Initialize the server
mcp = FastMCP("My First MCP Server")

# 2. Define a tool
# The docstring is CRITICAL: it tells the AI when and how to use this tool.
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

# 3. Define a resource (Optional)
# Resources are data that the AI can read (like files or database rows)
@mcp.resource("config://app-settings")
def get_config() -> str:
    """Return application configuration settings."""
    return "Theme: Dark, Language: English, Version: 1.0"

# 4. Run the server
if __name__ == "__main__":
    mcp.run()

```

### 3. How to Run and Test It

MCP servers are rarely run "standalone" like a web server; they are usually run *by* a client (like the Claude Desktop app or an IDE like Cursor) over standard input/output (stdio).

#### Option A: Test with the MCP Inspector (Recommended)

The MCP Inspector is a web-based tool to test your server without needing Claude.

1. Install the inspector: `npm install -g @modelcontextprotocol/inspector` (requires Node.js) or use `npx`.
2. Run your server through the inspector:
```bash
npx @modelcontextprotocol/inspector python server.py

```


3. This will open a browser UI where you can click your tools (`add_numbers`) and see the results.

#### Option B: Connect to Claude Desktop

To use your new server inside the Claude Desktop app:

1. Open (or create) the configuration file:
* **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
* **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`


2. Add your server details:
```json
{
  "mcpServers": {
    "my-python-server": {
      "command": "python",
      "args": ["/absolute/path/to/your/server.py"]
    }
  }
}

```


*(Note: Use the absolute path to your python executable if you are using a virtual environment, e.g., `"/path/to/venv/bin/python"`)*.
3. Restart Claude Desktop. You should see a generic "plug" icon, indicating the tool is connected. You can now ask Claude: *"Please add 123 and 456 using the tool."*

### 4. Key Concepts to Know

* **Tools:** Functions the AI can execute. These are for taking actions (calculating, fetching API data, querying a DB).
* **Resources:** Data the AI can read. Think of these like "files" that the AI can open and read context from.
* **Prompts:** Reusable prompt templates you can define in code to help users start specific workflows.
* **Context:** If your tool needs to report progress (e.g., for a long-running download), you can accept a `Context` argument in your function to send status updates back to the client.

### Next Step

Would you like me to show you how to write a more advanced tool, such as one that **fetches live data from a real API** (like a weather or stock price API)?