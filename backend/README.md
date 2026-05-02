# Intelligent Data Analysis Backend

FastAPI backend for the LangChain-based intelligent data analysis system.

## Run

```bash
cd backend
conda activate Langchain-py13
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Python version target: 3.13.

## Implemented API

- `GET /api/health`
- `GET /api/health/llm`
- `GET /api/config/client`
- `POST /api/datasets/upload`
- `GET /api/datasets`
- `GET /api/datasets/{dataset_id}`
- `DELETE /api/datasets/{dataset_id}`
- `GET /api/datasets/{dataset_id}/preview`
- `GET /api/datasets/{dataset_id}/schema`
- `GET /api/datasets/{dataset_id}/profile`
- `POST /api/analysis/query`
- `GET /api/analysis/query/stream`
- `GET /api/analysis/history`
- `GET /api/analysis/{analysis_id}`
- `GET /api/analysis/{analysis_id}/code`
- `POST /api/analysis/{analysis_id}/rerun`
- `DELETE /api/analysis/history/{history_id}`
- `GET /api/charts/{chart_id}`
- `GET /api/charts/{chart_id}/download`
- `POST /api/reports/export`
- `GET /api/reports/{report_id}/download`

## Test

```bash
cd backend
conda activate Langchain-py13
python -m pytest -q
```

The test suite uses a mocked LLM response so it does not require a live model call.
