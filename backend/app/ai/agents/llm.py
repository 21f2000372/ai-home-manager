"""LangChain-compatible LLM client bound to OpenRouter.

This module is the single construction point for chat-model clients and also
provides lightweight per-call telemetry. The telemetry deliberately lives at
this boundary so planner/specialist/document nodes can be compared before and
after optimization without changing their business contracts.

Compatibility target: Python 3.8+.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from time import perf_counter
from typing import Any, Dict, Iterable, Optional

from langchain_openai import ChatOpenAI

from app.config import config


logger = logging.getLogger(__name__)


def _input_chars(messages: Iterable[Any]) -> int:
    total = 0
    for message in messages:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            total += len(content)
        else:
            total += len(str(content or ""))
    return total


def _usage_metadata(result: Any) -> Dict[str, Optional[int]]:
    """Extract token usage when the response exposes it."""

    usage = getattr(result, "usage_metadata", None)
    if isinstance(usage, dict):
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }

    response_metadata = getattr(result, "response_metadata", None)
    if isinstance(response_metadata, dict):
        token_usage = (
            response_metadata.get("token_usage")
            or response_metadata.get("usage")
        )
        if isinstance(token_usage, dict):
            input_tokens = (
                token_usage.get("input_tokens")
                or token_usage.get("prompt_tokens")
            )
            output_tokens = (
                token_usage.get("output_tokens")
                or token_usage.get("completion_tokens")
            )
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": token_usage.get("total_tokens"),
            }

    return {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }


def invoke_with_telemetry(
    runnable: Any,
    messages: Iterable[Any],
    *,
    node: str,
) -> Any:
    """Invoke one LLM runnable and log latency/token information.

    The return type is untouched, so structured-output nodes continue to
    receive their current Pydantic objects.
    """

    materialized_messages = list(messages)
    input_chars = _input_chars(materialized_messages)
    started = perf_counter()

    try:
        result = runnable.invoke(materialized_messages)
    except Exception:
        latency_ms = round((perf_counter() - started) * 1000.0, 1)
        logger.exception(
            "llm_call node=%s status=error latency_ms=%s input_chars=%s",
            node,
            latency_ms,
            input_chars,
        )
        raise

    latency_ms = round((perf_counter() - started) * 1000.0, 1)
    usage = _usage_metadata(result)

    logger.info(
        "llm_call node=%s status=ok latency_ms=%s input_chars=%s "
        "input_tokens=%s output_tokens=%s total_tokens=%s",
        node,
        latency_ms,
        input_chars,
        usage["input_tokens"],
        usage["output_tokens"],
        usage["total_tokens"],
    )

    return result


@lru_cache(maxsize=None)
def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """Return a cached ChatOpenAI instance pointed at OpenRouter."""

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
        max_tokens=4096,
    )
