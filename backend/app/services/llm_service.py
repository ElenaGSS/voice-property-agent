import json
import logging
import os
import re
from typing import Any

from app.models.schemas import AnswerItem, ClientCard, LeadScore

logger = logging.getLogger(__name__)


BASE_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Как вас зовут?",
        "Какой телефон или email удобен для связи?",
        "Вы единственный собственник объекта или есть другие собственники?",
    ],
    2: [
        "Где находится объект?",
        "Какой тип недвижимости?",
        "Опишите объект своими словами.",
    ],
    3: [
        "Что вы хотите сделать: продать или сдать?",
        "Почему приняли это решение?",
        "Какие особенности объекта важно учитывать?",
    ],
    4: [
        "Какую цену или арендную плату вы ожидаете?",
        "Что для вас важно при работе с агентом?",
        "Есть ли вопросы или опасения по процессу?",
    ],
}

MAX_ROUNDS = len(BASE_QUESTIONS)
QUESTIONS_PER_ROUND = 3
TOTAL_QUESTIONS = MAX_ROUNDS * QUESTIONS_PER_ROUND


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
    return _find_by_question(answers, ["продать", "сдать", "хотите сделать"])


def _build_client_card(answers: list[AnswerItem]) -> ClientCard:
    return ClientCard(
        name=_find_by_question(answers, ["как вас зовут", "имя"]),
        contact=_find_by_question(answers, ["телефон", "email", "связи"]),
        ownership_status=_find_by_question(
            answers, ["единственный собственник", "другие собственники", "собственники"]
        ),
        property_type=_find_by_question(answers, ["тип недвижимости"]),
        location=_find_by_question(answers, ["где находится", "локац", "адрес", "район"]),
        goal=_infer_goal(answers),
        expected_price=_find_by_question(answers, ["цену", "арендную плату", "ожидаете"]),
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
    if next_round > MAX_ROUNDS:
        return ""

    if _has_openai_key():
        prompt = (
            "Ты ассистент риэлтора. Сгенерируй один короткий следующий вопрос для интервью "
            "собственника недвижимости на русском. Вопрос должен соответствовать текущему этапу "
            f"Раунд {next_round}, вопрос {next_index + 1}. Не добавляй пояснений.\n\n"
            f"Базовый вопрос: {BASE_QUESTIONS[next_round][next_index]}\n\n"
            f"Ответы:\n{_answers_text(answers)}"
        )
        llm_result = _call_openai_text(prompt)
        if llm_result:
            return llm_result.strip().strip('"')

    return _fallback_adaptive_question(answers, next_round, next_index)


def generate_report(answers: list[AnswerItem]) -> dict[str, Any]:
    client_card = _build_client_card(answers)
    lead_score = _score_lead(answers)

    if _has_openai_key():
        prompt = (
            "Сформируй Markdown-отчёт для риэлтора по интервью собственника. "
            "Обязательно добавь раздел '## Контактные данные' с полями Имя, "
            "Телефон / email, Собственники. Затем добавь карточку клиента, мотивацию, "
            "ожидания, опасения и рекомендованные следующие шаги. Пиши на русском.\n\n"
            f"{_answers_text(answers)}"
        )
        llm_report = _call_openai_text(prompt)
        if llm_report:
            return {
                "client_card": client_card,
                "lead_score": lead_score,
                "markdown_report": _ensure_contact_section(llm_report, client_card),
            }

    markdown = _fallback_markdown_report(answers, client_card, lead_score)
    return {
        "client_card": client_card,
        "lead_score": lead_score,
        "markdown_report": markdown,
    }


def get_next_position(current_round: int, current_question_index: int) -> tuple[int, int]:
    if current_question_index < QUESTIONS_PER_ROUND - 1:
        return current_round, current_question_index + 1
    return current_round + 1, 0


def _fallback_adaptive_question(
    answers: list[AnswerItem], next_round: int, next_index: int
) -> str:
    base_question = BASE_QUESTIONS[next_round][next_index]
    text = _combined_answers(answers)

    if next_round == 3 and next_index == 1:
        if any(word in text for word in ["срочно", "быстро", "переезд"]):
            return "Какой срок продажи или сдачи для вас был бы комфортным?"
        if any(word in text for word in ["сдана", "сдан", "арендатор", "договор"]):
            return "На какой срок сейчас действует договор аренды и есть ли ограничения для показа объекта?"

    if next_round == 3 and next_index == 2:
        if "ремонт" in text:
            return "Что по ремонту важно подчеркнуть агенту при презентации объекта?"
        if "ипотек" in text or "обремен" in text:
            return "Есть ли юридические или финансовые ограничения, которые агент должен учесть заранее?"

    if next_round == 4 and next_index == 1:
        if any(word in text for word in ["комисс", "оплат", "дорого"]):
            return "Какой формат комиссии или оплаты услуг был бы для вас комфортным?"
        if any(word in text for word in ["срочно", "быстро"]):
            return "Что для вас важнее: максимальная цена или скорость сделки?"

    if next_round == 4 and next_index == 2:
        if any(word in text for word in ["боюсь", "опас", "сомнен", "комисс"]):
            return "Какие условия сотрудничества помогли бы вам чувствовать себя спокойнее?"

    return base_question


def _fallback_markdown_report(
    answers: list[AnswerItem], client_card: ClientCard, lead_score: LeadScore
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
