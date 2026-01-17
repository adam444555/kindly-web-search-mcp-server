from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .extract import extract_content_as_markdown
from .sanitize import sanitize_markdown
from ..utils.diagnostics import (
    Diagnostics,
    MAX_SAMPLE_CHARS,
    MAX_STDERR_CHARS,
    mask_env_values,
    sample_data,
    truncate_text,
)


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class UniversalHtmlLoaderConfig:
    """
    Configuration for universal HTML loading.

    Values are intentionally conservative to keep MCP tool calls bounded.
    """

    user_agent: str = DEFAULT_USER_AGENT
    wait_seconds: float = 2.0
    total_timeout_seconds: float = 60.0
    max_markdown_chars: int = 50_000


def _is_probably_pdf_url(url: str) -> bool:
    """Cheap heuristic: avoid HTML loader for obvious PDFs."""
    try:
        return urlparse(url).path.lower().endswith(".pdf")
    except Exception:
        return url.lower().endswith(".pdf")


def _maybe_add_src_to_pythonpath(env: dict[str, str]) -> dict[str, str]:
    """
    Ensure subprocesses can import this package when running from source.

    The example script modifies `sys.path` in-process (to include `./src`) so it can be executed
    without installing the package. Subprocesses do not inherit that mutation, so the universal
    loader sets `PYTHONPATH` to include `./src` when it exists.
    """
    try:
        # Anchor to this file's physical location instead of relying on cwd.
        # When running from source, this resolves to `<repo>/src`.
        src_dir = Path(__file__).resolve().parents[2]
        if src_dir.is_dir():
            existing = env.get("PYTHONPATH", "")
            parts = [str(src_dir)]
            if existing:
                parts.append(existing)
            env["PYTHONPATH"] = os.pathsep.join(parts)
        return env
    except Exception:
        return env


def _resolve_browser_executable_path() -> str | None:
    """
    Resolve a Chromium-based browser binary path for nodriver.

    This is required on some systems (notably fresh WSL/Linux installs) where
    no default Chrome/Chromium binary exists in standard locations.
    """
    for key in (
        "KINDLY_BROWSER_EXECUTABLE_PATH",
        "BROWSER_EXECUTABLE_PATH",
        "CHROME_BIN",
        "CHROME_PATH",
    ):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return None


def _ensure_no_proxy_localhost_env(env: dict[str, str]) -> None:
    """
    Ensure Python subprocesses bypass proxies for loopback.

    The nodriver worker (and nodriver itself) may use urllib for `http://127.0.0.1:<port>/json/version`.
    If HTTP(S)_PROXY/ALL_PROXY are set without NO_PROXY/no_proxy, urllib can attempt to proxy loopback
    requests, leading to long hangs (commonly on Windows corporate machines).
    """
    raw = (env.get("KINDLY_NODRIVER_ENSURE_NO_PROXY_LOCALHOST") or "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return

    needed = ("localhost", "127.0.0.1", "::1")
    for key in ("NO_PROXY", "no_proxy"):
        existing = [x.strip() for x in (env.get(key) or "").split(",") if x.strip()]
        existing_lower = {x.lower() for x in existing}
        merged = list(existing)
        for host in needed:
            if host.lower() not in existing_lower:
                merged.append(host)
        if merged:
            env[key] = ",".join(merged)


def _split_worker_diagnostics(
    stderr_text: str,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    entries: list[dict[str, Any]] = []
    cleaned_lines: list[str] = []
    error_samples: list[str] = []
    for line in (stderr_text or "").splitlines():
        if not line.startswith("KINDLY_DIAG "):
            cleaned_lines.append(line)
            continue
        payload = line[len("KINDLY_DIAG ") :].strip()
        try:
            parsed = json.loads(payload)
        except Exception:
            if len(error_samples) < 3:
                sample, _, _ = truncate_text(payload, 200)
                error_samples.append(sample)
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
        else:
            if len(error_samples) < 3:
                sample, _, _ = truncate_text(payload, 200)
                error_samples.append(sample)
    cleaned_text = "\n".join(cleaned_lines).strip()
    return entries, cleaned_text, error_samples


async def _terminate_process_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return

    if os.name == "nt":
        with contextlib.suppress(Exception):
            proc.terminate()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), timeout=1.5)
        if proc.returncode is None and proc.pid is not None:
            with contextlib.suppress(Exception):
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/T",
                    "/F",
                    "/PID",
                    str(proc.pid),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await killer.wait()
                if killer.returncode not in (0, None):
                    with contextlib.suppress(Exception):
                        proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        return

    with contextlib.suppress(Exception):
        proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()


async def fetch_html_via_nodriver(
    url: str,
    *,
    referer: str | None = None,
    config: UniversalHtmlLoaderConfig = UniversalHtmlLoaderConfig(),
    diagnostics: Diagnostics | None = None,
) -> str:
    """
    Fetch a rendered HTML snapshot via headless Nodriver.

    Design constraints:
    - Keep the MCP stdio stream clean (no third-party debug prints).
    - Avoid Windows shutdown-time asyncio transport noise seen with in-process browser automation.

    Implementation detail:
    - A dedicated subprocess runs `kindly_web_search_mcp_server.scrape.nodriver_worker`.
    - The worker writes only HTML to stdout; all incidental output is discarded in the worker.
    """

    cmd = [
        sys.executable,
        "-m",
        "kindly_web_search_mcp_server.scrape.nodriver_worker",
        "--url",
        url,
        "--user-agent",
        config.user_agent,
        "--wait-seconds",
        str(config.wait_seconds),
    ]
    if referer:
        cmd.extend(["--referer", referer])

    browser_executable_path = _resolve_browser_executable_path()
    if browser_executable_path:
        cmd.extend(["--browser-executable-path", browser_executable_path])

    env = _maybe_add_src_to_pythonpath(dict(os.environ))
    if diagnostics and diagnostics.enabled:
        env["KINDLY_DIAGNOSTICS"] = "1"
        env["KINDLY_REQUEST_ID"] = diagnostics.request_id
    _ensure_no_proxy_localhost_env(env)

    if diagnostics:
        env_snapshot = {
            "KINDLY_BROWSER_EXECUTABLE_PATH": env.get("KINDLY_BROWSER_EXECUTABLE_PATH", ""),
            "KINDLY_HTML_TOTAL_TIMEOUT_SECONDS": env.get("KINDLY_HTML_TOTAL_TIMEOUT_SECONDS", ""),
            "KINDLY_NODRIVER_RETRY_ATTEMPTS": env.get("KINDLY_NODRIVER_RETRY_ATTEMPTS", ""),
            "KINDLY_NODRIVER_RETRY_BACKOFF_SECONDS": env.get("KINDLY_NODRIVER_RETRY_BACKOFF_SECONDS", ""),
            "KINDLY_NODRIVER_DEVTOOLS_READY_TIMEOUT_SECONDS": env.get(
                "KINDLY_NODRIVER_DEVTOOLS_READY_TIMEOUT_SECONDS", ""
            ),
            "KINDLY_NODRIVER_SNAP_BACKOFF_MULTIPLIER": env.get(
                "KINDLY_NODRIVER_SNAP_BACKOFF_MULTIPLIER", ""
            ),
            "KINDLY_NODRIVER_ENSURE_NO_PROXY_LOCALHOST": env.get(
                "KINDLY_NODRIVER_ENSURE_NO_PROXY_LOCALHOST", ""
            ),
            "NO_PROXY": env.get("NO_PROXY", ""),
            "no_proxy": env.get("no_proxy", ""),
            "HTTP_PROXY": env.get("HTTP_PROXY", ""),
            "HTTPS_PROXY": env.get("HTTPS_PROXY", ""),
        }
        diagnostics.emit(
            "worker.spawn",
            "Launching nodriver worker",
            {
                "url": url,
                "referer": referer or "",
                "user_agent": config.user_agent,
                "wait_seconds": config.wait_seconds,
                "cmd": cmd,
                "env": mask_env_values(env_snapshot),
            },
        )

    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    try:
        raw_timeout = (os.environ.get("KINDLY_HTML_TOTAL_TIMEOUT_SECONDS") or "").strip()
        used_default = False
        invalid = False
        parsed_value = config.total_timeout_seconds
        try:
            if raw_timeout:
                parsed_value = float(raw_timeout)
            else:
                used_default = True
        except ValueError:
            used_default = True
            invalid = True
        if parsed_value <= 0:
            used_default = True
            invalid = True
            parsed_value = config.total_timeout_seconds
        clamped = False
        timeout_seconds = max(1.0, min(parsed_value, 600.0))
        clamped = timeout_seconds != parsed_value
        if diagnostics:
            diagnostics.emit(
                "worker.timeout_budget_parent",
                "Resolved worker timeout budget",
                {
                    "raw_value": raw_timeout,
                    "clamped_value": timeout_seconds,
                    "effective_timeout_seconds": timeout_seconds,
                    "clamped": clamped,
                    "used_default": used_default,
                    "invalid": invalid,
                    "default_seconds": config.total_timeout_seconds,
                },
            )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        await _terminate_process_tree(proc)
        stderr_text = ""
        try:
            _, stderr_tail = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            stderr_text = (stderr_tail or b"").decode("utf-8", errors="ignore").strip()
        except Exception:
            stderr_text = ""
        worker_entries, stderr_text, error_samples = _split_worker_diagnostics(stderr_text)
        if diagnostics and worker_entries:
            diagnostics.entries.extend(worker_entries)
        if diagnostics and error_samples:
            diagnostics.emit(
                "worker.diag_parse_error",
                "Failed to parse worker diagnostics",
                {"samples": error_samples},
            )
        if diagnostics:
            stderr_sample, stderr_truncated, stderr_len = truncate_text(
                stderr_text, MAX_STDERR_CHARS
            )
            diagnostics.emit(
                "worker.timeout",
                "Nodriver worker timed out",
                {
                    "timeout_seconds": timeout_seconds,
                    "runtime_ms": int((time.monotonic() - started) * 1000),
                    "stderr_len": stderr_len,
                    "stderr_sample": stderr_sample,
                    "stderr_truncated": stderr_truncated,
                },
            )
        raise
    except asyncio.CancelledError:
        await _terminate_process_tree(proc)
        if diagnostics:
            diagnostics.emit("worker.cancelled", "Nodriver worker cancelled", {})
        raise

    stderr_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
    worker_entries, stderr_text, error_samples = _split_worker_diagnostics(stderr_text)
    if diagnostics and worker_entries:
        diagnostics.entries.extend(worker_entries)
    if diagnostics and error_samples:
        diagnostics.emit(
            "worker.diag_parse_error",
            "Failed to parse worker diagnostics",
            {"samples": error_samples},
        )

    if proc.returncode != 0:
        detail = stderr_text
        if diagnostics:
            stderr_sample, stderr_truncated, stderr_len = truncate_text(
                detail, MAX_STDERR_CHARS
            )
            diagnostics.emit(
                "worker.exit",
                "Nodriver worker failed",
                {
                    "exit_code": proc.returncode,
                    "stderr_len": stderr_len,
                    "stderr_sample": stderr_sample,
                    "stderr_truncated": stderr_truncated,
                    "runtime_ms": int((time.monotonic() - started) * 1000),
                },
            )
        raise RuntimeError(
            f"nodriver worker failed (exit={proc.returncode}): {detail or 'unknown error'}"
        )

    if diagnostics:
        if stderr_text:
            stderr_sample, stderr_truncated, stderr_len = truncate_text(
                stderr_text, MAX_STDERR_CHARS
            )
            diagnostics.emit(
                "worker.stderr",
                "Nodriver worker stderr output",
                {
                    "stderr_len": stderr_len,
                    "stderr_sample": stderr_sample,
                    "stderr_truncated": stderr_truncated,
                    "runtime_ms": int((time.monotonic() - started) * 1000),
                },
            )
        diagnostics.emit(
            "worker.stdout",
            "Nodriver worker completed",
            {
                "stdout_len": len(stdout or b""),
                "runtime_ms": int((time.monotonic() - started) * 1000),
            },
        )

    return (stdout or b"").decode("utf-8", errors="ignore")


def html_to_markdown(
    html: str,
    *,
    source_url: str,
    config: UniversalHtmlLoaderConfig = UniversalHtmlLoaderConfig(),
) -> str:
    """
    Convert raw HTML to sanitized Markdown and cap output length.
    """
    markdown = extract_content_as_markdown(html)
    markdown = sanitize_markdown(markdown)
    if len(markdown) > config.max_markdown_chars:
        markdown = markdown[: config.max_markdown_chars].rstrip() + "\n\n…(truncated)\n"
    if markdown.strip() in ("", "Could not extract main content."):
        return f"_Could not extract main content._\n\nSource: {source_url}\n"
    return markdown


async def load_url_as_markdown(
    url: str,
    *,
    referer: str | None = None,
    config: UniversalHtmlLoaderConfig = UniversalHtmlLoaderConfig(),
    diagnostics: Diagnostics | None = None,
) -> str | None:
    """
    Universal fallback: fetch HTML via headless Nodriver and return Markdown.

    Returns `None` for obvious non-HTML targets (e.g., PDFs).
    """
    if _is_probably_pdf_url(url):
        if diagnostics:
            diagnostics.emit("content.skip", "Skipping probable PDF", {"url": url})
        return None

    try:
        html = await fetch_html_via_nodriver(
            url, referer=referer, config=config, diagnostics=diagnostics
        )
    except Exception as exc:
        detail = str(exc).strip()
        if len(detail) > 400:
            detail = detail[:400].rstrip() + "…"
        suffix = f": {detail}" if detail else ""
        if diagnostics:
            diagnostics.emit(
                "content.error",
                "Universal HTML loader failed",
                {"error": type(exc).__name__, "detail": detail},
            )
        return f"_Failed to retrieve page content: {type(exc).__name__}{suffix}_\n\nSource: {url}\n"

    # If we somehow got a PDF/binary marker, refuse to parse it as HTML.
    if html.lstrip().startswith("%PDF-"):
        if diagnostics:
            diagnostics.emit("content.skip", "HTML looked like PDF", {"url": url})
        return None

    if diagnostics:
        diagnostics.emit(
            "content.html_sample",
            "Captured HTML sample",
            sample_data(html, MAX_SAMPLE_CHARS),
        )

    markdown = html_to_markdown(html, source_url=url, config=config)
    # Release the HTML buffer promptly (best-effort).
    html = ""
    return markdown
