"""Unit tests for SAAS workspace metric helpers."""

from __future__ import annotations

from datetime import datetime

from STATpy_platform.features.saas.pages.workspace import metrics


def test_excel_quarter_label_formats_datetime_values():
    assert metrics.excel_quarter_label(datetime(2024, 1, 15)) == "2024Q1"
    assert metrics.excel_quarter_label(datetime(2024, 12, 31)) == "2024Q4"


def test_compute_saas_metric_record_uses_history_and_projection_values():
    rows = [
        {"Date": datetime(2020, 3, 31), "Quarter": -1, "MEV Value": 1.0},
        {"Date": datetime(2020, 6, 30), "Quarter": 0, "MEV Value": 3.0},
        {"Date": datetime(2020, 9, 30), "Quarter": 1, "MEV Value": 5.0},
    ]

    record = metrics.compute_saas_metric_record(
        "Model A",
        "MEV X",
        rows,
        baseline_min=0.5,
        baseline_max=6.0,
    )

    assert record is not None
    assert record["model_descriptive"] == "Model A"
    assert record["history_min"] == 1.0
    assert record["history_max"] == 3.0
    assert record["sevadv_max"] == 5.0
    assert record["minmax_daterange"] == "2020-03-31 to 2020-06-30"


def test_compute_historical_dispersion_stats_for_visible_lines():
    rows = [
        {"Date": datetime(2024, 3, 31), "Scenario": "baseline", "Run For": "Cycle A", "MEV Value": 1.0},
        {"Date": datetime(2024, 3, 31), "Scenario": "baseline", "Run For": "Cycle B", "MEV Value": 3.0},
        {"Date": datetime(2024, 6, 30), "Scenario": "baseline", "Run For": "Cycle A", "MEV Value": 2.0},
        {"Date": datetime(2024, 6, 30), "Scenario": "baseline", "Run For": "Cycle B", "MEV Value": 6.0},
        {"Date": datetime(2024, 6, 30), "Scenario": "intsevere", "Run For": "Cycle C", "MEV Value": 99.0},
    ]

    stats = metrics.compute_historical_dispersion_stats(rows, ["baseline"])

    assert stats is not None
    assert stats["has_dispersion"] is True
    assert stats["visible_lines"] == 2
    assert stats["matched_quarters"] == 2
    assert stats["avg_range"] == 3.0
    assert stats["max_range"] == 4.0
    assert stats["max_range_date"] == datetime(2024, 6, 30)


def test_compute_historical_dispersion_stats_requires_two_lines():
    rows = [
        {"Date": datetime(2024, 3, 31), "Scenario": "baseline", "Run For": "Cycle A", "MEV Value": 1.0},
    ]

    stats = metrics.compute_historical_dispersion_stats(rows, ["baseline"])

    assert stats == {
        "visible_lines": 1,
        "matched_quarters": 0,
        "has_dispersion": False,
    }
