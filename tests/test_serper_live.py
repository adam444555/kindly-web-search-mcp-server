from __future__ import annotations

import sys
from pathlib import Path
import json
import os
import unittest
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _load_dotenv(path: str) -> None:
    """Minimal dotenv loader (avoids printing secrets)."""
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and (
                (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
            ):
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)


class TestSerperLive(unittest.TestCase):
    """
    Integration test: hits the real Serper API.

    Requirements:
    - `tests/.env.test` exists and contains `SERPER_API_KEY=...`
    - outbound network access to https://google.serper.dev
    """

    def test_serper_search_live(self) -> None:
        if os.environ.get("RUN_LIVE_TESTS", "").strip().lower() not in ("1", "true", "yes"):
            self.skipTest("Live tests disabled; set RUN_LIVE_TESTS=1 to enable")

        # Prefer the real environment (e.g., IDE run config / CI secrets). If absent,
        # fall back to `tests/.env.test` (which is gitignored).
        if not os.environ.get("SERPER_API_KEY"):
            try:
                _load_dotenv("tests/.env.test")
            except FileNotFoundError:
                pass

        api_key = os.environ.get("SERPER_API_KEY", "")
        self.assertTrue(api_key, "SERPER_API_KEY is missing; set it in tests/.env.test")

        url = "https://google.serper.dev/search"
        payload = {"q": "mcp server fastmcp", "num": 1}
        body = json.dumps(payload).encode("utf-8")
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))

        self.assertIsInstance(data, dict)
        organic = data.get("organic")
        self.assertIsInstance(organic, list)
        self.assertGreaterEqual(len(organic), 1)

        first = organic[0]
        self.assertIsInstance(first, dict)
        self.assertIsInstance(first.get("title"), str)
        self.assertTrue(first.get("title"))
        self.assertIsInstance(first.get("link"), str)
        self.assertTrue(first.get("link"))
        self.assertIsInstance(first.get("snippet"), str)
        self.assertTrue(first.get("snippet"))


if __name__ == "__main__":
    unittest.main()
