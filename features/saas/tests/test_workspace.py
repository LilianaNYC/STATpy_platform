"""Smoke test for the SAAS workspace page: the layout builds without raising."""

from __future__ import annotations

from dash.dcc import Loading
from dash.development.base_component import Component

from STATpy_platform.features.saas.ui.views import workspace as page


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


def test_workspace_layout_builds():
    layout = page.page_layout()
    assert isinstance(layout, list) and layout


def test_workspace_wraps_model_panel_stack_in_loading_shell():
    layout = page.page_layout()
    assert any(_contains_loading(node) for node in layout)

    panel_stack = None
    for node in layout:
        panel_stack = _find_component_by_id(node, page.MEV_MODEL_PANELS_ID)
        if panel_stack is not None:
            break

    assert panel_stack is not None
    assert "saas-model-panel-stack" in (getattr(panel_stack, "className", "") or "")


def test_workspace_includes_export_loading_targets():
    layout = page.page_layout()
    target_ids = {
        page.DOWNLOAD_REPORT_STATUS_ID,
        page.EXCEL_STATUS_ID,
        page.RECON_STATUS_ID,
        page.PROJECTION_STATUS_ID,
    }

    found_ids = set()
    for node in layout:
        for component_id in list(target_ids):
            if _find_component_by_id(node, component_id) is not None:
                found_ids.add(component_id)

    assert found_ids == target_ids
