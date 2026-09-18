"""Chat endpoint that runs a household message through the LangGraph agent
pipeline: Router -> Specialist -> Authorize -> Execute -> Save -> Embed.
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.ai.agents.graph import run_agent
from app.auth.decorators import login_required

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")


@agent_bp.route("/message", methods=["POST"])
@login_required
def send_message():
    """Send a chat message through the full agent pipeline for the logged-in user."""
    data = request.get_json() or {}
    message = data.get("message")
    session_id = data.get("session_id") or g.current_user.user_id
    conversation_id = data.get("conversation_id")

    if not message:
        return jsonify({"error": "message is required"}), 400

    result = run_agent(
        message=message,
        session_id=session_id,
        user_id=g.current_user.user_id,
        role=g.current_role.value,
        conversation_id=conversation_id,
    )

    
    body = {
        "response": result.get("response"),
        "planned_actions": result.get("planned_actions", []),
        "interaction_id": result.get("interaction_id"),
        "conversation_id": result.get("conversation_id"),
        "error": result.get("auth_error"),
    }

    return jsonify(body), 200
