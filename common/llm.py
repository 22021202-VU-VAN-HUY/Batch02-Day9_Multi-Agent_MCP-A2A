"""Shared LLM factory for all agents.

Prefers Xiaomi MiMo when MIMO_API_KEY is configured and otherwise falls
back to OpenRouter. Both providers expose OpenAI-compatible APIs.
"""

import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    """Return a MiMo client when configured, otherwise use OpenRouter."""
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    mimo_api_key = os.getenv("MIMO_API_KEY", "").strip()

    if mimo_api_key:
        return ChatOpenAI(
            model=os.getenv("MIMO_MODEL", "mimo-v2.5-pro"),
            openai_api_key=mimo_api_key,
            openai_api_base=os.getenv(
                "MIMO_BASE_URL",
                "https://api.xiaomimimo.com/v1",
            ),
            max_tokens=max_tokens,
            temperature=temperature,
        )

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2-pro:free"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
        max_tokens=max_tokens,
        temperature=temperature,
    )
