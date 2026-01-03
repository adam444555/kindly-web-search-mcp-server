Below is a practical, product-by-product “make it painless to install” playbook for a **Python MCP server** that **requires environment variables**.

I’ll assume your server can run as a **local stdio** MCP server (most common for Python) and optionally as a **remote HTTP (streamable)** server (best for cloud / enterprise).

---

## What to do in your repo (so every client setup is easy)

### 1) Ship a single, reliable command users can run

Most MCP clients ultimately want a `command` + `args`.

**Best practice for Python packaging**

* Publish to PyPI and expose a console entry point like:

  * `your-mcp-server` (recommended)
  * also support `python -m your_pkg` (nice fallback)
* Keep startup fast and deterministic (tool discovery happens at startup in most clients).

**Why:** every client here can be configured around a single executable command (Claude Code, Codex, Gemini CLI, VS Code/Copilot, Claude Desktop; Cursor too). See how these clients expect `command`/`args` patterns in their config formats. ([Visual Studio Code][1])

### 2) Make env-var configuration explicit, validated, and friendly

Because env vars are central to your server:

* **Document them as a contract**

  * list every required env var
  * specify format + example
  * state which are secrets
* **Fail fast with a great error**

  * on startup, check required env vars
  * print *exactly* which variables are missing and how to set them
  * exit non-zero
* Include a `.env.example` (never real secrets) and copy-paste install snippets per client.

### 3) Provide “env file” support where clients have it

Some clients can load a `.env` directly (or have their own secure input handling). For example, VS Code supports `envFile` in `mcp.json` and explicitly recommends avoiding hardcoding secrets. ([Visual Studio Code][1])

**Repo suggestion**

```
examples/
  vscode/.vscode/mcp.json
  claude-code/.mcp.json
  codex/config.toml.snippet
  gemini/settings.json.snippet
  claude-desktop/claude_desktop_config.json.snippet
  cursor/.cursor/mcp.json
```

### 4) Offer two distribution options (local stdio + optional remote HTTP)

* **Local stdio** is the common denominator (works everywhere that supports local servers).
* **Remote streamable HTTP** is increasingly supported (VS Code, Codex, Gemini CLI, Claude Code) and avoids local Python runtime issues. ([Visual Studio Code][1])

---

# Product-specific requirements & best practices

## 1) Claude Code (Anthropic)

Claude Code supports **HTTP (recommended), SSE (deprecated), and local stdio** MCP servers, and you can set env vars via CLI flags or JSON config. ([Claude Code][2])

### Best UX approach

* Provide a one-liner using their CLI:

  * `claude mcp add --transport stdio ... --env ... -- your-mcp-server ...`
* Also provide a project-checked-in `.mcp.json` template for teams.

### Install example (CLI)

```bash
claude mcp add --transport stdio yourserver \
  --env YOUR_API_KEY="$YOUR_API_KEY" \
  --env YOUR_BASE_URL="$YOUR_BASE_URL" \
  -- your-mcp-server --stdio
```

Claude Code clearly documents the `--env` pattern and how `--` separates Claude flags from server args. ([Claude Code][2])

### Team setup example (`.mcp.json` in repo root)

```json
{
  "mcpServers": {
    "yourserver": {
      "command": "your-mcp-server",
      "args": ["--stdio"],
      "env": {
        "YOUR_API_KEY": "${YOUR_API_KEY}",
        "YOUR_BASE_URL": "${YOUR_BASE_URL}"
      }
    }
  }
}
```

Claude Code supports env var expansion in `.mcp.json` and different “scopes” (local/project/user). ([Claude Code][2])

**Extra:** call out Windows quirks if your users run Windows; Claude Code notes Windows wrappers for some command styles. ([Claude Code][2])

---

## 2) Codex (OpenAI CLI + IDE extension)

Codex supports MCP in both the CLI and IDE extension, stores config in `~/.codex/config.toml`, and supports env vars for stdio servers. ([OpenAI Developers][3])

### Best UX approach

* Provide:

  * `codex mcp add ... --env ... -- <command>`
  * plus a `config.toml` snippet for advanced users
* Prefer **forwarding existing env vars** rather than requiring users to paste secrets into config files.

### Install example (CLI)

```bash
codex mcp add yourserver \
  --env YOUR_API_KEY="$YOUR_API_KEY" \
  --env YOUR_BASE_URL="$YOUR_BASE_URL" \
  -- your-mcp-server --stdio
```

Codex documents this `codex mcp add ... --env ... -- <stdio command>` flow. ([OpenAI Developers][3])

### `~/.codex/config.toml` example (stdio)

```toml
[mcp_servers.yourserver]
command = "your-mcp-server"
args = ["--stdio"]

[mcp_servers.yourserver.env]
YOUR_BASE_URL = "https://api.example.com"

# Prefer allowing/forwarding from the user's environment for secrets:
# (so users set it in their shell, keychain tooling, or CI secrets)
env_vars = ["YOUR_API_KEY"]
```

Codex documents `env`, `env_vars`, and other server options. ([OpenAI Developers][3])

---

## 3) Gemini CLI

Gemini CLI configures MCP servers in `settings.json` under `mcpServers`, supports stdio/SSE/HTTP streaming, and supports an `env` object where values can reference existing environment variables (`$VAR` / `${VAR}`). ([Gemini CLI][4])

### Best UX approach

* Provide a `settings.json` snippet.
* Encourage users to set secrets in their shell environment and reference them.

### `settings.json` example (stdio)

```json
{
  "mcpServers": {
    "yourserver": {
      "command": "your-mcp-server",
      "args": ["--stdio"],
      "env": {
        "YOUR_API_KEY": "$YOUR_API_KEY",
        "YOUR_BASE_URL": "https://api.example.com"
      },
      "timeout": 30000,
      "trust": false
    }
  }
}
```

This matches Gemini CLI’s documented server properties (`command`, `args`, `env`, `timeout`, `trust`, etc.). ([Gemini CLI][4])

---

## 4) Cursor

Cursor supports MCP server configuration via a project config file (commonly cited as `.cursor/mcp.json`) and users expect Claude/VS Code–style `command` + `args` + `env`. Cursor documentation and community notes cover this setup pattern. ([Cursor - Community Forum][5])

### Best UX approach (today)

* Provide a `.cursor/mcp.json` template.
* If Cursor’s current build has limitations around env handling, offer a wrapper script approach (below).

### `.cursor/mcp.json` example

```json
{
  "mcpServers": {
    "yourserver": {
      "command": "your-mcp-server",
      "args": ["--stdio"],
      "env": {
        "YOUR_API_KEY": "${YOUR_API_KEY}",
        "YOUR_BASE_URL": "${YOUR_BASE_URL}"
      }
    }
  }
}
```

### If env injection is limited: wrapper script fallback

Ship `scripts/run-yourserver.sh` and `scripts/run-yourserver.ps1` that load `.env` then exec the server, and tell Cursor to run the script as the `command`.

Example (Cursor uses the script as the command):

```json
{
  "mcpServers": {
    "yourserver": {
      "command": "bash",
      "args": ["scripts/run-yourserver.sh"]
    }
  }
}
```

---

## 5) Claude Desktop

Claude Desktop uses `claude_desktop_config.json` with `mcpServers` entries including `command`, `args`, and optional `env`. Paths are documented for macOS and Windows, and users typically must restart the app after editing. ([DeepWiki][6])

### Best UX approach

* Provide a copy-paste config snippet for:

  * macOS path: `~/Library/Application Support/Claude/claude_desktop_config.json`
  * Windows path: `%APPDATA%\Claude\claude_desktop_config.json` ([DeepWiki][6])
* Mention logs location for debugging and the “hammer” tool icon expectation. ([DeepWiki][6])

### Config snippet

```json
{
  "mcpServers": {
    "yourserver": {
      "command": "your-mcp-server",
      "args": ["--stdio"],
      "env": {
        "YOUR_API_KEY": "REPLACE_ME",
        "YOUR_BASE_URL": "https://api.example.com"
      }
    }
  }
}
```

### “Best possible” Claude Desktop UX: ship an MCPB (Desktop Extension)

If you want true “single-click install” in Claude Desktop, Anthropic supports **MCPB bundles** (`.mcpb`) that install like extensions. ([Claude Help Center][7])

Important caveat: Anthropic currently *strongly recommends Node.js for MCPB* because Claude Desktop ships with a Node runtime, so bundling Python is non-trivial and can add friction. ([Claude Help Center][7])
**Practical approach for a Python server:** keep Python for CLI/other clients, and optionally provide a small Node wrapper MCPB that calls your Python binary (or points to a remote HTTP server).

---

## 6) GitHub Copilot (in VS Code)

For “GitHub Copilot” in practice, your main integration surface is **VS Code’s MCP support** (Copilot is the chat/agent UI). VS Code supports stdio + HTTP (streamable) + legacy SSE MCP servers and has a formal `mcp.json` format with `env`, `envFile`, and secure `inputs`. ([Visual Studio Code][1])

GitHub also documents a shared `mcp.json` approach in the repo and an MCP server registry. ([GitHub Docs][8])

### Best UX approach

* Provide a `.vscode/mcp.json` template in your repo
* Encourage either:

  * `envFile` (simple), or
  * `inputs` for secrets (best UX + avoids committing secrets)

### `.vscode/mcp.json` example (recommended)

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "your-api-key",
      "description": "YourServer API Key",
      "password": true
    }
  ],
  "servers": {
    "yourserver": {
      "type": "stdio",
      "command": "your-mcp-server",
      "args": ["--stdio"],
      "env": {
        "YOUR_API_KEY": "${input:your-api-key}",
        "YOUR_BASE_URL": "https://api.example.com"
      },
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

This matches VS Code’s documented schema (`servers`, optional `inputs`, `env`, `envFile`) and guidance to avoid hardcoding secrets. ([Visual Studio Code][1])

**Bonus UX win:** VS Code can autodiscover MCP server configurations from other apps like Claude Desktop if enabled. ([Visual Studio Code][1])

---

## 7) Microsoft Copilot

This depends on what you mean by “Microsoft Copilot”:

### A) Copilot in VS Code (most common “dev tool” meaning)

Treat it exactly like the GitHub Copilot section above: **VS Code MCP configuration is the integration point.** ([Visual Studio Code][1])

### B) Copilot Studio / Microsoft 365 Copilot extensibility

Microsoft has announced MCP support in Copilot Studio as a way to connect agents to tools/actions. ([Microsoft][9])
This is typically **not** “install a local server”; it’s “publish an endpoint / connector” that Copilot Studio can call. In that case:

* Prefer a **remote streamable HTTP MCP server**
* Implement OAuth / token-based auth (Gemini CLI and Codex both support OAuth flows for remote MCP servers; Codex explicitly documents OAuth login for servers that support it). ([Gemini CLI][4])
* Provide an Azure-hosted deployment option + clear admin docs.

---

# A concrete “gold standard” UX checklist (what I’d ensure)

### Server behavior

* ✅ `your-mcp-server --stdio` starts a stdio MCP server and never prints junk to stdout (only MCP protocol).
* ✅ On missing env vars, print a single, clear error to stderr and exit non-zero.
* ✅ Provide `your-mcp-server --print-env` (or `--doctor`) to list required env vars and example values.

### Secrets & configuration

* ✅ `.env.example` in repo root
* ✅ Recommend `envFile` where supported (VS Code), and “reference existing shell env” where supported (Gemini CLI) ([Visual Studio Code][1])
* ✅ Never ask users to paste secrets into version-controlled JSON.

### Copy/paste snippets per client

* ✅ Claude Code: `claude mcp add ... --env ... -- your-mcp-server` ([Claude Code][2])
* ✅ Codex: `codex mcp add ... --env ... -- your-mcp-server` + `config.toml` snippet ([OpenAI Developers][3])
* ✅ Gemini CLI: `settings.json` snippet with `$YOUR_API_KEY` references ([Gemini CLI][4])
* ✅ Claude Desktop: config file snippet + paths + restart/logs info ([DeepWiki][6])
* ✅ VS Code (GitHub Copilot / Microsoft Copilot): `.vscode/mcp.json` with `inputs` + `envFile` ([Visual Studio Code][1])
* ✅ Cursor: `.cursor/mcp.json` template + wrapper-script fallback ([Cursor - Community Forum][5])

---

If you share your repo link (or just your package name + how your server starts), I can turn the snippets above into **ready-to-commit files** in the exact paths each product expects, plus a README section per tool with copy/paste commands.

[1]: https://code.visualstudio.com/docs/copilot/customization/mcp-servers "Use MCP servers in VS Code"
[2]: https://code.claude.com/docs/en/mcp "Connect Claude Code to tools via MCP - Claude Code Docs"
[3]: https://developers.openai.com/codex/mcp "Model Context Protocol"
[4]: https://geminicli.com/docs/tools/mcp-server/ "MCP servers with the Gemini CLI | Gemini CLI"
[5]: https://forum.cursor.com/t/resolve-local-environment-variables-in-mcp-server-definitions/79639?utm_source=chatgpt.com "Resolve local environment variables in MCP server definitions"
[6]: https://deepwiki.com/modelcontextprotocol/docs/4.3-user-guide-for-claude-desktop "User Guide for Claude Desktop | modelcontextprotocol/docs | DeepWiki"
[7]: https://support.claude.com/en/articles/12922929-building-desktop-extensions-with-mcpb "Building Desktop Extensions with MCPB | Claude Help Center"
[8]: https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/extend-copilot-chat-with-mcp "Extending GitHub Copilot Chat with Model Context Protocol (MCP) servers - GitHub Docs"
[9]: https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/introducing-model-context-protocol-mcp-in-copilot-studio-simplified-integration-with-ai-apps-and-agents/?utm_source=chatgpt.com "Introducing Model Context Protocol (MCP) in Copilot Studio: Simplified ..."
