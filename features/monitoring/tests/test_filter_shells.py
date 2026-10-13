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
    """PD/LGD/EAD/Loss select exactly one model. Deliberate, and load-bearing:
    these tabs *look up* their metrics rather than computing them --
    ``calculations.ctx_store_keys`` resolves one
    ``(model, segment, quarter, horizon)`` row and the store holds only
    per-model rows, with no aggregate. Given several models it would return
    ``models[0]`` and silently drop the rest, rendering one model's numbers
    under a toggle claiming several. Overview is the only multi-select Model
    filter -- see ``test_overview_is_the_only_multi_select_model_filter``.
    """
    from STATpy_platform.shared.ui import controls as pd_controls
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA

    pages = [
        ([pd_controls.build_global_filters(PD_PERFORMANCE_DATA)], pd_controls.MODELS_ID),
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
        assert model_filter is not None, component_id
        # A single-select Dropdown, not a multi checklist.
        assert isinstance(model_filter, Dropdown), component_id
        assert getattr(model_filter, "multi", False) is not True, component_id


def test_overview_is_the_only_multi_select_model_filter():
    """The other half of the rule above. Overview pools models rather than
    reporting one model's diagnostics, so it takes a checklist -- and it is the
    only tab that may."""
    from dash.dcc import Checklist
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA

    model_filter = None
    for node in overview_page.page_layout(PD_PERFORMANCE_DATA):
        model_filter = _find_component_by_id(node, overview_page.OVERVIEW_MODEL_ID)
        if model_filter is not None:
            break
    assert isinstance(model_filter, Checklist)
    assert isinstance(model_filter.value, list)


def test_monitoring_point_opens_unanswered_on_every_tab():
    """It used to default to the latest visible quarter. The page now opens with
    nothing selected at all, so the control shows its "Select …" placeholder --
    ``resolve_monitoring_point_value`` is deliberately no longer reached from
    the initial layout, because it would answer the filter for the user."""
    from STATpy_platform.shared.ui.controls import SELECT_PROMPTS, UNSELECTED

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
        assert monitoring_point.value == UNSELECTED, component_id
        assert monitoring_point.options[0]["label"] == SELECT_PROMPTS["monitoring-point"], component_id


def test_the_read_seam_promotes_pd_monitoring_point_into_quarter():
    """Everything downstream means the **as-of** by ``quarter``. PD's sheet now
    uses ``Quarter`` for the cohort start, so the read seam swaps them and keeps
    the cohort start as ``cohort_quarter``. Without this the metrics store and
    the Monitoring Point filter would silently shift one to two years back.
    """
    from STATpy_platform.shared.repositories.tables import read_table

    pd_df = read_table("PD_Performance_Metrics")
    assert {"quarter", "cohort_quarter", "monitoring_point"} <= set(pd_df.columns)
    assert (pd_df["quarter"] == pd_df["monitoring_point"]).all()
    assert (pd_df["quarter"] != pd_df["cohort_quarter"]).all()

    # A sheet without the column is passed through untouched.
    lgd_df = read_table("LGD_Performance_Metrics")
    assert "cohort_quarter" not in lgd_df.columns
    assert "quarter" in lgd_df.columns


def test_pd_monitoring_points_are_the_as_of_dates_not_the_cohort_quarters():
    from STATpy_platform.shared.repositories.filters_config import monitoring_points_by_cycle

    points = monitoring_points_by_cycle("pd")
    assert points["CCAR 2026"] == ["2025Q4", "2026Q1", "2026Q2", "2026Q3"]


def test_every_tab_takes_its_model_list_from_its_own_metrics_sheet():
    """Including Loss, whose "All Models" used to be a hardcoded constant.

    Sourcing from the MEV catalogue instead let a tab offer models it has no
    metrics for: the two sources agreed until portfolio.xlsx was trimmed, after
    which PD's bar listed five models whose panels came back empty and whose
    scope could never enable Apply.
    """
    import pandas as pd
    from STATpy_platform.config.settings import settings
    from STATpy_platform.shared.repositories import filters_config as fc
    from STATpy_platform.shared.repositories.tables import read_table

    for tab, sheet_name in fc._METRICS_SHEET_BY_TAB.items():
        from_sheet = sorted({str(v).strip() for v in read_table(sheet_name)["model"].dropna().unique()})
        assert fc.model_names(tab) == from_sheet, tab

    # ... and nothing is hardcoded: deleting the constant that used to supply
    # Loss would not change the answer, because there is no constant.
    assert not hasattr(fc, "_LOSS_MODEL_NAMES")
