from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.models.schemas import AnswerItem
from app.services.llm_service import (
    TOTAL_QUESTIONS,
    analyze_round,
    generate_adaptive_question,
    generate_report,
)


class InterviewState(TypedDict, total=False):
    session_id: str
    answers: list[AnswerItem]
    current_round: int
    current_question_index: int
    round_summary: str
    next_question: str
    final_report: dict[str, Any]
    force_final_report: bool


def analyze_answers(state: InterviewState) -> InterviewState:
    state["round_summary"] = analyze_round(state.get("answers", []))
    return state


def generate_next_question(state: InterviewState) -> InterviewState:
    state["next_question"] = generate_adaptive_question(
        state.get("answers", []),
        state.get("current_round", 1),
        state.get("current_question_index", 0),
    )
    return state


def generate_final_report(state: InterviewState) -> InterviewState:
    state["final_report"] = generate_report(state.get("answers", []))
    return state


def _route_after_analysis(state: InterviewState) -> str:
    if state.get("force_final_report"):
        return "generate_final_report"
    if len(state.get("answers", [])) >= TOTAL_QUESTIONS:
        return "generate_final_report"
    return "generate_next_question"


def build_interview_graph():
    graph = StateGraph(InterviewState)
    graph.add_node("analyze_answers", analyze_answers)
    graph.add_node("generate_next_question", generate_next_question)
    graph.add_node("generate_final_report", generate_final_report)

    graph.set_entry_point("analyze_answers")
    graph.add_conditional_edges(
        "analyze_answers",
        _route_after_analysis,
        {
            "generate_next_question": "generate_next_question",
            "generate_final_report": "generate_final_report",
        },
    )
    graph.add_edge("generate_next_question", END)
    graph.add_edge("generate_final_report", END)
    return graph.compile()


interview_graph = build_interview_graph()
