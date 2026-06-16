import logging
from typing import Any

from app.models.schemas import AnswerItem
from app.services.answer_extraction_service import extract_context
from app.services.tools import barcelona_market_tool, rental_yield_tool, tax_estimator_tool

logger = logging.getLogger(__name__)

TOOL_MODULES = [
    tax_estimator_tool,
    barcelona_market_tool,
    rental_yield_tool,
]
SUCCESS_STATUSES = {"success", "calculation_completed"}


def run_agent_tools(answers: list[AnswerItem]) -> dict[str, Any]:
    context = extract_context(answers)
    used_tools: list[str] = []
    tool_results: dict[str, dict[str, Any]] = {}

    for tool in TOOL_MODULES:
        if not tool.should_use(context):
            continue

        result = tool.run(context)
        tool_name = result.get("tool_name", tool.TOOL_NAME)
        tool_results[tool_name] = result
        if result.get("status") in SUCCESS_STATUSES:
            used_tools.append(tool_name)
        logger.info("Agent tool evaluated: %s status=%s", tool_name, result.get("status"))

    return {
        "used_tools": used_tools,
        "tool_results": tool_results,
        "extracted_context": context,
    }
