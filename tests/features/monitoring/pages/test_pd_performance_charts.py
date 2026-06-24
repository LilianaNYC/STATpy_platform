"""Structural regression tests for PD Performance chapter-one charts."""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.pages.pd_performance import page


CHAPTER_ONE_CHART_IDS = {
    "pd-calibration-rag-trend-chart",
    "pd-confidence-interval-trend-chart",
    "pd-notching-trend-chart",
    "pd-default-rate-trend-chart",
    "pd-discrimination-rag-trend-chart",
    "pd-go-live-accuracy-trend-chart",
    "pd-discrimination-trend-gini-coefficient",
    "pd-discrimination-trend-ks-statistic",
    "pd-discrimination-trend-kendall-tau",
    "pd-balance-sheet-calibration-rag-trend-chart",
    "pd-balance-sheet-confidence-interval-trend-chart",
    "pd-balance-sheet-notching-trend-chart",
    "pd-balance-sheet-default-rate-trend-chart",
}


def _children_of(node) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _collect_chart_ids_with_surface(node, *, inside_surface: bool = False) -> set[str]:
    if not isinstance(node, Component):
        return set()

    class_name = getattr(node, "className", "") or ""
    node_is_surface = "pd-chart-card-surface" in class_name.split()
    current_inside_surface = inside_surface or node_is_surface

    collected = set()
    node_id = getattr(node, "id", None)
    if isinstance(node_id, str) and node_id in CHAPTER_ONE_CHART_IDS and current_inside_surface:
        collected.add(node_id)

    for child in _children_of(node):
        collected |= _collect_chart_ids_with_surface(child, inside_surface=current_inside_surface)

    return collected


def test_chapter_one_charts_render_inside_chart_surfaces():
    layout = page.build_layout()
    chart_ids = set()
    for node in layout:
        chart_ids |= _collect_chart_ids_with_surface(node)

    assert chart_ids == CHAPTER_ONE_CHART_IDS
