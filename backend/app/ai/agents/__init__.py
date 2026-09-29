"""LangGraph agent package.

Keep package import side-effect free.

Important:
Importing a lightweight submodule such as ``app.ai.agents.permissions`` must
not eagerly import the full LangGraph graph. The document-ingestion layer uses
the permission module, while the graph imports document_flow -> ingestion, so
an eager graph import here creates a circular import.

The public ``build_graph`` and ``run_agent`` entry points are preserved through
small lazy wrappers.
"""
from __future__ import annotations

from typing import Any, Optional


def build_graph() -> Any:
    """Lazily import and build the LangGraph application graph."""

    from app.ai.agents.graph import build_graph as _build_graph

    return _build_graph()


def run_agent(
    *,
    message: str,
    session_id: str,
    user_id: str,
    role: str,
    conversation_id: Optional[str] = None,
    uploaded_file: Any = None,
) -> Any:
    """Lazily invoke the agent graph while preserving the existing API."""

    from app.ai.agents.graph import run_agent as _run_agent

    return _run_agent(
        message=message,
        session_id=session_id,
        user_id=user_id,
        role=role,
        conversation_id=conversation_id,
        uploaded_file=uploaded_file,
    )


__all__ = [
    "build_graph",
    "run_agent",
]
