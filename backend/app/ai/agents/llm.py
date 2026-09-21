"""LangChain-compatible LLM client bound to OpenRouter.

OpenRouter exposes an OpenAI-compatible /chat/completions endpoint, so we
reuse langchain_openai.ChatOpenAI by pointing base_url at OpenRouter and
authenticating with the OpenRouter API key already read into app.config.
This gives every agent node tool-binding and structured output for free.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import config


@lru_cache(maxsize=None)
def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """Return a cached ChatOpenAI instance pointed at OpenRouter.

    Cached per temperature so nodes that want deterministic routing
    (temperature=0 for intent classification) and nodes that want more
    natural phrasing (e.g. 0.3 for the final response) don't share a client
    config or clobber each other's settings.
    """
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to your .env before running "
            "any agent node that calls the LLM."
        )
    return ChatOpenAI(
        model=config.OPENROUTER_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        temperature=temperature,
    )
