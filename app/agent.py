"""
agent.py — LangChain Pandas Agent Query Engine (Phase 2)

Sets up a multi-DataFrame LangChain agent backed by GPT-4o and exposes
a run_query() function for the FastAPI /chat endpoint to consume.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.data_loader import get_dataframes, get_schema_summary

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class QueryResult(BaseModel):
    answer: str
    raw_output: str
    success: bool
    error: str | None = None

# ---------------------------------------------------------------------------
# Static business context (sourced from Section 3 of the technical brief)
# ---------------------------------------------------------------------------
 
_DATA_MODELS = """
## Data Models
 
### df1 — METRICS  (Dataset 1: Métricas Input)
Operational metrics per zone across the last 8 weeks.
 
| Column              | Type   | Description                                                                 |
|---------------------|--------|-----------------------------------------------------------------------------|
| COUNTRY             | string | Country code: AR, BR, CL, CO, CR, EC, MX, PE, UY                           |
| CITY                | string | City name                                                                   |
| ZONE                | string | Operational zone or neighbourhood                                           |
| ZONE_TYPE           | string | Wealth segmentation: "Wealthy" or "Non Wealthy"                             |
| ZONE_PRIORITIZATION | string | Strategic priority tier: "High Priority", "Prioritized", or "Not Prioritized" |
| METRIC              | string | Name of the metric being measured (see Metrics Dictionary below)            |
| L"N"W_VALUE         | float  | Metric value of N weeks ago 0(current)-8(oldest)                          |                                   |
 
### df2 — ORDERS  (Dataset 2: Órdenes)
Order volume per zone across the last 8 weeks.
 
| Column              | Type   | Description                                    |
|---------------------|--------|------------------------------------------------|
| COUNTRY             | string | Country code (same values as METRICS)          |
| CITY                | string | City name                                      |
| ZONE                | string | Operational zone or neighbourhood              |
| METRIC              | string | Always "Orders"                                |
| L"N"W_VALUE         | float  | Order count of N weeks ago 0(current)-8(oldest)|                                   |
"""

_METRICS_DICTIONARY = """
## Metrics Dictionary
 
| Metric Name                          | Definition                                                                                                                                      |
|--------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| % PRO Users Who Breakeven            | Users whose Pro subscription value generated for the company (purchases, commissions, etc.) has covered the full cost of their membership / Total Pro users |
| % Restaurants Sessions With Optimal Assortment | Sessions with at least 40 restaurants available / Total sessions                                                               |
| Gross Profit UE                      | Gross profit margin / Total orders (unit-economics view of profitability per order)                                                             |
| Lead Penetration                     | Stores enabled on Rappi / (Identified prospect stores + Enabled stores + Stores that left Rappi). Measures marketplace supply capture.          |
| MLTV Top Verticals Adoption          | Users with orders across multiple verticals (restaurants, super, pharmacy, liquors) / Total users. Measures cross-vertical engagement.          |
| Non-Pro PTC > OP                     | Conversion of non-Pro users from "Proceed to Checkout" to "Order Placed". Measures checkout completion rate for non-subscribers.                |
| Perfect Orders                       | Orders with no cancellations, defects, or delays / Total orders. Primary quality metric.                                                        |
| Pro Adoption                         | Pro subscription users / Total Rappi users. Measures subscription programme penetration.                                                        |
| Restaurants Markdowns / GMV          | Total discounts on restaurant orders / Total Restaurant Gross Merchandise Value. Measures discount intensity.                                   |
| Restaurants SS > ATC CVR             | Restaurant funnel conversion: "Select Store" → "Add to Cart".                                                                                  |
| Restaurants SST > SS CVR             | Percentage of users who, after selecting the Restaurants category, proceed to select a specific store from the list shown.                      |
| Retail SST > SS CVR                  | Percentage of users who, after selecting the Supermarkets category, proceed to select a specific store from the list shown.                     |
| Turbo Adoption                       | Users who purchase through Turbo (Rappi's fast-delivery service) / Total Rappi users with Turbo stores available.                               |
 
### Metric Interpretation Notes
- **Lead Penetration** and **Perfect Orders** are the two most-watched health indicators.
  A zone with high Lead Penetration but low Perfect Orders signals supply quantity without
  quality — typically a prioritisation candidate.
- **Gross Profit UE** declining alongside stable or growing Orders suggests margin
  compression — look for correlated increases in Restaurants Markdowns / GMV.
- **Non-Pro PTC > OP** below benchmark in a zone with high Pro Adoption may indicate
  that non-Pro users face friction that Pro users bypass (e.g. delivery fee thresholds).
- When a user asks about "zonas problemáticas" (problematic zones), interpret this as
  zones with ≥1 metric showing week-over-week deterioration of >10%, OR zones in
  consistent decline (3+ consecutive weeks) in Perfect Orders or Gross Profit UE.
- When a user asks about "oportunidades" (opportunities), interpret this as zones with
  high Orders growth but below-average Lead Penetration or MLTV Top Verticals Adoption.
"""
 
_TEMPORAL_CONVENTIONS = """
## Temporal Conventions
- Columns L8W_VALUE → L0W_VALUE represent the last 9 data points, from oldest (L8W)
  to most recent (L0W = current week).
- When computing week-over-week change, use: (L0W_VALUE - L1W_VALUE) / L1W_VALUE.
- When identifying trends (3+ weeks), compare L2W, L1W, and L0W directional movement.
- For 8-week trend queries, use all LxW columns in chronological order.
"""

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    schema = get_schema_summary()
    return f"""You are a data analyst for a food delivery platform (Rappi).
You have access to three DataFrames: df1 (METRICS), df2 (ORDERS), and df3 (SUMMARY).
 
{_DATA_MODELS}
 
{_METRICS_DICTIONARY}
 
{_TEMPORAL_CONVENTIONS}
 
## Inferred Schema (from loaded data)
{schema}
 
## Operating Rules
- Perform READ-ONLY operations. Never call df.drop(), df.insert(), df.pop(),
  or any method that mutates a DataFrame in place.
- If the question cannot be answered with the available data, say so clearly
  and briefly — do not fabricate values.
- Return a concise natural-language answer with supporting data (e.g. a table
  or key numbers) where relevant.
- Keep your final answer focused. Avoid restating the question.
- When filtering by metric name, match against the METRIC column using the
  exact strings in the Metrics Dictionary above (case-insensitive .str.contains
  is acceptable for fuzzy user inputs).
- For temporal trend questions, always sort LxW columns chronologically
  (L8W → L0W) before computing or displaying results.
"""


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

_agent_executor: Any = None


def _build_agent() -> Any:
    """Construct and return the LangChain Pandas agent."""
    dfs_map = get_dataframes()

    # Guarantee stable ordering: df1=METRICS, df2=ORDERS, df3=SUMMARY
    ordered_keys = ["METRICS", "ORDERS", "SUMMARY"]
    dfs = [dfs_map[k] for k in ordered_keys if k in dfs_map]

    if not dfs:
        raise RuntimeError("No DataFrames available — ensure data_loader was initialised first.")

    llm = ChatOpenAI(
        model=_MODEL,
        temperature=0,
    )

    agent = create_pandas_dataframe_agent(
        llm=llm,
        df=dfs,                        # list → multi-df mode
        verbose=True,
        agent_type="openai-tools",
        allow_dangerous_code=True,     # required by langchain-experimental
        max_iterations=_MAX_ITERATIONS,
        prefix=_build_system_prompt(),
    )

    logger.info(
        "Pandas agent initialised | model=%s | dataframes=%s | max_iterations=%d",
        _MODEL,
        [f"df{i+1}={k}" for i, k in enumerate(ordered_keys) if k in dfs_map],
        _MAX_ITERATIONS,
    )
    return agent


def get_agent() -> Any:
    """Return the cached agent, building it on first call."""
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = _build_agent()
    return _agent_executor


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_query(question: str) -> QueryResult:
    """
    Run a natural-language question through the Pandas agent.

    Returns a QueryResult with the answer, raw output, and success status.
    Never raises — all exceptions are caught and surfaced via QueryResult.error.
    """
    if not question or not question.strip():
        return QueryResult(
            answer="Please provide a question.",
            raw_output="",
            success=False,
            error="Empty question received.",
        )

    logger.info("run_query | question=%r", question)

    try:
        agent = get_agent()
        raw = agent.invoke({"input": question})

        # agent.invoke() returns a dict: {"input": ..., "output": ...}
        answer = raw.get("output", "").strip() if isinstance(raw, dict) else str(raw).strip()

        if not answer:
            return QueryResult(
                answer="The agent produced no output for this question.",
                raw_output=str(raw),
                success=False,
                error="Empty agent output.",
            )

        logger.info("run_query | success=True | answer_chars=%d", len(answer))
        return QueryResult(answer=answer, raw_output=str(raw), success=True)

    except OutputParserException as exc:
        msg = "The agent could not parse its own output. Try rephrasing your question."
        logger.warning("run_query | OutputParserException: %s", exc)
        return QueryResult(answer=msg, raw_output="", success=False, error=str(exc))

    except ValueError as exc:
        msg = "Invalid input or unexpected data shape encountered."
        logger.warning("run_query | ValueError: %s", exc)
        return QueryResult(answer=msg, raw_output="", success=False, error=str(exc))

    except Exception as exc:  # noqa: BLE001
        msg = "An unexpected error occurred while processing your question."
        logger.exception("run_query | Unhandled exception: %s", exc)
        return QueryResult(answer=msg, raw_output="", success=False, error=str(exc))


