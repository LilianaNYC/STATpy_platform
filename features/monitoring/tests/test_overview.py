"""Focused regression tests for the Overview page."""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.domain.overview import governance_summary
from STATpy_platform.features.monitoring.ui.views.overview import (
    _build_governance_section,
    _heatmap_column_headers,
    _rag_heatmap_figure,
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

    assert "Overall" in text
    assert "overview-heatmap-column-header-overall" in class_tokens
    assert "overview-heatmap-column-header-kicker" in class_tokens


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
