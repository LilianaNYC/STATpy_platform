"""Focused regression tests for the Overview page."""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.callbacks.overview import (
    _checked_monitoring_point,
    _overview_filter_snapshot,
    _resolve_rag_flow_current_rows,
)
from STATpy_platform.features.monitoring.domain.overview import governance_summary
from STATpy_platform.features.monitoring.ui.views.overview import (
    _build_governance_section,
    _heatmap_column_headers,
    _heatmap_group_headers,
    _rag_heatmap_figure,
    _rag_flow_entity_browser,
    _rag_flow_models,
    _rag_flow_sankey_figure,
)


def _children_of(node) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _collect_text(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if not isinstance(node, Component):
        return []
    return [
        text
        for child in _children_of(node)
        for text in _collect_text(child)
    ]


def _collect_class_tokens(node) -> set[str]:
    if not isinstance(node, Component):
        return set()
    tokens = set((getattr(node, "className", "") or "").split())
    for child in _children_of(node):
        tokens |= _collect_class_tokens(child)
    return tokens


def _sample_governance_data() -> tuple[list[dict], list[dict]]:
    current_rows = [
        {
            "Model Group": "PD",
            "Model": "PD Model A",
            "Monitoring Period": "2025Q4",
            "Overall RAG": "Amber",
        },
        {
            "Model Group": "Loss",
            "Model": "Loss Model A",
            "Monitoring Period": "2025Q4",
            "Overall RAG": "Green",
        },
    ]
    findings = [
        {
            "Model Group": "PD",
            "Model": "PD Model A",
            "Monitoring Period": "2025Q4",
            "Metric": "Overall RAG",
            "RAG": "Amber",
        },
        {
            "Model Group": "PD",
            "Model": "PD Model A",
            "Monitoring Period": "2025Q4",
            "Metric": "Calibration RAG",
            "RAG": "Red",
        },
    ]
    return current_rows, findings


def test_governance_summary_prefers_underlying_test_as_driver():
    current_rows, findings = _sample_governance_data()

    summary = governance_summary(current_rows, findings)

    assert summary["top_metric"] == "Calibration RAG"
    assert summary["top_metric_count"] == 1
    assert "PD PD Model A" not in summary["narrative"]


def test_governance_section_renders_one_decision_board():
    current_rows, findings = _sample_governance_data()

    section = _build_governance_section(current_rows, findings)
    text = _collect_text(section)
    class_tokens = _collect_class_tokens(section)

    assert "Decision Summary" in text
    assert "Escalation required" in text
    assert "Escalation Register — 2025Q4" in text
    assert "Calibration RAG" in text
    assert "Portfolio RAG Mix" not in text
    assert "Overall RAG distribution" not in text
    assert "overview-governance-board" in class_tokens


def test_governance_narrative_preserves_underlying_red_escalation():
    current_rows, findings = _sample_governance_data()
    current_rows[0]["Overall RAG"] = "Green"
    findings = [row for row in findings if row["Metric"] != "Overall RAG"]

    summary = governance_summary(current_rows, findings)

    assert summary["red"] == 0
    assert len(summary["escalations"]) == 1
    assert "underlying test still requires escalation" in summary["narrative"]


def test_heatmap_headers_emphasize_overall_as_section_verdict():
    headers = _heatmap_column_headers(["Calibration RAG", "Discrimination RAG", "Balance Sheet Calibration RAG", "Overall RAG"])
    text = _collect_text(headers)
    class_tokens = _collect_class_tokens(headers)

    assert "Performance RAG" in text
    assert "overview-heatmap-column-header-overall" in class_tokens
    assert "overview-heatmap-column-tooltip" in class_tokens
    assert "?" not in text


def test_heatmap_review_and_mitigation_headers_keep_rag_suffix():
    group_text = _collect_text(_heatmap_group_headers())
    header_text = _collect_text(_heatmap_column_headers([
        "Post Subjective Review RAG",
        "Pre Mitigation RAG",
        "Post Mitigation RAG",
    ]))

    assert "2. Post Subjective Review" in group_text
    assert "Post Subjective Review RAG" in header_text
    assert "Pre Mitigation RAG" in header_text
    assert "Post Mitigation RAG" in header_text


def test_heatmap_figure_highlights_overall_column():
    rows = [
        {
            "Model Group": "PD",
            "Model": "PD Model A",
            "Monitoring Period": "2025Q4",
            "Calibration RAG": "Green",
            "Discrimination RAG": "Amber",
            "Balance Sheet Calibration RAG": "Red",
            "Overall RAG": "Red",
            "Transition Matrix RAG": "N/A",
            "PSI RAG": "Amber",
            "Scenario Ranking RAG": "Green",
            "Sensitivity Analysis RAG": "Green",
            "MEV Range RAG": "Green",
            "Transition Matrix Metric": "—",
            "PSI Metric": "0.142",
            "Scenario Ranking Metric": "Maintained",
            "Sensitivity Analysis Metric": "3.1%",
            "MEV Range Metric": "2 breaches",
        }
    ]

    figure = _rag_heatmap_figure(rows, "light")

    assert len(figure.layout.shapes) >= 3
    assert any(getattr(shape, "type", None) == "rect" for shape in figure.layout.shapes)


def test_rag_flow_sankey_uses_models_with_review_flow_data():
    rows = [
        {
            "Model Group": "PD",
            "Model": "PD Model A",
            "Monitoring Period": "2025Q4",
            "Overall RAG": "Green",
            "Post Subjective Review RAG": "Amber",
            "Pre Mitigation RAG": "Amber",
            "Post Mitigation RAG": "Green",
        },
        {
            "Model Group": "PD",
            "Model": "PD Model B",
            "Monitoring Period": "2025Q4",
            "Overall RAG": "Red",
            "Post Subjective Review RAG": "Amber",
            "Pre Mitigation RAG": "Green",
            "Post Mitigation RAG": "Green",
        },
        {
            "Model Group": "LGD",
            "Model": "LGD Model A",
            "Monitoring Period": "2025Q4",
            "Overall RAG": "Red",
            "Post Subjective Review RAG": "Red",
            "Pre Mitigation RAG": "Red",
            "Post Mitigation RAG": "Red",
        },
    ]

    figure = _rag_flow_sankey_figure(rows, "light")
    assert len(figure.data) == 13
    assert all(trace.type == "scatter" for trace in figure.data)
    bucket_counts = {
        (int(item[1]), str(item[2])): int(item[3])
        for trace in figure.data
        for item in (getattr(trace, "customdata", None) or [])
        if item and item[0] == "rag-bucket"
    }
    assert bucket_counts[(0, "Green")] == 1
    assert bucket_counts[(0, "Red")] == 2
    assert bucket_counts[(1, "Amber")] == 2
    assert bucket_counts[(3, "Green")] == 2
    assert len(figure.layout.shapes) >= 7


def test_rag_flow_sankey_focuses_bucket_and_highlights_selected_model():
    rows = [
        {
            "Model Group": "PD",
            "Model": "PD Model A",
            "Overall RAG": "Green",
            "Post Subjective Review RAG": "Amber",
            "Pre Mitigation RAG": "Amber",
            "Post Mitigation RAG": "Green",
        },
        {
            "Model Group": "PD",
            "Model": "PD Model B",
            "Overall RAG": "Red",
            "Post Subjective Review RAG": "Amber",
            "Pre Mitigation RAG": "Green",
            "Post Mitigation RAG": "Green",
        },
        {
            "Model Group": "LGD",
            "Model": "LGD Model A",
            "Overall RAG": "Red",
            "Post Subjective Review RAG": "Red",
            "Pre Mitigation RAG": "Red",
            "Post Mitigation RAG": "Red",
        },
    ]
    selection = {
        "stage_index": 1,
        "tone": "Amber",
        "entity": "PD Model A",
    }

    figure = _rag_flow_sankey_figure(rows, "light", selection=selection)
    browser = _rag_flow_entity_browser(rows, selection, "model")
    bucket_counts = {
        (int(item[1]), str(item[2])): int(item[3])
        for trace in figure.data
        for item in (getattr(trace, "customdata", None) or [])
        if item and item[0] == "rag-bucket"
    }
    text = _collect_text(browser)
    class_tokens = _collect_class_tokens(browser)

    assert bucket_counts[(1, "Amber")] == 2
    assert bucket_counts[(3, "Green")] == 2
    assert "PD Model A" in text
    assert "PD Model B" in text
    assert "LGD Model A" not in text
    assert "overview-rag-flow-entity-row-active" in class_tokens
    assert not any(
        getattr(trace, "mode", None) == "lines"
        and getattr(trace, "hoverinfo", None) == "skip"
        for trace in figure.data
    )
    entity_markers = next(
        trace
        for trace in figure.data
        if getattr(trace, "customdata", None)
        and trace.customdata[0][0] == "rag-entity"
    )
    entity_labels = [
        annotation
        for annotation in figure.layout.annotations
        if "PD Model A" in str(annotation.text)
    ]
    assert entity_markers.mode == "markers"
    assert entity_markers.marker.line.width == 0
    assert len(entity_labels) == 2
    assert {annotation.xanchor for annotation in entity_labels} == {"left", "right"}


def test_rag_flow_large_population_keeps_chart_bounded_and_lists_every_model():
    rows = [
        {
            "Model Group": "PD",
            "Model": f"Wholesale Credit Risk Model With A Long Name {index:02d}",
            "Overall RAG": "Green",
            "Post Subjective Review RAG": "Amber",
            "Pre Mitigation RAG": "Amber",
            "Post Mitigation RAG": "Green",
        }
        for index in range(50)
    ]
    selection = {
        "stage_index": 1,
        "tone": "Amber",
        "entity": None,
    }

    figure = _rag_flow_sankey_figure(rows, "dark", selection=selection)
    browser = _rag_flow_entity_browser(rows, selection, "model")
    entity_list = browser.children[1]

    assert figure.layout.height == 460
    assert len(entity_list.children) == 50
    assert "overview-rag-flow-entity-list" in (entity_list.className or "")


def test_rag_flow_excludes_incomplete_or_unnamed_journeys():
    rows = [
        {
            "Model Group": "PD",
            "Model": "Recorded Model",
            "Monitoring Period": "2026Q3",
            "Overall RAG": "Green",
            "Post Subjective Review RAG": "Amber",
            "Pre Mitigation RAG": "Amber",
            "Post Mitigation RAG": "Green",
        },
        {
            "Model Group": "PD",
            "Model": "Incomplete Model",
            "Monitoring Period": "2026Q3",
            "Overall RAG": "Green",
            "Post Subjective Review RAG": "",
            "Pre Mitigation RAG": "Amber",
            "Post Mitigation RAG": "Green",
        },
        {
            "Model Group": "",
            "Model": "",
            "Monitoring Period": "2026Q3",
            "Overall RAG": "Green",
            "Post Subjective Review RAG": "Green",
            "Pre Mitigation RAG": "Green",
            "Post Mitigation RAG": "Green",
        },
    ]

    flow_rows = _rag_flow_models(rows)

    assert [row["Entity Label"] for row in flow_rows] == ["PD Recorded Model"]
    assert flow_rows[0]["Monitoring Period"] == "2026Q3"


def test_rag_flow_click_state_keeps_the_current_monitoring_point_slice():
    model_rows = [
        {"Model Group": "PD", "Model": "Model A", "Monitoring Period": "2026Q2"},
        {"Model Group": "PD", "Model": "Model A", "Monitoring Period": "2026Q3"},
        {"Model Group": "LGD", "Model": "Model B", "Monitoring Period": "2026Q2"},
    ]
    segment_rows = [
        {"Model Group": "PD", "Segment": "Cyclical", "Monitoring Period": "2026Q2"},
        {"Model Group": "PD", "Segment": "Cyclical", "Monitoring Period": "2026Q3"},
        {"Model Group": "LGD", "Segment": "Defensive", "Monitoring Period": "2026Q2"},
    ]

    current_models, current_segments = _resolve_rag_flow_current_rows(
        model_rows,
        segment_rows,
        {"monitoring_point": "All"},
    )

    assert len(current_models) == 2
    assert len(current_segments) == 2
    assert {
        (row["Model"], row["Monitoring Period"])
        for row in current_models
    } == {("Model A", "2026Q3"), ("Model B", "2026Q2")}

    q3_models, q3_segments = _resolve_rag_flow_current_rows(
        model_rows,
        segment_rows,
        {"monitoring_point": "2026Q3"},
    )

    assert [(row["Model"], row["Monitoring Period"]) for row in q3_models] == [
        ("Model A", "2026Q3"),
    ]
    assert [(row["Segment"], row["Monitoring Period"]) for row in q3_segments] == [
        ("Cyclical", "2026Q3"),
    ]


def test_overview_initial_filter_snapshot_matches_visible_monitoring_point():
    snapshot = _overview_filter_snapshot("CCAR 2026", "2026Q3", "All")
    invalid_snapshot = _overview_filter_snapshot("CCAR 2026", "2024Q4", "PD")

    assert snapshot == {
        "reporting_cycle": "CCAR 2026",
        "monitoring_point": "2026Q3",
        "segment_model_group": "All",
    }
    assert invalid_snapshot == {
        "reporting_cycle": "CCAR 2026",
        "monitoring_point": "2026Q3",
        "segment_model_group": "PD",
    }


def test_overview_apply_uses_the_monitoring_point_with_the_checkmark():
    option_ids = [
        {"type": "pd-single-select-option", "filter": "overview-monitoring-point", "value": "2026Q1"},
        {"type": "pd-single-select-option", "filter": "overview-monitoring-point", "value": "2026Q2"},
        {"type": "pd-single-select-option", "filter": "overview-monitoring-point", "value": "2026Q3"},
    ]
    option_classes = [
        "single-select-option",
        "single-select-option is-selected",
        "single-select-option",
    ]

    selected = _checked_monitoring_point(
        option_ids,
        option_classes,
        fallback="2025Q4",
    )

    assert selected == "2026Q2"


def test_rag_flow_chart_colors_change_with_theme():
    rows = [
        {
            "Model Group": "PD",
            "Model": "Theme Model",
            "Monitoring Period": "2026Q3",
            "Overall RAG": "Green",
            "Post Subjective Review RAG": "Amber",
            "Pre Mitigation RAG": "Red",
            "Post Mitigation RAG": "Green",
        },
    ]

    light = _rag_flow_sankey_figure(rows, "light")
    dark = _rag_flow_sankey_figure(rows, "dark")
    light_transition = next(
        trace
        for trace in light.data
        if getattr(trace, "customdata", None)
        and trace.customdata[0][0] == "rag-transition"
    )
    dark_transition = next(
        trace
        for trace in dark.data
        if getattr(trace, "customdata", None)
        and trace.customdata[0][0] == "rag-transition"
    )
    light_bucket = next(
        trace
        for trace in light.data
        if getattr(trace, "customdata", None)
        and trace.customdata[0][0] == "rag-bucket"
    )
    dark_bucket = next(
        trace
        for trace in dark.data
        if getattr(trace, "customdata", None)
        and trace.customdata[0][0] == "rag-bucket"
    )

    assert light_transition.line.color != dark_transition.line.color
    assert list(light_bucket.marker.color) != list(dark_bucket.marker.color)
    assert light.layout.shapes[0].fillcolor != dark.layout.shapes[0].fillcolor
    assert light.layout.annotations[4].font.color != dark.layout.annotations[4].font.color
