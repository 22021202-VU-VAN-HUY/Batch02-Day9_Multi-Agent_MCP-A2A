"""Tests for the Stage 5 web demo API and static fallback."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from common.stage5_client import Stage5Result
from web_demo.server import app


class WebDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_static_fallback_serves_html_css_and_javascript(self) -> None:
        root = self.client.get("/")
        css = self.client.get("/src/styles.css")
        javascript = self.client.get("/src/main.js")

        self.assertEqual(root.status_code, 200)
        self.assertIn("/src/styles.css", root.text)
        self.assertEqual(css.status_code, 200)
        self.assertIn("text/css", css.headers["content-type"])
        self.assertEqual(javascript.status_code, 200)
        self.assertIn("javascript", javascript.headers["content-type"])
        self.assertNotIn('import "./styles.css"', javascript.text)

    def test_query_validation_rejects_short_question(self) -> None:
        response = self.client.post(
            "/api/query",
            json={"question": "x", "mode": "customer"},
        )

        self.assertEqual(response.status_code, 422)

    def test_vite_config_proxies_api_to_fastapi(self) -> None:
        web_root = Path(__file__).resolve().parents[1] / "web_demo"
        package = json.loads((web_root / "package.json").read_text(encoding="utf-8"))
        vite_config = (web_root / "vite.config.js").read_text(encoding="utf-8")

        self.assertEqual(package["scripts"]["dev"], "vite --host 127.0.0.1")
        self.assertIn('"/api": "http://127.0.0.1:8080"', vite_config)

    @patch("web_demo.server.ask_stage5", new_callable=AsyncMock)
    def test_query_returns_latency_and_trace_contract(
        self,
        ask_stage5_mock: AsyncMock,
    ) -> None:
        ask_stage5_mock.return_value = Stage5Result(
            answer="ok",
            mode="direct-law",
            trace_id="trace-id",
            context_id="context-id",
            total_seconds=1.25,
            discovery_seconds=0.05,
            request_seconds=1.2,
            route=["Client", "Law Agent"],
        )

        response = self.client.post(
            "/api/query",
            json={
                "question": "What are the contract and tax consequences?",
                "mode": "direct-law",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "ok",
                "mode": "direct-law",
                "trace_id": "trace-id",
                "context_id": "context-id",
                "total_seconds": 1.25,
                "discovery_seconds": 0.05,
                "request_seconds": 1.2,
                "route": ["Client", "Law Agent"],
            },
        )
        ask_stage5_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
