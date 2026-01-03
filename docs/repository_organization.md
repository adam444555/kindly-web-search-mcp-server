Below is a repo organization that matches how the **official MCP Python SDK** expects you to build servers (FastMCP, stdio/SSE/Streamable HTTP, uv-friendly) ([GitHub][1]), while cleanly separating **search → fetch → extract → HTML→Markdown** so you can swap providers and extraction strategies without rewriting your MCP tool layer.

---

## 1) Start from the “minimum MCP server” skeleton (then grow it)

The official `create-python-server` template creates a tiny, packaging-correct baseline:

```
my-server/
├── README.md
├── pyproject.toml
└── src/
    └── my_server/
        ├── __init__.py
        ├── __main__.py
        └── server.py
```

That’s a great starting point because it already matches how MCP Python projects are commonly laid out and run with `uv`. ([GitHub][2])

---

## 2) Recommended production-ready repo layout for “Web Search + optional scrape + Markdown”

This structure is still small, but gives you the seams you’ll want (providers, extraction pipeline, caching, policy):

```
web-mcp-server/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── Dockerfile
├── .gitignore
├── .github/workflows/ci.yml
├── docs/
│   ├── architecture.md
│   ├── configuration.md
│   ├── providers.md
│   └── scraping_policy.md
├── examples/
│   ├── claude_desktop_config.json
│   └── curl_streamable_http.md
├── src/web_mcp_server/
│   ├── __init__.py
│   ├── __main__.py              # `python -m web_mcp_server`
│   ├── server.py                # FastMCP tool registration (thin layer)
│   ├── settings.py              # env + defaults (Pydantic Settings recommended)
│   ├── models.py                # typed request/response schemas
│   ├── search/
│   │   ├── base.py              # SearchProvider interface
│   │   ├── ddgs_provider.py     # API-key-free fallback (metasearch)
│   │   ├── brave_provider.py    # provider via official API key
│   │   ├── serper_provider.py   # provider via Serper API key
│   │   └── dataforseo_provider.py
│   ├── scrape/
│   │   ├── fetch.py             # http client + timeouts + size limits
│   │   ├── robots.py            # robots.txt checks + crawl delay
│   │   ├── extract.py           # main-content extraction (trafilatura/readability)
│   │   ├── html_to_md.py        # raw HTML→MD fallback (markdownify/html2text)
│   │   └── sanitize.py          # clean/trim markdown for token budgets
│   └── utils/
│       ├── cache.py             # optional persistent caching
│       ├── rate_limit.py        # per-domain throttling
│       └── logging.py
└── tests/
    ├── unit/
    └── integration/
```

Why this shape works well:

* **`server.py` stays thin**: only MCP tool definitions + wiring. MCP transports are handled by the SDK (stdio/SSE/Streamable HTTP). ([GitHub][1])
* **Search is an interface**: you can swap ddgs/Brave/Serper/DataForSEO without touching scraping code.
* **Scraping pipeline is composable**: fetch → extract → convert → sanitize.

---

## 3) Tool surface area: keep it small and composable

Even if your *main* tool is “search and optionally scrape”, you’ll thank yourself for splitting the MCP tools like this:

### Tool A — `web_search(query, provider=..., max_results=..., …)`

Returns **structured** results: title/url/snippet/rank, plus provider metadata. (Many MCP web-search servers already do this pattern.) ([GitHub][3])

### Tool B — `fetch_as_markdown(url, …)`

Fetches one page and returns cleaned Markdown.

### Tool C — `search_and_scrape(query, scrape=True, scrape_top_k=…, …)`

Calls A, then (optionally) calls B on top K results.

This mirrors what existing MCP search projects do (search + get_webpage_content as separate tools) while still supporting your “one-call” workflow. ([GitHub][4])

---

## 4) Provider strategy (important if you want reliability)

### “No API key” option (good default fallback)

* `duckduckgo-search` has been renamed to `ddgs`—plan your dependency and import accordingly. ([PyPI][5])

### Paid / official SERP options (more stable than scraping Google HTML)

* **Serper** (Google results via API) ([Serper][6])
* **DataForSEO SERP API** (structured SERP, multiple engines/functions) ([DataForSEO Docs][7])

Repository implication: put each provider behind `SearchProvider` and select via env/config (`SEARCH_PROVIDER=ddgs|serper|dataforseo|brave`).

---

## 5) Scraping + HTML→Markdown: recommend an “extract-first” pipeline

If your goal is LLM-ready text, don’t just convert full HTML to Markdown—**extract main content first**.

**Recommended default**

* **Trafilatura**: supports extraction and can output **Markdown** directly (output format `"markdown"`). ([Trafilatura][8])

**Fallbacks**

* `readability-lxml` for main-body extraction when trafilatura struggles. ([PyPI][9])
* Raw HTML→Markdown converters as last resort:

  * `markdownify` ([PyPI][10])
  * `html2text` ([PyPI][11])

Repo implication: `scrape/extract.py` should choose extractor strategy; `scrape/html_to_md.py` is strictly fallback conversion.

---

## 6) Fetching responsibly (robots, rate limits, caching)

These are worth first-class modules because they shape your reliability:

* **robots.txt**: Python’s `urllib.robotparser.RobotFileParser` exists specifically to answer “can I fetch this URL as this user-agent?” ([Python documentation][12])
* **Async HTTP**: if you scrape multiple results, use an async client (HTTPX supports async and long-lived connections). ([HTTPX][13])
* **Caching**: optional, but helpful for repeated calls and tests; `requests-cache` is a common drop-in persistent cache (if you use `requests`). ([PyPI][14])

Repo implication: keep these separate (`robots.py`, `rate_limit.py`, `cache.py`) so your MCP tool code stays clean.

---

## 7) Configuration: ship a good `.env.example`

Include env keys that match your modules:

* `SEARCH_PROVIDER=ddgs|brave|serper|dataforseo`
* `SERPER_API_KEY=...`
* `BRAVE_API_KEY=...`
* `DATAFORSEO_LOGIN=...`, `DATAFORSEO_PASSWORD=...`
* `SCRAPE_DEFAULT=false`
* `SCRAPE_TOP_K=3`
* `MAX_RESULTS=10`
* `HTTP_TIMEOUT_S=15`
* `MAX_BYTES=2000000`
* `MAX_MD_CHARS=20000`
* `RESPECT_ROBOTS=true`
* `USER_AGENT=YourBotName/1.0 (+contact…)`
* `CONCURRENCY=5`

(Existing MCP servers commonly document `.env` + `PORT` + Claude Desktop config, so this will feel familiar to users.) ([GitHub][15])

---

## 8) Quick note on transports

The MCP Python SDK supports **stdio, SSE, and Streamable HTTP**. Keep stdio as your default (best desktop integration), and add Streamable HTTP as an optional run mode for hosting. ([GitHub][1])

---

* [The Verge](https://www.theverge.com/news/667517/microsoft-bing-search-api-end-of-support-ai-replacement?utm_source=chatgpt.com)
* [WIRED](https://www.wired.com/story/bing-microsoft-api-support-ending?utm_source=chatgpt.com)

[1]: https://github.com/modelcontextprotocol/python-sdk "GitHub - modelcontextprotocol/python-sdk: The official Python SDK for Model Context Protocol servers and clients"
[2]: https://github.com/modelcontextprotocol/create-python-server "GitHub - modelcontextprotocol/create-python-server: Create a Python MCP server"
[3]: https://github.com/null-create/mcp-web-server "GitHub - null-create/mcp-web-server: A simple MCP server that provides web search functionality for SLMs and LLMs with zero API keys required."
[4]: https://github.com/pranavms13/web-search-mcp "GitHub - pranavms13/web-search-mcp: A Model Context Protocol (MCP) server that provides web search functionality using a headless Chrome browser to scrape Google, DuckDuckGo and Bing search results."
[5]: https://pypi.org/project/duckduckgo-search/?utm_source=chatgpt.com "duckduckgo-search · PyPI"
[6]: https://serper.dev/?utm_source=chatgpt.com "Serper - The World's Fastest and Cheapest Google Search API"
[7]: https://docs.dataforseo.com/v3/serp-overview/?utm_source=chatgpt.com "serp/overview – DataForSEO API v.3"
[8]: https://trafilatura.readthedocs.io/en/latest/usage-python.html?utm_source=chatgpt.com "With Python — Trafilatura 2.0.0 documentation"
[9]: https://pypi.org/project/readability-lxml/?utm_source=chatgpt.com "readability-lxml · PyPI"
[10]: https://pypi.org/project/markdownify/?utm_source=chatgpt.com "markdownify · PyPI"
[11]: https://pypi.org/project/html2text/?utm_source=chatgpt.com "html2text · PyPI"
[12]: https://docs.python.org/3.15/library/urllib.robotparser.html?utm_source=chatgpt.com "urllib.robotparser — Parser for robots.txt — Python 3.15.0a2 documentation"
[13]: https://www.python-httpx.org/async/?utm_source=chatgpt.com "Async Support - HTTPX"
[14]: https://pypi.org/project/requests-cache/?utm_source=chatgpt.com "requests-cache · PyPI"
[15]: https://github.com/vikrambhat2/mcp-server-web-search "GitHub - vikrambhat2/mcp-server-web-search"
