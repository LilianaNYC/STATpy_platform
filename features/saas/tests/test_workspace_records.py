"""Unit tests for SAAS workspace record filters."""

from __future__ import annotations

from datetime import datetime

from STATpy_platform.features.saas.domain import records


def test_filter_records_by_snapshot_period_keeps_expected_quarters():
    rows = [
        {"Quarter": -1, "MEV Name": "A"},
        {"Quarter": 0, "MEV Name": "B"},
        {"Quarter": 1, "MEV Name": "C"},
        {"Quarter": "", "MEV Name": "D"},
    ]

    assert [row["MEV Name"] for row in records.filter_records_by_snapshot_period(rows, "history")] == ["A", "B"]
    assert [row["MEV Name"] for row in records.filter_records_by_snapshot_period(rows, "projection")] == ["B", "C"]


def test_filter_records_by_date_range_uses_available_date_bounds():
    rows = [
        {"Date": datetime(2024, 3, 31), "MEV Name": "A"},
        {"Date": datetime(2024, 6, 30), "MEV Name": "B"},
        {"Date": datetime(2024, 9, 30), "MEV Name": "C"},
    ]

    filtered = records.filter_records_by_date_range(
        rows,
        {"from": "2024-06-30", "to": "2024-09-30"},
    )

    assert [row["MEV Name"] for row in filtered] == ["B", "C"]


def test_filter_records_by_scenarios_respects_all_value():
    rows = [
        {"Scenario": "baseline", "MEV Name": "A"},
        {"Scenario": "intsevere", "MEV Name": "B"},
    ]

    assert records.filter_records_by_scenarios(rows, ["all"]) == rows
    assert records.filter_records_by_scenarios(rows, ["BASELINE"]) == [rows[0]]


def test_build_scenario_options_deduplicates_and_formats_labels():
    rows = [
        {"Scenario": "baseline"},
        {"Scenario": "BASELINE"},
        {"Scenario": "int_severe"},
        {"Scenario": ""},
    ]

    assert records.build_scenario_options(rows) == [
        {"label": "Baseline", "value": "baseline"},
        {"label": "Int Severe", "value": "int_severe"},
    ]


def test_build_model_mev_options_sorts_by_selected_label_mode(monkeypatch):
    monkeypatch.setitem(
        records.SAAS_PAGE_DATA,
        "mev_label_map",
        {"MEV A": "Descriptive A"},
    )
    rows = [
        {"MEV Name": "MEV B"},
        {"MEV Name": "MEV A"},
        {"MEV Name": "MEV A"},
        {"MEV Name": ""},
    ]

    assert records.build_model_mev_options(rows, "long_name") == [
        {"label": "Descriptive A", "value": "MEV A"},
        {"label": "MEV B", "value": "MEV B"},
    ]


def test_active_selected_mevs_expands_family_when_requested(monkeypatch):
    monkeypatch.setitem(
        records.SAAS_PAGE_DATA,
        "model_mev_family_map",
        {"Model A": {"Transformed A": ["Raw A", "Raw B"]}},
    )
    rows = [
        {"MEV Name": "Transformed A"},
        {"MEV Name": "Raw B"},
    ]

    assert records.family_display_mevs("Model A", "Transformed A", rows) == ["Transformed A", "Raw B"]
    assert records.active_selected_mevs("Model A", "family", "Transformed A", ["Raw A"], rows) == [
        "Transformed A",
        "Raw B",
    ]
    assert records.active_selected_mevs("Model A", "raw_only", "Transformed A", ["Raw A"], rows) == ["Raw A"]
