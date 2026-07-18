"""Unit tests for SAAS workspace report orchestration helpers."""

from __future__ import annotations

import plotly.graph_objects as go

from STATpy_platform.features.saas.services import exports, reports


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


def test_build_saas_report_html_group_kicker_carries_descriptive_name_no_gmis_name():
    """Mirrors the workspace UI: the group kicker is "N. <Model Descriptive Name>"
    with no separate heading duplicating it, and a child model's section no longer
    surfaces the raw GMIS Model Name (see components.build_model_group_card /
    build_model_panel, which dropped the redundant H4 and the GMIS-name tooltip).
    The report's "Model structure" coverage-tree page (Region -> Portfolio ->
    Model Group -> parent -> segment) drops the raw Model Name too."""
    groups = [
        {
            "parent_label": "PD Model A",
            "shared_attributes": ["Region: US"],
            "models": [
                {
                    "model_name": "PD_MODEL_A_001",
                    "segment_label": "Cyclical",
                    "attributes": [],
                    "figures": [],
                },
            ],
        },
    ]

    html = exports.build_saas_report_html(groups, [])

    # Nowhere in the report -- neither the coverage tree nor the per-model
    # chart section -- should the raw GMIS Model Name appear.
    assert "PD_MODEL_A_001" not in html
    assert "saas-report-tree-gmis" not in html
    assert "Cyclical" in html  # the segment is still shown, just not the GMIS name

    group_section = html[html.index('<section class="saas-report-group"') :]
    assert "1. PD Model A" in group_section
    assert "<h2>" not in group_section
    assert "saas-report-gmis" not in group_section
    assert "Cyclical" in html


def test_build_saas_report_html_toc_counts_segments_not_models():
    """The Contents entry counts distinct segments, not raw models -- with the
    GMIS Model Name no longer shown, "N models" was an opaque, untraceable
    count; "N segments" matches what a reader can actually see and verify."""
    groups = [
        {
            # Two Model Names (PD_model_d / PD_model_e) sharing one Descriptive
            # Name, each with its own single segment -> 2 distinct segments.
            "parent_label": "PD Model D",
            "shared_attributes": [],
            "models": [
                {"model_name": "PD_model_d", "segment_label": "Cyclical", "attributes": [], "figures": [("t", go.Figure())]},
                {"model_name": "PD_model_e", "segment_label": "Defensive", "attributes": [], "figures": [("t", go.Figure())]},
            ],
        },
        {
            # A single model spanning two segments -> still 2 distinct segments,
            # even though there is only one model dict.
            "parent_label": "EAD Model A",
            "shared_attributes": [],
            "models": [
                {"model_name": "EAD_model_a", "segment_label": "Cyclical, Defensive", "attributes": [], "figures": []},
            ],
        },
    ]

    html = exports.build_saas_report_html(groups, [])
    toc = html[html.index('<nav class="saas-report-toc">') : html.index("</nav>")]

    assert "2 segments &middot; 2 charts" in toc
    assert "2 segments &middot; 0 charts" in toc
    assert "1 model" not in toc
    assert "2 model" not in toc


def test_build_saas_report_html_model_headings_are_numbered_group_dot_model():
    """Each model section heading is "N.N. <segment>" -- matching the live
    workspace's child-panel kicker numbering (e.g. "1.1. CYCLICAL") -- so a
    reader can cross-reference a chart back to its position in the hierarchy."""
    groups = [
        {
            "parent_label": "PD Model D",
            "shared_attributes": [],
            "models": [
                {"model_name": "PD_model_d", "segment_label": "Cyclical", "attributes": [], "figures": []},
                {"model_name": "PD_model_e", "segment_label": "Defensive", "attributes": [], "figures": []},
            ],
        },
        {
            "parent_label": "EAD Model A",
            "shared_attributes": [],
            "models": [
                {"model_name": "EAD_model_a", "segment_label": "Cyclical", "attributes": [], "figures": []},
            ],
        },
    ]

    html = exports.build_saas_report_html(groups, [])

    assert "<h3>1.1. Cyclical</h3>" in html
    assert "<h3>1.2. Defensive</h3>" in html
    assert "<h3>2.1. Cyclical</h3>" in html
