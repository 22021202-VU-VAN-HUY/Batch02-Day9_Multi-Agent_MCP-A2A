"""Tests for the Stage 5 command-line output."""

from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import AsyncMock, patch

import test_client
from common.stage5_client import Stage5Result


class TestClientCliTests(unittest.IsolatedAsyncioTestCase):
    @patch("test_client.ask_stage5", new_callable=AsyncMock)
    async def test_json_mode_outputs_valid_json_only(
        self,
        ask_stage5_mock: AsyncMock,
    ) -> None:
        ask_stage5_mock.return_value = Stage5Result(
            answer="answer",
            mode="direct-law",
            trace_id="trace",
            context_id="context",
            total_seconds=2.0,
            discovery_seconds=0.1,
            request_seconds=1.9,
            route=["Client", "Law Agent"],
        )

        output = StringIO()
        with (
            patch(
                "sys.argv",
                ["test_client.py", "--mode", "direct-law", "--json"],
            ),
            redirect_stdout(output),
        ):
            await test_client.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["results"][0]["mode"], "direct-law")
        self.assertNotIn("Sending request", output.getvalue())


if __name__ == "__main__":
    unittest.main()
