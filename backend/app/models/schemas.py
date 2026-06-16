from typing import Any, Literal

from pydantic import BaseModel, Field


class AnswerItem(BaseModel):
    round: int = Field(..., ge=1, le=4)
    question: str
    answer: str


class TranscriptionResponse(BaseModel):
    text: str
    raw_text: str | None = None


class NextQuestionRequest(BaseModel):
    session_id: str
    current_round: int = Field(..., ge=1, le=4)
    current_question_index: int = Field(..., ge=0, le=12)
    answers: list[AnswerItem] = []


class NextQuestionResponse(BaseModel):
    question: str
    round: int
    question_index: int
    is_finished: bool


class GenerateReportRequest(BaseModel):
    session_id: str
    answers: list[AnswerItem]


class ClientCard(BaseModel):
    name: str
    contact: str
    ownership_status: str
    property_type: str
    location: str
    goal: str
    expected_price: str


class LeadScore(BaseModel):
    label: Literal["HOT", "WARM", "INFO"]
    title: str
    reason: str


class GenerateReportResponse(BaseModel):
    client_card: ClientCard
    lead_score: LeadScore
    markdown_report: str
    used_tools: list[str] = Field(default_factory=list)
    tool_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
