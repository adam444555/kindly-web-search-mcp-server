# uvx Installation & Codex-Friendly Entrypoint — Requirements

## As Is
- The repository is a Python package (`pyproject.toml`) with a `src/kindly_web_search_mcp_server/` layout.
- The MCP server can be started via console scripts:
  - `mcp-web-search --stdio|--http|--sse`
  - `kindly-web-search --stdio|--http|--sse`
  - `mcp-server --stdio|--http|--sse`
- These scripts directly execute `kindly_web_search_mcp_server.server:main`, which expects transport flags (no subcommands).
- Documentation covers `pip install .` and `uv run -m kindly_web_search_mcp_server ...`, but does not provide an `uvx`-friendly snippet patterned after Serena’s `start-mcp-server --context codex` flow.

## To Be
- The MCP server can be launched via `uvx` from a Git URL, using a Codex-style config:
  - Example:
    ```toml
    [mcp_servers.kindly_web_search]
    command = "uvx"
    args = [
      "--from",
      "git+https://github.com/<ORG>/<REPO>",
      "kindly-web-search-mcp-server",
      "start-mcp-server",
      "--context",
      "codex"
    ]
    startup_timeout_sec = 60.0
    ```
- A new console entrypoint `kindly-web-search-mcp-server` is added which supports a `start-mcp-server` subcommand and a `--context` flag (for parity with Serena and Codex installations).
- Existing console scripts (`mcp-web-search`, `kindly-web-search`, `mcp-server`) remain supported and backward-compatible.

## Requirements
1. New CLI entrypoint
   - Add a new console script named `kindly-web-search-mcp-server`.
   - The entrypoint must be provided via `pyproject.toml` under `[project.scripts]`.
2. `start-mcp-server` subcommand
   - The new CLI must implement `start-mcp-server` as a subcommand.
   - When invoked with no additional flags, it must start the MCP server in stdio mode (default behavior).
   - It must support forwarding any additional server arguments to the existing `kindly_web_search_mcp_server.server:main` (e.g., `--http`, `--host`, `--port`, `--mount-path`).
3. `--context` flag
   - The `start-mcp-server` subcommand must accept `--context <name>` (e.g., `codex`).
   - Context must not be required for correct operation, but must be accepted for compatibility with Codex/Serena-style configuration.
   - When provided, the wrapper must expose the context value to the server process via `KINDLY_MCP_CONTEXT=<name>` (non-secret) for future behavior toggles.
4. Argument forwarding strategy
   - The wrapper must parse only its own flags (currently `--context`) and forward any remaining arguments verbatim to `kindly_web_search_mcp_server.server:main`.
   - If no transport flag is present in forwarded args, the wrapper must inject `--stdio`.
4. Backward compatibility
   - Existing entrypoints must keep their current behavior (no required subcommands).
5. Documentation
   - Add a README section documenting `uvx --from git+...` usage, including the Codex `config.toml` snippet above.
   - Document that `uvx` runs tools in temporary isolated environments, so system dependencies (e.g., Chromium for `nodriver`) are still required on the host.

## Acceptance Criteria (mapped to requirements)
1. `pyproject.toml` exposes a `kindly-web-search-mcp-server` console script.
2. Running `kindly-web-search-mcp-server start-mcp-server --context codex` starts the server (stdio by default) and forwards optional server flags.
3. Existing scripts (`mcp-web-search`, `kindly-web-search`, `mcp-server`) still work with their existing flags.
4. README includes a working Codex `uvx` configuration snippet and a one-liner `uvx` command example.
5. When `--context` is provided, the server process environment includes `KINDLY_MCP_CONTEXT` set to the provided value.

## Testing Plan (TDD)
- Unit tests
  - CLI parsing:
    - `start-mcp-server --context codex` forwards `["--stdio"]` (or empty, but must result in stdio) to the server entrypoint.
    - `start-mcp-server --context codex --http --host 127.0.0.1 --port 8000` forwards all flags verbatim.
  - Backward compatibility: no changes required for existing entrypoints; add tests only for the new CLI wrapper.
- Smoke test (manual)
  - Run locally:
    - `uvx --from . kindly-web-search-mcp-server start-mcp-server --context codex`
  - Run from Git:
    - `uvx --from git+https://github.com/<ORG>/<REPO> kindly-web-search-mcp-server start-mcp-server --context codex`

## Implementation Plan (smallest safe increments)
1. Add `src/kindly_web_search_mcp_server/cli.py` with an argparse-based CLI supporting `start-mcp-server`.
   - Test: patch `kindly_web_search_mcp_server.server.main` and assert forwarded args.
2. Register `kindly-web-search-mcp-server` in `pyproject.toml` pointing to `kindly_web_search_mcp_server.cli:main`.
   - Test: import `kindly_web_search_mcp_server.cli` in unit tests.
3. Update `README.md` with a Codex `uvx` config snippet and a short explanation of `--from git+...`.
   - Test: none (docs-only).
