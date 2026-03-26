import os
import sys
import types

# Ensure local package path is resolvable from tests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Inject lightweight stubs for optional LangChain dependencies so tests run
# in environments where they may not be installed (e.g. task runner context).
langchain_experimental = types.ModuleType("langchain_experimental")
langchain_experimental.agents = types.ModuleType("langchain_experimental.agents")
langchain_experimental.agents.create_pandas_dataframe_agent = lambda *a, **k: None
sys.modules["langchain_experimental"] = langchain_experimental
sys.modules["langchain_experimental.agents"] = langchain_experimental.agents

langchain_openai = types.ModuleType("langchain_openai")
langchain_openai.ChatOpenAI = type("ChatOpenAI", (), {"__init__": lambda self, *a, **k: None})
sys.modules["langchain_openai"] = langchain_openai

langchain_core = types.ModuleType("langchain_core")
langchain_core.exceptions = types.ModuleType("langchain_core.exceptions")
langchain_core.exceptions.OutputParserException = Exception
sys.modules["langchain_core"] = langchain_core
sys.modules["langchain_core.exceptions"] = langchain_core.exceptions

import pytest

from app.agent import run_query


def test_run_query_empty_question():
    result = run_query("")
    assert result.success is False
    assert "Please provide a question" in result.answer
    assert result.error == "Empty question received."


def test_run_query_success_with_mock(monkeypatch):
    class DummyAgent:
        def invoke(self, payload):
            assert payload["input"] == "Hello"
            return {"output": "Hi there!"}

    monkeypatch.setattr("app.agent.get_agent", lambda: DummyAgent())

    result = run_query("Hello")
    assert result.success is True
    assert result.answer == "Hi there!"
    assert "output" in result.raw_output
