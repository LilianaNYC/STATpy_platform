"""Regression coverage for Monitoring top filter dropdown shells."""

from __future__ import annotations

from dash.development.base_component import Component
from dash.dcc import Dropdown

from STATpy_platform.features.monitoring.ui import common as filter_shell
from STATpy_platform.features.monitoring.ui.views import overview as overview_page
from STATpy_platform.features.monitoring.ui.views import ead_performance as ead_page
from STATpy_platform.features.monitoring.ui.views import lgd_performance as lgd_page
from STATpy_platform.features.monitoring.ui.views import loss_performance as loss_page


def _children_of(node) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _count_class_token(node, token: str) -> int:
    if not isinstance(node, Component):
        return 0

    class_name = getattr(node, "className", "") or ""
    count = 1 if token in class_name.split() else 0
    for child in _children_of(node):
        count += _count_class_token(child, token)
    return count


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


def test_monitoring_top_filters_use_pd_single_select_shells():
    pages = [
        (lgd_page.build_layout(), 2),
        (ead_page.page_layout(), 2),
        (loss_page.build_layout(), 2),
    ]

    for layout, expected_count in pages:
        count = sum(_count_class_token(node, "single-select-dropdown") for node in layout)
        assert count >= expected_count


def test_performance_specific_models_use_single_select_dropdown():
    pages = [
        (lgd_page.build_layout(), lgd_page.MODEL_DROPDOWN_ID),
        (ead_page.page_layout(), ead_page.MODEL_DROPDOWN_ID),
        (loss_page.build_layout(), loss_page.MODEL_DROPDOWN_ID),
    ]

    for layout, component_id in pages:
        model_filter = None
        for node in layout:
            model_filter = _find_component_by_id(node, component_id)
            if model_filter is not None:
                break
        # Models is a single-select Dropdown (not a multi checklist) on
        # the LGD/EAD/Loss tabs.
        assert isinstance(model_filter, Dropdown)
        assert getattr(model_filter, "multi", False) is not True


def test_monitoring_point_defaults_use_latest_visible_option():
    pages = [
        (overview_page.build_layout(), overview_page.MONITORING_POINT_ID),
        (lgd_page.build_layout(), lgd_page.MONITORING_POINT_DROPDOWN_ID),
        (ead_page.page_layout(), ead_page.MONITORING_POINT_DROPDOWN_ID),
        (loss_page.build_layout(), loss_page.MONITORING_POINT_DROPDOWN_ID),
    ]

    for layout, component_id in pages:
        monitoring_point = None
        for node in layout:
            monitoring_point = _find_component_by_id(node, component_id)
            if monitoring_point is not None:
                break

        assert isinstance(monitoring_point, Dropdown)
        option_values = [option["value"] for option in (monitoring_point.options or [])]
        assert monitoring_point.value == filter_shell.resolve_monitoring_point_value(option_values, None)
