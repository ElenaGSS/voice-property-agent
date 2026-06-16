from typing import Any


TOOL_NAME = "Tax Estimator Tool"
IRPF_BRACKETS: list[tuple[float | None, float]] = [
    (6000, 0.19),
    (50000, 0.21),
    (200000, 0.23),
    (300000, 0.27),
    (None, 0.30),
]


def should_use(context: dict[str, Any]) -> bool:
    has_sale_goal = context.get("goal") in {"sale", "undecided"}
    has_both_prices = bool(context.get("purchase_price") and context.get("sale_price"))
    has_price_signal = bool(context.get("purchase_price") or context.get("sale_price"))
    text = context.get("normalized_text", "")
    has_tax_context = any(word in text for word in ["beneficio", "ganancia", "profit", "прибыл", "налог", "ремонт", "расход"])
    return has_both_prices or (has_sale_goal and (has_price_signal or has_tax_context))


def run(context: dict[str, Any]) -> dict[str, Any]:
    sale_price = context.get("sale_price")
    purchase_price = context.get("purchase_price")
    deductible_expenses = context.get("deductible_expenses") or 0

    if not sale_price or not purchase_price:
        return {
            "tool_name": TOOL_NAME,
            "status": "insufficient_data",
            "reason": "Для ориентировочного налогового расчёта нужны цена покупки и цена продажи.",
        }

    estimated_gain = max(sale_price - purchase_price - deductible_expenses, 0)
    estimated_irpf = _calculate_irpf(estimated_gain)
    return {
        "tool_name": TOOL_NAME,
        "status": "calculation_completed",
        "sale_price": round(sale_price, 2),
        "purchase_price": round(purchase_price, 2),
        "deductible_expenses": round(deductible_expenses, 2),
        "estimated_capital_gain": round(estimated_gain, 2),
        "estimated_irpf": round(estimated_irpf, 2),
        "disclaimer": (
            "Ориентировочная симуляция, не налоговая и не юридическая консультация. "
            "Расчёт может не учитывать gastos deducibles, plusvalía municipal, exenciones "
            "и конкретную налоговую ситуацию."
        ),
    }


def _calculate_irpf(gain: float) -> float:
    remaining = gain
    previous_limit = 0.0
    tax = 0.0

    for limit, rate in IRPF_BRACKETS:
        if remaining <= 0:
            break
        if limit is None:
            taxable = remaining
        else:
            taxable = min(remaining, limit - previous_limit)
        tax += taxable * rate
        remaining -= taxable
        if limit is not None:
            previous_limit = limit

    return tax
