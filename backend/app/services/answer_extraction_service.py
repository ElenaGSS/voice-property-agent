import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.models.schemas import AnswerItem


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "barcelona_market_data.json"
DISTRICT_ALIASES: dict[str, list[str]] = {
    "Eixample": ["eixample", "l'eixample", "эшампле", "эйшампле", "ешампле", "ensanche"],
    "Gràcia": ["gracia", "gràcia"],
    "Horta-Guinardó": ["horta-guinardo", "horta-guinardó", "guinardo", "guinardó", "horta"],
    "Sant Martí": ["sant marti", "sant martí", "сан марти", "сант марти", "poblenou", "diagonal mar"],
    "Sants-Montjuïc": ["sants-montjuic", "sants-montjuïc", "sants", "montjuic", "montjuïc"],
    "Les Corts": ["les corts"],
    "Sarrià-Sant Gervasi": ["sarria", "sarrià", "sant gervasi", "sarria-sant gervasi", "sarrià-sant gervasi"],
    "Nou Barris": ["nou barris"],
    "Ciutat Vella": ["ciutat vella", "gotic", "gòtic", "raval", "born", "barceloneta"],
    "Sant Andreu": ["sant andreu", "сан андреу", "сант андреу"],
}

PURCHASE_QUESTION_MARKERS = [
    "покупали",
    "покупка",
    "купили",
    "купили объект",
    "за сколько вы покупали",
    "purchase",
    "compra",
]
SALE_QUESTION_MARKERS = [
    "продавать",
    "продажи",
    "планируете продавать",
    "ожидаемая цена продажи",
    "venta",
    "vender",
    "sale price",
]
RENT_QUESTION_MARKERS = [
    "месячной аренды",
    "аренда",
    "арендная плата",
    "monthly rent",
    "alquiler",
]
AREA_QUESTION_MARKERS = ["площадь", "м²", "м2", "metros", "area"]
DISTRICT_QUESTION_MARKERS = ["район", "локац", "location", "district", "zona", "barrio"]
CONTACT_QUESTION_MARKERS = ["телефон", "email", "связи", "contact", "phone"]
INVALID_CONTACT_TEXT = "Номер распознан некорректно. Введите вручную или повторите запись."
NEGATIVE_RENT_MARKERS = [
    "-",
    "—",
    "не знаю",
    "не рассматриваю",
    "не рассматриваю аренду",
    "нет",
    "n/a",
]
FINAL_PUNCTUATION_PATTERN = re.compile(r"[\s.,!?;:]+$")
MARKDOWN_EMAIL_PATTERN = re.compile(
    r"\[[^\]\s]+@[^\]\s]+\]\(mailto:[^)]+\)",
    flags=re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
    flags=re.IGNORECASE,
)
RUSSIAN_NUMBER_WORDS: dict[str, float] = {
    "ноль": 0,
    "один": 1,
    "одна": 1,
    "одно": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
    "сто": 100,
    "двести": 200,
    "триста": 300,
    "четыреста": 400,
    "пятьсот": 500,
    "шестьсот": 600,
    "семьсот": 700,
    "восемьсот": 800,
    "девятьсот": 900,
}
RUSSIAN_HALF_WORDS = {"полтора", "полторы"}
RUSSIAN_THOUSAND_WORDS = {"тысяча", "тысячи", "тысяч"}
RUSSIAN_MILLION_WORDS = {"миллион", "миллиона", "миллионов"}


def extract_context(answers: list[AnswerItem]) -> dict[str, Any]:
    normalized_pairs = [
        (item.question, normalize_numeric_answer(item.question, item.answer))
        for item in answers
    ]
    answer_text = " ".join(answer for _, answer in normalized_pairs)
    qa_text = " ".join(f"{question} {answer}" for question, answer in normalized_pairs)
    normalized_answer_text = _normalize(answer_text)
    normalized_qa_text = _normalize(qa_text)
    qa_values = _extract_values_from_question_answers(answers)

    goal = _extract_goal(normalized_qa_text)
    district_query = qa_values.get("district_query")
    district = _extract_district(normalized_answer_text) or (
        _extract_district(str(district_query)) if district_query else None
    )
    area_m2 = qa_values.get("area_m2") or _extract_area_m2(normalized_answer_text)
    monthly_rent = qa_values.get("monthly_rent") or _extract_money_near(
        normalized_answer_text,
        ["alquiler", "renta", "mensual", "mes", "arriendo", "alquilar", "аренда", "аренд", "месяц", "сдать"],
        max_value=20000,
        prefer="min",
    )
    purchase_price = qa_values.get("purchase_price") or _extract_money_near(
        normalized_answer_text,
        ["compra", "compre", "comprado", "purchase", "купил", "купила", "покуп", "приобрет"],
        min_value=20000,
    )
    sale_price = qa_values.get("sale_price") or _extract_money_near(
        normalized_answer_text,
        ["venta", "vender", "precio", "sale", "прод", "цена", "ожида", "стоимость"],
        min_value=20000,
        prefer="max",
    )
    deductible_expenses = _extract_money_near(
        normalized_answer_text,
        ["gastos", "reforma", "reformas", "renovacion", "renovación", "ремонт", "расход"],
        min_value=1000,
        max_value=200000,
    )

    if goal == "rent" and sale_price and not monthly_rent and sale_price < 20000:
        monthly_rent = sale_price
        sale_price = None

    estimated_property_value = sale_price or _extract_money_near(
        normalized_answer_text,
        ["valor", "value", "стоимость", "оцениваю"],
        min_value=20000,
    )

    return {
        "answers_text": answer_text,
        "normalized_text": normalized_answer_text,
        "goal": goal,
        "district": district,
        "district_query": district_query,
        "sale_price": sale_price,
        "purchase_price": purchase_price,
        "deductible_expenses": deductible_expenses or 0,
        "area_m2": area_m2,
        "monthly_rent": monthly_rent,
        "estimated_property_value": estimated_property_value,
    }


def normalize_numeric_answer(question_text: str, answer_text: str) -> str:
    clean_answer = answer_text.strip()
    if not clean_answer:
        return clean_answer

    question = _normalize(question_text)
    is_area_question = _contains_any(question, AREA_QUESTION_MARKERS)
    is_purchase_question = _contains_any(question, PURCHASE_QUESTION_MARKERS)
    is_sale_question = _contains_any(question, SALE_QUESTION_MARKERS)
    is_rent_question = _contains_any(question, RENT_QUESTION_MARKERS)

    if not any([is_area_question, is_purchase_question, is_sale_question, is_rent_question]):
        return clean_answer
    if is_rent_question and _is_negative_rent_answer(_normalize(clean_answer)):
        return clean_answer

    normalized_answer = _normalize(clean_answer)
    numeric_value: float | None = None

    if is_area_question:
        numeric_value = (
            _extract_area_m2(normalized_answer)
            or _extract_number_value(normalized_answer, min_value=10, max_value=1000)
            or _extract_russian_number_value(normalized_answer, min_value=10, max_value=1000)
        )
        return f"{_format_normalized_number(numeric_value)} м2" if numeric_value else clean_answer

    if is_rent_question:
        numeric_value = _extract_number_value(
            normalized_answer,
            min_value=100,
            max_value=20000,
            prefer="min",
        ) or _extract_russian_number_value(normalized_answer, min_value=100, max_value=20000)
        return _format_normalized_number(numeric_value) if numeric_value else clean_answer

    if is_purchase_question or is_sale_question:
        numeric_value = _extract_number_value(
            normalized_answer,
            min_value=20000,
            prefer="max",
        ) or _extract_russian_number_value(normalized_answer, min_value=20000)
        return _format_normalized_number(numeric_value) if numeric_value else clean_answer

    return clean_answer


def clean_transcribed_text(question_text: str, answer_text: str) -> str:
    if _is_contact_question(question_text):
        return normalize_contact_answer(question_text, answer_text)
    numeric_answer = normalize_numeric_answer(question_text, answer_text)
    if numeric_answer != answer_text.strip():
        return numeric_answer
    return _strip_final_punctuation(answer_text.strip())


def normalize_contact_answer(question_text: str, answer_text: str) -> str:
    clean_answer = _strip_final_punctuation(answer_text.strip())
    if not clean_answer:
        return clean_answer
    if not _is_contact_question(question_text):
        return clean_answer

    markdown_email = MARKDOWN_EMAIL_PATTERN.search(clean_answer)
    if markdown_email:
        return _strip_final_punctuation(markdown_email.group(0))

    email = EMAIL_PATTERN.search(clean_answer)
    if email:
        return _strip_final_punctuation(email.group(0))

    phone = _normalize_phone_candidate(clean_answer)
    if not phone:
        return clean_answer

    digits = re.sub(r"\D", "", phone)
    if len(digits) > 15:
        return INVALID_CONTACT_TEXT
    if len(digits) == 9:
        return digits
    if len(digits) == 11 and digits.startswith("34"):
        return f"+{digits}" if phone.startswith("+") else digits
    if 10 <= len(digits) <= 15:
        return f"+{digits}" if phone.startswith("+") else digits
    return clean_answer


def _is_contact_question(question_text: str) -> bool:
    return _contains_any(_normalize(question_text), CONTACT_QUESTION_MARKERS)


def _strip_final_punctuation(value: str) -> str:
    return FINAL_PUNCTUATION_PATTERN.sub("", value).strip()


def _normalize_phone_candidate(value: str) -> str:
    compact = re.sub(r"[\s,.\-()]+", "", value.strip())
    compact = re.sub(r"(?!^\+)\D", "", compact)
    if compact.startswith("+"):
        return "+" + re.sub(r"\D", "", compact[1:])
    return re.sub(r"\D", "", compact)


def _extract_values_from_question_answers(answers: list[AnswerItem]) -> dict[str, float | str | None]:
    values: dict[str, float | str | None] = {
        "purchase_price": None,
        "sale_price": None,
        "monthly_rent": None,
        "area_m2": None,
        "district_query": None,
    }

    for item in answers:
        question = _normalize(item.question)
        normalized_answer = normalize_numeric_answer(item.question, item.answer)
        answer = _normalize(normalized_answer)

        if _contains_any(question, PURCHASE_QUESTION_MARKERS):
            values["purchase_price"] = values["purchase_price"] or _extract_number_value(
                answer,
                min_value=20000,
                prefer="max",
            )

        if _contains_any(question, SALE_QUESTION_MARKERS):
            values["sale_price"] = values["sale_price"] or _extract_number_value(
                answer,
                min_value=20000,
                prefer="max",
            )

        if _contains_any(question, RENT_QUESTION_MARKERS) and not _is_negative_rent_answer(answer):
            values["monthly_rent"] = values["monthly_rent"] or _extract_number_value(
                answer,
                min_value=100,
                max_value=20000,
                prefer="min",
            )

        if _contains_any(question, AREA_QUESTION_MARKERS):
            values["area_m2"] = values["area_m2"] or _extract_area_m2(answer) or _extract_number_value(
                answer,
                min_value=10,
                max_value=1000,
                prefer="first",
            )

        if _contains_any(question, DISTRICT_QUESTION_MARKERS) and answer.strip():
            values["district_query"] = values["district_query"] or item.answer.strip()

    return values


def _contains_any(text: str, markers: list[str]) -> bool:
    return any(_normalize(marker) in text for marker in markers)


def _is_negative_rent_answer(answer: str) -> bool:
    clean = answer.strip()
    if not clean:
        return True
    return any(marker in clean for marker in NEGATIVE_RENT_MARKERS)


def _normalize(value: str) -> str:
    lowered = value.lower().replace("ё", "е")
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    without_dashes = re.sub(r"[-‐‑‒–—―'’`´]", " ", without_accents)
    return re.sub(r"\s+", " ", without_dashes).strip()


def _extract_goal(text: str) -> str:
    sale = any(word in text for word in ["прод", "venta", "vender", "sell"])
    rent = any(word in text for word in ["сдать", "аренд", "alquiler", "alquilar", "rent"])
    undecided = any(
        phrase in text
        for phrase in [
            "продать или сдать",
            "сдать или продать",
            "venta o alquiler",
            "vender o alquilar",
            "alquilar o vender",
        ]
    )
    if undecided or (sale and rent):
        return "undecided"
    if sale:
        return "sale"
    if rent:
        return "rent"
    return "unknown"


def _extract_district(text: str) -> str | None:
    normalized = _normalize(text)
    for district, aliases in _district_aliases().items():
        if any(_normalize(alias) in normalized for alias in aliases):
            return district
    return None


def _district_aliases() -> dict[str, list[str]]:
    aliases = {district: [district, *items] for district, items in DISTRICT_ALIASES.items()}
    try:
        with DATA_PATH.open("r", encoding="utf-8") as file:
            dataset = json.load(file)
        for item in dataset.get("districts", []):
            district = item.get("district")
            if not district:
                continue
            district_aliases = aliases.setdefault(district, [district])
            for alias in item.get("aliases", []):
                if alias not in district_aliases:
                    district_aliases.append(alias)
    except (OSError, json.JSONDecodeError):
        return aliases
    return aliases


def _extract_area_m2(text: str) -> float | None:
    pattern = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:m2|m²|metros?|кв\.?\s*м|м2|квадрат(?:ов|а|ные)?|sqm)")
    matches = pattern.findall(text)
    for match in matches:
        value = _parse_number(match)
        if value and 10 <= value <= 1000:
            return value
    return None


def _extract_money_near(
    text: str,
    keywords: list[str],
    min_value: float | None = None,
    max_value: float | None = None,
    prefer: str = "nearest",
) -> float | None:
    candidates: list[tuple[int, float]] = []
    number_pattern = re.compile(
        r"(?P<number>\d{1,3}(?:[ .]\d{3})+|\d+(?:[.,]\d+)?)\s*"
        r"(?P<mil>mil|тыс\.?|тысяч|k)?\s*"
        r"(?P<currency>eur|euro|euros|€|евро)?"
    )
    direct_candidates = _direct_money_candidates(text, keywords, number_pattern, min_value, max_value)
    if direct_candidates:
        if prefer == "max":
            return max(direct_candidates)
        if prefer == "min":
            return min(direct_candidates)
        return direct_candidates[0]

    for match in number_pattern.finditer(text):
        value = _parse_number(match.group("number"))
        if not value:
            continue
        has_money_marker = bool(match.group("mil") or match.group("currency"))
        if not has_money_marker and value < 1000:
            continue
        if match.group("mil") and value < 10000:
            value *= 1000
        if min_value is not None and value < min_value:
            continue
        if max_value is not None and value > max_value:
            continue

        start, end = match.span()
        window = text[max(0, start - 70) : min(len(text), end + 70)]
        keyword_distances = []
        for keyword in keywords:
            for keyword_match in re.finditer(re.escape(keyword), window):
                keyword_start = max(0, start - 70) + keyword_match.start()
                keyword_end = max(0, start - 70) + keyword_match.end()
                keyword_distances.append(min(abs(keyword_start - start), abs(keyword_end - end)))

        if keyword_distances:
            distance = min(keyword_distances)
            candidates.append((distance, value))

    if candidates:
        if prefer == "max":
            return max(value for _, value in candidates)
        if prefer == "min":
            return min(value for _, value in candidates)
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]
    return None


def _extract_number_value(
    text: str,
    min_value: float | None = None,
    max_value: float | None = None,
    prefer: str = "first",
) -> float | None:
    number_pattern = re.compile(
        r"(?P<number>\d{1,3}(?:[ .]\d{3})+|\d+(?:[.,]\d+)?)\s*"
        r"(?P<mil>mil|тыс\.?|тысяч|k)?\s*"
        r"(?P<currency>eur|euro|euros|€|евро)?"
    )
    values: list[float] = []
    for match in number_pattern.finditer(text):
        value = _parse_number(match.group("number"))
        if not value:
            continue
        if match.group("mil") and value < 10000:
            value *= 1000
        if min_value is not None and value < min_value:
            continue
        if max_value is not None and value > max_value:
            continue
        values.append(value)

    if not values:
        return None
    if prefer == "max":
        return max(values)
    if prefer == "min":
        return min(values)
    return values[0]


def _extract_russian_number_value(
    text: str,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float | None:
    tokens = re.sub(r"[.,!?;:€]", " ", _normalize(text)).split()
    total = 0.0
    current = 0.0
    found = False

    for token in tokens:
        if token in RUSSIAN_NUMBER_WORDS:
            current += RUSSIAN_NUMBER_WORDS[token]
            found = True
            continue
        if token in RUSSIAN_HALF_WORDS:
            current += 1.5
            found = True
            continue
        if token in RUSSIAN_THOUSAND_WORDS:
            total += (current or 1) * 1000
            current = 0.0
            found = True
            continue
        if token in RUSSIAN_MILLION_WORDS:
            total += (current or 1) * 1_000_000
            current = 0.0
            found = True
            continue

    if not found:
        return None

    value = total + current
    if min_value is not None and value < min_value:
        return None
    if max_value is not None and value > max_value:
        return None
    return value


def _format_normalized_number(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def _direct_money_candidates(
    text: str,
    keywords: list[str],
    number_pattern: re.Pattern[str],
    min_value: float | None,
    max_value: float | None,
) -> list[float]:
    candidates: list[float] = []
    for keyword in keywords:
        for keyword_match in re.finditer(re.escape(keyword), text):
            after = text[keyword_match.end() : keyword_match.end() + 45]
            before = text[max(0, keyword_match.start() - 45) : keyword_match.start()]
            segment_matches = [
                list(number_pattern.finditer(after))[:1],
                list(number_pattern.finditer(before))[-1:],
            ]
            for matches in segment_matches:
                if not matches:
                    continue
                number_match = matches[0]
                value = _money_value_from_match(number_match)
                if value:
                    if min_value is not None and value < min_value:
                        continue
                    if max_value is not None and value > max_value:
                        continue
                    candidates.append(value)
    return candidates


def _money_value_from_match(match: re.Match[str]) -> float | None:
    value = _parse_number(match.group("number"))
    if not value:
        return None
    has_money_marker = bool(match.group("mil") or match.group("currency"))
    if not has_money_marker and value < 1000:
        return None
    if match.group("mil") and value < 10000:
        value *= 1000
    return value


def _parse_number(value: str) -> float | None:
    clean = value.strip().replace("\u00a0", " ")
    if not clean:
        return None

    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+", clean):
        clean = clean.replace(" ", "").replace(".", "")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+", clean):
        clean = clean.replace(",", "")
    else:
        clean = clean.replace(" ", "").replace(",", ".")
        if clean.count(".") > 1:
            clean = clean.replace(".", "")
        elif "." in clean:
            left, right = clean.split(".", 1)
            if len(right) == 3 and len(left) <= 3:
                clean = left + right

    try:
        return float(clean)
    except ValueError:
        return None
