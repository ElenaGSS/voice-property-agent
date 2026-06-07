from app.models.schemas import AnswerItem
from app.services.llm_service import generate_report


def build_report(answers: list[AnswerItem]) -> dict:
    return generate_report(answers)
