"""Smoke and structure tests for the Monitoring Overview page."""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import overview as page


EXPECTED_WORKSTREAM_PATHS = {
    "/overview",
    "/",
    "/lgd-performance",
    "/ead-performance",
    "/loss-performance",
}


def _children_of(node) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _collect_workstream_paths(node) -> set[str]:
    if not isinstance(node, Component):
        return set()

    collected = set()
    class_name = getattr(node, "className", "") or ""
    href = getattr(node, "href", None)
    if isinstance(href, str) and "overview-workstream-card" in class_name.split():
        collected.add(href)

    for child in _children_of(node):
        collected |= _collect_workstream_paths(child)

    return collected


def _collect_text(node) -> list[str]:
    if node is None:
        return []
    if isinstance(node, str):
        return [node]
    if not isinstance(node, Component):
        return []

    collected = []
    for child in _children_of(node):
        collected.extend(_collect_text(child))
    return collected


def _collect_class_tokens(node) -> set[str]:
    if not isinstance(node, Component):
        return set()

    class_name = getattr(node, "className", "") or ""
    tokens = set(class_name.split())
    for child in _children_of(node):
        tokens |= _collect_class_tokens(child)
    return tokens


def _count_class_token(node, token: str) -> int:
    if not isinstance(node, Component):
        return 0

    class_name = getattr(node, "className", "") or ""
    count = 1 if token in class_name.split() else 0
    for child in _children_of(node):
        count += _count_class_token(child, token)
    return count


def test_overview_layout_builds():
    layout = page.build_layout()
    assert isinstance(layout, list) and layout


def test_overview_build_stores():
    stores = page.build_stores()
    assert {store.id for store in stores} == {"overview-range-store"}


def test_overview_workstream_links_render():
    layout = page.build_layout()
    workstream_paths = set()
    for node in layout:
        workstream_paths |= _collect_workstream_paths(node)

    assert workstream_paths == EXPECTED_WORKSTREAM_PATHS


def test_overview_summary_removes_health_rate_and_donut():
    layout = page.build_layout()
    text = []
    class_tokens = set()
    for node in layout:
        text.extend(_collect_text(node))
        class_tokens |= _collect_class_tokens(node)

    assert "Health Rate" not in text
    assert "overview-hero-donut" not in class_tokens


def test_overview_heatmap_renders_as_matrix():
    layout = page.build_layout()
    text = []
    class_tokens = set()
    heatmap_cell_count = 0
    for node in layout:
        text.extend(_collect_text(node))
        class_tokens |= _collect_class_tokens(node)
        heatmap_cell_count += _count_class_token(node, "overview-heatmap-cell")

    assert "RAG cells by status" in text
    assert "overview-heatmap-panel" in class_tokens
    assert "overview-heatmap-stat-grid" in class_tokens
    assert heatmap_cell_count > 0
