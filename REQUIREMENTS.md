# Kindly Web Search MCP Server — Requirements (Tavily + uvx + non-null `page_content`)

## As Is
- The server is a Python MCP server built on `FastMCP`.
- Tools:
  - `web_search(query: str, num_results: int = 3)`:
    - Queries a web search provider (Serper and/or Tavily).
    - For each result, fetches and extracts the linked page into LLM-ready Markdown.
    - Returns `{ "results": [{title, link, snippet, page_content}, ...] }`.
  - `get_content(url: str)`:
    - Fetches a single URL and returns `{ "url": url, "page_content": <markdown> }`.
- Search providers:
  - Serper: `SERPER_API_KEY` (Google Serper API).
  - Tavily: `TAVILY_API_KEY` (Tavily Search API).
  - If both keys are present, Serper is primary and Tavily is fallback on transient errors.
- Content extraction pipeline:
  - Specialized loaders (StackExchange, GitHub Issues, Wikipedia, arXiv) with a universal HTML fallback (Nodriver/Chromium in a subprocess).
- Known pain points observed by users:
  - Browser automation (Nodriver/Chromium) may intermittently fail to connect on the first run, especially with Snap Chromium in Linux/WSL, then succeed on subsequent invocations.
  - Older versions exposed `return_full_pages`; when set to false, clients saw `"page_content": null` and assumed a bug.

## To Be
- `web_search` must be a single, stable contract:
  - No `return_full_pages` flag (no “off” switch).
  - Always returns parsed search results and always includes a **non-null** `page_content` string for each result.
    - If content cannot be fetched/extracted, `page_content` is a deterministic Markdown error note (never `null`).
- Search provider routing:
  - The server works when **either** Serper or Tavily key is present.
  - If both keys are present:
    - Serper is used by default.
    - If the primary provider fails with a transient error, the server transparently retries via the secondary provider.
- Installation:
  - The server must be runnable via `uvx --from git+...` (no local install) on all MCP clients that support stdio commands.
  - A thin wrapper CLI must exist for “Serena-style” invocation: `kindly-web-search-mcp-server start-mcp-server --context codex`.
- Robustness:
  - Nodriver should tolerate intermittent “Failed to connect to browser” startup failures via retry/backoff.
  - All errors must avoid leaking secrets (API keys, tokens).

## Requirements
1. Tool contract: `web_search`
   - Inputs:
     - `query: str` (required)
     - `num_results: int` (default `3`)
   - Outputs:
     - `results: list` of items with fields:
       - `title: str`, `link: str`, `snippet: str`, `page_content: str` (**required, never null**)
   - Behavior:
     - Always fetch + extract each linked result page into Markdown (best-effort).
     - If extraction yields “no content” or the URL is unsupported, return a deterministic Markdown note in `page_content`.
2. Search providers: Serper + Tavily + fallback
   - Configuration:
     - Serper key: `SERPER_API_KEY`
     - Tavily key: `TAVILY_API_KEY`
   - Provider selection:
     - If both keys are present: primary Serper, secondary Tavily.
     - If only one is present: use that provider, no fallback.
     - If neither is present: tool call fails with an actionable error mentioning both env vars.
   - Fallback triggers only on transient/provider errors:
     - HTTP 5xx, HTTP 429
     - network/timeout errors
     - invalid/unparseable responses
   - No fallback on:
     - missing/invalid API key (auth/config issues; e.g., HTTP 401/403)
     - HTTP 400
     - empty result sets
3. uvx support (Git-run install)
   - The repo must provide console scripts so that `uvx --from git+<repo> <command> ...` works.
   - Provide a “Serena-style” wrapper command:
     - `kindly-web-search-mcp-server start-mcp-server --context <ctx> [-- <forwarded args>]`
4. Nodriver reliability (first-run flake)
   - Nodriver startup should retry on known “Failed to connect to browser” cases with exponential backoff.
   - Retry behavior must be configurable via env vars (attempts/backoff), with safe defaults.
5. Security
   - Never include API keys/tokens in tool outputs or error messages.
6. Documentation
   - README must document:
     - Provider selection rules and env vars.
     - `uvx` install/run examples (including “Serena-style” wrapper).
     - Platform/client config snippets (Codex, Claude Code, Gemini CLI, Cursor, Claude Desktop, VS Code / Copilot).

## Acceptance Criteria (mapped to requirements)
1. With only `TAVILY_API_KEY` set, `web_search` returns results (with non-null `page_content`) without requiring `SERPER_API_KEY`.
2. With both keys set, `web_search` uses Serper by default.
3. With both keys set and Serper returns an error (e.g., HTTP 500), `web_search` returns Tavily results instead.
4. With neither key set, `web_search` fails with an actionable error mentioning both env vars.
5. `web_search` responses never contain `"page_content": null` (the key always exists and is always a string).
6. Errors never include the raw values of `SERPER_API_KEY`, `TAVILY_API_KEY`, or `GITHUB_TOKEN`.
7. `uvx --from git+<repo> kindly-web-search-mcp-server start-mcp-server --context codex` successfully launches the server in stdio mode.

## Testing Plan (TDD)
- Unit tests (no network)
  - Tavily request + response parsing via `httpx.MockTransport`.
  - Provider selection + fallback rules (Serper primary, Tavily secondary):
    - transient Serper failure triggers Tavily; auth failure does not.
  - `web_search` response shape:
    - `page_content` is always present and always a string.
  - Nodriver worker retry policy:
    - `_is_retryable_browser_connect_error` classifications.
    - env var parsing for retry attempts/backoff.
- Smoke tests (local, optional)
  - Run via stdio in an MCP client (Codex/Cursor/Claude Desktop) with a real provider key and a working Chromium.

## Implementation Plan (smallest safe increments)
1. Finalize the `web_search` contract (remove `return_full_pages` entirely).
   - Test: update server tests to assert `page_content` is always present.
2. Ensure response models match the contract (`page_content: str`, not optional).
   - Test: pydantic validation and tool response shape tests.
3. Confirm search routing + fallback matches requirements.
   - Test: selection/fallback unit tests (no network).
4. Improve nodriver startup reliability (retry/backoff defaults and doc).
   - Test: unit tests for retry policy functions; smoke test with Snap Chromium.
5. Ensure uvx wrapper CLI works and is documented.
   - Test: `tests/test_uvx_cli.py` and README snippets remain consistent.
