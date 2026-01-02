from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_server_web_search_advanced_scraping.models import WebSearchResult


class TestPageContentResolver(unittest.IsolatedAsyncioTestCase):
    async def test_web_search_populates_page_content_for_stackexchange(self) -> None:
        from mcp_server_web_search_advanced_scraping.server import web_search

        serper_results = [
            WebSearchResult(
                title="SO",
                link="https://stackoverflow.com/questions/11227809/example",
                snippet="snippet",
                page_content=None,
            )
        ]

        with patch(
            "mcp_server_web_search_advanced_scraping.server.search_serper", new_callable=AsyncMock
        ) as mock_search, patch(
            "mcp_server_web_search_advanced_scraping.server.resolve_page_content_markdown",
            new_callable=AsyncMock,
        ) as mock_resolve:
            mock_search.return_value = serper_results
            mock_resolve.return_value = "# Question\n..."

            out = await web_search("q", num_results=1, return_full_pages=True)

        self.assertEqual(out["results"][0]["page_content"], "# Question\n...")


if __name__ == "__main__":
    unittest.main()
