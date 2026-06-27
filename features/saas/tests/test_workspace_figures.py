"""Unit tests for SAAS workspace figure builders."""

from __future__ import annotations

from datetime import datetime

from STATpy_platform.features.saas.ui.views import figures, workspace as page


def test_build_model_figure_filters_records_and_passes_chart_options(monkeypatch):
    captured = {}

    def fake_time_series_figure(records_arg, **kwargs):
        captured["records"] = records_arg
        captured["kwargs"] = kwargs
        return {"figure": "ok"}

    monkeypatch.setattr(figures, "build_saas_mev_time_series_figure", fake_time_series_figure)
    monkeypatch.setattr(
        figures.selectors,
        "active_mev_label_map",
        lambda label_mode: {"MEV A": "Label A"} if label_mode == "long_name" else {},
    )
    monkeypatch.setattr(
        figures.selectors,
        "projection_start_date_for_run_for",
        lambda run_for: "projection-start" if run_for == "Cycle A" else None,
    )

    rows = [
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 3, 31)},
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 6, 30)},
        {"MEV Name": "MEV A", "Scenario": "intsevere", "Date": datetime(2024, 6, 30)},
        {"MEV Name": "MEV B", "Scenario": "baseline", "Date": datetime(2024, 6, 30)},
    ]
    reference_rows = [
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 3, 31)},
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 6, 30)},
        {"MEV Name": "MEV B", "Scenario": "baseline", "Date": datetime(2024, 6, 30)},
    ]

    result = figures.build_model_figure(
        "Model A",
        rows,
        reference_rows,
        "family",
        ["baseline"],
        "history",
        "long_name",
        {"from": "2024-06-30", "to": "2024-06-30"},
        None,
        primary_run_for="Cycle A",
        development_date="development-date",
        current_date="current-date",
        selected_mevs=["MEV A"],
        theme_value="light",
    )

    assert result == {"figure": "ok"}
    assert captured["records"] == [
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 6, 30)}
    ]
    assert captured["kwargs"]["historical_reference_records"] == [
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 6, 30)}
    ]
    assert captured["kwargs"]["monitoring_reference_records"] == [
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 3, 31)},
        {"MEV Name": "MEV A", "Scenario": "baseline", "Date": datetime(2024, 6, 30)},
    ]
    assert captured["kwargs"]["mev_label_map"] == {"MEV A": "Label A"}
    assert captured["kwargs"]["y_axis_title"] == "Label A"
    assert captured["kwargs"]["reference_lines"] == page.DEFAULT_REFERENCE_LINES
    assert captured["kwargs"]["snapshot_period"] == "history"
    assert captured["kwargs"]["projection_start_date"] == "projection-start"
    assert captured["kwargs"]["theme"] == "light"
