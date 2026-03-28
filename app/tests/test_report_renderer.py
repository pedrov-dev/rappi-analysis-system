import os
import sys
import types

# Ensure local package path is resolvable from tests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Lightweight stubs for optional LangChain dependencies so tests run in this environment.
langchain_experimental = types.ModuleType("langchain_experimental")
langchain_experimental.agents = types.ModuleType("langchain_experimental.agents")
langchain_experimental.agents.create_pandas_dataframe_agent = lambda *a, **k: None
sys.modules["langchain_experimental"] = langchain_experimental
sys.modules["langchain_experimental.agents"] = langchain_experimental.agents

langchain_openai = types.ModuleType("langchain_openai")
langchain_openai.ChatOpenAI = type("ChatOpenAI", (), {"__init__": lambda self, *a, **k: None, "invoke": lambda self, *a, **k: None})
sys.modules["langchain_openai"] = langchain_openai

langchain_core = types.ModuleType("langchain_core")
langchain_core.messages = types.ModuleType("langchain_core.messages")
langchain_core.messages.SystemMessage = lambda content=None: None
langchain_core.messages.HumanMessage = lambda content=None: None
sys.modules["langchain_core"] = langchain_core
sys.modules["langchain_core.messages"] = langchain_core.messages

from app.report_generator import AnomalyFinding, ReportFindings
from app.report_renderer import _render_html


def _sample_findings() -> ReportFindings:
    return ReportFindings(
        anomalies=[],
        trends=[],
        benchmarks=[],
        correlations=[],
        opportunities=[],
        data_summary={"total_zones": 1, "total_metrics": 1},
    )


def test_render_recommendations_table_rows():
    findings = _sample_findings()
    narrative = {
        "executive_summary": "Test summary",
        "key_findings": ["item1"],
        "recommendations": [
            {
                "priority": "high",
                "finding": "Test finding",
                "action": "Test action",
                "metric": "Test metric",
            }
        ],
    }

    html = _render_html(findings, narrative)

    assert "🎬 Prioritised Action Plan" in html
    assert "<span class='badge red'>HIGH</span>" in html
    assert "Test finding" in html
    assert "Test action" in html
    assert "Test metric" in html


def test_render_recommendations_ignore_invalid_payload():
    findings = _sample_findings()
    narrative = {
        "executive_summary": "Test summary",
        "key_findings": [],
        "recommendations": {"priority": "high", "finding": "Bad format"},
    }

    html = _render_html(findings, narrative)

    assert "No recommendations generated" in html
