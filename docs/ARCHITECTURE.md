# Rappi Analysis System - Architecture Overview

## Goal

Provide an end-to-end analytics assistant for CSV order/metrics data, using a lightweight Python stack (FastAPI + pandas + OpenAI) to power:

- conversational queries (`/chat`)
- automated insights (`/insights`)
- chart suggestions (`/chart`)
- executive report generation (`/report`)

---

## 1. Data Layer

- Location: `data/` (CSV files)
  - `METRICS.csv`
  - `ORDERS.csv`
  - `SUMMARY.csv`

- Loader: `app/data_loader.py`
  - `get_dataframes()` loads and caches all datasets as pandas DataFrames.
  - Data refresh happens at API startup (`app/main.py` lifespan event).

- Purpose: provide in-memory tabular data for query synthesis and analysis.

---

## 2. Query Layer (Agent)

- Location: `app/agent.py`
  - `run_query(prompt)` receives natural language and returns `QueryResult`.
  - Internally: prompt-to-pandas translations, filter/group logic, likely via LLM + local data.

- API endpoint: `POST /chat` in `app/main.py`.
  - Models query + response semantics (answer, success, error).

- Purpose: convert business question into computed results over DataFrame data.

---

## 3. Insight Layer

- Location: `app/insights.py`
  - `generate_insights(question, query_result)` generates structured insights + narrative.

- API endpoint: `POST /insights` in `app/main.py`.
  - Accepts base question + previous query answer.
  - Responds with summary, insight list, status.

- Purpose: elevate raw query output into actionable insights and suggested interpretations.

---

## 4. Chart Layer

- Location: `app/chart_generator.py`
  - `generate_chart_data(question, query_result)` produces chart metadata (labels/datasets).

- API endpoint: `POST /chart` in `app/main.py`.
  - Useful for UI graph rendering from extracted chart-ready data.

- Purpose: visualize query outcomes with chart structures (bar/line etc.).

---

## 5. Report Layer

- Location: `app/report_generator.py` and `app/report_renderer.py`
  - `generate_report()` in `report_generator` orchestrates multi-category analysis and narrative.
  - `report_renderer` templates final HTML delivery.

- API endpoint: `GET /report` in `app/main.py`.
  - Returns full executive report HTML; handles failures as HTTP exceptions.

- Purpose: deliver comprehensive standalone report for stakeholders.

---

## 6. API Layer

- Main App: `app/main.py` (FastAPI)
  - `/` root status
  - `/health` status
  - `/chat`, `/insights`, `/chart`, `/report`
  - CORS open for dev (`allow_origins=["*"]`).

- Startup hook ensures `get_dataframes()` executed once.

---

## 7. Frontend Layer

- Example path: `ui/index.html`
  - Minimal static UI communicating with FastAPI endpoints.

- Optional improvements (not part of core implementation): React/Next.js.

---

## 8. Testing

- Location: `app/tests/`
  - `test_agent.py`
  - `test_data_loader.py`
  - `test_report_generator.py`
  - `test_report_renderer.py`

- Goal: unit-level coverage for each major component and API behavior.

---

## Data flow (high-level)

1. Startup loads CSVs to pandas DataFrames.
2. User asks question via `/chat`.
3. `agent.run_query()` translates and computes results.
4. `/insights` and `/chart` can enrich the same query results.
5. `/report` builds narrative across categories and returns HTML.

---

## Optional architecture notes

- AI/LLM dependency is fully contained in agent/insights/chart/report components.
- Swappable engine: replace OpenAI with another LLM as needed.
- Data volume: current in-memory for small/medium CSV. For large datasets, add DuckDB or OLAP layer.

---

## Repo structure summary

- `app/` core business logic
- `data/` source data CSVs
- `ui/` frontend demo
- `docs/` supporting documentation
- `requirements*.txt` dependencies

---

## Next polish steps (optional)

- add sequence diagrams in docs
- define architecture decisions in ADR format
- add security notes (auth, input sanitization, CORS scope)
- add performance monitoring and caching details
