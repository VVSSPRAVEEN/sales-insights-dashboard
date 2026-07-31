"""Tests for the sales data pipeline and dashboard aggregations."""
import sys
import pathlib

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.build_dashboard import compute_kpis, find_drop, monthly_revenue  # noqa: E402
from scripts.generate_data import generate_sales  # noqa: E402


@pytest.fixture(scope="module")
def df():
    return generate_sales(n=100_000, seed=42)


def test_deterministic_generation():
    a = generate_sales(n=50_000, seed=7)
    b = generate_sales(n=50_000, seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_revenue_invariant(df):
    expected = (df.units * df.unit_price * df.seasonal_factor).round(2)
    pd.testing.assert_series_equal(df.revenue, expected, check_names=False)


def test_orders_and_aov(df):
    kpis = compute_kpis(df)
    assert kpis["orders"] == len(df)
    assert kpis["aov"] == pytest.approx(kpis["total_revenue"] / len(df))


def test_monthly_aggregation_matches_total(df):
    assert monthly_revenue(df).sum() == pytest.approx(df.revenue.sum())


def test_drop_detected(df):
    drop = find_drop(df)
    assert drop["year"] == 2023
    assert drop["quarter"] == 2
    assert drop["pct"] <= -20.0  # the flagged ~22% drop


def test_data_shape(df):
    assert len(df) == 100_000
    assert df.region.nunique() >= 50
    assert set(df.columns) >= {"order_id", "date", "region", "revenue"}
