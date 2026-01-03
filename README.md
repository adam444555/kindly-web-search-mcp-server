# Kindly MCP Server: Web Search + Robust Content Retrieval

This repository contains a Python MCP server focused on **web search + high-quality content retrieval** for LLM agents.

Core idea:
- Use **Serper** (default when configured) or **Tavily** for search results (title/link/snippet).
- For any URL, retrieve **LLM-ready Markdown** using a robust pipeline:
  - Prefer **source APIs** when available (StackExchange / GitHub Issues / Wikipedia / arXiv).
  - Fall back to a **universal HTML loader** (headless browser) for other sites.

## MCP Tools

### `web_search(query, num_results=3)`
Searches the web and returns the top results, always including `page_content` (Markdown) for each result (best-effort) using the same pipeline as `get_content`.

Search providers (at least one required):
- Provide `SERPER_API_KEY` and/or `TAVILY_API_KEY`.
- If both are set, Serper is used by default and Tavily may be used as a fallback if Serper fails.

**Output shape**
```json
{
  "results": [
    {
      "title": "Example",
      "link": "https://example.com",
      "snippet": "Preview text…",
      "page_content": "# … (Markdown) …"
    }
  ]
}
```

### `get_content(url)`
Fetches a single URL and returns best-effort Markdown using the same content-resolution pipeline as `web_search(...)`.

**Output shape**
```json
{
  "url": "https://example.com",
  "page_content": "# … (Markdown) …"
}
```

## Content Resolution Pipeline (How `page_content` Is Produced)

`content.resolver.resolve_page_content_markdown()` attempts these stages in order:
1. **StackExchange (StackOverflow + StackExchange network)** via StackExchange API.
2. **GitHub Issues** via GitHub GraphQL API.
3. **Wikipedia** via MediaWiki Action API (`parse`).
4. **arXiv** via arXiv Atom API + **PDF → Markdown** (PDF-first, in-memory).
5. **Universal HTML loader** fallback via headless `nodriver` (subprocess) → HTML → Markdown.

Important notes:
- The universal HTML loader intentionally **skips obvious PDFs**. Generic PDF support is not implemented yet.
- arXiv is handled as PDF (by design).
- All retrieval is **best-effort**; anti-bot measures, paywalls, or rate limits may prevent full extraction.

## Output Limits (Defaults)

To avoid “context bombs”, content is capped per source:
- StackExchange: `STACKEXCHANGE_MAX_CHARS` default `20000`
- GitHub Issues: `GITHUB_MAX_CHARS` default `20000`
- Wikipedia: `WIKIPEDIA_MAX_CHARS` default `50000`
- arXiv: `ARXIV_MAX_CHARS` default `50000`
- arXiv page cap: `ARXIV_MAX_PAGES` default `30`

When truncated, the Markdown includes a `…(truncated)` marker (and/or a truncation note).

## Configuration (Environment Variables)

This server expects environment variables to be provided by the runtime (IDE run configuration, shell export, or container env). The application code **does not auto-load** a local `.env` file.

### Required
- `SERPER_API_KEY` or `TAVILY_API_KEY`: at least one search provider API key must be set.
  - If both are set, Serper is used by default and Tavily is used as a fallback if Serper fails.
  - If only one is set, that provider is used.
  - Get it from Serper or Tavily: create an account and generate an API key.

### Required (System Dependency)
- A **Chromium-based browser** is required for the universal HTML loader (`nodriver`) used by `get_content()` and by `web_search(...)` for most non-API sources.
  - `uv` / `pip` can install Python dependencies, but **cannot install system browsers** (Chrome/Chromium/Edge/Brave). Users must install a browser separately, or run via Docker.
  - If nodriver can’t auto-detect a browser, set `KINDLY_BROWSER_EXECUTABLE_PATH` (or one of the fallbacks) to the full path of the browser binary.
    - Resolution order: `KINDLY_BROWSER_EXECUTABLE_PATH` → `BROWSER_EXECUTABLE_PATH` → `CHROME_BIN` → `CHROME_PATH` → nodriver auto-detect.
  - WSL note: install the **Linux** browser inside WSL (a Windows Chrome install is not visible as a Linux binary).

### Optional (Recommended)
- `GITHUB_TOKEN`: GitHub Personal Access Token used to retrieve GitHub Issue threads via GitHub APIs.
  - Create it in GitHub → Settings → Developer settings → Personal access tokens.
  - For public repos, a **read-only token** is highly recommended: it enables richer `get_content()` / `web_search(...)` results for GitHub Issues pages. It is not mandatory, but without it GitHub Issues URLs may fall back to generic HTML extraction and produce a poorer representation (missing full thread context).
  - For classic tokens: `public_repo` is usually enough for public repositories. For private repos: `repo` (or equivalent fine-grained read permissions).
- `WIKIPEDIA_USER_AGENT`: Wikimedia asks API clients to use a descriptive User-Agent (ideally with contact info).
- `ARXIV_USER_AGENT`: User-Agent string for arXiv API + PDF requests.

### Optional (Tuning)
- `LOG_LEVEL` (default `WARNING`): logging verbosity. Logs go to stderr in stdio mode (stdout is reserved for MCP).
- `GITHUB_MAX_COMMENTS` (default `50`): max issue comments to fetch.
- `GITHUB_MAX_CHARS` (default `20000`): max Markdown characters returned for a GitHub issue thread.
- `STACKEXCHANGE_KEY`: optional StackExchange API key (higher quotas).
- `STACKEXCHANGE_FILTER`: StackExchange API filter (default `withbody`).
- `STACKEXCHANGE_MAX_CHARS` (default `20000`): max Markdown characters returned for a StackExchange thread.
- `WIKIPEDIA_MAX_CHARS` (default `50000`): max Markdown characters returned for a Wikipedia article.
- `ARXIV_MAX_CHARS` (default `50000`): max Markdown characters returned for an arXiv paper render.
- `ARXIV_MAX_PAGES` (default `30`): max PDF pages processed for arXiv.
- `KINDLY_HTML_TOTAL_TIMEOUT_SECONDS` (default `20`, clamped `1–300`): total timeout for a single universal HTML fetch (nodriver worker subprocess).
- `KINDLY_NODRIVER_RETRY_ATTEMPTS` (default `3`, clamped `1–5`): nodriver start/connect retry attempts.
- `KINDLY_NODRIVER_RETRY_BACKOFF_SECONDS` (default `0.5`, clamped `0–10`): base backoff between retries.
- `KINDLY_NODRIVER_SNAP_BACKOFF_MULTIPLIER` (default `3.0`, clamped `1–20`): extra backoff multiplier for snap Chromium cold starts.
- `KINDLY_NODRIVER_SANDBOX` (default `0`): set to `1` to enable Chrome sandbox (may break in WSL/Docker).
- `MCP_ALLOW_TTY_STDIO` (default `0`): set to `1` to allow `--stdio` when stdin is a TTY.

## Installation

This project is a standard Python package. It exposes a console script and can also be run via `python -m ...`.

### Option A: `pip`
```bash
pip install .
```

For editable/dev installs:
```bash
pip install -e ".[dev]"
```

### Option B: `uv` (fast, zero-friction)
If you use `uv`, you can run without activating a virtualenv:
```bash
# When launched by an MCP client (stdio):
uv run -m kindly_web_search_mcp_server --stdio

# For manual testing (Streamable HTTP):
uv run -m kindly_web_search_mcp_server --http --host 127.0.0.1 --port 8000
```

### Option C: `uvx` (run from Git, no local install)
Install `uv` / `uvx` (Astral) if you don’t have it yet:
```bash
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Recommended (runs the server entrypoint directly):
```bash
uvx --from git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server mcp-web-search --stdio
```

You can pin to a branch/tag/commit:
```bash
uvx --from git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server@v0.0.1 mcp-web-search --stdio
```

### Environment variables
This server expects environment variables to be set by your runtime (IDE, shell, CI, container).

- Copy `.env.example` into your secret manager / IDE run config values (do not commit real secrets). This repo does not auto-load `.env`.
- Required: `SERPER_API_KEY` or `TAVILY_API_KEY`
- Recommended: `GITHUB_TOKEN`, `WIKIPEDIA_USER_AGENT`, `ARXIV_USER_AGENT`

## Running the Server

An entrypoint is provided via `pyproject.toml`:
- `mcp-web-search` → `kindly_web_search_mcp_server.server:main` (**recommended**)
- `kindly-web-search` → `kindly_web_search_mcp_server.server:main` (alias)
- `mcp-server` → `kindly_web_search_mcp_server.server:main` (generic name; may conflict)
- `kindly-web-search-mcp-server` → `kindly_web_search_mcp_server.cli:main` (wrapper; supports `start-mcp-server --context ...`)

Note: `--stdio` is meant to be launched by an MCP client. If you run it directly in a terminal and press Enter, the
server will try to parse your input as JSON-RPC and log errors. For interactive/manual runs, prefer `--http`.

Examples:
```bash
mcp-web-search --stdio
```

Streamable HTTP (useful for gateways / remote deployments):
```bash
mcp-web-search --http --host 0.0.0.0 --port 8000
```

Security note: binding to `0.0.0.0` exposes the server to your network. Prefer `--host 127.0.0.1` for local-only use.

Module form (handy in some environments):
```bash
python -m kindly_web_search_mcp_server --stdio
```

## Client Installation (Claude / Codex / Gemini / Cursor / Copilot)

This server supports both:
- **Local stdio** (most common): clients launch a local command and talk over stdin/stdout.
- **Streamable HTTP** (recommended for remote/container): clients connect to a URL.

Important: in **stdio** mode, stdout is reserved for the MCP protocol. This repo avoids printing on stdout during tool execution.

Note: the command you configure must be executable in the environment your client runs in. If you installed this server
into a virtualenv, prefer using an **absolute path** to the virtualenv executable (Claude Code does not run MCP servers
from your project directory, so relative paths often break).

Note on env vars in config files: different clients support different placeholder syntaxes and secret-handling mechanisms:
- **Claude Code**: `.mcp.json` supports environment variable expansion like `${VAR}` and `${VAR:-default}`.
- **Cursor**: `.cursor/mcp.json` supports `${env:VAR}` interpolation (and can also load from an `envFile`).
- **VS Code / GitHub Copilot / Microsoft Copilot**: `.vscode/mcp.json` supports `${input:...}` variables (prompts on first run) and `envFile`.
- **Gemini CLI**: `.gemini/settings.json` supports `$VAR` and `${VAR}` expansion.
- **Codex**: `~/.codex/config.toml` does not do string interpolation; prefer `env_vars = ["NAME", ...]` to forward variables from your environment.
- **Claude Desktop**: `claude_desktop_config.json` uses literal values; avoid hardcoding secrets in a repo.

### Claude Code

Prereq (WSL/Linux): install into a virtualenv so the executable exists.

If you used `uv`, it will typically create `.venv/` automatically; in that case the executable will be at:
- `$(pwd)/.venv/bin/mcp-web-search`

If you prefer a dedicated virtualenv for agents/automation in this repo, use `.venv-codex/`:
```bash
python -m venv .venv-codex
.venv-codex/bin/python -m pip install -U pip
.venv-codex/bin/python -m pip install -e .
```
Note: `.venv-codex/` is intended for Linux/WSL automation; use `.venv/` for typical local development.

CLI install (stdio):
```bash
# WARNING: `--env KEY="$VALUE"` expands in your shell; values may end up in shell history/process listings.
claude mcp add --transport stdio kindly-web-search \
  --env SERPER_API_KEY="$SERPER_API_KEY" \
  --env TAVILY_API_KEY="$TAVILY_API_KEY" \
  --env GITHUB_TOKEN="$GITHUB_TOKEN" \
  --env KINDLY_BROWSER_EXECUTABLE_PATH="$KINDLY_BROWSER_EXECUTABLE_PATH" \
  -- "$(pwd)/.venv/bin/mcp-web-search" --stdio

# If you used `.venv-codex/` instead of `.venv/`, use:
#   -- "$(pwd)/.venv-codex/bin/mcp-web-search" --stdio
```

Tip: the `--env KEY="$VALUE"` syntax expands the variable in your shell before passing it to the command, so the actual value may appear in shell history and process listings. If you prefer config-based secrets, use `.mcp.json` with `${VAR}` expansion and set the vars in your environment.

No local install (run from Git via `uvx`):
```bash
# WARNING: `--env KEY="$VALUE"` expands in your shell; values may end up in shell history/process listings.
claude mcp add --transport stdio kindly-web-search \
  --env SERPER_API_KEY="$SERPER_API_KEY" \
  --env TAVILY_API_KEY="$TAVILY_API_KEY" \
  --env GITHUB_TOKEN="$GITHUB_TOKEN" \
  --env KINDLY_BROWSER_EXECUTABLE_PATH="$KINDLY_BROWSER_EXECUTABLE_PATH" \
  -- uvx --from git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server \
    mcp-web-search --stdio
```

Project config (`.mcp.json` in repo root):
```json
{
  "mcpServers": {
    "kindly-web-search": {
      "command": "/ABS/PATH/TO/REPO/.venv/bin/mcp-web-search",
      "args": ["--stdio"],
      "env": {
        "SERPER_API_KEY": "${SERPER_API_KEY}",
        "TAVILY_API_KEY": "${TAVILY_API_KEY}",
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "KINDLY_BROWSER_EXECUTABLE_PATH": "${KINDLY_BROWSER_EXECUTABLE_PATH}"
      }
    }
  }
}
```

### Codex (CLI / IDE extension)

Codex can run this server either from a local virtualenv (traditional install) or directly from Git via `uvx`.

#### Option A: virtualenv install
Prereq (WSL/Linux): install into a virtualenv so the executable exists.

If you used `uv`, it will typically create `.venv/` automatically; in that case the executable will be at:
- `$(pwd)/.venv/bin/mcp-web-search`

If you prefer a dedicated virtualenv for agents/automation in this repo, use `.venv-codex/`:
```bash
python -m venv .venv-codex
.venv-codex/bin/python -m pip install -U pip
.venv-codex/bin/python -m pip install -e .
```
Note: `.venv-codex/` is intended for Linux/WSL automation; use `.venv/` for typical local development.

CLI install (stdio):
```bash
# WARNING: `--env KEY="$VALUE"` expands in your shell; values may end up in shell history/process listings.
codex mcp add kindly-web-search \
  --env SERPER_API_KEY="$SERPER_API_KEY" \
  --env TAVILY_API_KEY="$TAVILY_API_KEY" \
  --env GITHUB_TOKEN="$GITHUB_TOKEN" \
  --env KINDLY_BROWSER_EXECUTABLE_PATH="$KINDLY_BROWSER_EXECUTABLE_PATH" \
  -- "$(pwd)/.venv/bin/mcp-web-search" --stdio

# If you used `.venv-codex/` instead of `.venv/`, use:
#   -- "$(pwd)/.venv-codex/bin/mcp-web-search" --stdio
```

Tip: for Codex, prefer `~/.codex/config.toml` with `env_vars = ["NAME", ...]` so values stay in your environment and out of config files/command history.

Manual config (`~/.codex/config.toml`):
```toml
[mcp_servers.kindly-web-search]
command = "/ABS/PATH/TO/REPO/.venv/bin/mcp-web-search"
args = ["--stdio"]

# Prefer keeping secrets out of config files:
env_vars = ["SERPER_API_KEY", "TAVILY_API_KEY", "GITHUB_TOKEN"]
#
# Optional: add "KINDLY_BROWSER_EXECUTABLE_PATH" if browser auto-detection fails.
#
# If you only use Tavily, you can omit `SERPER_API_KEY` from the list.
```

#### Option B: `uvx` from Git (no local install)
Recommended (direct server entrypoint; simplest):

CLI install (stdio):
```bash
# WARNING: `--env KEY="$VALUE"` expands in your shell; values may end up in shell history/process listings.
codex mcp add kindly-web-search \
  --env SERPER_API_KEY="$SERPER_API_KEY" \
  --env TAVILY_API_KEY="$TAVILY_API_KEY" \
  --env GITHUB_TOKEN="$GITHUB_TOKEN" \
  --env KINDLY_BROWSER_EXECUTABLE_PATH="$KINDLY_BROWSER_EXECUTABLE_PATH" \
  -- uvx --from git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server \
    mcp-web-search --stdio
```

Alternative (wrapper with `--context` flag):
```bash
# WARNING: `--env KEY="$VALUE"` expands in your shell; values may end up in shell history/process listings.
codex mcp add kindly-web-search \
  --env SERPER_API_KEY="$SERPER_API_KEY" \
  --env TAVILY_API_KEY="$TAVILY_API_KEY" \
  --env GITHUB_TOKEN="$GITHUB_TOKEN" \
  --env KINDLY_BROWSER_EXECUTABLE_PATH="$KINDLY_BROWSER_EXECUTABLE_PATH" \
  -- uvx --from git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server \
    kindly-web-search-mcp-server start-mcp-server --context codex
```

Manual config (`~/.codex/config.toml`):
```toml
[mcp_servers.kindly-web-search]
command = "uvx"
args = [
  "--from",
  "git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server",
  "mcp-web-search",
  "--stdio"
]
startup_timeout_sec = 60.0

# Prefer keeping secrets out of config files:
env_vars = ["SERPER_API_KEY", "TAVILY_API_KEY", "GITHUB_TOKEN"]
#
# Optional: add "KINDLY_BROWSER_EXECUTABLE_PATH" if browser auto-detection fails.
```

Note: the wrapper command is equivalent to `mcp-web-search --stdio` but sets `KINDLY_MCP_CONTEXT` from `--context` (currently informational / compatibility-only).

### Gemini CLI

Gemini uses JSON config under `mcpServers` (project `.gemini/settings.json` or user `~/.gemini/settings.json`).
String values can reference environment variables using `$VAR_NAME` or `${VAR_NAME}`.

```json
{
  "mcpServers": {
    "kindly-web-search": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server",
        "mcp-web-search",
        "--stdio"
      ],
      "env": {
        "SERPER_API_KEY": "$SERPER_API_KEY",
        "TAVILY_API_KEY": "$TAVILY_API_KEY",
        "GITHUB_TOKEN": "$GITHUB_TOKEN",
        "KINDLY_BROWSER_EXECUTABLE_PATH": "$KINDLY_BROWSER_EXECUTABLE_PATH"
      }
    }
  }
}
```

### Cursor

Project config (commonly `.cursor/mcp.json`):
Note: Cursor requires `"type": "stdio"` for stdio-based servers.
```json
{
  "mcpServers": {
    "kindly-web-search": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server",
        "mcp-web-search",
        "--stdio"
      ],
      "env": {
        "SERPER_API_KEY": "${env:SERPER_API_KEY}",
        "TAVILY_API_KEY": "${env:TAVILY_API_KEY}",
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}",
        "KINDLY_BROWSER_EXECUTABLE_PATH": "${env:KINDLY_BROWSER_EXECUTABLE_PATH}"
      }
    }
  }
}
```

### Claude Desktop

Edit `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`

Security note: this file contains secrets if you put API keys in it. Do not commit it into a repository.

```json
{
  "mcpServers": {
    "kindly-web-search": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server",
        "mcp-web-search",
        "--stdio"
      ],
      "env": {
        "SERPER_API_KEY": "YOUR_SERPER_API_KEY",
        "TAVILY_API_KEY": "YOUR_TAVILY_API_KEY",
        "GITHUB_TOKEN": "YOUR_GITHUB_TOKEN",
        "KINDLY_BROWSER_EXECUTABLE_PATH": "/path/to/chromium"
      }
    }
  }
}
```

### GitHub Copilot (VS Code) + Microsoft Copilot (local)

VS Code MCP config is typically `.vscode/mcp.json`.
VS Code MCP support is available starting from VS Code `1.102` and requires access to Copilot.

This example uses **input variables** so you don’t have to hardcode secrets in the file (VS Code will prompt once and store them):
Security best practice: this `${input:...}` approach stores secrets in VS Code’s secret storage rather than in your repo files.
```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "serper-api-key",
      "description": "Serper API key (leave empty if using Tavily only)",
      "password": true
    },
    {
      "type": "promptString",
      "id": "tavily-api-key",
      "description": "Tavily API key (leave empty if using Serper only)",
      "password": true
    },
    {
      "type": "promptString",
      "id": "github-token",
      "description": "GitHub token (optional; improves GitHub Issues extraction)",
      "password": true
    },
    {
      "type": "promptString",
      "id": "chromium-path",
      "description": "Chromium/Chrome binary path (optional; leave empty to auto-detect)",
      "password": false
    }
  ],
  "servers": {
    "kindlyWebSearch": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server",
        "mcp-web-search",
        "--stdio"
      ],
      "env": {
        "SERPER_API_KEY": "${input:serper-api-key}",
        "TAVILY_API_KEY": "${input:tavily-api-key}",
        "GITHUB_TOKEN": "${input:github-token}",
        "KINDLY_BROWSER_EXECUTABLE_PATH": "${input:chromium-path}"
      }
    }
  }
}
```

Note: the server key `kindlyWebSearch` uses camelCase to match VS Code naming conventions; other clients use kebab-case like `kindly-web-search`.

For enterprise / hosted scenarios (Copilot Studio / Microsoft Copilot), prefer running this MCP server remotely over **HTTPS Streamable HTTP** and store secrets in the hosting platform (not in client config files).

## Development Environments (Windows + WSL)

This repo is typically developed on Windows, but automation/agents may run in WSL/Linux.

- `.venv/` may contain **Windows** Python. Use it in PyCharm/Windows only.
- `.venv-codex/` is a **Linux/WSL** virtualenv used by automation in this repo. Do not use `.venv/` from WSL.

## Testing

Unit tests (recommended):
```bash
python -m pytest -q
```

## Logging

Logs go to **stderr** (stdout is reserved for MCP stdio transport). Control verbosity with `LOG_LEVEL` (default `WARNING`).

Live integration tests:
- Set `RUN_LIVE_TESTS=1` to enable (default: skipped).
- `tests/test_serper_live.py` will load `SERPER_API_KEY` from:
  1) your environment (preferred), otherwise
  2) `tests/.env.test` (gitignored)

## Examples

- `examples/script_run_mcp_tools.py` demonstrates calling the tool functions directly (useful for local debugging).

## Docker

This repo includes a `Dockerfile` for a “no local Python install” path.

Build:
```bash
docker build -t mcp-web-search:local .
```

Run as a stdio MCP server (works with clients that can launch `docker run -i ...`):
```bash
docker run -i --rm \
  -e SERPER_API_KEY \
  -e TAVILY_API_KEY \
  -e GITHUB_TOKEN \
  -e KINDLY_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium \
  mcp-web-search:local --stdio
```

Run as Streamable HTTP (for gateways / remote clients):
```bash
docker run --rm -p 8000:8000 \
  -e SERPER_API_KEY \
  -e TAVILY_API_KEY \
  -e GITHUB_TOKEN \
  -e KINDLY_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium \
  -e FASTMCP_HOST=0.0.0.0 \
  -e FASTMCP_PORT=8000 \
  mcp-web-search:local --http
```

Notes:
- Use `-i` for stdio so stdin stays open.
- For clean signal handling, consider `docker run --init ...`.

## Troubleshooting

- **nodriver says it can’t find Chrome/Chromium**: install a Chromium-based browser and/or set `KINDLY_BROWSER_EXECUTABLE_PATH`.
  - Ubuntu/WSL example: `sudo apt-get update && sudo apt-get install -y chromium`
  - Confirm it launches: run `chromium`
  - Find the binary path: `which chromium`
  - Then set it for your MCP client environment (or its config): `export KINDLY_BROWSER_EXECUTABLE_PATH="$(which chromium)"`
  - Browser executable resolution order: `KINDLY_BROWSER_EXECUTABLE_PATH` → `BROWSER_EXECUTABLE_PATH` → `CHROME_BIN` → `CHROME_PATH` → nodriver auto-detect
- **nodriver can’t connect to the browser (sandbox/root error)**: Chrome’s sandbox often fails in WSL/Docker/headless environments.
  - This repo disables nodriver sandbox by default for reliability. To force sandbox on: `export KINDLY_NODRIVER_SANDBOX=1`
  - If this happens intermittently on first run (common with snap Chromium cold starts), increase retries/timeouts:
    - `export KINDLY_NODRIVER_RETRY_ATTEMPTS=3`
    - `export KINDLY_HTML_TOTAL_TIMEOUT_SECONDS=45`
- **No `page_content` / empty content**: the site may block automation or require login; try `get_content(url)` directly and inspect the returned Markdown error note.
- **GitHub Issues retrieval fails**: ensure `GITHUB_TOKEN` is set and has permission to read the target repo’s issues.
- **Noisy stdout during PDF conversion**: this repo suppresses third-party PDF conversion prints to keep MCP stdio clean (see `content/arxiv.py`).
