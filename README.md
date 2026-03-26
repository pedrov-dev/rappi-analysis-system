# Chatbot + Insights AI System for Rappi Data Analysis

Chatbot and Insights AI System for Rappi Data Analysis.

## Commands

```powershell
.\.venv\Scripts\Activate.ps1
pytest
ruff check .
mypy src
```

## Structure

- src/app: application code
- tests: test suite
- .github/workflows/ci.yml: Windows CI pipeline

## Notes

- Keep dependencies in pyproject.toml and requirements-dev.txt aligned.
- Use .env.example as the starting point for local environment variables.
