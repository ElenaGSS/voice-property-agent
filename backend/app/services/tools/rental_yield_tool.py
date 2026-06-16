from typing import Any


TOOL_NAME = "Rental Yield Analyzer"


def should_use(context: dict[str, Any]) -> bool:
    has_value = bool(context.get("estimated_property_value") or context.get("sale_price"))
    has_rent = bool(context.get("monthly_rent"))
    return (has_value and has_rent) or context.get("goal") == "undecided"


def run(context: dict[str, Any]) -> dict[str, Any]:
    property_value = context.get("estimated_property_value") or context.get("sale_price")
    monthly_rent = context.get("monthly_rent")

    if not property_value or not monthly_rent:
        return {
            "tool_name": TOOL_NAME,
            "status": "insufficient_data",
            "reason": "Для анализа рентабельности нужны стоимость объекта и ожидаемая месячная аренда.",
        }

    annual_rent = monthly_rent * 12
    gross_yield_percent = (annual_rent / property_value) * 100
    payback_years = property_value / annual_rent if annual_rent else None

    return {
        "tool_name": TOOL_NAME,
        "status": "calculation_completed",
        "property_value": round(property_value, 2),
        "monthly_rent": round(monthly_rent, 2),
        "annual_rent": round(annual_rent, 2),
        "gross_yield_percent": round(gross_yield_percent, 2),
        "payback_years": round(payback_years, 1) if payback_years else None,
        "yield_category": _yield_category(gross_yield_percent),
    }


def _yield_category(gross_yield_percent: float) -> str:
    if gross_yield_percent < 3.5:
        return "low"
    if gross_yield_percent < 5.5:
        return "medium"
    return "high"
