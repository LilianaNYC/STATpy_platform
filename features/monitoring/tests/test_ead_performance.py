"""Smoke tests for the EAD Performance page."""

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


def _collect_prop_values(node, prop_name: str) -> list[str]:
    if not isinstance(node, Component):
        return []
    values = []
    value = getattr(node, prop_name, None)
    if isinstance(value, str):
        values.append(value)
    for child in _children_of(node):
        values.extend(_collect_prop_values(child, prop_name))
    return values


def _render_ead_content_with(**overrides):
    """Render the live dashboard content (post-Apply), not the getting-started prompt."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA as data
    from STATpy_platform.features.monitoring.domain.ead import set_ead_metrics

    cycle = data["ead_observations_by_cycle"]["CCAR 2026"]
    set_ead_metrics(cycle.get("metrics_store"), cycle.get("quarters"))
    try:
        return page.render_ead_performance_content(
            data, "EAD Model A", "All", "2026Q3", {},
            reporting_cycle="CCAR 2026", scenario="intsevere",
            scenario_ranking_store={}, theme_value="light",
            **overrides,
        )
    finally:
        set_ead_metrics(None, [])


def _render_ead_content():
    return _render_ead_content_with()


def test_ead_performance_layout_builds():
    layout = page.page_layout()
    assert isinstance(layout, list) and layout


def test_ead_main_overview_and_conclusion_render():
    layout = _render_ead_content()
    text = " ".join(_collect_text(node) for node in layout)
    ids = []
    for node in layout:
        ids.extend(_collect_prop_values(node, "id"))

    assert "Dashboard Main Overview" in text
    assert "Chapter breakdown" in text
    assert "Calibration Conservatism" in text
    assert "Discriminatory Power" in text
    assert "PSI" in text
    assert "Scenario Ranking" in text
    assert "Sensitivity Analysis" in text
    assert "MEV Range" in text
    assert "3.1 Conclusion" in text
    assert "Post Subjective Review RAG" in text
    assert "Pre Mitigation RAG" in text
    assert "Post Mitigation RAG" in text
    assert "Reviewer sign-off" in text
    assert "ead-dashboard-overview" in ids
    assert "ead-conclusions-verdict" in ids
    assert text.index("Dashboard Main Overview") < text.index("RAG Assignment")


def test_ead_subnav_has_overview_and_conclusion_group_first():
    layout = page.page_layout()
    text = " ".join(_collect_text(node) for node in layout)

    assert "Overview & Conclusion" in text
    assert "Main Overview" in text
    assert text.index("Overview & Conclusion") < text.index("Main Overview")
    assert text.index("Main Overview") < text.index("RAG Assignment")
    assert "RAG Assignment Overview" in text
    assert "Post Subjective Review Analysis" in text
    assert text.index("RAG Assignment Overview") < text.index("Post Subjective Review Analysis")
    assert "Post Subjective Review Analysis Overview" in text


def test_apply_ead_filters_clears_the_reviewer_signoff_draft(monkeypatch):
    from dash import no_update

    import STATpy_platform.features.monitoring.callbacks.ead_performance as cb

    captured: dict = {}

    class StubApp:
        def callback(self, *args, **kwargs):
            def decorator(fn):
                captured[fn.__name__] = fn
                return fn

            return decorator

    monkeypatch.setattr(cb, "already_registered", lambda app, key: False)
    cb.register_callbacks(StubApp())

    apply_fn = captured["apply_ead_filters"]
    applied, notes, pending, save_status = apply_fn(
        1, "CCAR 2026", "intsevere", "EAD Model A", "All", "2026Q3",
    )
    assert applied["monitoring_point"] == "2026Q3"
    assert notes == "", "an Apply click must discard the unsaved sign-off draft"
    assert pending == {}, "an Apply click must discard staged review-flow RAG picks"
    assert save_status == "", "an Apply click must discard the stale save-status message"

    # Spurious fire (router re-insert, n_clicks=0) must touch no store.
    assert apply_fn(0, "CCAR 2026", "intsevere", "EAD Model A", "All", "2026Q3") == (
        no_update, no_update, no_update, no_update,
    )
