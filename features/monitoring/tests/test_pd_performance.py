"""Smoke test for the PD Performance page: the layout builds without raising."""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui import common as filter_shell
from STATpy_platform.features.monitoring.ui.views import pd_performance as page


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


def _collect_nodes_with_class(node, class_token: str) -> list[Component]:
    if not isinstance(node, Component):
        return []

    matches = []
    class_name = getattr(node, "className", "") or ""
    if class_token in class_name.split():
        matches.append(node)
    for child in _children_of(node):
        matches.extend(_collect_nodes_with_class(child, class_token))
    return matches


def _render_pd_content_with(**overrides):
    """Render the live dashboard content (post-Apply), not the getting-started prompt."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA as data
    from STATpy_platform.shared.domain.calculations import PdFilterContext, set_precomputed_metrics

    cycle = data["observations_by_cycle"]["CCAR 2026"]
    set_precomputed_metrics(cycle["metrics_store"])
    try:
        ctx = PdFilterContext(
            quarters=cycle["quarters"],
            models=set(data["model_names"]),
            segment="all",
            monitoring_point=cycle["quarters"][-1],
        )
        return page.render_pd_performance_content(
            {**data, "quarters": cycle["quarters"]},
            ctx,
            {},
            dict(page.DEFAULT_TREND_HORIZON_STORE),
            dict(page.DEFAULT_MEV_FILTER_STORE),
            {},
            reporting_cycle="CCAR 2026",
            scenario="intsevere",
            **overrides,
        )
    finally:
        set_precomputed_metrics(None)


def _render_pd_content():
    return _render_pd_content_with()


def test_pd_performance_layout_builds():
    layout = page.build_layout()
    assert isinstance(layout, list) and layout


def test_apply_filters_clears_the_reviewer_signoff_draft(monkeypatch):
    from dash import no_update

    import STATpy_platform.features.monitoring.callbacks.pd_performance as cb

    captured: dict = {}

    class StubApp:
        def callback(self, *args, **kwargs):
            def decorator(fn):
                captured[fn.__name__] = fn
                return fn

            return decorator

    monkeypatch.setattr(cb, "already_registered", lambda app, key: False)
    cb.register_callbacks(StubApp())

    apply_fn = captured["apply_pd_filters"]
    applied, notes, pending, save_status = apply_fn(1, "2026Q3", "all", "", "CCAR 2026", "intsevere")
    assert applied["monitoring_point"] == "2026Q3"
    assert notes == "", "an Apply click must discard the unsaved sign-off draft"
    assert pending == {}, "an Apply click must discard staged review-flow RAG picks"
    assert save_status == "", "an Apply click must discard the stale save-status message"

    # Spurious fire (router re-insert, n_clicks=0) must touch no store.
    assert apply_fn(0, "2026Q3", "all", "", "CCAR 2026", "intsevere") == (
        no_update, no_update, no_update, no_update,
    )


def test_navigating_to_pd_discards_unsaved_staged_state(monkeypatch):
    """Entering the PD page (path "/") clears staged RAG picks, the draft sign-off,
    and any stale save-status, so a page leave never leaves an unsaved edit behind.
    Navigating elsewhere leaves the stores untouched."""
    from dash import no_update

    import STATpy_platform.features.monitoring.callbacks.pd_performance as cb

    captured: dict = {}

    class StubApp:
        def callback(self, *args, **kwargs):
            def decorator(fn):
                captured[fn.__name__] = fn
                return fn

            return decorator

    monkeypatch.setattr(cb, "already_registered", lambda app, key: False)
    cb.register_callbacks(StubApp())

    discard_fn = captured["discard_pd_staged_state_on_entry"]
    # Entering the PD page resets the three staged stores.
    assert discard_fn("/") == ({}, "", "")
    # Any other page leaves them alone.
    assert discard_fn("/overview") == (no_update, no_update, no_update)
    assert discard_fn("/lgd-performance") == (no_update, no_update, no_update)


def test_pd_performance_build_stores():
    stores = page.build_stores()
    assert {store.id for store in stores} == {
        "pd-range-store",
        "pd-trend-horizon-store",
        "pd-mev-filter-store",
        "pd-scenario-ranking-store",
        "pd-applied-filters-store",
        "pd-conclusions-notes-store",
        "pd-review-flow-pending-store",
        "pd-review-flow-status-store",
    }


def test_pd_monitoring_point_shell_marks_only_the_selected_option():
    options = [
        {"label": "2025Q4", "value": "2025Q4"},
        {"label": "2026Q1", "value": "2026Q1"},
        {"label": "2026Q2", "value": "2026Q2"},
        {"label": "2026Q3", "value": "2026Q3"},
    ]

    label, buttons = filter_shell.build_single_select_shell(
        options=options,
        value="2025Q4",
        filter_key="monitoring-point",
    )

    assert label == "2025Q4"
    assert buttons[0].className == "single-select-option is-selected"
    assert all(button.className == "single-select-option" for button in buttons[1:])


def test_pd_main_overview_summarizes_both_chapters_before_the_deep_dive():
    layout = _render_pd_content()
    text = " ".join(_collect_text(node) for node in layout)
    ids = []
    class_tokens = set()
    aria_labels = []
    for node in layout:
        ids.extend(_collect_prop_values(node, "id"))
        class_tokens |= _collect_class_tokens(node)
        aria_labels.extend(_collect_prop_values(node, "aria-label"))

    assert "Dashboard Main Overview" in text
    assert "Overall posture" in text
    assert "How the dashboard story splits across the two chapters" in text
    assert "Recommended deep dive" in text
    assert "1. RAG Assignment" in text
    assert "2. Post Subjective Review Analysis" in text
    assert "Calibration Conservatism" in text
    assert "Discriminatory Power" in text
    assert "Performance PD RAG" in text
    assert "Transition Matrix" in text
    assert "Ranking maintained" in text
    assert "Peak shock impact" in text
    assert "Current scope" not in text
    assert "Areas Needing Attention" not in text
    assert "RAG Assignment Overall Status" not in text
    assert "Post Subjective Review Analysis Test Flagged" not in text
    assert "pd-dashboard-overview" in ids
    assert "overview-chapter-diagram" in class_tokens
    assert "overview-post-review-strip" in class_tokens
    assert "Overview area 1" in aria_labels
    assert "Overview area 8" in aria_labels
    assert text.index("Dashboard Main Overview") < text.index("RAG Assignment")


def test_pd_subnav_keeps_main_overview_without_adding_a_dashboard_summary_row():
    layout = page.build_layout()
    text = " ".join(_collect_text(node) for node in layout)

    assert "Overview & Conclusion" in text
    assert "Main Overview" in text
    assert "RAG Assignment" in text
    assert text.index("Main Overview") < text.index("RAG Assignment")
    assert "RAG Assignment Overview" in text
    assert "Post Subjective Review Analysis" in text
    assert text.index("RAG Assignment Overview") < text.index("Post Subjective Review Analysis")
    assert "Post Subjective Review Analysis Overview" in text
    assert "ECL PIT PD - Calibration Conservatism" in text
    assert "ECL PIT PD - Discriminatory Power" in text
    assert "Balance Sheet PD - Calibration Conservatism" in text
    assert "Transition Matrix" in text
    assert "PSI" in text
    assert "Scenario Ranking" in text
    assert "Sensitivity Analysis" in text
    assert "MEV Range" in text
    assert text.index("Overview & Conclusion") < text.index("Main Overview")
    assert text.index("RAG Assignment") < text.index("RAG Assignment Overview")
    assert text.index("Post Subjective Review Analysis") < text.index("Post Subjective Review Analysis Overview")
    assert "Dashboard Summary" not in text


def test_pd_sensitivity_section_uses_projection_data_and_baseline_shock_view():
    layout = _render_pd_content()
    text = " ".join(_collect_text(node) for node in layout)
    ids = []
    class_tokens = set()
    for node in layout:
        ids.extend(_collect_prop_values(node, "id"))
        class_tokens |= _collect_class_tokens(node)

    assert "Sensitivity Analysis" in text
    # The projection paths and relative shock impact now share one combined card.
    assert "Projected PD Sensitivity" in text
    assert "baseline_2std_shock" in text
    assert "Relative Shock Impact" in text
    assert "Scenario Test RAG" in text
    assert "Peak Relative Impact" in text
    # The combined card lists Threshold Breaches above Peak Relative Impact.
    assert text.index("Scenario Test RAG") < text.index("Peak Relative Impact")
    assert "abs(shocked − baseline) / baseline" in text
    assert "Future section for showing how model outputs react" not in text
    assert "A lightweight placeholder is ready for future parameter sensitivities" not in text
    assert "pd-sensitivity-combined-chart" in ids
    assert "pd-live-section" in class_tokens


def test_pd_scenario_ranking_section_surfaces_all_scenario_diagnostics():
    layout = _render_pd_content()
    text = " ".join(_collect_text(node) for node in layout)
    ids = []
    class_tokens = set()
    for node in layout:
        ids.extend(_collect_prop_values(node, "id"))
        class_tokens |= _collect_class_tokens(node)

    assert text.index("PSI") < text.index("Scenario Ranking")
    assert text.index("Scenario Ranking") < text.index("Sensitivity Analysis")
    assert "Projected PD by Scenario" in text
    assert "Scenario Rank Matrix" in text
    assert "Scenario selection" in text
    assert "intsevere" in text
    assert "baseline_2std_shock" in text
    assert "Maximum PD spread" in text
    assert "Highest average PD" in text
    assert "pd-scenario-projection-chart" in ids
    assert "pd-scenario-rank-chart" in ids
    assert "pd-scenario-ranking-filter" in ids
    assert "pd-sensitivity-chart-grid" in class_tokens


def test_pd_scenario_ranking_selection_can_include_or_exclude_shocked_scenarios():
    rows = [
        {"scenario_variant": "baseline"},
        {"scenario_variant": "intsevere"},
        {"scenario_variant": "baseline_2std_shock"},
    ]

    default_selection = page._resolve_pd_scenario_ranking_selection(rows, {})
    custom_selection = page._resolve_pd_scenario_ranking_selection(
        rows,
        {"scenarios": ["baseline", "baseline_2std_shock", "missing"]},
    )

    assert default_selection == ["baseline", "intsevere", "baseline_2std_shock"]
    assert custom_selection == ["baseline", "baseline_2std_shock"]


def test_pd_mev_range_heading_explains_reporting_cycle_basis():
    layout = _render_pd_content()
    aria_labels = []
    for node in layout:
        aria_labels.extend(_collect_prop_values(node, "aria-label"))

    assert any(
        "MEV Range charts" in label
        and "selected Model Use Case / Cycle value" in label
        and "does not move the MEV scenario Q0 date" in label
        for label in aria_labels
    )


def test_pd_range_filters_render_at_section_level():
    layout = _render_pd_content()
    filter_bars = []
    text = " ".join(_collect_text(node) for node in layout)
    for node in layout:
        filter_bars.extend(_collect_nodes_with_class(node, "pd-section-filter-bar"))

    assert len(filter_bars) >= 4
    assert "Calibration Conservatism RAG (ECL PIT) Trend" in text
    assert "Accuracy Ratio and Go-Live Delta Trend" in text
    assert "Balance Sheet Calibration Trend" in text
    assert "Population Stability Index Trend" in text
