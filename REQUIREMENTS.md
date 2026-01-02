# arXiv Paper Content Retrieval (API + PDF) — Requirements

## As Is
- `web_search()` returns Serper results with optional `page_content`.
- Page content resolution pipeline:
  - Stage 1: StackExchange via StackExchange API.
  - Stage 2: GitHub Issues via GitHub GraphQL.
  - Stage 3: Wikipedia via MediaWiki Action API.
  - Stage 4: Universal HTML loader (headless browser) → HTML → Markdown (best-effort).
- PDFs are currently *not* handled by a specialized retriever; the universal loader skips obvious PDFs.

## To Be
- If a search result URL is an **arXiv paper URL** (e.g. `https://arxiv.org/pdf/2205.01491` or `https://arxiv.org/abs/2205.01491v2`), the MCP server retrieves the paper **as a PDF** and converts it to Markdown:
  - Use arXiv API to fetch authoritative metadata (title, authors, abstract, categories, canonical links).
  - Download the PDF bytes (in-memory).
  - Convert the PDF to Markdown (in-memory, no persistent files).
- arXiv retrieval is integrated into `resolve_page_content_markdown()` before the universal loader (because the universal loader skips PDFs).
- Output is deterministic, bounded (caps prevent “context bombs”), and includes a truncation notice when capped.

## Requirements
1. URL detection: Recognize arXiv URLs and extract an arXiv identifier.
   - Support `/abs/<id>`, `/pdf/<id>`, and `/pdf/<id>.pdf` formats.
   - Support version suffixes (`vN`) in both `abs` and `pdf` URLs.
   - Support both modern IDs (`YYMM.NNNNN[vN]`) and legacy IDs (`cs/9901001[vN]`).
   - Ignore benign URL suffixes like trailing slashes and query strings.
2. arXiv API retrieval:
   - Use the arXiv Atom API (export endpoint) to fetch metadata for the identifier.
   - Parse Atom XML robustly and extract: title, authors, abstract/summary, published/updated, primary category, and a canonical PDF URL.
   - Use a descriptive `User-Agent` header (configurable via env var).
   - Use reasonable timeouts and handle transient HTTP failures (e.g., 429/5xx) gracefully.
3. PDF download:
   - Download the PDF in-memory (bytes).
   - Validate the payload is a PDF (content-type and `%PDF-` signature).
   - Use reasonable timeouts and handle transient HTTP failures (e.g., 429/5xx) gracefully.
4. PDF → Markdown conversion:
   - Convert PDF bytes to Markdown in-memory (no writing to disk).
   - Include a clear Markdown structure:
     - `# arXiv Paper`
     - `## Metadata` (title, authors, arXiv id, links, category, dates)
     - `## Abstract`
     - `## Full Text (PDF)` (converted content)
5. Output bounds:
   - Cap total Markdown characters (default: 50k via `ARXIV_MAX_CHARS`).
   - Optionally cap number of pages processed (default: 30 via `ARXIV_MAX_PAGES`).
   - If truncated, append a truncation note with the source URL.
6. Safety:
   - Never print debug output during tool execution.
   - Never include secrets in returned Markdown.
7. Error handling:
   - If metadata fetch fails (missing paper, network), return a short Markdown error note.
   - If PDF download/conversion fails, return a short Markdown error note (no secrets) rather than `None` (because fallback would skip PDFs).

## Acceptance Criteria (mapped to requirements)
1. Given an arXiv URL, parsing returns the correct arXiv identifier; non-arXiv URLs do not match.
2. For a known public arXiv paper, retriever returns Markdown with `# arXiv Paper`, `## Abstract`, and non-empty `## Full Text (PDF)` (best-effort).
3. Output includes metadata (title/authors/id/links) and is deterministic.
4. Large PDFs respect caps (`ARXIV_MAX_CHARS` and/or `ARXIV_MAX_PAGES`) and include a truncation notice.
5. Failures produce a short Markdown error without secrets and do not crash the tool call.
6. `resolve_page_content_markdown()` routes arXiv URLs to the arXiv retriever and does not break StackExchange/GitHub/Wikipedia.

## Testing Plan (TDD)
- Unit tests
  - URL parser: abs/pdf/pdf.pdf formats; version suffix; legacy IDs; invalid URLs.
  - Atom parser: mock API XML for success + missing entry; ensure correct metadata extraction.
  - PDF converter: with a minimal in-memory PDF (blank page is fine) ensures conversion doesn’t crash and produces bounded Markdown.
  - Truncation: enforce `ARXIV_MAX_CHARS`/`ARXIV_MAX_PAGES` behavior deterministically.
- Integration tests (opt-in)
  - `RUN_LIVE_TESTS=1`: fetch a stable arXiv ID and assert basic structure; skip by default.
- Smoke test
  - Run `examples/script_run_mcp_tools.py` with a query returning arXiv links; confirm `page_content` is populated via arXiv retriever.

## Implementation Plan (smallest safe increments)
1. Add arXiv URL parsing utility.
   - Test: unit tests for parsing.
2. Add arXiv Atom API client + XML parsing.
   - Test: mocked httpx response with Atom XML.
3. Add PDF downloader (bytes) with PDF validation.
   - Test: mocked PDF response and invalid content-type handling.
4. Add PDF→Markdown converter (in-memory).
   - Test: minimal in-memory PDF, truncation behavior.
5. Integrate into `content/resolver.py` before universal loader.
   - Test: resolver selects arXiv retriever when URL matches.
6. Add optional live integration test gated by env vars.
   - Test: run only when explicitly enabled.
