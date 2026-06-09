"""Reusable Stage 5 client with end-to-end latency measurements."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Literal
from uuid import uuid4

from common.a2a_client import delegate
from common.registry_client import discover

Stage5Mode = Literal["customer", "direct-law"]


@dataclass(frozen=True)
class Stage5Result:
    """Result and timing data for one Stage 5 request."""

    answer: str
    mode: Stage5Mode
    trace_id: str
    context_id: str
    total_seconds: float
    discovery_seconds: float
    request_seconds: float
    route: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


async def ask_stage5(
    question: str,
    mode: Stage5Mode = "customer",
    *,
    trace_id: str | None = None,
    context_id: str | None = None,
) -> Stage5Result:
    """Send a legal question through the baseline or optimized Stage 5 route.

    The baseline route enters through Customer Agent. The optimized route is
    intended for callers that already know the request is a substantive legal
    question; it discovers and calls Law Agent directly, avoiding the Customer
    Agent's routing and response-synthesis LLM turns.
    """
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("Question must not be empty.")
    if mode not in ("customer", "direct-law"):
        raise ValueError(f"Unsupported Stage 5 mode: {mode}")

    request_trace_id = trace_id or str(uuid4())
    request_context_id = context_id or str(uuid4())
    total_started = perf_counter()
    discovery_seconds = 0.0

    if mode == "customer":
        endpoint = os.getenv("CUSTOMER_AGENT_URL", "http://localhost:10100")
        depth = 0
        route = [
            "Client",
            "Customer Agent",
            "Registry",
            "Law Agent",
            "Tax + Compliance (parallel)",
            "Law aggregate",
            "Customer response",
        ]
    else:
        discovery_started = perf_counter()
        endpoint = await discover("legal_question")
        discovery_seconds = perf_counter() - discovery_started
        depth = 1
        route = [
            "Client",
            "Registry",
            "Law Agent",
            "Tax + Compliance (parallel)",
            "Law aggregate",
        ]

    request_started = perf_counter()
    answer = await delegate(
        endpoint=endpoint,
        question=normalized_question,
        context_id=request_context_id,
        trace_id=request_trace_id,
        depth=depth,
    )
    request_seconds = perf_counter() - request_started
    total_seconds = perf_counter() - total_started

    return Stage5Result(
        answer=answer,
        mode=mode,
        trace_id=request_trace_id,
        context_id=request_context_id,
        total_seconds=total_seconds,
        discovery_seconds=discovery_seconds,
        request_seconds=request_seconds,
        route=route,
    )
