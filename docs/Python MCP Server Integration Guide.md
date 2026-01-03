# **The Definitive Architecture for Distributing Python MCP Servers: A Comprehensive Analysis of Cross-Platform Installation and Configuration**

## **Executive Summary**

The Model Context Protocol (MCP) has rapidly established itself as the interoperability standard for the next generation of AI agents, providing a universal interface ("USB-C for AI") that connects Large Language Models (LLMs) to external data, tools, and resources.1 For developers, this shifts the paradigm from building bespoke integrations for every AI client to building a single, standardized server. However, while the *protocol* is unified, the *distribution and installation* landscape remains deeply fragmented. A Python-based MCP server hosted on a public GitHub repository faces a complex matrix of client-specific requirements: varying configuration file formats (JSON vs. TOML), disparate environment variable security models, and divergent execution contexts (local STDIO subprocesses vs. remote HTTP/SSE streams).

This report provides an exhaustive, expert-level analysis of the deployment architecture required to ensure a "zero-friction" installation experience for a Python MCP server across seven distinct platforms: **Claude Code, OpenAI Codex, Gemini CLI, Cursor, Claude Desktop, GitHub Copilot, and Microsoft Copilot**.

The analysis identifies the uv package manager as the critical architectural component for solving the Python dependency distribution problem, enabling transient, isolated execution without manual environment setup. Furthermore, it delineates the specific configuration schemas, authentication flows, and security best practices for propagating environment variables (such as API keys) in each tool. By synthesizing these findings, this report offers a unified strategy for repository structure and documentation that satisfies the unique constraints of each client while maintaining a seamless developer experience.

## **1\. Architectural Foundations: The Python Distribution Challenge in the MCP Ecosystem**

The user's core objective is to allow seamless installation of a Python MCP server directly from an open GitHub repository. To achieve this, we must first address the inherent friction of Python software distribution. Traditional workflows—requiring users to clone a repository, manually create a virtual environment (python \-m venv venv), activate it, and install dependencies (pip install \-r requirements.txt)—are antithetical to the "easy to install" requirement. They introduce high cognitive load and multiple points of failure, particularly regarding Python version mismatches and path management.3

### **1.1 The uv Revolution: Ephemeral execution and Dependency Isolation**

The research overwhelmingly supports the adoption of **uv** as the standard distribution mechanism for Python MCP servers.3 Developed by Astral, uv is a high-performance Python package manager that fundamentally alters the execution model by treating Python tools as transient, runnable entities rather than static installations.

Mechanism of Action:  
Unlike pip, which installs packages into a persistent environment, uv allows for the execution of remote scripts with ad-hoc environment construction. For an MCP server hosted on GitHub, this capability is transformative. It allows the developer to provide a single command that:

1. Downloads the necessary Python interpreter version (isolated from the system Python).  
2. Creates a cached, ephemeral virtual environment.  
3. Installs the dependencies defined in the script or project metadata (e.g., mcp\[cli\], pydantic).  
4. Executes the server entry point.

This entire process occurs transparently to the user, eliminating "dependency hell." The user does not need to manage venv directories or worry about conflicting library versions.7

The Standardized Installation Syntax:  
Throughout this report, the recommended installation strategy relies on uv's ability to pull and run code directly from a URL or Git repository. The generic "easy install" command pattern, which will be adapted for each tool, is:

Bash

uv run \--with mcp\[cli\] https://github.com/username/repo/blob/main/server.py

Or, for complex multi-file projects packaged as tools:

Bash

uv tool install git+https://github.com/username/repo

This approach shifts the burden of environment management from the end-user to the package manager, satisfying the requirement for ease of use.9

### **1.2 The Transport Layer: STDIO vs. SSE**

A critical architectural distinction that impacts installation across the seven target tools is the transport protocol. The MCP specification supports two primary transport modes:

1. **STDIO (Standard Input/Output):** The client application (e.g., Claude Desktop, Cursor) spawns the MCP server as a local child process. Communication occurs via stdin and stdout pipes. This is the dominant mode for local desktop tools.10  
2. **SSE (Server-Sent Events) over HTTP:** The MCP server runs as an independent web service (often utilizing FastAPI or Starlette). The client connects to an HTTP endpoint. This is required for enterprise-grade tools like Microsoft Copilot and distributed agent architectures.1

Implications for Python Servers:  
To be "easy to install" across all requested tools, the server architecture must ideally support both transports, or the documentation must explicitly guide users on how to run the server in the appropriate mode.

* **STDIO constraint:** Any extraneous output to stdout (e.g., print("Initializing...")) will corrupt the JSON-RPC message stream and cause connection failure. Python servers must strictly direct logs to stderr.13  
* **Environment Variable Injection:** In STDIO mode, the parent process (the MCP Client) is responsible for injecting environment variables into the server process. In SSE mode, the server process is usually started manually by the user, inheriting the user's shell environment directly.

The following sections analyze the specific configuration and installation nuances for each of the seven requested tools.

## ---

**2\. Platform Analysis: Claude Desktop**

Claude Desktop serves as the reference implementation for local MCP integration. It provides deep file system access and a robust UI for interacting with tools, but its configuration is entirely file-based, requiring users to manually edit a JSON file.

### **2.1 Configuration Architecture**

Claude Desktop does not possess an internal command-line interface for adding tools. Instead, it watches a specific configuration file for changes.

* **macOS Location:** \~/Library/Application Support/Claude/claude\_desktop\_config.json  
* **Windows Location:** %APPDATA%\\Claude\\claude\_desktop\_config.json.14

The configuration schema is a JSON object containing an mcpServers key, which maps server names to their execution commands.

### **2.2 The "Easy Install" Strategy**

For a Python server hosted on GitHub, the naive approach of asking users to git clone the repo and then point the config to a local path is error-prone. It relies on the user successfully setting up a local virtual environment. The superior strategy utilizes uv to execute the remote code.

Recommended Configuration Snippet:  
Users should be instructed to paste the following block into their claude\_desktop\_config.json.

JSON

{  
  "mcpServers": {  
    "my-github-tool": {  
      "command": "/absolute/path/to/uv",  
      "args": \[  
        "run",  
        "--with", "mcp",  
        "https://github.com/username/repo/blob/main/server.py"  
      \],  
      "env": {  
        "API\_KEY": "YOUR\_API\_KEY\_HERE"  
      }  
    }  
  }  
}

Technical Nuance \- The PATH Problem:  
A frequent point of failure in Claude Desktop on macOS and Linux is environment isolation. The desktop application is often launched via the Dock or a launcher, not from the user's shell. Consequently, it does not inherit the user's PATH variable (e.g., configurations in .zshrc are ignored).16

* **Implication:** Simply specifying "command": "uv" often results in a "command not found" error, even if uv is installed.  
* **Requirement:** The installation documentation **must** explicitly instruct users to provide the *absolute path* to the uv executable (e.g., /Users/alice/.cargo/bin/uv). This is a critical detail for ensuring reliability.16

### **2.3 Environment Variable Handling**

The user's request specifies that the server relies on environment variables. Claude Desktop's handling of these variables is rigid and presents a security/usability trade-off.

* **No Interpolation:** The configuration file does not support variable expansion syntax (e.g., ${API\_KEY} or $HOME).  
* **Static Definition:** Variables must be defined explicitly in the env dictionary within the JSON config.14

Implication for "Easy Installation":  
Since the config file does not read from the user's system environment, the user must be instructed to paste their secrets (API keys) directly into the claude\_desktop\_config.json file. While this is functional, it is not ideal for security. A more advanced "easy" setup involves instructing the user to create a .env file and using uv to load it, or handling .env loading within the Python server code itself (using python-dotenv), so the config file remains clean.  
**Table 1: Claude Desktop Configuration Summary**

| Feature | Implementation Detail |
| :---- | :---- |
| **Config Format** | JSON (claude\_desktop\_config.json) |
| **Transport** | STDIO (Default) |
| **Env Vars** | Static env block only; no shell inheritance. |
| **Exec Path** | Requires absolute path to binary (e.g., /usr/bin/python). |
| **Best Practice** | Use uv with absolute path to abstract dependency management. |

## ---

**3\. Platform Analysis: Claude Code (CLI)**

Claude Code represents Anthropic's venture into terminal-centric AI assistance. Unlike the Desktop app, it is managed almost entirely through imperative CLI commands, making it significantly easier to script and automate.

### **3.1 Configuration Architecture**

Claude Code maintains an internal configuration state but allows for project-specific overrides.

* **Global Scope:** Managed internally by the tool.  
* **Project Scope:** Stored in a .claude.json or .mcp.json file in the project root.17

### **3.2 The "Easy Install" Strategy**

Claude Code offers perhaps the most streamlined installation experience of all seven tools. It does not require the user to edit a file manually; they simply run a command.

**The Command Pattern:**

Bash

claude mcp add my-server \-- uv run https://github.com/username/repo/blob/main/server.py

Critical Syntax \- The Double Dash (--):  
The syntax relies on the double dash delimiter. Everything before the \-- constitutes arguments for the Claude Code tool (e.g., naming the server, setting scope). Everything after the \-- is the actual command string that Claude Code will use to launch the server process.10 Omitting this delimiter is a common user error that documentation must address.

### **3.3 Environment Variable Handling**

Claude Code excels in handling environment variables during the installation process. The add command accepts an \--env flag.

**Command with Variables:**

Bash

claude mcp add my-server \--env API\_KEY=sk-12345 \-- uv run https://github.com/username/repo/blob/main/server.py

Security Insight \- Project Scope:  
If the user installs the server with \--scope project, the configuration—including the environment variables—is written to .mcp.json in the current directory.17

* **Risk:** If the user commits .mcp.json to version control, they will leak their API keys.  
* **Requirement:** The installation guide must explicitly warn users to add .mcp.json to their .gitignore file if they use project-scoped installation with secrets. Alternatively, use the \--scope user flag (default) to store secrets in the global user configuration, which is safer.10

## ---

**4\. Platform Analysis: Cursor**

Cursor, the AI-powered fork of VS Code, has aggressively integrated MCP, positioning it as a core extensibility layer. Its configuration model is highly developer-centric, favoring project-local configuration files that can be shared (minus the secrets).

### **4.1 Configuration Architecture**

Cursor looks for MCP configuration in a specific location within the project:

* **Project Config:** .cursor/mcp.json.19  
* **Global Config:** Accessible via Cursor Settings \> Features \> MCP.

For a GitHub repository, the "easiest" installation involves including a pre-configured .cursor/mcp.json template in the repo that the user can simply copy.

### **4.2 The "Easy Install" Strategy**

The user should be instructed to create the .cursor directory and the mcp.json file.

**Recommended .cursor/mcp.json:**

JSON

{  
  "mcpServers": {  
    "my-repo-tool": {  
      "command": "uv",  
      "args": \[  
        "run",  
        "server.py"  
      \],  
      "env": {  
        "API\_KEY": "${env:MY\_API\_KEY}"  
      }  
    }  
  }  
}

### **4.3 Environment Variable Handling**

Cursor provides the most robust support for environment variable interpolation among the tools analyzed. It supports the syntax ${env:VARIABLE\_NAME} within the configuration file.20

Mechanism:  
When Cursor launches the MCP server, it resolves ${env:MY\_API\_KEY} by looking at:

1. The .env file in the project root (automatically loaded by Cursor).  
2. The shell environment variables where Cursor was launched.

Benefit for Ease of Use:  
This allows for a clear separation of concerns. The .cursor/mcp.json file can be committed to the repository without secrets. The user is instructed to simply:

1. Create a .env file.  
2. Add MY\_API\_KEY=xyz.  
3. Cursor automatically injects this into the server process.

Troubleshooting Note:  
Research indicates a specific bug in Cursor (and some VS Code environments) regarding the handling of spaces in arguments on Windows. If arguments contain spaces, they may not be escaped correctly when passed to npx or uv. The workaround is to pass complex values via environment variables rather than command-line arguments.21

## ---

**5\. Platform Analysis: Gemini CLI**

Google's Gemini CLI leverages MCP to enhance its command-line reasoning capabilities. Its configuration model is hierarchical and JSON-based, adhering to Google's structural conventions.

### **5.1 Configuration Architecture**

Gemini CLI searches for settings in a prioritized order:

1. **Project:** .gemini/settings.json (Overrides user/system).  
2. **User:** \~/.gemini/settings.json.  
3. **System:** /etc/gemini-cli/settings.json.22

### **5.2 The "Easy Install" Strategy**

Installation requires the user to edit one of these JSON files. Unlike Claude Code, there isn't a widely cited "single command" to add a server, so documentation must provide the JSON snippet.

**Configuration Schema:**

JSON

{  
  "mcpServers": {  
    "python-reasoner": {  
      "command": "uv",  
      "args": \["run", "server.py"\],  
      "env": {  
        "API\_KEY": "$GEMINI\_API\_KEY"  
      }  
    }  
  }  
}

### **5.3 Environment Variable Handling**

Gemini CLI supports robust variable expansion using shell-like syntax: $VAR\_NAME or ${VAR\_NAME}.22

Key Advantage \- Auto-Loading:  
Significantly, the Gemini CLI automatically searches for and loads .env files from the current working directory and parent directories.24

* **Mechanism:** If a user has a .env file, the CLI loads those variables into its process environment *before* launching MCP servers.  
* **Implication:** This is extremely user-friendly. The Python server (if using os.environ) will inherit these variables automatically without them needing to be explicitly mapped in the env block of settings.json, provided the server process inherits the parent environment (which is standard behavior). However, to be explicit and safe, mapping them via $VAR in the config is recommended.

OAuth Support:  
Gemini CLI is notable for having built-in support for OAuth 2.0 authentication for remote MCP servers using the SSE transport. While the user's request focuses on local environment variables, this capability is relevant if the server were to be deployed remotely.26

## ---

**6\. Platform Analysis: OpenAI Codex (CLI)**

The OpenAI Codex CLI (currently in beta/preview phases) introduces a divergence in configuration standards, utilizing **TOML** instead of JSON. This presents a unique challenge for documentation and standardization.

### **6.1 Configuration Architecture**

The central configuration file is located at \~/.codex/config.toml.11 This file is shared between the Codex CLI and the Codex IDE extension, offering a unified configuration plane.

### **6.2 The "Easy Install" Strategy**

Users can add servers via the CLI, which modifies the TOML file, or by editing the file directly.

**CLI Command:**

Bash

codex mcp add my-server \--env API\_KEY=value \-- uv run server.py

TOML Configuration Schema:  
If editing manually, the syntax is significantly different from the other tools:

Ini, TOML

\[mcp\_servers.my-server\]  
command \= "uv"  
args \= \["run", "server.py"\]  
env \= { "API\_KEY" \= "value" }

### **6.3 Environment Variable Handling**

Codex implements a "Whitelist" security model for environment variables. By default, the MCP server subprocess does *not* inherit the parent's full environment.

The env\_vars Whitelist:  
To pass a variable that exists in the user's shell (e.g., OPENAI\_API\_KEY) to the server, it must be explicitly listed in the env\_vars array in the TOML config.28

Ini, TOML

\[mcp\_servers.my-server\]  
command \= "uv"  
\# Whitelist: Pass these shell variables through to the server  
env\_vars \=

Alternatively, static values can be set in the env dictionary. For "easy installation" relying on secrets, the env\_vars approach is superior as it keeps secrets out of the config file.

Critical Troubleshooting \- Type Strictness:  
Research highlights that Codex is strictly compliant with JSON-RPC types, often more so than other clients. Specifically, it distinguishes rigidly between integer and number.

* **The Issue:** If a Python Pydantic model defines a field as float but the server receives an integer, or vice versa, Codex may reject the tool definition or call.29  
* **Fix:** Python servers targeting Codex should ensure their type definitions are robust (e.g., using Union\[int, float\]) or that the Pydantic schema generation is compatible with strict JSON schema validation.

## ---

**7\. Platform Analysis: GitHub Copilot**

GitHub Copilot's MCP integration is bifurcated into two distinct contexts: **Copilot Chat** (running locally in the IDE) and the **Copilot Coding Agent** (running remotely on GitHub infrastructure). The installation strategy differs fundamentally between the two.

### **7.1 Context A: Copilot Chat (VS Code Extension)**

This context allows a developer to use MCP tools within their local VS Code environment.

* **Configuration:** Managed via mcp.json inside the .vscode directory or global user storage. Users can add servers via the extension UI.  
* **Installation:** Similar to Cursor, the "easy" path is a project-local config.  
* **Env Vars:** VS Code supports ${env:VAR} syntax. However, reliability issues have been reported with variable resolution in some versions.30  
* **Workaround:** For maximum reliability, users should be instructed to launch VS Code from a terminal where the environment variables are already exported, or use a wrapper script (via uv) that loads .env before starting the server.

### **7.2 Context B: Copilot Coding Agent (Repository)**

This context involves the autonomous agent that operates on GitHub.com (e.g., for Pull Request reviews).

* **Configuration:** Requires a file at .github/copilot/mcp.json (or sometimes .github/mcp.json) committed to the repository.31  
* **Constraint:** The Coding Agent runs in a secured, containerized environment. It **cannot** execute arbitrary local commands like uv run from the user's machine. It typically connects to *remote* MCP servers (HTTP/SSE) or utilizes pre-approved actions.  
* **Env Vars:** Secrets **must** be managed via GitHub Actions Secrets. The configuration references them using specific prefixes (e.g., COPILOT\_MCP\_SECRET\_NAME).31

Conclusion for "Easy Install":  
For the Coding Agent, "easy install" is a misnomer for a local Python script. The script must likely be deployed as a service or packaged as a GitHub Action. For the purpose of this report, we focus on the Copilot Chat (local) integration as the primary target for a "newly built Python server," as it aligns with the other local tools.

## ---

**8\. Platform Analysis: Microsoft Copilot (Copilot Studio & M365)**

Microsoft Copilot represents the enterprise tier, integrating with Microsoft 365 data. Its architecture is fundamentally "cloud-first," prioritizing connectors over local subprocesses.

### **8.1 Configuration Architecture**

Integration is managed via **Copilot Studio**, where administrators or developers define "Actions" and "Knowledge Sources." There is no simple local JSON config file for the cloud agent to read.34

### **8.2 The "Developer Mode" Loophole**

To test a local Python MCP server with Microsoft Copilot (e.g., in M365 chat), the user must enable **Developer Mode**.

* **Activation:** Often triggered by typing \-developer on in the Copilot chat interface.36  
* **Transport Requirement:** Unlike Claude or Cursor, Microsoft Copilot generally expects an **SSE (Server-Sent Events)** endpoint. It cannot spawn a local STDIO process because the "brain" is running in the Microsoft cloud, not on the local machine.

### **8.3 The Installation Strategy**

To make the Python server work here, the "easy install" instruction must guide the user to run the server as a web service.

1. **Command:** uv run server.py \--transport sse \--port 8000 (The server code must support this flag).  
2. **Tunneling:** Since the Copilot cloud service needs to reach the user's local machine, a tunnel (like ngrok or dev tunnels) is often required unless using a specific "Local Device" connector feature in Windows.38  
3. **Registration:** The user manually registers the https://.../sse endpoint in the Copilot Studio "Developer" tab.

Env Var Handling:  
Since the user runs the server manually in their terminal (to open the port), the server simply inherits the terminal's environment. export API\_KEY=xyz before running uv works perfectly.

## ---

**9\. Synthesis: The Unified Installation Matrix**

To satisfy the request for the "easiest possible installation" across this diverse ecosystem, the repository's documentation (README.md) should present a consolidated configuration matrix.

**Table 2: Cross-Platform Configuration and Environment Variable Matrix**

| Tool | Config File Location | Installation Command / Config Snippet | Env Variable Syntax | Secret Best Practice |
| :---- | :---- | :---- | :---- | :---- |
| **Claude Code** | CLI (Internal) | claude mcp add name \--env K=V \-- uv run... | \--env K=V (Flag) | Pass via CLI flag; careful with .mcp.json in git. |
| **Cursor** | .cursor/mcp.json | {"command": "uv", "args": \[...\], "env": {"K": "${env:K}"}} | ${env:VAR} | User sets in .env; config references it. |
| **Gemini CLI** | \~/.gemini/settings.json | {"command": "uv",... "env": {"K": "$K"}} | $VAR or ${VAR} | User sets in .env; CLI auto-loads it. |
| **Claude Desktop** | \~/Library/.../config.json | {"command": "/abs/path/uv",... "env": {"K": "VAL"}} | Static strings only | User manually pastes key into JSON. |
| **Codex** | \~/.codex/config.toml | \[mcp\_servers.name\] command="uv" env\_vars=\["K"\] | env\_vars (List) | Whitelist shell vars via env\_vars list. |
| **GitHub Copilot** | .vscode/mcp.json | {"command": "uv",... "env": {"K": "${env:K}"}} | ${env:VAR} | Use uv to load .env context if interpolation fails. |
| **MS Copilot** | Copilot Studio (UI) | Run manually: uv run server.py \--transport sse | Shell Inheritance | Export vars in terminal before running server. |

### **9.1 Recommended Repository Structure**

To support all these tools simultaneously, the GitHub repository should be structured as follows:

my-mcp-server/  
├── server.py \# Entry point (supports STDIO and SSE via flags)  
├── pyproject.toml \# Dependencies (managed by uv)  
├──.env.example \# Template for secrets  
├──.cursor/  
│ └── mcp.json \# Pre-configured for Cursor users  
├──.vscode/  
│ └── mcp.json \# Pre-configured for VS Code/Copilot users  
└── README.md \# Contains the matrix above

### **9.2 The Universal "Run" Code**

The server.py must be written to handle the transport duality. Using a library like fastmcp (Python SDK) simplifies this, as it can auto-detect the transport mode or accept arguments.

Python

\# Conceptual server.py structure  
from mcp.server.fastmcp import FastMCP

mcp \= FastMCP("My Server")

@mcp.tool()  
def my\_tool(arg: str) \-\> str:  
    return f"Processed {arg}"

if \_\_name\_\_ \== "\_\_main\_\_":  
    \# fastmcp handles 'mcp dev', 'run', and transport modes automatically  
    mcp.run()

## **10\. Conclusion**

The distribution of Python MCP servers is currently a task of navigating architectural divergence. While the Model Context Protocol unifies the *capabilities* of AI agents, the *client implementations* vary significantly in how they instantiate and configure these capabilities.

For the developer, the adoption of **uv** is the single most high-impact decision to ensure installability. It bridges the gap between the stateless nature of MCP config (which expects an executable) and the stateful nature of Python environments. By standardizing on uv run commands, the developer effectively neutralizes the "dependency hell" that would otherwise prevent a Python-novice user from installing the server.

However, the handling of environment variables remains the primary friction point. There is no universal syntax for injecting secrets. The most robust strategy is to document the specific syntax for each tool (as detailed in the matrix above) and, where possible, leverage the tool's native ability to load .env files (Cursor, Gemini). For tools with rigid configs like Claude Desktop, the trade-off of hardcoding secrets into the config file must be accepted and clearly documented until the platform matures to support secure secret storage or shell inheritance.

#### **Works cited**

1. Announcing official MCP support for Google services | Google Cloud Blog, accessed January 2, 2026, [https://cloud.google.com/blog/products/ai-machine-learning/announcing-official-mcp-support-for-google-services](https://cloud.google.com/blog/products/ai-machine-learning/announcing-official-mcp-support-for-google-services)  
2. Creating Your First MCP Server: A Hello World Guide | by Gianpiero Andrenacci | AI Bistrot | Dec, 2025, accessed January 2, 2026, [https://medium.com/data-bistrot/creating-your-first-mcp-server-a-hello-world-guide-96ac93db363e](https://medium.com/data-bistrot/creating-your-first-mcp-server-a-hello-world-guide-96ac93db363e)  
3. How to setup MCP with UV in Python the right way\! \- AWS Builder Center, accessed January 2, 2026, [https://builder.aws.com/content/301AFBdz2tMxoTTpsRCZj4QyY6u/how-to-setup-mcp-with-uv-in-python-the-right-way](https://builder.aws.com/content/301AFBdz2tMxoTTpsRCZj4QyY6u/how-to-setup-mcp-with-uv-in-python-the-right-way)  
4. Beginner's Guide to Building and Testing Your First MCP Server with uv and Claude, accessed January 2, 2026, [https://mahendranp.medium.com/beginners-guide-to-building-and-testing-your-first-mcp-server-with-uv-and-claude-3bfc6198212a](https://mahendranp.medium.com/beginners-guide-to-building-and-testing-your-first-mcp-server-with-uv-and-claude-3bfc6198212a)  
5. Build an MCP client \- Model Context Protocol, accessed January 2, 2026, [https://modelcontextprotocol.io/docs/develop/build-client](https://modelcontextprotocol.io/docs/develop/build-client)  
6. uv \- Astral Docs, accessed January 2, 2026, [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)  
7. Getting Started with uv: A Modern Python Environment and Package Manager \- Medium, accessed January 2, 2026, [https://medium.com/@yanxingyang/getting-started-with-uv-a-modern-python-environment-and-package-manager-d9d9af098cca](https://medium.com/@yanxingyang/getting-started-with-uv-a-modern-python-environment-and-package-manager-d9d9af098cca)  
8. astral-sh/uv: An extremely fast Python package and project manager, written in Rust. \- GitHub, accessed January 2, 2026, [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)  
9. MPC Server: mcp dev vs deployed \- Medium, accessed January 2, 2026, [https://medium.com/@paul.d.short/mpc-server-mcp-dev-vs-deployed-d4a892397d2c](https://medium.com/@paul.d.short/mpc-server-mcp-dev-vs-deployed-d4a892397d2c)  
10. Connect Claude Code to tools via MCP, accessed January 2, 2026, [https://code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp)  
11. Model Context Protocol \- OpenAI for developers, accessed January 2, 2026, [https://developers.openai.com/codex/mcp/](https://developers.openai.com/codex/mcp/)  
12. Model Context Protocol (MCP) is now generally available in Microsoft Copilot Studio, accessed January 2, 2026, [https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/model-context-protocol-mcp-is-now-generally-available-in-microsoft-copilot-studio/](https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/model-context-protocol-mcp-is-now-generally-available-in-microsoft-copilot-studio/)  
13. Build an MCP server \- Model Context Protocol, accessed January 2, 2026, [https://modelcontextprotocol.io/docs/develop/build-server](https://modelcontextprotocol.io/docs/develop/build-server)  
14. mcp-server-gemini/docs/claude-desktop-setup.md at main \- GitHub, accessed January 2, 2026, [https://github.com/aliargun/mcp-server-gemini/blob/main/docs/claude-desktop-setup.md](https://github.com/aliargun/mcp-server-gemini/blob/main/docs/claude-desktop-setup.md)  
15. Connect to local MCP servers \- Model Context Protocol, accessed January 2, 2026, [https://modelcontextprotocol.io/docs/develop/connect-local-servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers)  
16. MCP Servers, Claude Desktop and fun with PATHs \- Emmanuel Bernard, accessed January 2, 2026, [https://emmanuelbernard.com/blog/2025/04/07/mcp-servers-and-claude-desktop-path/](https://emmanuelbernard.com/blog/2025/04/07/mcp-servers-and-claude-desktop-path/)  
17. CLI Tool \- Claude Code Subagents & Commands Collection, accessed January 2, 2026, [https://www.buildwithclaude.com/docs/cli](https://www.buildwithclaude.com/docs/cli)  
18. Configuring MCP Tools in Claude Code \- The Better Way \- Scott Spence, accessed January 2, 2026, [https://scottspence.com/posts/configuring-mcp-tools-in-claude-code](https://scottspence.com/posts/configuring-mcp-tools-in-claude-code)  
19. MCP | Cursor Docs, accessed January 2, 2026, [https://cursor.com/docs/cli/mcp](https://cursor.com/docs/cli/mcp)  
20. Model Context Protocol (MCP) | Cursor Docs, accessed January 2, 2026, [https://cursor.com/docs/context/mcp](https://cursor.com/docs/context/mcp)  
21. Can't use/escape spaces or use environment variables in MCP configurations \- Bug Reports, accessed January 2, 2026, [https://forum.cursor.com/t/cant-use-escape-spaces-or-use-environment-variables-in-mcp-configurations/115917](https://forum.cursor.com/t/cant-use-escape-spaces-or-use-environment-variables-in-mcp-configurations/115917)  
22. Gemini CLI configuration, accessed January 2, 2026, [https://geminicli.com/docs/get-started/configuration/](https://geminicli.com/docs/get-started/configuration/)  
23. gemini-cli/docs/cli/configuration.md at main · google-gemini/gemini-cli \- GitHub, accessed January 2, 2026, [https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/configuration.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/configuration.md)  
24. Where are the Gemini CLI config files stored? \- Milvus, accessed January 2, 2026, [https://milvus.io/ai-quick-reference/where-are-the-gemini-cli-config-files-stored](https://milvus.io/ai-quick-reference/where-are-the-gemini-cli-config-files-stored)  
25. Gemini CLI Tutorial Series — Part 3 : Configuration settings via settings.json and .env files | by Romin Irani | Google Cloud \- Medium, accessed January 2, 2026, [https://medium.com/google-cloud/gemini-cli-tutorial-series-part-3-configuration-settings-via-settings-json-and-env-files-669c6ab6fd44](https://medium.com/google-cloud/gemini-cli-tutorial-series-part-3-configuration-settings-via-settings-json-and-env-files-669c6ab6fd44)  
26. MCP servers with the Gemini CLI, accessed January 2, 2026, [https://geminicli.com/docs/tools/mcp-server/](https://geminicli.com/docs/tools/mcp-server/)  
27. Configuring Codex \- OpenAI for developers, accessed January 2, 2026, [https://developers.openai.com/codex/local-config/](https://developers.openai.com/codex/local-config/)  
28. codex/docs/config.md at main · openai/codex \- GitHub, accessed January 2, 2026, [https://github.com/openai/codex/blob/main/docs/config.md](https://github.com/openai/codex/blob/main/docs/config.md)  
29. Codex is not Fully MCP Compliant \- How to Work Around That \- Reddit, accessed January 2, 2026, [https://www.reddit.com/r/mcp/comments/1mn6s4h/codex\_is\_not\_fully\_mcp\_compliant\_how\_to\_work/](https://www.reddit.com/r/mcp/comments/1mn6s4h/codex_is_not_fully_mcp_compliant_how_to_work/)  
30. Support env variables in mcp.json · Issue \#264448 · microsoft/vscode \- GitHub, accessed January 2, 2026, [https://github.com/microsoft/vscode/issues/264448](https://github.com/microsoft/vscode/issues/264448)  
31. Extending GitHub Copilot coding agent with the Model Context Protocol (MCP), accessed January 2, 2026, [https://docs.github.com/copilot/how-tos/agents/copilot-coding-agent/extending-copilot-coding-agent-with-mcp](https://docs.github.com/copilot/how-tos/agents/copilot-coding-agent/extending-copilot-coding-agent-with-mcp)  
32. Extending GitHub Copilot coding agent with the Model Context Protocol (MCP), accessed January 2, 2026, [https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp)  
33. Customizing the development environment for GitHub Copilot coding agent, accessed January 2, 2026, [https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment)  
34. Extend your agent with Model Context Protocol \- Microsoft Copilot Studio, accessed January 2, 2026, [https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-mcp](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-mcp)  
35. Introducing Model Context Protocol (MCP) in Copilot Studio: Simplified Integration with AI Apps and Agents \- Microsoft, accessed January 2, 2026, [https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/introducing-model-context-protocol-mcp-in-copilot-studio-simplified-integration-with-ai-apps-and-agents/](https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/introducing-model-context-protocol-mcp-in-copilot-studio-simplified-integration-with-ai-apps-and-agents/)  
36. Copilot extensibility in the Microsoft 365 ecosystem, accessed January 2, 2026, [https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/ecosystem](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/ecosystem)  
37. Test and debug agents in Microsoft 365 Copilot using Developer Mode, accessed January 2, 2026, [https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/debugging-agents-copilot-studio](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/debugging-agents-copilot-studio)  
38. Set up Standard workflows as MCP servers \- Azure Logic Apps \- Microsoft Learn, accessed January 2, 2026, [https://learn.microsoft.com/en-us/azure/logic-apps/set-up-model-context-protocol-server-standard](https://learn.microsoft.com/en-us/azure/logic-apps/set-up-model-context-protocol-server-standard)