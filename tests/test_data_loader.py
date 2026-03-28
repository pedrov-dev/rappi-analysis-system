import pandas as pd

from app.data_loader import get_dataframes


def test_get_dataframes_keys_are_uppercase():
    dfs = get_dataframes()

    assert isinstance(dfs, dict)
    assert "METRICS" in dfs
    assert "ORDERS" in dfs

    # If SUMMARY is not loaded that's okay; at least this code path works.
    assert all(k == k.upper() for k in dfs.keys())
    assert all(isinstance(v, pd.DataFrame) for v in dfs.values())
