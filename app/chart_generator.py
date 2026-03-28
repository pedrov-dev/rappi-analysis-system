"""
Chart Generator — Layer 4
Inspects a QueryResult and determines whether a chart is appropriate.
If so, returns structured Chart.js-compatible data for the frontend.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Dataset:
    label: str
    data: list[float | int]


@dataclass
class ChartData:
    has_chart: bool
    chart_type: str                    = "bar"   # bar | line | pie | doughnut
    title: str                         = ""
    labels: list[str]                  = field(default_factory=list)
    datasets: list[Dataset]            = field(default_factory=list)
    x_label: str                       = ""
    y_label: str                       = ""
    success: bool                      = True
    error: str | None                  = None


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a data visualisation expert for a food delivery analytics platform.
Given a natural-language question and its text-based answer, decide whether
a chart adds meaningful value. If yes, extract the numbers into a
Chart.js-compatible structure.

Rules:
- Return ONLY valid JSON — no markdown fences, no preamble.
- has_chart = false when the answer is purely narrative (no numeric data,
  or only a single number with no series/categories).
- chart_type selection:
    "line"     → time-series / week-over-week trends (L8W … L0W)
    "bar"      → category comparisons (stores, zones, cities, metrics)
    "pie"      → proportions with ≤ 8 slices
    "doughnut" → same as pie but with a central total
- Extract labels and data values directly from the answer text.
  Numbers should be floats (round percentages to 2 decimal places).
- Cap labels at 20 entries for readability; keep the N most significant.
- datasets is an array; use multiple datasets only when the answer
  contains parallel series (e.g. two metrics side by side).
- title should be a compact chart title (≤ 8 words).
- x_label / y_label: short axis descriptions.

JSON schema (strict):
{
  "has_chart": boolean,
  "chart_type": "bar|line|pie|doughnut",
  "title": "string",
  "labels": ["string", ...],
  "x_label": "string",
  "y_label": "string",
  "datasets": [
    { "label": "string", "data": [number, ...] }
  ]
}
"""

USER_PROMPT_TEMPLATE = """\
Original question: {question}

Data answer:
{result}

Determine if a chart is appropriate and extract the data.
"""


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class ChartGenerator:
    """Converts a natural-language query result into Chart.js config data."""

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.1):
        self.llm = ChatOpenAI(model=model, temperature=temperature)

    # --- public ------------------------------------------------------------

    def generate(self, question: str, query_result: str) -> ChartData:
        if not query_result or not query_result.strip():
            return ChartData(has_chart=False)
        try:
            raw = self._call_llm(question, query_result)
            return self._parse(raw)
        except Exception as exc:
            logger.exception("ChartGenerator failed: %s", exc)
            return ChartData(has_chart=False, success=False, error=str(exc))

    # --- private -----------------------------------------------------------

    def _call_llm(self, question: str, result: str) -> str:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT_TEMPLATE.format(
                question=question, result=result
            )),
        ]
        content = self.llm.invoke(messages).content
        if isinstance(content, list):
            content = "\n".join(
                item if isinstance(item, str) else json.dumps(item)
                for item in content
            )
        return content

    def _parse(self, raw: str) -> ChartData:
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
            logger.error("Bad chart JSON: %s\n%s", exc, raw)
            return ChartData(has_chart=False, success=False, error=f"Malformed JSON: {exc}")

        if not data.get("has_chart"):
            return ChartData(has_chart=False)

        datasets = [
            Dataset(label=d.get("label", ""), data=[float(v) for v in d.get("data", [])])
            for d in data.get("datasets", [])
        ]

        return ChartData(
            has_chart=True,
            chart_type=data.get("chart_type", "bar"),
            title=data.get("title", ""),
            labels=data.get("labels", []),
            datasets=datasets,
            x_label=data.get("x_label", ""),
            y_label=data.get("y_label", ""),
            success=True,
        )


# ---------------------------------------------------------------------------
# Singleton + convenience wrapper
# ---------------------------------------------------------------------------

_generator: ChartGenerator | None = None


def get_chart_generator() -> ChartGenerator:
    global _generator
    if _generator is None:
        _generator = ChartGenerator()
    return _generator


def generate_chart_data(question: str, query_result: str) -> ChartData:
    """Drop-in function for main.py."""
    return get_chart_generator().generate(question, query_result)