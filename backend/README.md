# Backend

FastAPI backend for the Voice Property Intake Agent.

## Local Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Environment Variables

- `OPENAI_API_KEY` optional. If missing, the backend uses fallback interview and report logic.
- `OPENAI_MODEL` optional, defaults to `gpt-4o-mini`.
- `WHISPER_MOCK_MODE=true` optional for local demos without loading Whisper Small.

## API

- `GET /health`
- `POST /api/transcribe`
- `POST /api/next-question`
- `POST /api/generate-report`
