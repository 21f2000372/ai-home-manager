from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


INVARIANT_POLICY = """You are a household tool caller.
Perform only the current action.
Use exactly one selected tool when a state change or lookup is required.
Never invent IDs, amounts, dates, or permissions.
Use the tool schema for argument names and types.
If required information is missing, ask one concise clarification.
After a tool result, either finish or make one necessary follow-up call.
Return no chain-of-thought."""


@dataclass
class PromptContext:
    role: str = "Guest"
    tenant_id: str = "global"
    action: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, str]] = field(default_factory=list)
    entity_context: list[str] = field(default_factory=list)
    result: str = ""
    current_datetime: str = ""


class ToolPromptBuilder:
    def build(self, context: PromptContext) -> str:
        lines = [INVARIANT_POLICY, f"Role: {context.role}", f"Tenant: {context.tenant_id}"]
        lines.append(f"Current date/time: {context.current_datetime or 'not provided'}")
        lines.extend(["Action:", json.dumps(context.action, ensure_ascii=False, separators=(",", ":")), "Candidates:"])
        lines.extend(
            f"- {item.get('name', 'unknown')}: {item.get('purpose', '')}".strip()
            for item in context.candidates[:5]
        )
        if not context.candidates:
            lines.append("- none")
        if context.entity_context:
            lines.append("Context:")
            lines.extend(f"- {item}" for item in context.entity_context[:5])
        if context.result:
            lines.extend(["Latest result:", context.result[:500]])
        return "\n".join(lines)
