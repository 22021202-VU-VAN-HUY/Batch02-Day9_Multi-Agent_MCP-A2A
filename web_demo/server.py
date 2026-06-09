"""FastAPI backend and static host for the Stage 5 Vite demo."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from time import perf_counter
from typing import Literal

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

from common.stage5_client import ask_stage5

WEB_ROOT = Path(__file__).resolve().parent
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:10000")

app = FastAPI(title="Stage 5 A2A Demo API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    mode: Literal["customer", "direct-law"] = "customer"


async def _probe(
    client: httpx.AsyncClient,
    name: str,
    url: str,
) -> tuple[str, dict]:
    started = perf_counter()
    try:
        response = await client.get(url)
        response.raise_for_status()
        return name, {
            "online": True,
            "latency_ms": round((perf_counter() - started) * 1000, 1),
        }
    except Exception as exc:
        return name, {
            "online": False,
            "latency_ms": round((perf_counter() - started) * 1000, 1),
            "error": str(exc),
        }


@app.get("/api/health")
async def health() -> dict:
    endpoints = {
        "registry": f"{REGISTRY_URL}/health",
        "customer": f"{os.getenv('CUSTOMER_AGENT_URL', 'http://localhost:10100')}/.well-known/agent.json",
        "law": "http://localhost:10101/.well-known/agent.json",
        "tax": "http://localhost:10102/.well-known/agent.json",
        "compliance": "http://localhost:10103/.well-known/agent.json",
    }
    async with httpx.AsyncClient(timeout=2.5) as client:
        pairs = await asyncio.gather(
            *(_probe(client, name, url) for name, url in endpoints.items())
        )
    services = dict(pairs)
    return {
        "ready": all(service["online"] for service in services.values()),
        "services": services,
    }


@app.post("/api/query")
async def query(payload: QueryRequest) -> dict:
    try:
        result = await ask_stage5(payload.question, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Stage 5 request failed: {exc}",
        ) from exc
    return result.to_dict()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


app.mount("/src", StaticFiles(directory=WEB_ROOT / "src"), name="src")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
