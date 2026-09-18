from __future__ import annotations

from app.ai.agents.tools import document_tools
from app.ai.agents.tools import finance_tools
from app.ai.agents.tools import food_tools
from app.ai.agents.tools import maintenance_tools
from app.ai.agents.tools import tasks_tools


TOOLSETS = {
    "finance": finance_tools.TOOLS,
    "tasks": tasks_tools.TOOLS,
    "food": food_tools.TOOLS,
    "maintenance": maintenance_tools.TOOLS,
    "documents": document_tools.TOOLS,
    "general": [],
}


ALL_TOOLS_BY_NAME = {
    **finance_tools.TOOLS_BY_NAME,
    **tasks_tools.TOOLS_BY_NAME,
    **food_tools.TOOLS_BY_NAME,
    **maintenance_tools.TOOLS_BY_NAME,
    **document_tools.TOOLS_BY_NAME,
}