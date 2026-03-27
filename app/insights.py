"""
Insight Generator — Layer 3
Consumes a QueryResult and produces structured, actionable insights
via a second LLM call.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class InsightSeverity(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


@dataclass
class Insight:
    title: str
    detail: str
    severity: InsightSeverity      = InsightSeverity.INFO
    metric: str | None             = None   # e.g. "cancel_rate"
    affected_entity: str | None    = None   # e.g. "Store #42"
    suggested_action: str | None   = None


@dataclass
class InsightResult:
    insights: list[Insight] = field(default_factory=list)
    summary:  str           = ""
    success:  bool          = True
    error:    str | None    = None


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior operations analyst for a food delivery platform.
You receive a data result from a pandas query engine. Extract concise,
actionable insights from it.

Rules:
- Return ONLY a valid JSON object — no markdown fences, no preamble.
- 1–5 insights, most meaningful only.
- Every insight needs: title, detail, severity ("info"|"warning"|"critical").
- Optional fields: metric, affected_entity, suggested_action.
- critical  → act now  (e.g. cancel_rate > 30 %)
- warning   → monitor closely
- info      → positive signal or neutral observation
- title < 10 words · detail < 40 words
- Include a top-level "summary" (1–2 plain-English sentences).

JSON schema:
{
  "summary": "string",
  "insights": [
    {
      "title": "string",
      "detail": "string",
      "severity": "info|warning|critical",
      "metric": "string|null",
      "affected_entity": "string|null",
      "suggested_action": "string|null"
    }
  ]
}
"""

USER_PROMPT_TEMPLATE = """\
Original question: {question}

Query result:
{result}

Generate insights from this data.
"""


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class InsightGenerator:
    """
    One extra LLM call that turns a raw query answer into structured insights.
    Lower temperature than the agent — we want deterministic analysis.
    """

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.2):
        self.llm = ChatOpenAI(model=model, temperature=temperature)

    # --- public -----------------------------------------------------------

    def generate(self, question: str, query_result: str) -> InsightResult:
        """
        question     — the original user question sent to the query engine
        query_result — QueryResult.answer from Layer 2
        """
        if not query_result or not query_result.strip():
            return InsightResult(
                success=False,
                error="Cannot generate insights: query result is empty.",
            )
        try:
            raw = self._call_llm(question, query_result)
            return self._parse(raw)
        except Exception as exc:
            logger.exception("InsightGenerator failed")
            return InsightResult(success=False, error=str(exc))

    # --- private ----------------------------------------------------------

    def _call_llm(self, question: str, result: str) -> str:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT_TEMPLATE.format(
                question=question, result=result
            )),
        ]
        content = self.llm.invoke(messages).content
        if isinstance(content, list):
            # Join list elements into a single string, handling dicts if present
            content = "\n".join(
                item if isinstance(item, str) else json.dumps(item)
                for item in content
            )
        return content

    def _parse(self, raw: str) -> InsightResult:
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Bad insight JSON – %s\n%s", exc, raw)
            return InsightResult(success=False, error=f"Malformed JSON: {exc}")

        insights = [
            Insight(
                title            = item.get("title", ""),
                detail           = item.get("detail", ""),
                severity         = InsightSeverity(item.get("severity", "info")),
                metric           = item.get("metric"),
                affected_entity  = item.get("affected_entity"),
                suggested_action = item.get("suggested_action"),
            )
            for item in data.get("insights", [])
        ]
        return InsightResult(
            insights=insights,
            summary=data.get("summary", ""),
            success=True,
        )


# ---------------------------------------------------------------------------
# Singleton + convenience wrapper (import this in main.py)
# ---------------------------------------------------------------------------

_generator: InsightGenerator | None = None

def get_generator() -> InsightGenerator:
    global _generator
    if _generator is None:
        _generator = InsightGenerator()
    return _generator

def generate_insights(question: str, query_result: str) -> InsightResult:
    """Drop-in function for main.py and tests."""
    return get_generator().generate(question, query_result)