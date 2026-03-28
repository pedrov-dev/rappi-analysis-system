# Data Layer Documentation

This document describes the data layer in the `rappi-analysis-system` project.

## Purpose

- Centralizes CSV loading for `METRICS.csv` and `ORDERS.csv`.
- Exposes loaded DataFrames as a simple read-only cache for the application.
- Provides schema summary text for prompt injection or diagnostics.

## File

- `app/data_loader.py`

## Constants

- `DATA_DIR`: base path `data`
- `_CSV_FILES`: mapping of dataset keys to files
  - `metrics` -> `data/METRICS.csv`
  - `orders` -> `data/ORDERS.csv`

## Internal helpers

- `_load_csv(path: Path) -> pd.DataFrame`
  - Reads the CSV using `pandas.read_csv`
  - Strips whitespace from column names (`df.columns = df.columns.str.strip()`)

## Startup behavior

On module import, the module loads all CSVs once:

- `_DATAFRAMES`: dict[str, pd.DataFrame]
  - keys are uppercase names: `METRICS`, `ORDERS`
  - values are loaded DataFrames

This means the first import has IO cost and raises exceptions immediately if files are missing.

## Public API

- `get_dataframes() -> dict[str, pd.DataFrame]`
  - Returns `_DATAFRAMES` object
  - DataFrames are shared by reference

- `get_schema_summary() -> str`
  - Generates readable schema lines for each dataframe:
    - `[{name}] ({row_count} rows) COL(dtype) | ...`
  - Includes dtype for each column from pandas

## Usage example

```python
from app.data_loader import get_dataframes, get_schema_summary

frames = get_dataframes()
metrics_df = frames['METRICS']
orders_df = frames['ORDERS']
print(get_schema_summary())
```

## Notes

- This module assumes `data` exists in working directory and contains CSV files.
- For tests, consider monkeypatching `_DATAFRAMES` or injecting a temporary path.
