"""LangGraph agent pipeline: Router -> Specialist -> Authorize -> Execute ->
Save -> Embed. See app.agents.graph.run_agent for the entry point used by
the /api/agent/message Flask route.
"""
from app.ai.agents.graph import build_graph, run_agent

__all__ = ["build_graph", "run_agent"]
