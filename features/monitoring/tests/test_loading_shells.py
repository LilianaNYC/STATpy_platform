"""Regression coverage for shared Monitoring loading shells."""

from __future__ import annotations

from dash.dcc import Loading
from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import ead_performance as ead_page
from STATpy_platform.features.monitoring.ui.views import lgd_performance as lgd_page
from STATpy_platform.features.monitoring.ui.views import loss_performance as loss_page
from STATpy_platform.features.monitoring.ui.views import overview as overview_page
from STATpy_platform.features.monitoring.ui.views import pd_performance as pd_page


def _children_of(node) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _find_component_by_id(node, component_id):
    if not isinstance(node, Component):
        return None
    if getattr(node, "id", None) == component_id:
        return node
    for child in _children_of(node):
        found = _find_component_by_id(child, component_id)
        if found is not None:
            return found
    return None


def _contains_loading(node) -> bool:
    if isinstance(node, Loading):
        return True
    if not isinstance(node, Component):
        return False
    return any(_contains_loading(child) for child in _children_of(node))


def test_monitoring_pages_wrap_live_content_in_loading_shell():
    pages = [
        (overview_page.build_layout(), overview_page.CONTENT_ID),
        (pd_page.build_layout(), pd_page.CONTENT_ID),
        (lgd_page.build_layout(), lgd_page.CONTENT_ID),
        (ead_page.page_layout(), ead_page.CONTENT_ID),
        (loss_page.build_layout(), loss_page.CONTENT_ID),
    ]

    for layout, content_id in pages:
        assert any(_contains_loading(node) for node in layout)
        assert any(_find_component_by_id(node, content_id) is not None for node in layout)
