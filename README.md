# Intelligent Data Analysis System

LangChain-based intelligent data analysis prototype with a Vue frontend and FastAPI backend.

## Structure

- `backend/`: FastAPI, LangChain/OpenAI-compatible LLM integration, SQLite, dataset storage, charts, history, and reports.
- `frontend/`: Vue frontend initialized with Vite.

## Environment Files

- `.env`: local secrets and runtime configuration. This file is ignored by git.
- `.env.example`: safe template that can be committed.

The backend reads both generic names (`API_KEY`, `BASE_URL`, `DEFAULT_MODEL`) and OpenAI-style names (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`).

## Backend

```bash
cd backend
conda activate Langchain-py13
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation is available at `http://127.0.0.1:8000/docs`.

## Language Readiness

The backend exposes supported UI/analysis languages through `GET /api/config/client`:

- `en`: English
- `zh`: 简体中文
- `ms`: Bahasa Melayu

Analysis requests can pass `options.language` with one of these codes.
