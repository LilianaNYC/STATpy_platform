from __future__ import annotations

import dash
import polars as pl

from Dashboards import data_store
from Dashboards.app import create_app
from Dashboards.data.overview import build_overview_rows, overview_summary
from Dashboards.data.transformations import (
    get_pd_range_preset,
    get_pd_range_selection,
    get_previous_pd_quarter,
)


def test_app_factory_creates_dash_app():
    app = create_app()

    assert isinstance(app, dash.Dash)
    assert app.title == "Wholesale Portfolio Model Monitoring Dashboard"


def test_pd_data_loads_expected_core_payload():
    data = data_store.get_pd_performance_data()

    assert isinstance(data["portfolio"], pl.DataFrame)
    assert data["quarters"]
    assert data["latest_quarter"] in data["quarters"]
    assert data["model_names"]
    assert data["segment_values"]
    assert data["performance_observations"]


def test_overview_data_loads_from_dashboard_payload():
    data = data_store.get_pd_performance_data()
    rows = build_overview_rows(data)
    summary = overview_summary(rows)

    assert rows
    assert {row["Model Group"] for row in rows} >= {"PD", "LGD", "EAD"}
    assert summary["models"] > 0


def test_quarter_and_range_helpers():
    periods = ["2022Q1", "2022Q2", "2022Q3", "2022Q4"]

    assert get_previous_pd_quarter("2022Q1") == "2021Q4"
    assert get_pd_range_selection({"from": "2022Q2", "to": ""}, periods) == {
        "from": "2022Q2",
        "to": "",
    }
    assert get_pd_range_preset({"from": "2022Q1", "to": "2022Q4"}, periods) == "last-4"
