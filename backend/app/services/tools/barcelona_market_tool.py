import json
import re
import unicodedata
from pathlib import Path
from typing import Any


TOOL_NAME = "Barcelona Market Data Tool"
DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "barcelona_market_data.json"


def should_use(context: dict[str, Any]) -> bool:
    has_location = bool(context.get("district") or context.get("district_query"))
    return bool(has_location and context.get("area_m2") and context.get("sale_price"))


def run(context: dict[str, Any]) -> dict[str, Any]:
    district = context.get("district") or context.get("district_query")
    area_m2 = context.get("area_m2")
    sale_price = context.get("sale_price")

    if not district or not area_m2 or not sale_price:
        return {
            "tool_name": TOOL_NAME,
            "status": "insufficient_data",
            "reason": "Для рыночного сравнения нужны район, площадь и ожидаемая цена продажи.",
        }

    dataset = _load_dataset()
    district_data = _find_district(dataset, district)
    if not district_data:
        return {
            "tool_name": TOOL_NAME,
            "status": "insufficient_data",
            "reason": "Район не найден в локальной базе",
        }

    object_price_m2 = sale_price / area_m2
    district_avg = district_data["avg_price_m2"]
    deviation_percent = ((object_price_m2 - district_avg) / district_avg) * 100
    market_position = _market_position(deviation_percent)

    return {
        "tool_name": TOOL_NAME,
        "status": "calculation_completed",
        "district": district_data["district"],
        "area_m2": round(area_m2, 2),
        "sale_price": round(sale_price, 2),
        "object_price_m2": round(object_price_m2, 2),
        "district_avg_price_m2": district_avg,
        "deviation_percent": round(deviation_percent, 2),
        "market_position": market_position,
        "estimated_sale_time": _estimated_sale_time(market_position),
        "confidence": district_data.get("confidence", "medium"),
        "dataset_updated_at": district_data.get("updated_at") or dataset.get("updated_at"),
        "disclaimer": dataset.get("source_note"),
    }


def _load_dataset() -> dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _find_district(dataset: dict[str, Any], district: str) -> dict[str, Any] | None:
    normalized_district = _normalize(district)
    for item in dataset.get("districts", []):
        candidates = [item.get("district", ""), *item.get("aliases", [])]
        if any(_normalize(candidate) in normalized_district or normalized_district in _normalize(candidate) for candidate in candidates):
            return item
    return None


def _normalize(value: str) -> str:
    lowered = value.lower().replace("ё", "е")
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    without_dashes = re.sub(r"[-‐‑‒–—―]", " ", without_accents)
    return re.sub(r"\s+", " ", without_dashes).strip()


def _market_position(deviation_percent: float) -> str:
    if deviation_percent < -5:
        return "below_market"
    if deviation_percent <= 10:
        return "near_market"
    if deviation_percent <= 20:
        return "above_market"
    return "strongly_above_market"


def _estimated_sale_time(position: str) -> str:
    return {
        "below_market": "1–3 месяца",
        "near_market": "2–4 месяца",
        "above_market": "4–8 месяцев",
        "strongly_above_market": "8+ месяцев / нужна корректировка стратегии",
    }[position]
