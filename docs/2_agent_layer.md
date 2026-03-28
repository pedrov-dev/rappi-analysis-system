# Agent Layer Documentation

This document covers the `agent` layer in `rappi-analysis-system`, implemented in `app/agent.py`.

## Purpose

- Provides a natural-language query interface against data in CSV-backed DataFrames.
- Uses LangChain’s experimental pandas agent and OpenAI LLM to translate questions into DataFrame operations.
- Serves the `/chat` endpoint in the API layer (via `app/main.py`) by exposing `run_query()`.

## Key components

- `get_dataframes()` and `get_schema_summary()` from `app/data_loader.py`.
- `ChatOpenAI` from `langchain_openai` for the LLM.
- `create_pandas_dataframe_agent(...)` from `langchain_experimental.agents`.
- `QueryResult` Pydantic model:
  - `answer`: final text response
  - `raw_output`: raw LLM/agent response for debugging
  - `success`: boolean status
  - `error`: optional message on failure

## Behavior

1. Build a system prompt with:
   - data model reference (`df1`, `df2`, `df3`)
   - metrics dictionary and temporal conventions
   - inferred schema from loaded data
   - operating rules (read-only, no DataFrame mutation, no fabrication)
2. Create or reuse a singleton agent in `get_agent()`.
3. On `run_query(question)`:
   - validate input
   - invoke the agent
   - handle parser/data errors and exceptions gracefully
   - return a `QueryResult` object

## Configuration

- `OPENAI_MODEL` env var (default: `gpt-5.4-mini`)
- `AGENT_MAX_ITERATIONS` env var (default: `5`)

## Notes

- The agent uses a multi-dataframe list: `METRICS`, `ORDERS`, `SUMMARY`.
- Designed as read-only analytics; updates to data are not supported by this layer.
- If the question is unanswerable with available data, the agent should clearly report this.
