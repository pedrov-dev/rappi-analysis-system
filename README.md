# Rappi Analysis System

FastAPI-based analytics pipeline for Rappi CSV datasets (METRICS + ORDERS).

## Features

- Data-loader from `data/METRICS.csv` and `data/ORDERS.csv` into Pandas DataFrames.
- LangChain Pandas agent (`app/agent.py`) with GPT model prompt context and dataset schema.
- Natural-language query API (`POST /chat`) returning structured `QueryResult`.
- Insight generation (`POST /insights`) that converts query answers into actionable JSON insights.
- Chart suggestion (`POST /chart`) for Chart.js-friendly payload (bar/line/pie/doughnut).
- Executive HTML report (`GET /report`) with 5 analytic categories:
  1. Anomalies (WoW delta ±10%)
  2. Concerning Trends (3+ weeks decline)
  3. Benchmarking (peer-group outliers)
  4. Correlations (metric relationships)
  5. Opportunities (growth levers)
- Health check and root support endpoints (`GET /`, `GET /health`).

## Quickstart

### 1. Create virtualenv and install deps

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Set OpenAI credentials via environment variables or `.env`

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (defaults to `gpt-5.4-mini`)
- `AGENT_MAX_ITERATIONS` (default `5`)

### 3. Run tests and lint

```powershell
pytest
ruff check .
mypy app
```

### 4. Run the API

```powershell
uvicorn app.main:app --reload --port 8000
```

### 5. API endpoints

- `GET /` → status message
- `GET /health` → `{ "status": "ok" }`
- `POST /chat` → input `{ "question": "..." }` returns `answer`, `raw_output`, `success`, `error`
- `POST /insights` → input `{ "question": "...", "query_result": "..." }`
- `POST /chart` → input `{ "question": "...", "query_result": "..." }`
- `GET /report` → HTML executive report

## Code structure

- `app/main.py` → FastAPI routes, orchestrates the layers
- `app/data_loader.py` → loads and summarizes CSV data frames
- `app/agent.py` → LangChain pandas agent and query runner
- `app/insights.py` → insights LLM layer
- `app/chart_generator.py` → chart generation LLM layer
- `app/report_generator.py` → deterministic analytics + report orchestration
- `app/report_renderer.py` → HTML report template
- `app/tests/*` → unit tests for each layer

## Notes

- Keep `pyproject.toml` and `requirements-dev.txt` aligned.
- Use `.env.example` as a starting point for environment variables.
