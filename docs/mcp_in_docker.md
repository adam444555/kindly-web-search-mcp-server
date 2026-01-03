Below is a practical “Docker support” playbook for a Python MCP server, plus how to wire that Dockerized server into each client you listed.

## 1) Pick the Docker model you want to support (recommend: support both)

### A) **Docker as a local STDIO server (client spawns `docker run …`)**

Best when: users want a zero-install experience (no Python, no venv), and the server needs local access (files, git repo, etc.).

**Key requirements**

* Your container must run the MCP server over **stdin/stdout** (stdio transport).
* Users (or the client config) must run Docker with **`-i`** so stdin stays open (this is the common gotcha). Example configs for Gemini CLI explicitly use `docker run -i --rm …` for MCP stdio. ([s1m0n38.github.io][1])
* **Never log MCP protocol messages to stdout**. Log to **stderr** only, or you’ll corrupt the JSON-RPC stream.

### B) **Docker as a remote “Streamable HTTP” MCP server (`http://…/mcp`)**

Best when: users don’t want Docker spawned per-session, you want easier enterprise rollout, or you want Copilot Studio compatibility.

Clients like VS Code/Copilot support both **local stdio** and **Streamable HTTP** transports. ([Visual Studio Code][2])
Claude Code recommends HTTP for remote MCP servers and shows `claude mcp add --transport http …` usage. ([Claude Code][3])
Codex supports **stdio** and **Streamable HTTP** (with bearer/OAuth options). ([OpenAI Developers][4])

---

## 2) What to add to your GitHub repo (so Docker “just works”)

### A) `Dockerfile` (thin, safe defaults)

* `PYTHONUNBUFFERED=1` (reduces buffering issues in stdio mode)
* run as non-root
* set an entrypoint that launches your server in stdio by default

```dockerfile
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install your package (adjust to your layout)
COPY pyproject.toml README.md /app/
COPY src/ /app/src/
RUN pip install --no-cache-dir .

# Create a non-root user
RUN useradd -u 10001 -m appuser
USER 10001

# Important: entrypoint prints MCP protocol on stdout; log to stderr in your code
ENTRYPOINT ["your-mcp-server"]
CMD ["--stdio"]
```

### B) `compose.yaml` (two profiles: stdio and http)

Use Compose mainly for **remote HTTP** mode (it’s awkward for stdio, since stdio is typically launched by the client).

```yaml
services:
  mcp:
    image: ghcr.io/you/your-mcp-server:latest
    environment:
      # Document required env vars here (values provided by user at runtime)
      REQUIRED_API_KEY: ${REQUIRED_API_KEY}
      REQUIRED_BASE_URL: ${REQUIRED_BASE_URL}
    ports:
      - "127.0.0.1:8787:8787"
    command: ["--http", "--host", "0.0.0.0", "--port", "8787"]
```

### C) A clear env-var story

* Provide `.env.example` listing **all required variables**, with comments.
* In docs: recommend `--env-file .env` for local runs (and add `.env` to `.gitignore`).
* For clients that support it, prefer **client-side `env` blocks** over embedding secrets in args.

### D) Release/publishing

* Publish images to **GHCR** with tags (`:latest`, `:vX.Y.Z`) and ideally **multi-arch** (linux/amd64 + linux/arm64) so macOS Apple Silicon users don’t suffer.

---

## 3) “Works everywhere” option: Docker MCP Toolkit / Gateway (highly recommended)

If you want the **smoothest UX across multiple MCP clients**, Docker’s MCP Gateway acts as a centralized proxy that:

* runs MCP servers in **isolated containers**
* manages lifecycle, routing, and **credential injection**
* avoids per-app manual config (you connect clients to the Gateway once) ([Docker Documentation][5])

Docker’s docs even show the flow:

1. enable a server, 2) connect a client (e.g. Claude Code), 3) run the gateway. ([Docker Documentation][5])

This is the closest thing today to “one install path for everyone”.

---

## 4) Client-specific: how to run your Dockerized MCP server

### Claude Code

Claude Code supports:

* remote HTTP (`claude mcp add --transport http …`)
* local stdio (`claude mcp add --transport stdio … -- <command>`) ([Claude Code][3])

**Docker stdio pattern**

```bash
claude mcp add --transport stdio myserver \
  --env REQUIRED_API_KEY=... \
  -- docker run -i --rm \
     -e REQUIRED_API_KEY \
     ghcr.io/you/your-mcp-server:latest
```

(Here `-e REQUIRED_API_KEY` tells Docker to pass through the env var from the spawned process environment into the container.)

**Docker HTTP pattern**

* Run your container with `-p 8787:8787` and configure as HTTP transport (recommended for remote services). ([Claude Code][3])

---

### Codex (CLI + IDE extension)

Codex MCP supports **stdio and Streamable HTTP**, and explicitly supports env vars in configuration. ([OpenAI Developers][4])

**Docker stdio pattern**

```bash
codex mcp add myserver \
  --env REQUIRED_API_KEY=... \
  -- docker run -i --rm -e REQUIRED_API_KEY ghcr.io/you/your-mcp-server:latest
```

**Docker HTTP pattern**
Run the container as a service, then configure Codex to use Streamable HTTP (use bearer/OAuth if you expose it beyond localhost). ([OpenAI Developers][4])

---

### Gemini CLI

Gemini CLI’s docs include a **Docker-based MCP server config** using:

* `command: "docker"`
* `args: ["run","-i","--rm","-e","API_KEY",…]`
* `env: { "API_KEY": "…" }` ([s1m0n38.github.io][1])

So your “official” snippet can mirror that pattern:

```json
{
  "mcpServers": {
    "yourServer": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "REQUIRED_API_KEY", "ghcr.io/you/your-mcp-server:latest"],
      "env": {
        "REQUIRED_API_KEY": "put-real-value-here-or-reference-your-token"
      }
    }
  }
}
```

Gemini CLI also supports HTTP-based MCP servers via `httpUrl`. ([s1m0n38.github.io][1])

---

### Cursor

Cursor supports MCP servers configured via command/args and an `env` section (common best practice is: **use `env`, don’t try to interpolate secrets inside args**). ([cursor.fan][6])

**Docker stdio pattern**

* Use `command: docker`
* Put secrets in Cursor’s `env`
* Pass-through into Docker with `-e VAR` (NOT `${VAR}` inside JSON)

Why: people often mistakenly put `"${GITHUB_TOKEN}"`-style strings into JSON; Docker receives the literal string, not the expanded token. ([Teddy’s Corner][7])

---

### Claude Desktop

Claude Desktop can launch MCP servers from config; Docker Desktop’s MCP Toolkit also automates connecting MCP servers to Claude Desktop. ([Docker][8])

**Best UX**: recommend users install via **Docker MCP Toolkit** (it can write the Claude Desktop config automatically in many setups). ([Docker Documentation][5])

---

### GitHub Copilot (VS Code)

VS Code (Copilot) supports MCP transports:

* `stdio`
* `http` (Streamable HTTP)
* legacy `sse` ([Visual Studio Code][2])

**Docker stdio pattern in `.vscode/mcp.json`**

* `command` must be `"docker"`
* put `docker run …` into `args` (don’t put the whole thing as a single string) — this mistake shows up frequently. ([GitHub][9])

Also: Docker’s MCP Toolkit integrates with VS Code Copilot Agent Mode, which can simplify setup and security posture. ([Docker][10])

---

### Microsoft Copilot (Copilot Studio)

Microsoft Copilot Studio has MCP support (for tools). ([Microsoft][11])
For Copilot Studio, you generally want the **remote HTTP** deployment model:

* run your container on Azure Container Apps / AKS / any HTTPS endpoint
* configure the MCP connection in Copilot Studio
* store env vars as **platform secrets/app settings** (not in client configs)

Microsoft’s guidance is explicitly about extending agents by connecting to tools from an MCP server. ([Microsoft Learn][12])

---

## 5) Docker-specific “don’t get burned” checklist (high-impact)

* **STDIO mode**

  * Require `docker run -i …` (stdin open) ([s1m0n38.github.io][1])
  * No protocol output on stdout except MCP JSON-RPC; log to stderr.
  * Consider `--init` for clean signal handling (`docker run --init …`).

* **Env vars**

  * Prefer **pass-through**: client sets env, docker args use `-e VAR` (no string interpolation pitfalls).
  * Offer `--env-file` docs for manual CLI usage.

* **Local filesystem access**

  * If your MCP server needs the user’s repo/files, document a volume mount pattern (e.g. `-v "$PWD:/workspace"`), and how your server locates that path.

* **Security**

  * Run as non-root; keep image minimal.
  * If you recommend Docker MCP Gateway, highlight that it runs servers in containers with restricted privileges and centralized credential handling. ([Docker Documentation][5])

---

If you share your repo link, I can draft a ready-to-paste **“Docker installation”** section for your README (including copy/paste configs for each client, matching your actual server name/entrypoint/env var names).

[1]: https://s1m0n38.github.io/gemini-cli/tools/mcp-server/ "MCP servers with the Gemini CLI - Gemini CLI"
[2]: https://code.visualstudio.com/docs/copilot/customization/mcp-servers "Use MCP servers in VS Code"
[3]: https://code.claude.com/docs/en/mcp "Connect Claude Code to tools via MCP - Claude Code Docs"
[4]: https://developers.openai.com/codex/mcp "Model Context Protocol"
[5]: https://docs.docker.com/ai/mcp-catalog-and-toolkit/mcp-gateway/ "MCP Gateway | Docker Docs
"
[6]: https://cursor.fan/tutorial/HowTo/how-to-config-mcp-server-with-an-env-parameter-in-cursor/?utm_source=chatgpt.com "How to config MCP server with an env parameter in Cursor"
[7]: https://asbjborg.github.io/posts/how-to-actually-setup-github-mcp-server-with-docker-in-cursor/?utm_source=chatgpt.com "How to Actually Setup GitHub MCP Server with Docker in Cursor (The ..."
[8]: https://www.docker.com/blog/connect-mcp-servers-to-claude-desktop-with-mcp-toolkit/?utm_source=chatgpt.com "Connect MCP Servers to Claude Desktop with Docker MCP Toolkit | Docker"
[9]: https://github.com/github/github-mcp-server/issues/898?utm_source=chatgpt.com "VS Code always tries to run docker run ... github-mcp-server and fails ..."
[10]: https://www.docker.com/blog/mcp-toolkit-and-vs-code-copilot-agent/?utm_source=chatgpt.com "How Docker MCP Toolkit Works with VS Code Copilot Agent Mode"
[11]: https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/introducing-model-context-protocol-mcp-in-copilot-studio-simplified-integration-with-ai-apps-and-agents/?utm_source=chatgpt.com "Introducing Model Context Protocol (MCP) in Copilot Studio: Simplified ..."
[12]: https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-mcp?utm_source=chatgpt.com "Extend your agent with Model Context Protocol - Microsoft Copilot ..."
