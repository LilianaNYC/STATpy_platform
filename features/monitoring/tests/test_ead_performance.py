"""Smoke test for the EAD Performance page (placeholder)."""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import ead_performance as page


def _children_of(node) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _collect_text(node) -> str:
    if isinstance(node, str):
        return node
    if not isinstance(node, Component):
        return ""
    return " ".join(_collect_text(child) for child in _children_of(node))


def _collect_class_tokens(node) -> set[str]:
    if not isinstance(node, Component):
        return set()
    class_name = getattr(node, "className", "") or ""
    tokens = set(class_name.split())
    for child in _children_of(node):
        tokens |= _collect_class_tokens(child)
    return tokens


def _render_ead_content():
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA as data
    from STATpy_platform.features.monitoring.domain.ead import set_ead_metrics

    cycle = data["observations_by_cycle"]["CCAR 2026"]
    set_ead_metrics(cycle["metrics_store"], cycle["quarters"])
    try:
        return page.render_ead_performance_content(
            data,
            selected_model=None,
            selected_segment="All",
            selected_monitoring_point=cycle["quarters"][-1],
            reporting_cycle="CCAR 2026",
            scenario="intsevere",
        )
    finally:
        set_ead_metrics(None, None)


def test_ead_performance_layout_builds():
    layout = page.page_layout()
    assert isinstance(layout, list) and layout


def test_ead_range_filters_render_at_section_level():
    layout = _render_ead_content()
    text = " ".join(_collect_text(node) for node in layout)
    class_tokens = set()
    for node in layout:
        class_tokens |= _collect_class_tokens(node)

    assert "pd-section-filter-bar" in class_tokens
    assert "Calibration Conservatism RAG Trend" in text
    assert "Mean Error Trend" in text
    assert "RMSE Trend" in text
    assert "Kendall's Tau Trend" in text
