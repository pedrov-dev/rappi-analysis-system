# Insights Layer Documentation

This document covers the `insights` layer in `rappi-analysis-system`, implemented in `app/insights.py`.

## Purpose

- Transforms raw query answers from the agent layer into structured, actionable insight objects.
- Uses a second LLM pass (via LangChain/OpenAI) to generate concise insights, severity levels, and recommended actions.
- Produces lightweight JSON data that can be rendered in reports or dashboards.

## Key components

- `InsightSeverity` enum (`info`, `warning`, `critical`).
- `Insight` dataclass with fields:
  - `title`, `detail`, `severity`, `metric`, `affected_entity`, `suggested_action`.
- `InsightResult` dataclass:
  - `insights` list, `summary`, `success`, `error`.
- `InsightGenerator` class:
  - `generate(question, query_result)`
  - `_call_llm()` sends prompts to `ChatOpenAI`
  - `_parse()` validates JSON return and maps to dataclasses.
- Singleton helpers: `get_generator()`, `generate_insights()`.

## Behavior

1. Validate query result non-empty.
2. Build system/user prompt with rules for JSON-only output.
3. Call LLM with deterministic temperature (default 0.2).
4. Parse JSON output into `InsightResult`; on parse error return `success=False`.
5. Return final insights summary for reporting.

## Failure handling

- Empty query result: explicit error message.
- JSON decoding error: logs issue and returns `InsightResult(success=False, error=...)`.
- Exceptions are caught and returned as error state.

## Integration points

- Used by `app/main.py` to enrich agent query responses before rendering.
- Keeps analytics pipeline readable, testable, and separate from raw query logic.
