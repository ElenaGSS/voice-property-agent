# Frontend

Next.js frontend for the Voice Property Intake Agent.

## Local Run

```bash
cd frontend
npm install
npm run dev
```

The app uses `NEXT_PUBLIC_BACKEND_URL` to find the FastAPI backend. If the
variable is not set, it uses `http://localhost:8000`.

## Environment Variables

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```
