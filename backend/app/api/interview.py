import logging

from fastapi import APIRouter

from app.graph.interview_graph import interview_graph
from app.models.schemas import (
    GenerateReportRequest,
    GenerateReportResponse,
    NextQuestionRequest,
    NextQuestionResponse,
)
from app.services.llm_service import (
    BASE_QUESTIONS,
    MAX_ROUNDS,
    TOTAL_QUESTIONS,
    get_next_position,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/next-question", response_model=NextQuestionResponse)
async def next_question(payload: NextQuestionRequest) -> NextQuestionResponse:
    next_round, next_index = get_next_position(
        payload.current_round, payload.current_question_index
    )

    if next_round > MAX_ROUNDS or len(payload.answers) >= TOTAL_QUESTIONS:
        return NextQuestionResponse(
            question="",
            round=MAX_ROUNDS,
            question_index=2,
            is_finished=True,
        )

    state = interview_graph.invoke(
        {
            "session_id": payload.session_id,
            "answers": payload.answers,
            "current_round": payload.current_round,
            "current_question_index": payload.current_question_index,
        }
    )
    question = state.get("next_question") or BASE_QUESTIONS[next_round][next_index]
    logger.info(
        "Generated next question for session=%s round=%s index=%s",
        payload.session_id,
        next_round,
        next_index,
    )
    return NextQuestionResponse(
        question=question,
        round=next_round,
        question_index=next_index,
        is_finished=False,
    )


@router.post("/generate-report", response_model=GenerateReportResponse)
async def generate_report(payload: GenerateReportRequest) -> GenerateReportResponse:
    state = interview_graph.invoke(
        {
            "session_id": payload.session_id,
            "answers": payload.answers,
            "current_round": MAX_ROUNDS,
            "current_question_index": 2,
            "force_final_report": True,
        }
    )
    report = state.get("final_report") or {}
    logger.info("Generated report for session=%s", payload.session_id)
    return GenerateReportResponse(**report)
