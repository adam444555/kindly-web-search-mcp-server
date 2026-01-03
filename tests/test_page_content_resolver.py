from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kindly_web_search_mcp_server.models import WebSearchResult


class TestPageContentResolver(unittest.IsolatedAsyncioTestCase):
    async def test_web_search_populates_page_content_for_stackexchange(self) -> None:
        from kindly_web_search_mcp_server.server import web_search

        serper_results = [
            WebSearchResult(
                title="SO",
                link="https://stackoverflow.com/questions/11227809/example",
                snippet="snippet",
                page_content="",
            )
        ]

        with patch(
            "kindly_web_search_mcp_server.server.search_web", new_callable=AsyncMock
        ) as mock_search, patch(
            "kindly_web_search_mcp_server.server.resolve_page_content_markdown",
            new_callable=AsyncMock,
        ) as mock_resolve:
            mock_search.return_value = serper_results
            mock_resolve.return_value = "# Question\n..."

            out = await web_search("q", num_results=1)

        self.assertEqual(out["results"][0]["page_content"], "# Question\n...")

    async def test_web_search_returns_note_when_page_content_is_none(self) -> None:
        from kindly_web_search_mcp_server.server import web_search

        results = [
            WebSearchResult(
                title="PDF",
                link="https://example.com/file.pdf",
                snippet="snippet",
                page_content="",
            )
        ]

        with patch(
            "kindly_web_search_mcp_server.server.search_web", new_callable=AsyncMock
        ) as mock_search, patch(
            "kindly_web_search_mcp_server.server.resolve_page_content_markdown",
            new_callable=AsyncMock,
        ) as mock_resolve:
            mock_search.return_value = results
            mock_resolve.return_value = None

            out = await web_search("q", num_results=1)

        self.assertIn("Could not retrieve content", out["results"][0]["page_content"])


if __name__ == "__main__":
    unittest.main()
