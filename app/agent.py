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
# System prompt
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    schema = get_schema_summary()
    return f"""You are a data analyst for a food delivery platform.
You have access to three DataFrames named df1 (METRICS), df2 (ORDERS), and df3 (SUMMARY).

Schema reference:
{schema}

Rules:
- Perform READ-ONLY operations. Never call df.drop(), df.insert(), df.pop(),
  or any method that mutates a DataFrame in place.
- If the question cannot be answered with the available data, say so clearly
  and briefly — do not fabricate values.
- Return a concise natural-language answer with supporting data (e.g. a table
  or key numbers) where relevant.
- Keep your final answer focused. Avoid restating the question.
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


