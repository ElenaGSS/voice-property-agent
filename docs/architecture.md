# Architecture

## Overview

The project is split into a frontend and a backend inside one repository. This keeps the course project easy to understand while still matching a realistic AI product architecture.

```text
Browser
  |
  | audio + interview state
  v
Next.js frontend
  |
  | HTTP API
  v
FastAPI backend
  |
  | Whisper Small, LangGraph, fallback logic
  v
Markdown report
```

## Why Frontend and Backend Are Separate

The frontend owns the user experience: landing page, interview flow, audio recording, loading states, and report display.

The backend owns AI and automation logic: speech-to-text, LangGraph orchestration, adaptive question generation, and final report generation. This separation keeps browser code simple and avoids exposing server-side API keys.

## Why Hugging Face Spaces for Backend

Hugging Face Spaces is a practical home for a Python AI backend because it supports Docker and model-oriented demos. The backend Dockerfile uses Python 3.11, installs the required packages, exposes port `7860`, and runs FastAPI with Uvicorn.

## Why Vercel for Frontend

Vercel is a natural fit for Next.js. The frontend can be deployed independently and pointed at the backend with `NEXT_PUBLIC_BACKEND_URL`.

## Why Whisper Small

`openai/whisper-small` is a good MVP choice because it is stronger than the tiny/base models while still being simpler to deploy than larger Whisper variants. The backend loads the model lazily on the first transcription request, which makes startup faster and helps during deployment and debugging.

For local development, `WHISPER_MOCK_MODE=true` skips model loading and returns a demo transcription. This keeps the project usable on machines where Whisper is too heavy.

## How LangGraph Works

The backend defines a small graph in `backend/app/graph/interview_graph.py`.

Graph state includes:

- `session_id`
- `answers`
- `current_round`
- `current_question_index`
- `round_summary`
- `next_question`
- `final_report`
- `used_tools`
- `tool_results`

Nodes:

- `analyze_answers`
- `generate_next_question`
- `run_agent_tools`
- `generate_final_report`

The graph first analyzes answers, then routes either to the next question node or the final report path. On the final path, `run_agent_tools` evaluates the collected answers and runs only the tools that have enough context. The graph is deliberately small so students can understand it quickly.

## Agent Tools

v2 adds three backend agent tools as separate services:

- Tax Estimator Tool: approximate Spanish IRPF simulation for property sales. It is not legal or tax advice and plusvalía municipal is separate.
- Barcelona Market Data Tool: compares the expected sale price against a local MVP dataset in `backend/data/barcelona_market_data.json`.
- Rental Yield Analyzer: estimates gross rental yield and payback period.

The frontend does not decide when tools run. The backend tool router extracts context from answers and decides which tools to call. If data is missing, tools return `insufficient_data` and the report does not invent numbers.

The Barcelona market data file is a local MVP dataset, not live valuation data. It should be updated from official/open data sources before production use.

## Waiting UX

Whisper Small can be slow on free Hugging Face CPU. The frontend keeps the existing interview flow but shows clearer stages:

- Audio received
- Voice recognition
- Answer analysis
- Next question selection

It also displays a timer and explains that the first request can be slower because the speech model loads after idle periods.

## Fallback Mode

The MVP must work without external LLM access. If `OPENAI_API_KEY` is missing or an OpenAI request fails, the backend uses deterministic fallback logic:

- base interview questions
- simple adaptive question rules
- template-based Markdown report
- rule-based lead score

This makes the project stable for classroom demos.

## Interview Flow

The public course version defaults to a short 7-question demo flow. It is designed to trigger the v2 agent tools quickly during a live presentation:

- name
- phone or email
- Barcelona district
- apartment area
- purchase price
- planned sale price
- expected monthly rent

The full production-style interview is preserved in code and can be restored with `INTERVIEW_MODE=full` on the backend and `NEXT_PUBLIC_INTERVIEW_MODE=full` on the frontend. It has 4 rounds with 3 questions each:

- Contact details
- Object details: Barcelona district, property type, condition, area, and rooms
- Sale data: sale/rent/both intent, purchase price, and planned sale price
- Rental, expectations, and circumstances: monthly rent, priorities, mortgage, tenants, inheritance, renovation, or urgency

## MVP Limitations

- No database; state lives in the frontend during the browser session.
- No authentication or user accounts.
- No long-term file storage.
- No advanced diarization, noise cleanup, or multilingual tuning.
- Whisper Small may be slow on CPU.
- The fallback analysis is simple and rule-based.

These constraints are intentional. The goal is a clear, deployable learning project rather than a production CRM system.
