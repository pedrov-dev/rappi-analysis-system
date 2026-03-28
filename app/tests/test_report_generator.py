import pandas as pd

from app.report_generator import (
    _find_anomalies,
    _find_trends,
    _find_benchmarks,
    _find_opportunities,
)


def test_find_anomalies_dedupes_by_zone_country_city_metric():
    df = pd.DataFrame([
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'METRIC': 'm', 'L0W': 120, 'L1W': 100},
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'METRIC': 'm', 'L0W': 120, 'L1W': 100},
        {'ZONE': 'B', 'COUNTRY': 'Y', 'CITY': 'y', 'METRIC': 'm', 'L0W': 10, 'L1W': 5},
    ])

    anomalies = _find_anomalies(df, threshold=10.0)

    assert len(anomalies) == 2
    keys = {(a.zone, a.country, a.city, a.metric) for a in anomalies}
    assert keys == {('A', 'X', 'x', 'm'), ('B', 'Y', 'y', 'm')}


def test_find_trends_dedupes_with_longest_weeks():
    df = pd.DataFrame([
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'METRIC': 'm', 'L0W': 8, 'L1W': 9, 'L2W': 10, 'L3W': 11},
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'METRIC': 'm', 'L0W': 8, 'L1W': 9, 'L2W': 10, 'L3W': 12},
    ])

    trends = _find_trends(df, min_weeks=3)

    assert len(trends) == 1
    assert trends[0].zone == 'A'
    assert trends[0].weeks == 3


def test_find_benchmarks_dedupes_by_zone_metric():
    df = pd.DataFrame([
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'ZONE_TYPE': 'z', 'METRIC': 'm', 'L0W': 50},
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'ZONE_TYPE': 'z', 'METRIC': 'm', 'L0W': 60},
        {'ZONE': 'B', 'COUNTRY': 'X', 'CITY': 'y', 'ZONE_TYPE': 'z', 'METRIC': 'm', 'L0W': 30},
        {'ZONE': 'C', 'COUNTRY': 'X', 'CITY': 'z', 'ZONE_TYPE': 'z', 'METRIC': 'm', 'L0W': 10},
    ])

    results = _find_benchmarks(df, z_threshold=0.5)

    assert len(results) == 1
    assert results[0].zone in {'A', 'B', 'C'}


def test_find_opportunities_dedupes_by_zone_and_type():
    df = pd.DataFrame([
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'METRIC': 'Lead Penetration', 'L0W': 0.1},
        {'ZONE': 'A', 'COUNTRY': 'X', 'CITY': 'x', 'METRIC': 'Lead Penetration', 'L0W': 0.2},
    ])

    opps = _find_opportunities(df)

    assert len(opps) == 1
    assert opps[0].opportunity_type == 'Supply Gap'
