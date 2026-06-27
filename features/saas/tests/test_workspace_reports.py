"""Unit tests for SAAS workspace report orchestration helpers."""

from __future__ import annotations

from STATpy_platform.features.saas.services import reports


def test_run_for_filename_prefix_sanitizes_selected_cycle(monkeypatch):
    monkeypatch.setattr(
        reports.selectors,
        "RUN_FOR_OPTIONS",
        [{"label": "CCAR 2025 / Q1", "value": "CCAR 2025 / Q1"}],
    )

    assert reports.run_for_filename_prefix("CCAR 2025 / Q1") == "CCAR-2025-Q1"
    assert reports.run_for_filename_prefix("missing") == "SAAS"


def test_build_model_report_figures_filters_to_selected_mevs():
    calls = []

    def build_figure(*args):
        calls.append(args)
        return {"selected_mevs": args[12]}

    sections = reports.build_model_report_figures(
        "Model A",
        [
            {"MEV Name": "MEV A", "Scenario": "baseline"},
            {"MEV Name": "MEV B", "Scenario": "baseline"},
        ],
        [
            {"MEV Name": "MEV B", "Scenario": "baseline", "Run For": "Cycle A"},
            {"MEV Name": "MEV C", "Scenario": "baseline", "Run For": "Cycle A"},
        ],
        "family",
        ["baseline"],
        "history",
        None,
        None,
        ["MEV B", "missing"],
        figure_builder=build_figure,
    )

    assert sections == [("Model A — MEV B", {"selected_mevs": ["MEV B"]})]
    assert len(calls) == 1
    assert calls[0][1] == [{"MEV Name": "MEV B", "Scenario": "baseline"}]
    assert calls[0][2] == [{"MEV Name": "MEV B", "Scenario": "baseline", "Run For": "Cycle A"}]


def test_build_model_report_figures_requires_single_monitoring_scenario():
    def fail_if_called(*_args):
        raise AssertionError("figure builder should not be called")

    sections = reports.build_model_report_figures(
        "Model A",
        [
            {"MEV Name": "MEV A", "Scenario": "baseline"},
            {"MEV Name": "MEV A", "Scenario": "intsevere"},
        ],
        [],
        "family",
        ["baseline", "intsevere"],
        "history",
        None,
        "monitoring",
        ["MEV A"],
        figure_builder=fail_if_called,
    )

    assert sections == []


def test_build_model_report_sections_uses_default_panel_selection(monkeypatch):
    monkeypatch.setattr(
        reports.selectors,
        "RUN_FOR_OPTIONS",
        [{"label": "Cycle A", "value": "Cycle A"}],
    )
    monkeypatch.setitem(
        reports.records.SAAS_PAGE_DATA,
        "model_mev_map",
        {"Model A": {"transformed": ["MEV A"], "raw": []}},
    )

    calls = []

    def build_figure(*args):
        calls.append(args)
        return {"selected_mevs": args[12]}

    sections = reports.build_model_report_sections(
        "Model A",
        [
            {"MEV Name": "MEV A", "Scenario": "baseline", "Quarter": 0},
            {"MEV Name": "MEV A", "Scenario": "baseline", "Quarter": 1},
        ],
        "Cycle A",
        "history",
        None,
        None,
        figure_builder=build_figure,
    )

    assert sections == [("Model A — MEV A", {"selected_mevs": ["MEV A"]})]
    assert calls[0][4] == ["baseline"]
