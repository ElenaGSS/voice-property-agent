# Voice Property Intake Agent

Voice Property Intake Agent is a simple educational MVP for an AI automation and productivity course. It interviews a real estate owner by voice, transcribes answers with Whisper Small, adapts follow-up questions with LangGraph, and generates a Markdown report for a real estate agent.

## What the Agent Does

For the public course demo, the agent runs a short 7-question demo interview that quickly collects the data needed for the agent tools:

1. Contact details
2. Preferred phone or email
3. Barcelona district
4. Apartment area
5. Purchase price
6. Planned sale price
7. Expected monthly rent

The full production-style flow is preserved in code as a 4-round interview with 12 total questions:

1. Contact details
2. Object details: Barcelona district, property type, condition, area, and rooms
3. Sale data: sale/rent/both intent, purchase price, and planned sale price
4. Rental, expectations, and circumstances: monthly rent, priorities, mortgage, tenants, inheritance, renovation, or urgency

Set `INTERVIEW_MODE=full` on the backend and `NEXT_PUBLIC_INTERVIEW_MODE=full` on the frontend to return to the full interview. If these variables are not set, the app uses the short demo flow.

After each round or demo step, the backend analyzes the collected answers. If an OpenAI API key is available, it can use an LLM for summaries, adaptive questions, and reports. If no key is available, it uses deterministic fallback logic so the demo still works.

In v2, the backend also includes agent tools that run automatically when the answers contain enough data:

- Tax Estimator Tool for an approximate Spanish capital gains tax simulation.
- Barcelona Market Data Tool for local MVP price-per-square-meter comparison.
- Rental Yield Analyzer for gross rental yield estimates.

The tools do not use live APIs or scraping. Market data is a local MVP dataset and should be updated from official/open data sources before real use. Tax calculations are approximate simulations, not legal or tax advice.

## Architecture

```text
voice-property-agent/
├── frontend/   # Next.js, TypeScript, Tailwind CSS
├── backend/    # FastAPI, LangGraph, Whisper Small
├── docs/
└── README.md
```

The frontend records audio with the browser MediaRecorder API and sends it to the backend. The backend transcribes audio, runs interview logic, and returns the next question or final report.

The frontend also shows clearer waiting stages during slow Hugging Face CPU transcription: audio received, voice recognition, answer analysis, and next-question selection.

## Tech Stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: Python, FastAPI, LangGraph
- Speech-to-text: `openai/whisper-small` via `transformers` pipeline
- Optional LLM: OpenAI API
- Backend deployment: Hugging Face Spaces with Docker
- Frontend deployment: Vercel

## How to Run Backend Locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

For a lightweight local demo without loading Whisper Small:

```bash
WHISPER_MOCK_MODE=true uvicorn app.main:app --reload
```

## How to Run Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## How to Deploy Backend to Hugging Face Spaces

1. Create a new Hugging Face Space.
2. Select Docker as the Space SDK.
3. Upload or connect this repository and set the Space root to `backend` if needed.
4. Add optional environment variables in Space settings.
5. The Dockerfile exposes port `7860` and runs:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

## How to Deploy Frontend to Vercel

1. Import the repository into Vercel.
2. Set the project root directory to `frontend`.
3. Add `NEXT_PUBLIC_BACKEND_URL` with the public Hugging Face Space URL.
4. Deploy.

## Environment Variables

Backend:

- `OPENAI_API_KEY` optional. Enables OpenAI-based analysis and report generation.
- `OPENAI_MODEL` optional. Defaults to `gpt-4o-mini`.
- `WHISPER_MOCK_MODE=true` optional. Skips Whisper loading and returns demo text.
- `INTERVIEW_MODE=full` optional. Defaults to the 7-question demo flow.

Frontend:

- `NEXT_PUBLIC_BACKEND_URL` optional. Defaults to `http://localhost:8000`.
- `NEXT_PUBLIC_INTERVIEW_MODE=full` optional. Defaults to the 7-question demo flow.

## Demo Flow

1. Start the backend.
2. Start the frontend.
3. Click "Начать интервью".
4. Record a voice answer or type the answer manually.
5. Save the answer and continue through 7 demo questions.
6. The app generates the Markdown report automatically.
7. Copy or download the report.

## MVP Notes

This project intentionally avoids databases, authentication, payments, and complex state management. It is designed to be easy to inspect, run, and present in a course setting.
