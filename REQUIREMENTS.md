# Universal HTML Loader: Chromium/nodriver Connect Failures — Requirements

## As Is
- `web_search(..., return_full_pages=true)` and `get_content(url)` rely on a universal HTML fallback implemented via a `nodriver` subprocess worker (`src/kindly_web_search_mcp_server/scrape/nodriver_worker.py`).
- Some environments fail to fetch HTML and return errors like:
  - `Failed to connect to browser ... One of the causes could be when you are running as root ... need to pass no_sandbox=True`
- The error is not always actionable:
  - The server may not be running as root, yet the same message appears.
  - Browser discovery can differ across environments (WSL/Docker/snap/apt installs).
  - Users may not have set `KINDLY_BROWSER_EXECUTABLE_PATH`, and auto-discovery may fail.

## To Be
- The universal HTML loader should reliably launch a Chromium-based browser across common environments (WSL, Docker, local Linux) and provide actionable diagnostics when it cannot.
- The worker should:
  - Prefer a known browser binary when available (from env vars or `PATH`) instead of relying purely on nodriver auto-discovery.
  - Force sandbox off when running as root (Chromium often cannot start with sandbox as root).
  - Preserve the “no stdout noise” invariant required by MCP stdio.

## Requirements
1. Root-safe sandbox behavior
   - If the worker runs as root (`os.geteuid() == 0`), it must force sandbox disabled regardless of `KINDLY_NODRIVER_SANDBOX`.
2. Browser executable resolution
   - If `--browser-executable-path` is not provided, the worker must attempt to resolve a browser binary from:
     - env: `KINDLY_BROWSER_EXECUTABLE_PATH`, `BROWSER_EXECUTABLE_PATH`, `CHROME_BIN`, `CHROME_PATH`
     - `PATH` via `shutil.which` for common names (e.g., `chromium`, `google-chrome`, `chrome`, `chromium-browser`)
   - If no browser binary can be resolved, the worker must fail with a concise error explaining how to fix it (install Chromium or set `KINDLY_BROWSER_EXECUTABLE_PATH`).
3. Actionable errors
   - When nodriver fails with “Failed to connect to browser”, the worker error should include enough context to debug:
     - whether sandbox was enabled
     - whether the process is root
     - which `browser_executable_path` was used (if any)

## Acceptance Criteria
1. With `os.geteuid()==0`, `_fetch_html(... )` calls `nodriver.start(..., sandbox=False, ...)` even if `KINDLY_NODRIVER_SANDBOX=1`.
2. If `shutil.which("chromium")` returns a path and no explicit executable path is passed, `_fetch_html` forwards that path to `nodriver.start(..., browser_executable_path=...)`.
3. When no browser executable can be resolved, `_fetch_html` raises a `RuntimeError` containing guidance to set `KINDLY_BROWSER_EXECUTABLE_PATH`.

## Testing Plan (TDD)
- Unit tests (no real browser)
  - Extend the existing nodriver worker sandbox tests to verify root override.
  - Add a test for browser executable resolution via `shutil.which`.
  - Add a test for missing browser executable producing a helpful error message.
- Smoke test (manual)
  - Run `get_content("https://docs.astral.sh/uv/guides/tools/")` in:
    - local Linux/WSL with Chromium installed
    - Docker container (root) with Chromium installed and sandbox disabled

## Implementation Plan (smallest safe increments)
1. Implement browser executable resolution helper in `scrape/nodriver_worker.py`.
   - Test: mock `shutil.which` and assert the chosen path is forwarded.
2. Force sandbox off when root.
   - Test: patch `os.geteuid` to return `0` and assert `sandbox=False`.
3. Improve connect-failure error message with context (root/sandbox/path).
   - Test: simulate connect failure by making `nodriver.start` raise and verify the error string.
