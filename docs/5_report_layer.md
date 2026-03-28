# Report Layer Documentation

This document covers the report generation layer in `rappi-analysis-system`, implemented in `app/report_generator.py`.

## Purpose

- Perform deterministic analytics on `METRICS` (and optionally `ORDERS`) dataframes.
- Extract top findings in five categories: anomalies, concerning trends, benchmarking, correlations, and growth opportunities.
- Enrich the structured findings with a narrative and recommendations via LLM (OpenAI / LangChain), with fallback text when LLM is unavailable or fails.
- Render a single self-contained HTML report via `app/report_renderer`.

## Entry point

- `generate_report() -> str`
  - loads data with `app.data_loader.get_dataframes()`
  - builds `ReportFindings` dataclass with module outputs
  - calls `_llm_enrich()` (or `_fallback_narrative()`)
  - returns `app.report_renderer._render_html(findings, narrative)`

## Analysis modules

1. **Anomalies** (`_find_anomalies`)
   - WoW change between `L0W` and `L1W` ≥ 10%
   - Returns `AnomalyFinding`

2. **Concerning Trends** (`_find_trends`)
   - 3+ consecutive declining weeks (L0W..L3W+)
   - Returns `TrendFinding`

3. **Benchmarking** (`_find_benchmarks`)
   - zones deviating >1.5 standard deviations from peer group median (COUNTRY+ZONE_TYPE+METRIC)
   - Returns `BenchmarkFinding`

4. **Correlations** (`_find_correlations`)
   - selected metrics with pairwise correlation |r| ≥ 0.5 across zones
   - Returns `CorrelationFinding`

5. **Opportunities** (`_find_opportunities`)
   - low adoption/quality zone signals (Lead penetration, MLTV, Pro, Perfect orders)
   - Returns `OpportunityFinding`

## Data helpers

- `_week_cols(df)` to identify `LxW` columns sorted newest→oldest
- `_safe_pct(new, old)` to compute robust percentage change
- `_dedupe_findings(...)` to keep strongest unique findings

## LLM narrative

- `_REPORT_SYSTEM` defines strict output JSON schema.
- `_llm_enrich(findings)` calls `langchain_openai.ChatOpenAI(model="gpt-4o")`, then JSON-parses response.
- On errors, `_fallback_narrative(findings)` returns deterministic summary + key finding counts.

## Testing

- Add coverage in `app/tests/test_report_generator.py` for:
  - each analysis helper behavior
  - fallback narrative path
  - report rendering from a small fake dataset

## Notes

- The layer is intentionally decoupled from the display layer; only returns HTML string.
- Default thresholds are defined in each module and a short list are returned (e.g., top 20 or 25 findings per category) to keep output manageable.
