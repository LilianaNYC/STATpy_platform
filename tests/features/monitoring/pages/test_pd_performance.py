"""Smoke test for the PD Performance page: the layout builds without raising."""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.pages.pd_performance import page


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


def _render_pd_content():
    """Render the live dashboard content (post-Apply), not the getting-started prompt."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA as data
    from STATpy_platform.data.analytics.calculations import PdFilterContext, set_precomputed_metrics

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
        )
    finally:
        set_precomputed_metrics(None)


def test_pd_performance_layout_builds():
    layout = page.build_layout()
    assert isinstance(layout, list) and layout


def test_pd_performance_build_stores():
    stores = page.build_stores()
    assert {store.id for store in stores} == {
        "pd-range-store",
        "pd-trend-horizon-store",
        "pd-mev-filter-store",
        "pd-scenario-ranking-store",
        "pd-applied-filters-store",
    }


def test_pd_psi_section_surfaces_stability_methodology_and_thresholds():
    layout = _render_pd_content()
    text = " ".join(_collect_text(node) for node in layout)
    class_tokens = set()
    for node in layout:
        class_tokens |= _collect_class_tokens(node)

    assert "PSI based on IRB CRR key-driver stability" in text
    assert "PSI Stability RAG" in text
    assert "Test basis: IRB CRR key driver" not in text
    assert "Stability bands" not in text
    assert "Indicative Thresholds" not in text
    assert "performing-book population" in text
    assert "PSI <= 0.10" in text
    assert "0.10 < PSI <= 0.25" in text
    assert "PSI > 0.25" in text
    assert "pd-discrimination-test-grid" in class_tokens
    assert "pd-psi-test-grid" in class_tokens
    assert "pd-psi-stability-card" in class_tokens
    assert "pd-psi-threshold-mini-grid" in class_tokens


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
        and "selected Reporting Cycle value" in label
        and "does not move the MEV scenario Q0 date" in label
        for label in aria_labels
    )
