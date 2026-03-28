# Chart Layer Documentation

Supports transforming a text-based query answer into Chart.js-ready data when charting adds value.

## Purpose

- Decides if a natural-language answer should be visualized as a chart.
- Parses numeric insights into a `ChartData` model for frontend rendering.
- Keeps charting optional: if data is narrative or insufficient, returns `has_chart: false`.

## Core implementation

File: `app/chart_generator.py`

Key class:

- `ChartGenerator` — orchestrates LLM prompt and parsing

Key functions:

- `ChartGenerator.generate(question, query_result) -> ChartData`
- `generate_chart_data(question, query_result) -> ChartData` (convenience wrapper)

Singleton helper:

- `get_chart_generator()`

## Data models

- `Dataset` (label, data list)
- `ChartData` with fields:
  - `has_chart` (bool)
  - `chart_type` (`bar|line|pie|doughnut`)
  - `title`, `x_label`, `y_label`
  - `labels`, `datasets`
  - `success`, `error` (diagnostic)

## LLM prompt behavior

- Uses `SYSTEM_PROMPT` for chart selection rules.
- Uses `USER_PROMPT_TEMPLATE` with original query and answer text.
- Calls ChatOpenAI with `model` default `gpt-4o` and low temperature.

Rules enforced by prompt:

- Return valid JSON only (no markdown fences)
- `has_chart=false` for narrative or single-number answers
- Chart type for trend vs categories vs proportions
- Parse numeric values as floats (percentages rounded to 2dp)
- Cap labels at 20 entries
- Encourage concise chart title and axis labels

## Parsing semantics

- `_parse(raw)` strips fences, loads JSON.
- For `has_chart=false`, returns `ChartData(has_chart=False)`.
- For charts, produces `Dataset` list with floats.
- On JSON parse errors, returns `ChartData(success=False, error=...)`.

## Integration

- `app/main.py` or event handlers can call `generate_chart_data()` after query results are obtained.
- Frontend should map `ChartData` into Chart.js config.

## Testing

- Add tests in `app/tests` to assert robust behavior for:
  - empty/narrative input (no chart)
  - valid JSON chart output
  - malformed JSON fallback
  - dataset value conversion

## Notes

- This layer is intentionally weakly typed as it relies on the LLM output shape.
- For deterministic unit tests, consider monkeypatching `_call_llm` or injecting the LLM client.
