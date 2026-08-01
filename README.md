# Personal Task Agent

An AI-powered agent that understands natural language requests and autonomously
completes multi-step tasks using a Reason → Plan → Act → Observe workflow,
built with FastAPI, LangGraph, and Groq.

## Status

**Milestone 1 complete:** project foundation — FastAPI app, configuration,
logging, SQLite/SQLAlchemy setup, base ORM models, and a static frontend shell.
The AI agent and business logic are not implemented yet.

## Project Structure

```
app/
├── agent/       # LangGraph agent (added in later milestones)
├── api/         # FastAPI routers
├── core/        # Config, logging, exceptions
├── database/    # SQLAlchemy engine/session + init
├── models/      # ORM models (workflows, notes, logs)
├── schemas/     # Pydantic request/response schemas (added later)
├── services/    # Business logic (added later)
├── tools/       # Agent tools (added later)
├── utils/       # Shared helpers (added later)
└── main.py      # FastAPI application factory
frontend/        # Static HTML/CSS/JS dashboard
logs/            # Runtime log files
tests/           # Test suite
run.py           # Uvicorn launcher
```

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy the environment template and fill in your values:
   ```bash
   cp .env.example .env
   ```

## Running the App

```bash
python run.py
```

The app starts at `http://localhost:8000`.

- Frontend dashboard: `http://localhost:8000/`
- Health check: `http://localhost:8000/api/v1/health`

On startup, SQLite tables are created automatically at the path configured
by `DATABASE_PATH` in `.env`.

## Verifying Milestone 1

```bash
curl http://localhost:8000/api/v1/health
# {"status": "ok", "database": "connected"}
```

Open `http://localhost:8000/` in a browser to see the tab-based dashboard
shell (Chat / Workflow History / Notes / Logs — each currently a placeholder).
