from pathlib import Path

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

DATA_DIR = Path("data")

_CSV_FILES = {
    "metrics": DATA_DIR / "METRICS.csv",
    "orders":  DATA_DIR / "ORDERS.csv",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV and strip column whitespace."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    return df


# ── Startup: load all DataFrames once ────────────────────────────────────────

# Normalize keys to uppercase so consumers can rely on stable dataset names.
_DATAFRAMES: dict[str, pd.DataFrame] = {
    name.upper(): _load_csv(path) for name, path in _CSV_FILES.items()
}

# ── Public API ────────────────────────────────────────────────────────────────

def get_dataframes() -> dict[str, pd.DataFrame]:
    """Return the loaded DataFrames keyed by dataset name."""
    return _DATAFRAMES


def get_schema_summary() -> str:
    """
    Return a compact schema string for injection into an LLM system prompt.

    Format:
        [METRICS]  COUNTRY(object) | CITY(object) | ... | L0W_ROLL(float64)
        [ORDERS]   COUNTRY(object) | CITY(object) | ... | L0W(float64)
    """
    lines: list[str] = []

    for name, df in _DATAFRAMES.items():
        col_tokens = " | ".join(
            f"{col}({dtype})" for col, dtype in zip(df.columns, df.dtypes, strict=True)
        )
        lines.append(f"[{name.upper()}] ({len(df)} rows) {col_tokens}")

    return "\n".join(lines)
