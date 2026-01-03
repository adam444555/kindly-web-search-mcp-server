# **The Comprehensive Engineering Guide to Building, Distributing, and Integrating Model Context Protocol (MCP) Servers in Python**

## **Executive Summary**

The rapid integration of Large Language Models (LLMs) into software engineering workflows has precipitated a fundamental architectural shift. While models possess vast parametric knowledge, they historically lacked a standardized, secure method to access active runtime data—local filesystems, proprietary databases, and live service states. This disconnection, often termed the "context gap," has forced developers to build brittle, one-off integrations for every model provider. The Model Context Protocol (MCP) has emerged as the industry-standard solution to this problem, functioning effectively as a "USB-C port for AI applications".1 By decoupling the intelligence layer (clients like Claude or GitHub Copilot) from the capability layer (servers exposing data and tools), MCP enables a unified ecosystem where a single server implementation can service any compliant AI agent.

This report provides an exhaustive, expert-level technical analysis of building production-grade MCP servers using Python. It moves beyond elementary implementations to explore the full lifecycle of an MCP server: from architectural decisions using the FastMCP framework to rigorous testing strategies with pytest and the MCP Inspector, and finally to secure distribution via the official MCP Registry and GitHub. Special emphasis is placed on "Day 2" operations—authentication, input validation, and continuous integration—addressing the critical requirements for integrating with professional tools like Claude Code, Cursor, and Visual Studio Code.

## ---

**1\. The Model Context Protocol (MCP) Paradigm**

### **1.1 The Context Gap and Protocol Evolution**

Before MCP, integrating an LLM with external data required bespoke implementation of provider-specific APIs (e.g., OpenAI Plugins, Anthropic Tool Use). This created an $N \\times M$ complexity problem: $N$ tools needed to be integrated with $M$ different model providers. MCP solves this by standardizing the protocol layer.3

At its core, MCP is a client-host-server architecture built upon JSON-RPC 2.0. It defines a strict message format for capability negotiation, lifecycle management, and bidirectional communication. The architecture separates concerns distinctively:

* **The Host (Client):** The application where the LLM "lives" (e.g., Claude Desktop, VS Code, Cursor). The Host manages the connection, user authorization, and the prompt context window.  
* **The Server:** A lightweight application that exposes three specific capabilities—Tools, Resources, and Prompts—to the Host.  
* **The Protocol:** The distinct set of JSON-RPC messages exchanged over a transport layer (Stdio or HTTP/SSE) that allows the Host to discover and utilize the Server's capabilities.

### **1.2 Core Primitives: Tools, Resources, and Prompts**

Understanding these primitives is essential for designing effective servers. They map to different interaction patterns between the user, the model, and the data.

#### **1.2.1 Tools: Executable Actions**

Tools are the functional arms of the agent. They represent executable code that can perform computations, modify system state, or retrieve dynamic data based on arguments provided by the model.3

* **Mechanism:** The server advertises a tool name (e.g., query\_database), a description, and a JSON Schema defining the required arguments. The LLM uses this schema to generate a structured call.  
* **Use Cases:** API requests (GET/POST), database mutations, complex mathematical calculations, or system commands (e.g., git commit).  
* **Risk Profile:** High. Because tools can modify state (side effects), they typically require user approval in the Host interface before execution.5

#### **1.2.2 Resources: Contextual Data**

Resources represent read-only data sources. Unlike tools, which require arguments to "act," resources are passive data streams identified by a URI.1

* **Mechanism:** A server exposes a list of resource templates (e.g., file://logs/{service\_name}). The Host can read these resources directly to load content into the context window.  
* **Use Cases:** File contents, system logs, API configuration data, or code repository listings.  
* **Distinction:** Think of Resources as "GET" requests that populate the prompt context, while Tools are "function calls" that the model actively decides to invoke.

#### **1.2.3 Prompts: Interaction Templates**

Prompts allow the server to define reusable interaction patterns. They are pre-written templates that help users accomplish specific tasks with the server's tools.2

* **Mechanism:** A server exposes a prompt (e.g., "Analyze Error Logs"). When selected by the user, the server returns a set of messages (System, User) that structure the conversation, potentially pre-loading relevant Resources.  
* **Use Cases:** Standardizing code review criteria, incident response checklists, or bug report formatting.

### **1.3 Transport Mechanisms: Stdio vs. SSE**

The protocol is transport-agnostic, but two primary transports dominate the ecosystem. Choosing the right one is the first critical architectural decision.7

| Feature | Stdio Transport | SSE (Server-Sent Events) Transport |
| :---- | :---- | :---- |
| **Mechanism** | Standard Input/Output streams over a subprocess. | HTTP Post (Client-\>Server) and SSE (Server-\>Client). |
| **Architecture** | Local Process. The Client spawns the Server directly. | Client-Server Network. The Server runs independently. |
| **Latency** | Ultra-low (In-memory/Pipe). | Low to Medium (Network overhead). |
| **Security** | Inherits user permissions; relies on OS process isolation. | Requires Authentication (OAuth/API Key); uses network security (TLS). |
| **Primary Use Case** | **Local Development Tools.** Integrating with Claude Desktop, VS Code, or CLI agents on a single machine. | **Enterprise/Cloud Deployment.** Running shared servers in Docker/K8s, or connecting to remote services. |

Critical Engineering Constraint:  
For Stdio-based servers, logging to stdout is strictly prohibited.5 The standard output channel is reserved exclusively for JSON-RPC protocol messages. Any unformatted text (like a print("debug") statement) sent to stdout will corrupt the message stream, causing the client to terminate the connection immediately. All logging must be directed to stderr.

## ---

**2\. Best Implementation Technologies: The Python Stack**

The user's request explicitly asks for "Best implementation technologies." While the official mcp SDK exists, the industry best practice has coalesced around the **FastMCP** framework for its ergonomic design and production readiness.

### **2.1 The Case for FastMCP**

The official Python SDK (mcp) provides the low-level building blocks: managing connection lifecycles, parsing messages, and handling types. However, using it directly requires significant boilerplate code.

**FastMCP** 2 acts as a high-level framework, analogous to what FastAPI is for REST APIs.

1. **Decorator-Based:** It allows developers to expose functions as tools using @mcp.tool(), handling the registration automatically.  
2. **Pydantic Integration:** It leverages Python type hints and Pydantic models to automatically generate the JSON Schema required by the MCP specification. This ensures that the documentation seen by the LLM acts as the source of truth for the validation logic.  
3. **Async Native:** Built on asyncio and httpx, it supports high-concurrency workloads—essential when an agent might request multiple long-running operations simultaneously.2  
4. **Transport Abstraction:** It abstracts the transport layer, allowing the same server code to run over Stdio or SSE with a simple flag change.

### **2.2 Dependency Management: The uv Standard**

For modern Python development, and specifically for MCP servers, **uv** is the recommended package manager.10

* **Speed:** uv is significantly faster than pip, which is crucial for the "ephemeral" execution environments often used by MCP clients.  
* **Project Structure:** uv init creates a standardized project layout compliant with modern Python packaging standards (pyproject.toml).  
* **Execution:** Clients like Claude Desktop can be configured to run servers using uv run, which creates a virtual environment on-the-fly, ensuring that the server's dependencies do not conflict with the system Python or other servers.

### **2.3 Environment Setup**

A production-grade environment for MCP development requires:

* **Python 3.10+:** FastMCP relies on modern type hinting features (e.g., X | Y syntax).  
* **uv:** For dependency resolution and virtual environment management.  
* **Git:** For version control and sharing.

## ---

**3\. Building a Production-Grade MCP Server**

To demonstrate best practices, we will detail the construction of a robust "DevOps Dashboard" server. This server will provide tools to check system health, resources to read logs, and prompts to report incidents.

### **3.1 Project Structure**

A flat file structure is insufficient for serious development. We recommend a modular architecture 10:

devops-mcp/  
├── pyproject.toml \# Dependencies (fastmcp, pydantic, httpx)  
├── uv.lock \# Exact versions for reproducibility  
├── README.md \# Critical for discovery and LLM context  
├── Dockerfile \# For containerized distribution  
├── src/  
│ ├── init.py  
│ ├── server.py \# Application Entrypoint  
│ ├── auth.py \# Authentication Middleware  
│ ├── tools/  
│ │ ├── init.py  
│ │ └── system.py \# Tool definitions  
│ └── resources/  
│ ├── init.py  
│ └── logs.py \# Resource definitions  
└── tests/  
├── init.py  
└── test\_system.py \# Pytest suite

### **3.2 Implementation: The Server Entrypoint**

In src/server.py, we initialize the FastMCP application.

Python

import sys  
import logging  
from fastmcp import FastMCP  
from src.tools.system import register\_system\_tools  
from src.resources.logs import register\_log\_resources

\# Configure logging to stderr to preserve Stdio transport integrity  
logging.basicConfig(  
    level=logging.INFO,  
    format\='%(asctime)s \- %(name)s \- %(levelname)s \- %(message)s',  
    stream=sys.stderr  \# CRITICAL: Do not use stdout  
)  
logger \= logging.getLogger("devops-server")

\# Initialize FastMCP with metadata  
mcp \= FastMCP(  
    "DevOps-Dashboard",  
    description="A server for monitoring system health and logs.",  
    dependencies=\["httpx", "pydantic"\]  
)

\# Register modular components  
register\_system\_tools(mcp)  
register\_log\_resources(mcp)

if \_\_name\_\_ \== "\_\_main\_\_":  
    \# Default to Stdio, but allow SSE via CLI args if needed  
    mcp.run()

### **3.3 Implementation: Tools with Complex Schemas**

Tools must be resilient. We use Pydantic models to enforce strict input validation.10

In src/tools/system.py:

Python

from fastmcp import FastMCP, Context  
from pydantic import BaseModel, Field  
import asyncio  
import httpx

class HealthCheckRequest(BaseModel):  
    service\_url: str \= Field(  
       ...,   
        description="The full URL of the service to check.",  
        pattern=r"^https?://"  
    )  
    timeout: int \= Field(  
        5,   
        ge=1,   
        le=30,   
        description="Timeout in seconds (1-30)."  
    )

def register\_system\_tools(mcp: FastMCP):  
      
    @mcp.tool()  
    async def check\_service\_health(req: HealthCheckRequest, ctx: Context) \-\> str:  
        """  
        Pings a service URL to check if it is reachable and measures latency.  
        """  
        ctx.info(f"Starting health check for {req.service\_url}")  
          
        \# Report progress for long-running tasks  
        await ctx.report\_progress(1, 3)  
          
        async with httpx.AsyncClient() as client:  
            try:  
                await ctx.report\_progress(2, 3)  
                resp \= await client.get(req.service\_url, timeout=req.timeout)  
                resp.raise\_for\_status()  
                  
                result \= {  
                    "status": "UP",  
                    "status\_code": resp.status\_code,  
                    "latency\_ms": resp.elapsed.total\_seconds() \* 1000  
                }  
                return str(result)  
                  
            except httpx.RequestError as e:  
                ctx.error(f"Request failed: {str(e)}")  
                return f"Error: Service unreachable \- {str(e)}"  
            finally:  
                await ctx.report\_progress(3, 3)

**Architectural Insight:** Note the use of ctx: Context.3 This allows the tool to send logs (ctx.info) and progress updates (ctx.report\_progress) back to the client UI. This feedback loop is essential for user trust, especially when the LLM is performing opaque operations.

### **3.4 Implementation: Dynamic Resources**

Resources allow the LLM to "read" data without executing a tool.

In src/resources/logs.py:

Python

from fastmcp import FastMCP

def register\_log\_resources(mcp: FastMCP):  
      
    \# Define a resource template with a parameter  
    @mcp.resource("logs://app/{service\_name}")  
    def get\_service\_logs(service\_name: str) \-\> str:  
        """  
        Retrieves the last 50 lines of logs for a specific service.  
        """  
        \# In a real app, this might read from a file or query ElasticSearch  
        fake\_logs \= \[  
            f"\[INFO\] Service {service\_name} started.",  
            f" Memory usage high in {service\_name}.",  
            f"\[INFO\] Heartbeat received."  
        \]  
        return "\\n".join(fake\_logs)

## ---

**4\. Quality Assurance: Testing the MCP Server**

The user requested specific guidance on "How to test an MCP server." Testing in the MCP context is unique because the "consumer" is a probabilistic model. Our testing strategy must cover three layers: Unit Logic, Schema/Protocol Compliance, and Interaction/Vibe Check.

### **4.1 Unit Testing with pytest and FastMCP**

Traditional mocking is often messy with network protocols. FastMCP provides a Client testing utility that simulates a connection in-memory.8

**Setup:**

Bash

uv add \--dev pytest pytest-asyncio

**Test Implementation (tests/test\_system.py):**

Python

import pytest  
from fastmcp import Client  
from src.server import mcp

@pytest.fixture  
async def client():  
    \# The Client context manager handles the lifecycle startup/shutdown  
    async with Client(mcp) as c:  
        yield c

@pytest.mark.asyncio  
async def test\_health\_check\_tool\_success(client):  
    """Verify the tool accepts valid input and returns a string."""  
    \# Simulate the JSON-RPC call structure  
    result \= await client.call\_tool(  
        "check\_service\_health",  
        arguments={"service\_url": "https://google.com", "timeout": 2}  
    )  
      
    \# Assert structural integrity of the response  
    assert result is not None  
    assert result.content.type \== "text"  
    assert "status" in result.content.text

@pytest.mark.asyncio  
async def test\_validation\_failure(client):  
    """Verify that invalid URLs are rejected by Pydantic."""  
    with pytest.raises(Exception):  
        await client.call\_tool(  
            "check\_service\_health",  
            arguments={"service\_url": "not-a-url"}  
        )

**Insight:** This testing pattern is critical. It validates not just the business logic (the HTTP request), but the *interface contract*. By asserting that invalid inputs raise exceptions, we prevent the LLM from confusedly retrying malformed requests.

### **4.2 The MCP Inspector**

While pytest validates logic, it cannot validate the "Developer Experience" for the LLM. The **MCP Inspector** is an interactive web tool that connects to your server and allows you to browse tools and resources as if you were the AI.4

**Workflow:**

1. **Install:** npm install \-g @modelcontextprotocol/inspector (Requires Node.js).  
2. **Run:**  
   Bash  
   npx @modelcontextprotocol/inspector uv run src/server.py

3. **Validate:**  
   * **Description Rendering:** Do the docstrings look helpful? Are arguments clearly labeled?  
   * **Execution:** Manually run the tools in the UI. Check the "Logs" tab in the Inspector to see if your ctx.info logs appear correctly.  
   * **Protocol Errors:** The Inspector will highlight malformed JSON-RPC messages immediately.

### **4.3 Automated Compliance Auditing**

For enterprise servers, it is recommended to use the **Ansible Collection for MCP Audit**.14 This allows you to write a playbook that queries the server capabilities in a CI/CD pipeline, ensuring that a deployed server explicitly exposes the required tools and version information before being promoted to production.

## ---

**5\. Integrating with Clients**

The utility of an MCP server is defined by its integration with Host applications. The user specifically asked about **Claude Code**, **Copilot**, and others. Each has unique configuration requirements.

### **5.1 Claude Code (CLI) Integration**

Claude Code is an autonomous coding agent that runs in the terminal. It uses a specific CLI syntax to register servers.15

Command Syntax:  
The command requires a double-dash separator (--) to distinguish between arguments for the Claude CLI and arguments for the server execution.  
claude mcp add \[server\_name\]\[scope\_flag\] \-- \[server\_command\]

**Example: Adding the DevOps Server**

Bash

claude mcp add devops-dashboard \--scope project \-- uv run src/server.py

**Scope Nuances:**

* \--scope project: Creates a .claude/mcp.json file in the *current directory*. This configuration is specific to the repository. This is best practice for sharing tools required for a specific codebase (e.g., a linting server).  
* \--scope user: Adds the server to the global user configuration. This is best for utility servers (e.g., a "Calendar" or "Spotify" server) that you want available in every session.

### **5.2 Claude Desktop Integration**

Claude Desktop requires manual editing of a configuration file.

**File Location:**

* macOS: \~/Library/Application Support/Claude/claude\_desktop\_config.json  
* Windows: %APPDATA%\\Claude\\claude\_desktop\_config.json

**Configuration Block:**

JSON

{  
  "mcpServers": {  
    "devops-dashboard": {  
      "command": "uv",  
      "args": \[  
        "run",  
        "--with",  
        "httpx",  
        "--with",  
        "pydantic",  
        "/absolute/path/to/project/src/server.py"  
      \],  
      "env": {  
        "API\_KEY": "secret\_value"  
      }  
    }  
  }  
}

**Important:** You must use **absolute paths** for the script location, as Claude Desktop's working directory is not guaranteed. Using uv run handles the environment setup automatically.

### **5.3 GitHub Copilot and VS Code**

Visual Studio Code (and by extension GitHub Copilot) supports MCP via a workspace configuration file.7

Configuration:  
Create a file at .vscode/mcp.json in your project root:

JSON

{  
  "mcpServers": {  
    "devops-dashboard": {  
      "command": "uv",  
      "args": \["run", "src/server.py"\]  
    }  
  }  
}

**Activation:**

1. Ensure the setting "chat.mcp.discovery.enabled": true is active in VS Code.  
2. In Copilot Chat, switch to "Agent Mode" (if available) or simply ask a question that requires the tool. Copilot will discover the tools defined in mcp.json and invoke them to answer user queries (e.g., "Check the health of the API").

### **5.4 Cursor Integration**

Cursor provides a dedicated UI for MCP management.19

**Steps:**

1. Open **Cursor Settings** (Cmd/Ctrl \+ Shift \+ J).  
2. Navigate to **Features** \> **MCP**.  
3. Click **Add New MCP Server**.  
4. **Name:** DevOps.  
5. **Type:** Stdio.  
6. **Command:** uv run src/server.py.

## ---

**6\. Distribution: Sharing on GitHub and the Registry**

To fulfill the user's requirement on "How to share it... such that people can use it," we must address the distribution lifecycle. A raw Python script is hard to share; a packaged MCP server is easy.

### **6.1 GitHub Repository Best Practices**

Your repository is the primary entry point. To ensure "people can use it," adhere to these standards 21:

1. **Naming:** Prefix your repo with mcp-server- (e.g., mcp-server-devops).  
2. **README.md:** This file is parsed by humans *and* LLMs. It must include:  
   * **Components Table:** A clear table listing every Tool, Resource, and Prompt.  
   * **Configuration Snippets:** Provide copy-paste JSON blocks for claude\_desktop\_config.json.  
   * **Docker Instructions:** If applicable.  
3. **License:** Use permissive licenses (MIT/Apache 2.0) to encourage adoption in the ecosystem.

### **6.2 The Official MCP Registry**

The **Model Context Protocol Registry** (registry.modelcontextprotocol.io) is the centralized catalog.23 Publishing here ensures your server is discoverable via mcp-publisher tools and future "App Store" interfaces in clients.

**Publishing Workflow:**

1. **Prerequisite:** Your package must be published to **PyPI** (Python Package Index). The registry does not host code; it points to existing packages.  
   Bash  
   uv build  
   uv publish

2. **Install Publisher CLI:**  
   Bash  
   brew install mcp-publisher

3. Initialize Manifest:  
   In your repo root:  
   Bash  
   mcp-publisher init

   This generates a server.json file. You must configure your **namespace**.  
   * **GitHub Namespace:** io.github.username.server-name (e.g., io.github.jdoe.devops-dashboard).  
   * **Company Namespace:** com.company.server-name (Requires DNS verification).  
4. Edit server.json:  
   Ensure the packages section points to your PyPI package:  
   JSON  
   "packages":

5. **Authenticate & Publish:**  
   Bash  
   mcp-publisher login github  
   mcp-publisher publish

### **6.3 Dockerizing for Distribution**

Containerization is the ultimate way to share servers "such that people can use it" without fighting Python environment issues.25

**Dockerfile:**

Dockerfile

\# Use a slim image to reduce size  
FROM python:3.10\-slim

\# Install uv  
COPY \--from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app  
COPY..

\# Install dependencies into system python (safe inside container)  
RUN uv pip install \--system \-r requirements.txt

\# Entrypoint  
ENTRYPOINT \["python", "src/server.py"\]

Usage:  
Users can now run your server without installing Python:  
docker run \-i \--rm my-mcp-server  
(The \-i flag is critical for Stdio communication).

## ---

**7\. Advanced Security and Authentication**

Connecting an LLM to your infrastructure introduces "Agentic Risks." An insecure MCP server is effectively a remote control for your systems.

### **7.1 Input Validation and Least Privilege**

* **Path Traversal:** If a tool accepts a file path, never trust the input. The LLM might hallucinate or be tricked into requesting /etc/shadow. Use pydantic validators to ensure paths are within a specific sandbox directory.  
* **Read-Only by Default:** Unless the server explicitly needs to write data, ensure all filesystem/database operations are read-only.  
* **Human-in-the-Loop:** While managed by the client, server developers should design tools to be atomic. Avoid generic "execute\_shell\_command" tools; instead, build "list\_files" or "read\_log". This gives the human user context to approve the specific action.

### **7.2 Remote Authentication with SSE**

When deploying an MCP server remotely (e.g., on AWS Lambda or Cloud Run), you cannot rely on Stdio. You must use the SSE transport, which is exposed over HTTP. This endpoint **must** be authenticated.27

**FastMCP Authentication Middleware Example:**

Python

from fastmcp import FastMCP  
from fastapi import Request, HTTPException, Depends  
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

\# Define security scheme  
security \= HTTPBearer()

async def verify\_api\_key(credentials: HTTPAuthorizationCredentials \= Depends(security)):  
    """Validates the Bearer token against a secret."""  
    if credentials.credentials\!= "production-secret-key-123":  
        raise HTTPException(status\_code=401, detail="Invalid API Key")  
    return credentials.credentials

\# Initialize server  
mcp \= FastMCP("Secure-Remote-Server")

\# Apply dependency to all tools in the server  
@mcp.tool(dependencies=)  
def secure\_operation(data: str):  
    return f"Processed {data} securely."

if \_\_name\_\_ \== "\_\_main\_\_":  
    \# Run in SSE mode  
    mcp.run(transport="sse")

Client Configuration for Remote Auth:  
When adding this server to Claude Desktop, headers must be configured:

JSON

"remote-server": {  
  "url": "https://api.myserver.com/sse",  
  "headers": {  
    "Authorization": "Bearer production-secret-key-123"  
  }  
}

## ---

**8\. Conclusion**

Building an MCP server involves more than writing a few Python functions. It requires a disciplined approach to architecture, utilizing **FastMCP** for efficient implementation, **Pydantic** for robust schema validation, and **uv** for reliable dependency management. By adhering to the distribution standards of the **MCP Registry** and implementing rigorous **testing via pytest and Inspector**, developers can create high-quality, secure integrations.

As the ecosystem matures, the MCP server will become the fundamental unit of AI interoperability. The steps outlined in this report—from local Stdio development to secure, dockerized remote deployment—provide the blueprint for building the next generation of context-aware AI applications.

### **Summary Checklist**

* \[ \] **Implementation:** Used FastMCP with Pydantic models.  
* \[ \] **Transport:** Stdio for local, SSE for remote.  
* \[ \] **Testing:** Unit tests with client.call\_tool() pass; Inspector validates UI.  
* \[ \] **Config:** Generated correct JSON for Claude/VS Code.  
* \[ \] **Distribution:** Published to PyPI and registered via mcp-publisher.  
* \[ \] **Security:** Auth middleware implemented for remote endpoints.

### ---

**References**

* **Protocol & SDK:** 3  
* **FastMCP Framework:** 2  
* **Testing:** 8  
* **Registry & Publishing:** 23  
* **Client Integration:** 15  
* **Security:** 27

*(End of Report)*

#### **Works cited**

1. Creating Your First MCP Server: A Hello World Guide | by Gianpiero Andrenacci | AI Bistrot | Dec, 2025, accessed January 2, 2026, [https://medium.com/data-bistrot/creating-your-first-mcp-server-a-hello-world-guide-96ac93db363e](https://medium.com/data-bistrot/creating-your-first-mcp-server-a-hello-world-guide-96ac93db363e)  
2. fastmcp \- PyPI, accessed January 2, 2026, [https://pypi.org/project/fastmcp/](https://pypi.org/project/fastmcp/)  
3. MCP Python SDK \- PyPI, accessed January 2, 2026, [https://pypi.org/project/mcp/1.7.1/](https://pypi.org/project/mcp/1.7.1/)  
4. Model Context Protocol \- GitHub, accessed January 2, 2026, [https://github.com/modelcontextprotocol](https://github.com/modelcontextprotocol)  
5. Build an MCP server \- Model Context Protocol, accessed January 2, 2026, [https://modelcontextprotocol.io/docs/develop/build-server](https://modelcontextprotocol.io/docs/develop/build-server)  
6. Model Context Protocol (MCP): Understanding security risks and controls \- Red Hat, accessed January 2, 2026, [https://www.redhat.com/en/blog/model-context-protocol-mcp-understanding-security-risks-and-controls](https://www.redhat.com/en/blog/model-context-protocol-mcp-understanding-security-risks-and-controls)  
7. Use MCP servers in VS Code, accessed January 2, 2026, [https://code.visualstudio.com/docs/copilot/customization/mcp-servers](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)  
8. jlowin/fastmcp: The fast, Pythonic way to build MCP servers and clients \- GitHub, accessed January 2, 2026, [https://github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)  
9. Welcome to FastMCP 2.0\! \- FastMCP, accessed January 2, 2026, [https://gofastmcp.com/](https://gofastmcp.com/)  
10. How to Build a Python MCP Server to Consult a Knowledge Base \- Auth0, accessed January 2, 2026, [https://auth0.com/blog/build-python-mcp-server-for-blog-search/](https://auth0.com/blog/build-python-mcp-server-for-blog-search/)  
11. How to find, install, and manage MCP servers with the GitHub MCP Registry, accessed January 2, 2026, [https://github.blog/ai-and-ml/generative-ai/how-to-find-install-and-manage-mcp-servers-with-the-github-mcp-registry/](https://github.blog/ai-and-ml/generative-ai/how-to-find-install-and-manage-mcp-servers-with-the-github-mcp-registry/)  
12. Testing your FastMCP Server, accessed January 2, 2026, [https://gofastmcp.com/patterns/testing](https://gofastmcp.com/patterns/testing)  
13. MCP Inspector \- Model Context Protocol, accessed January 2, 2026, [https://modelcontextprotocol.io/docs/tools/inspector](https://modelcontextprotocol.io/docs/tools/inspector)  
14. Building the Ansible Collection for MCP Server Testing | by Tosin Akinosho | Nov, 2025, accessed January 2, 2026, [https://medium.com/@tcij1013/building-the-ansible-collection-for-mcp-server-testing-da00f576a2b7](https://medium.com/@tcij1013/building-the-ansible-collection-for-mcp-server-testing-da00f576a2b7)  
15. Claude Code (CLI) | docs \- Trunk Platform, accessed January 2, 2026, [https://docs.trunk.io/ci-autopilot/overview/use-mcp-server/configuration/claude-code-cli](https://docs.trunk.io/ci-autopilot/overview/use-mcp-server/configuration/claude-code-cli)  
16. CLI reference \- Claude Code Docs, accessed January 2, 2026, [https://code.claude.com/docs/en/cli-reference](https://code.claude.com/docs/en/cli-reference)  
17. Connect Claude Code to tools via MCP, accessed January 2, 2026, [https://code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp)  
18. Extending GitHub Copilot Chat with Model Context Protocol (MCP) servers, accessed January 2, 2026, [https://docs.github.com/copilot/customizing-copilot/using-model-context-protocol/extending-copilot-chat-with-mcp](https://docs.github.com/copilot/customizing-copilot/using-model-context-protocol/extending-copilot-chat-with-mcp)  
19. Enabling MCP in Cursor: Step-by-Step Guide | Natoma, accessed January 2, 2026, [https://natoma.ai/blog/how-to-enabling-mcp-in-cursor](https://natoma.ai/blog/how-to-enabling-mcp-in-cursor)  
20. Building MCP Tools and Running Them in Cursor Editor \- DEV Community, accessed January 2, 2026, [https://dev.to/lovestaco/building-mcp-tools-and-running-them-in-cursor-editor-3ono](https://dev.to/lovestaco/building-mcp-tools-and-running-them-in-cursor-editor-3ono)  
21. microsoft/mcp-for-beginners: This open-source curriculum introduces the fundamentals of Model Context Protocol (MCP) through real-world, cross-language examples in .NET, Java, TypeScript, JavaScript, Rust and Python. Designed for developers, it focuses on practical techniques for building modular, scalable, \- GitHub, accessed January 2, 2026, [https://github.com/microsoft/mcp-for-beginners](https://github.com/microsoft/mcp-for-beginners)  
22. awesome-mcp-servers/README.md at main \- GitHub, accessed January 2, 2026, [https://github.com/punkpeye/awesome-mcp-servers/blob/main/README.md](https://github.com/punkpeye/awesome-mcp-servers/blob/main/README.md)  
23. How to Publish Your MCP Server to the Official Registry: A Complete Guide | by Ali Ibrahim, accessed January 2, 2026, [https://techwithibrahim.medium.com/how-to-publish-your-mcp-server-to-the-official-registry-a-complete-guide-3622f0edceef](https://techwithibrahim.medium.com/how-to-publish-your-mcp-server-to-the-official-registry-a-complete-guide-3622f0edceef)  
24. Publish your Gram server on the MCP Registry \- Speakeasy, accessed January 2, 2026, [https://www.speakeasy.com/docs/gram/host-mcp/publish-gram-server-mcp-registry](https://www.speakeasy.com/docs/gram/host-mcp/publish-gram-server-mcp-registry)  
25. 5 Best Practices for Building MCP Servers \- Snyk, accessed January 2, 2026, [https://snyk.io/articles/5-best-practices-for-building-mcp-servers/](https://snyk.io/articles/5-best-practices-for-building-mcp-servers/)  
26. MCP Catalog \- Docker Docs, accessed January 2, 2026, [https://docs.docker.com/ai/mcp-catalog-and-toolkit/catalog/](https://docs.docker.com/ai/mcp-catalog-and-toolkit/catalog/)  
27. FastMCP: Streamline with Pangea AuthN Integration, accessed January 2, 2026, [https://pangea.cloud/blog/integrating-pangea-authn-into-fastmcp/](https://pangea.cloud/blog/integrating-pangea-authn-into-fastmcp/)  
28. Implementing Authentication in a Remote MCP Server with Python and FastMCP, accessed January 2, 2026, [https://gelembjuk.com/blog/post/authentication-remote-mcp-server-python/](https://gelembjuk.com/blog/post/authentication-remote-mcp-server-python/)  
29. The official Python SDK for Model Context Protocol servers and clients \- GitHub, accessed January 2, 2026, [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)  
30. Publish Your MCP Server, accessed January 2, 2026, [https://modelcontextprotocol.info/tools/registry/publishing/](https://modelcontextprotocol.info/tools/registry/publishing/)  
31. Security Best Practices \- Model Context Protocol, accessed January 2, 2026, [https://modelcontextprotocol.io/specification/draft/basic/security\_best\_practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)