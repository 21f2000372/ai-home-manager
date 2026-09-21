from __future__ import annotations

import re
from typing import Any

from app.ai.agents.permissions import TOOL_DOMAINS, is_authorized
from app.ai.agents.tools import ALL_TOOLS_BY_NAME
from app.models.enums import HouseholdRole


class ToolCatalogRepository:
    """Retrieve role-safe tool candidates from the indexed catalog."""

    def __init__(self, rag_service: Any) -> None:
        self._rag = rag_service

    def search(
        self,
        query_text: str,
        *,
        role: HouseholdRole | str,
        tenant_id: str = "global",
        domain: str | None = None,
        n_results: int = 5,
        include_global: bool = True,
    ) -> list[dict[str, Any]]:
        if not query_text.strip():
            return []
        role_value = role.value if isinstance(role, HouseholdRole) else str(role)
        result = self._rag.retrieve(
            query_text,
            role=HouseholdRole(role_value),
            tenant_id=tenant_id,
            n_results=max(n_results, 3),
            source_domain="tool_catalog",
            include_global=include_global,
            content_types=["tool"],
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        candidates = []
        for group_index, docs in enumerate(documents):
            metadata_group = metadatas[group_index] if group_index < len(metadatas) else []
            for index, text in enumerate(docs):
                metadata = metadata_group[index] if index < len(metadata_group) else {}
                name = str(metadata.get("tool_name") or "").strip()
                tool_domain = str(metadata.get("tool_domain") or "").strip()
                if not name:
                    match = re.search(r"Tool:\s*([A-Za-z0-9_]+)", text)
                    name = match.group(1) if match else ""
                tool_domain = tool_domain or TOOL_DOMAINS.get(name, "")
                if name not in ALL_TOOLS_BY_NAME or not tool_domain:
                    continue
                if domain and tool_domain != domain:
                    continue
                if not is_authorized(role_value, tool_domain, name):
                    continue
                normalized_query = query_text.lower()
                score = (8 if name.lower() in normalized_query else 0) + sum(
                    token in normalized_query for token in (name.lower().split("_"))
                )
                score += sum(token in normalized_query for token in text.lower().split()) * 0.01
                candidates.append({
                    "tool_name": name,
                    "tool_domain": tool_domain,
                    "score": score,
                    "summary": text[:180],
                })
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[:n_results]
