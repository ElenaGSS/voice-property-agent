import json
import logging
import os
import re
from typing import Any

from app.models.schemas import AnswerItem, ClientCard, LeadScore

logger = logging.getLogger(__name__)


SUCCESS_TOOL_STATUSES = {"success", "calculation_completed"}

DEMO_INTERVIEW_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Как вас зовут?",
        "Какой телефон или email удобен для связи?",
        "В каком районе Барселоны находится квартира? Например: Гинардо, Эшампле, Грасия, Сан Андреу, Сантс, Лес Кортс.",
        "Какая площадь квартиры в м²?",
        "За сколько вы покупали квартиру?",
        "За сколько вы планируете продавать квартиру?",
        "Какая предполагаемая стоимость месячной аренды?",
    ],
}

FULL_INTERVIEW_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Как вас зовут?",
        "Какой телефон или email удобен для связи?",
        "Вы единственный собственник объекта или есть другие собственники?",
    ],
    2: [
        "В каком районе Барселоны находится объект?",
        "Какой это объект: квартира, дом, помещение? В каком он состоянии?",
        "Какая площадь объекта в м² и сколько комнат?",
    ],
    3: [
        "Что вы рассматриваете: продажу, аренду или оба варианта?",
        "За сколько вы покупали объект? Если не помните точно, укажите примерно.",
        "За сколько вы планируете продавать объект?",
    ],
    4: [
        "Какая предполагаемая стоимость месячной аренды?",
        "Что для вас сейчас важнее: продать быстрее, получить максимальную цену, понять налоги или проконсультироваться по аренде?",
        "Есть ли важные обстоятельства: ипотека, арендаторы, наследство, ремонт, срочность или другие вопросы?",
    ],
}

INTERVIEW_MODE = os.getenv("INTERVIEW_MODE", "demo").strip().lower()
BASE_QUESTIONS = (
    FULL_INTERVIEW_QUESTIONS if INTERVIEW_MODE == "full" else DEMO_INTERVIEW_QUESTIONS
)
MAX_ROUNDS = len(BASE_QUESTIONS)
QUESTIONS_PER_ROUND = max(len(questions) for questions in BASE_QUESTIONS.values())
TOTAL_QUESTIONS = sum(len(questions) for questions in BASE_QUESTIONS.values())
LAST_QUESTION_INDEX = len(BASE_QUESTIONS[MAX_ROUNDS]) - 1


def _answers_text(answers: list[AnswerItem]) -> str:
    return "\n".join(
        f"Раунд {item.round}. Вопрос: {item.question}\nОтвет: {item.answer}"
        for item in answers
    )


def _combined_answers(answers: list[AnswerItem]) -> str:
    return " ".join(item.answer.lower() for item in answers)


def _safe_first(value: str | None, fallback: str = "Не указано") -> str:
    if not value:
        return fallback
    clean = value.strip()
    return clean or fallback


def _find_by_question(answers: list[AnswerItem], fragments: list[str]) -> str:
    for item in answers:
        question = item.question.lower()
        if any(fragment in question for fragment in fragments):
            return item.answer
    return "Не указано"


def _infer_goal(answers: list[AnswerItem]) -> str:
    text = _combined_answers(answers)
    if any(word in text for word in ["сдать", "аренда", "аренд", "сдаю", "сдана"]):
        return "Аренда"
    if any(word in text for word in ["продать", "продажа", "продаю", "сделка"]):
        return "Продажа"
    fallback = _find_by_question(answers, ["продать", "сдать", "хотите сделать", "рассматриваете"])
    if fallback == "Не указано" and INTERVIEW_MODE != "full":
        return "Продажа + возможная аренда"
    return fallback


def _build_client_card(answers: list[AnswerItem]) -> ClientCard:
    property_type = _find_by_question(answers, ["тип недвижимости", "какой это объект"])
    if property_type == "Не указано" and INTERVIEW_MODE != "full":
        property_type = "Квартира"

    return ClientCard(
        name=_find_by_question(answers, ["как вас зовут", "имя"]),
        contact=_find_by_question(answers, ["телефон", "email", "связи"]),
        ownership_status=_find_by_question(
            answers, ["единственный собственник", "другие собственники", "собственники"]
        ),
        property_type=property_type,
        location=_find_by_question(answers, ["где находится", "локац", "адрес", "район"]),
        goal=_infer_goal(answers),
        expected_price=_find_by_question(
            answers,
            ["цену", "арендную плату", "ожидаете", "планируете продавать", "стоимость месячной аренды"],
        ),
    )


def _score_lead(answers: list[AnswerItem]) -> LeadScore:
    text = _combined_answers(answers)
    hot_words = ["срочно", "быстро", "готов", "в ближайшее", "уже прода", "уже сда"]
    warm_words = ["думаю", "планирую", "хочу понять", "интересно", "возможно"]
    concern_words = ["боюсь", "опас", "комисс", "сомнен", "не уверен"]

    if any(word in text for word in hot_words):
        return LeadScore(
            label="HOT",
            title="Горячий лид",
            reason="Собственник показывает срочность или готовность к сделке.",
        )
    if any(word in text for word in concern_words):
        return LeadScore(
            label="WARM",
            title="Тёплый лид",
            reason="Есть интерес, но нужно закрыть сомнения по процессу или условиям.",
        )
    if any(word in text for word in warm_words) or len(answers) >= 6:
        return LeadScore(
            label="WARM",
            title="Тёплый лид",
            reason="Собственник дал достаточно контекста и рассматривает дальнейшие шаги.",
        )
    return LeadScore(
        label="INFO",
        title="Информационный запрос",
        reason="Пока недостаточно признаков срочности или готовности к сотрудничеству.",
    )


def analyze_round(answers: list[AnswerItem]) -> str:
    if _has_openai_key():
        prompt = (
            "Сделай краткое резюме ответов собственника недвижимости на русском. "
            "Выдели объект, цель, мотивацию, риски и возможные уточнения.\n\n"
            f"{_answers_text(answers)}"
        )
        llm_result = _call_openai_text(prompt)
        if llm_result:
            return llm_result

    text = _combined_answers(answers)
    signals: list[str] = []
    if "срочно" in text or "быстро" in text:
        signals.append("есть срочность")
    if "комисс" in text:
        signals.append("есть чувствительность к комиссии")
    if "сдан" in text or "аренд" in text:
        signals.append("есть арендный контекст")
    if "прод" in text:
        signals.append("есть намерение продажи")
    return "Fallback-анализ: " + (", ".join(signals) if signals else "ответы собраны, явных сигналов мало")


def generate_adaptive_question(
    answers: list[AnswerItem], current_round: int, current_question_index: int
) -> str:
    next_round, next_index = get_next_position(current_round, current_question_index)
    if next_round > MAX_ROUNDS or next_index >= len(BASE_QUESTIONS.get(next_round, [])):
        return ""

    if INTERVIEW_MODE != "full":
        return _fallback_adaptive_question(answers, next_round, next_index)

    if _has_openai_key():
        prompt = (
            "Ты ассистент риэлтора. Сгенерируй один короткий следующий вопрос для интервью "
            "собственника недвижимости на русском. Вопрос должен соответствовать текущему этапу "
            f"Раунд {next_round}, вопрос {next_index + 1}. Сохрани обязательную цель базового вопроса: "
            "если он просит район, площадь, цену покупки, цену продажи или арендную плату, обязательно спроси именно это. "
            "Не добавляй пояснений.\n\n"
            f"Базовый вопрос: {BASE_QUESTIONS[next_round][next_index]}\n\n"
            f"Ответы:\n{_answers_text(answers)}"
        )
        llm_result = _call_openai_text(prompt)
        if llm_result:
            return llm_result.strip().strip('"')

    return _fallback_adaptive_question(answers, next_round, next_index)


def generate_report(
    answers: list[AnswerItem],
    used_tools: list[str] | None = None,
    tool_results: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    client_card = _build_client_card(answers)
    lead_score = _score_lead(answers)
    used_tools = used_tools or []
    tool_results = tool_results or {}

    if _has_openai_key():
        prompt = (
            "Сформируй Markdown-отчёт для риэлтора по интервью собственника. "
            "Обязательно добавь раздел '## Контактные данные' с полями Имя, "
            "Телефон / email, Собственники. Затем добавь карточку клиента, мотивацию, "
            "ожидания, опасения и рекомендованные следующие шаги. Пиши на русском.\n\n"
            f"{_answers_text(answers)}\n\n"
            f"Результаты agent tools:\n{json.dumps(tool_results, ensure_ascii=False, indent=2)}"
        )
        llm_report = _call_openai_text(prompt)
        if llm_report:
            markdown_report = _ensure_contact_section(llm_report, client_card)
            markdown_report = _append_tool_sections(markdown_report, used_tools, tool_results)
            return {
                "client_card": client_card,
                "lead_score": lead_score,
                "markdown_report": markdown_report,
                "used_tools": used_tools,
                "tool_results": tool_results,
            }

    markdown = _fallback_markdown_report(answers, client_card, lead_score, used_tools, tool_results)
    return {
        "client_card": client_card,
        "lead_score": lead_score,
        "markdown_report": markdown,
        "used_tools": used_tools,
        "tool_results": tool_results,
    }


def get_next_position(current_round: int, current_question_index: int) -> tuple[int, int]:
    current_questions = BASE_QUESTIONS.get(current_round, [])
    if current_question_index < len(current_questions) - 1:
        return current_round, current_question_index + 1
    return current_round + 1, 0


def _fallback_adaptive_question(
    answers: list[AnswerItem], next_round: int, next_index: int
) -> str:
    return BASE_QUESTIONS[next_round][next_index]


def _fallback_markdown_report(
    answers: list[AnswerItem],
    client_card: ClientCard,
    lead_score: LeadScore,
    used_tools: list[str],
    tool_results: dict[str, dict[str, Any]],
) -> str:
    answer_lines = "\n".join(
        f"- **{item.question}**\n  {item.answer or 'Не указано'}" for item in answers
    )
    return f"""# Отчёт по собственнику недвижимости

## Карточка клиента

- **Имя:** {client_card.name}
- **Телефон / email:** {client_card.contact}
- **Собственники:** {client_card.ownership_status}
- **Тип недвижимости:** {client_card.property_type}
- **Локация:** {client_card.location}
- **Цель:** {client_card.goal}
- **Ожидаемая цена / аренда:** {client_card.expected_price}

## Контактные данные

- **Имя:** {client_card.name}
- **Телефон / email:** {client_card.contact}
- **Собственники:** {client_card.ownership_status}

## Оценка лида

**{lead_score.title}** ({lead_score.label})

{lead_score.reason}

## Ответы интервью

{answer_lines}

{_render_tool_sections(used_tools, tool_results)}

## Рекомендованные следующие шаги

1. Уточнить документы и готовность собственника к встрече.
2. Проверить рыночный диапазон цены или аренды по похожим объектам.
3. Закрыть основные сомнения собственника и предложить понятный план работы.
"""


def _ensure_contact_section(markdown: str, client_card: ClientCard) -> str:
    if "## Контактные данные" in markdown:
        return markdown

    contact_section = f"""
## Контактные данные

- **Имя:** {client_card.name}
- **Телефон / email:** {client_card.contact}
- **Собственники:** {client_card.ownership_status}
"""
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join([lines[0], contact_section, *lines[1:]])
    return contact_section + "\n" + markdown


def _append_tool_sections(
    markdown: str,
    used_tools: list[str],
    tool_results: dict[str, dict[str, Any]],
) -> str:
    if "## Использованные инструменты" in markdown:
        return markdown
    return markdown.rstrip() + "\n\n" + _render_tool_sections(used_tools, tool_results)


def _render_tool_sections(
    used_tools: list[str],
    tool_results: dict[str, dict[str, Any]],
) -> str:
    lines: list[str] = ["## Использованные инструменты", ""]
    if used_tools:
        lines.extend(f"- {tool_name}" for tool_name in used_tools)
    else:
        lines.append("- Инструменты не использованы: недостаточно данных для расчётов.")

    tax = tool_results.get("Tax Estimator Tool")
    if tax:
        lines.extend(["", "## Ориентировочный налоговый расчёт", ""])
        if _is_tool_success(tax):
            lines.extend(
                [
                    f"- **Ориентировочная прибыль:** {_format_eur(tax.get('estimated_capital_gain'))}",
                    f"- **Ориентировочный IRPF sobre ganancia patrimonial:** {_format_eur(tax.get('estimated_irpf'))}",
                    f"- **Цена продажи:** {_format_eur(tax.get('sale_price'))}",
                    f"- **Цена покупки:** {_format_eur(tax.get('purchase_price'))}",
                    f"- **Расходы / ремонт:** {_format_eur(tax.get('deductible_expenses'))}",
                    f"- {tax.get('disclaimer')}",
                ]
            )
        else:
            lines.append(f"- Недостаточно данных для расчёта. {tax.get('reason', '')}".strip())

    market = tool_results.get("Barcelona Market Data Tool")
    if market:
        lines.extend(["", "## Рыночное сравнение по району", ""])
        if _is_tool_success(market):
            lines.extend(
                [
                    f"- **Район:** {market.get('district')}",
                    f"- **Цена объекта:** {_format_eur_m2(market.get('object_price_m2'))}",
                    f"- **Средняя цена района:** {_format_eur_m2(market.get('district_avg_price_m2'))}",
                    f"- **Отклонение:** {market.get('deviation_percent')}%",
                    f"- **Позиция:** {_market_position_label(str(market.get('market_position')))}",
                    f"- {market.get('disclaimer')}",
                    "",
                    "## Оценка срока продажи",
                    "",
                    f"- **Ориентировочный срок:** {market.get('estimated_sale_time')}",
                ]
            )
        else:
            lines.append(f"- Недостаточно данных для сравнения. {market.get('reason', '')}".strip())

    rental = tool_results.get("Rental Yield Analyzer")
    if rental:
        lines.extend(["", "## Анализ рентабельности аренды", ""])
        if _is_tool_success(rental):
            lines.extend(
                [
                    f"- **Годовой арендный доход:** {_format_eur(rental.get('annual_rent'))}",
                    f"- **Валовая доходность:** {rental.get('gross_yield_percent')}%",
                    f"- **Окупаемость:** {rental.get('payback_years')} лет",
                    f"- **Вывод:** {_yield_category_label(str(rental.get('yield_category')))}",
                ]
            )
        else:
            lines.append(f"- Недостаточно данных для расчёта. {rental.get('reason', '')}".strip())

    return "\n".join(lines)


def _is_tool_success(result: dict[str, Any]) -> bool:
    return result.get("status") in SUCCESS_TOOL_STATUSES


def _format_eur(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{value:,.0f} €".replace(",", " ")
    return "Недостаточно данных"


def _format_eur_m2(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{value:,.0f} €/м²".replace(",", " ")
    return "Недостаточно данных"


def _market_position_label(value: str) -> str:
    return {
        "below_market": "ниже рынка",
        "near_market": "около рынка",
        "above_market": "выше рынка",
        "strongly_above_market": "значительно выше рынка",
    }.get(value, value)


def _yield_category_label(value: str) -> str:
    return {
        "low": "низкая доходность",
        "medium": "средняя доходность",
        "high": "высокая доходность",
    }.get(value, value)


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _call_openai_text(prompt: str) -> str | None:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Ты полезный AI-ассистент для учебного MVP по real estate intake.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.warning("OpenAI call failed, using fallback mode: %s", exc)
        return None


def parse_report_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
