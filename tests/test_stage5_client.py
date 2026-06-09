"""Tests for Stage 5 routing and latency metadata."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from common.stage5_client import ask_stage5


class Stage5ClientTests(unittest.IsolatedAsyncioTestCase):
    @patch("common.stage5_client.delegate", new_callable=AsyncMock)
    async def test_customer_mode_uses_entry_point(self, delegate_mock: AsyncMock) -> None:
        delegate_mock.return_value = "baseline answer"

        result = await ask_stage5(
            "A contract and tax question",
            mode="customer",
            trace_id="trace-1",
            context_id="context-1",
        )

        self.assertEqual(result.answer, "baseline answer")
        self.assertEqual(result.mode, "customer")
        self.assertIn("Customer Agent", result.route)
        self.assertEqual(delegate_mock.await_args.kwargs["depth"], 0)

    @patch("common.stage5_client.discover", new_callable=AsyncMock)
    @patch("common.stage5_client.delegate", new_callable=AsyncMock)
    async def test_direct_mode_discovers_law_agent(
        self,
        delegate_mock: AsyncMock,
        discover_mock: AsyncMock,
    ) -> None:
        discover_mock.return_value = "http://localhost:10101"
        delegate_mock.return_value = "optimized answer"

        result = await ask_stage5(
            "A contract and tax question",
            mode="direct-law",
            trace_id="trace-2",
            context_id="context-2",
        )

        discover_mock.assert_awaited_once_with("legal_question")
        self.assertNotIn("Customer Agent", result.route)
        self.assertEqual(delegate_mock.await_args.kwargs["depth"], 1)
        self.assertGreaterEqual(result.total_seconds, result.request_seconds)

    async def test_empty_question_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            await ask_stage5("  ")


if __name__ == "__main__":
    unittest.main()
