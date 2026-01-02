# Repository Guidelines

## Project Structure & Module Organization

- `docs/` contains design notes and reference material (see `docs/repository_organization.md` for the intended MCP server layout).
- When adding real implementation code, prefer a `src/<package_name>/` package layout and keep the entrypoint thin (CLI + wiring).

## Build, Test, and Development Commands

- `python -V` — this project targets Python `>=3.13` (see `pyproject.toml`).
- `python main.py` — run the current placeholder script.
- `python -m pip install -U pip` — upgrade tooling inside the virtualenv (recommended).

### Codex agent virtualenv (`.venv-codex`)

This repository is developed on Windows, but this coding agent runs in a Linux (WSL) environment. The existing `.venv/` may contain a Windows Python and must **not** be used by the agent.

- Use `.venv-codex/` for all agent-installed dependencies and tooling.
- The agent is allowed to create, modify, and delete packages inside `.venv-codex/` as needed.

## Coding Style & Naming Conventions

- Indentation: 4 spaces; keep lines reasonably short (PEP 8).
- Naming: `snake_case` (functions/vars), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants).
- Prefer type hints for public functions and explicit request/response models for MCP tools.
- If implementing an MCP stdio server, write logs to **stderr** and reserve **stdout** for protocol transport.

## Testing Guidelines

- No test suite is committed yet.
- When adding tests, use `pytest` and place files under `tests/` named `test_*.py`.
- Run locally with `python -m pytest -q`.

## Commit & Pull Request Guidelines

- This checkout may not include Git history; if/when initialized, use Conventional Commit-style messages (e.g., `feat: …`, `fix: …`, `docs: …`).
- Pull requests should include: purpose, key design choices, how you tested, and any docs updates in `docs/`.

## Security & Configuration Tips

- Do not commit API keys; use environment variables and provide a sanitized `.env.example`.
- For scraping-related code, document policy decisions (timeouts, robots.txt, rate limits) and keep them configurable.
