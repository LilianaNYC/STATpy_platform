"""Interactive controls & chrome for the PD Performance dashboard.

Builds the filter bar, the per-chart range / PD-horizon controls, the chart
header, and the section sub-navigation. (The name is ``controls`` rather than
``filters`` because only the filter bar is a filter -- the rest are navigation
and chart chrome.)

Ports the global monitoring filter bar (``components/monitoring_layout.py``'s
``MONITORING_POINT`` / ``MONITORING_PORTFOLIO_SEGMENT`` / ``MONITORING_MODELS``
selectors) and the per-chart range controls (``buildPdRangeControls`` /
``buildPdCalibrationTrendHorizonControl`` /
``buildPdDiscriminationTrendHorizonControl`` /
``buildPdFrozenOneYearHorizonControl``) from
``pages/monitoring_pd_models_page.py``.

The JS versions mutated module-level globals and re-rendered the page on
every change. In Dash, the equivalent state lives in ``dcc.Store``/component
``value`` props and is read by callbacks in ``callbacks.py``.
"""

from __future__ import annotations

from dash import dcc, html

from ..domain.calculations import get_pd_range_preset, get_pd_range_selection
from ..domain.quarter_labels import format_pd_compact_quarter_label
from ..repositories.filters_config import monitoring_points_by_cycle

# ---------------------------------------------------------------------------
# Component ids
# ---------------------------------------------------------------------------

REPORTING_CYCLE_ID = "pd-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "pd-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "pd-reporting-cycle-menu"

# Monitoring points available per reporting cycle, sourced from the workbook's
# ``Filters`` tab so cycles/quarters can be edited without code changes.
REPORTING_CYCLE_QUARTERS = monitoring_points_by_cycle()
SCENARIO_ID = "pd-scenario"
SCENARIO_TOGGLE_ID = "pd-scenario-toggle"
SCENARIO_MENU_ID = "pd-scenario-menu"

MONITORING_POINT_ID = "pd-monitoring-point"
PORTFOLIO_SEGMENT_ID = "pd-portfolio-segment"
MONITORING_POINT_TOGGLE_ID = "pd-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "pd-monitoring-point-menu"
PORTFOLIO_SEGMENT_TOGGLE_ID = "pd-portfolio-segment-toggle"
PORTFOLIO_SEGMENT_MENU_ID = "pd-portfolio-segment-menu"
MODELS_ID = "pd-models"
MODELS_TOGGLE_ID = "pd-models-toggle"
MODELS_MENU_ID = "pd-models-menu"
FILTER_HELP_ID = "pd-filter-help"
SINGLE_SELECT_OPTION_ID = "pd-single-select-option"

REGION_ID = "pd-region"
REGION_TOGGLE_ID = "pd-region-toggle"
REGION_MENU_ID = "pd-region-menu"
PORTFOLIO_ID = "pd-portfolio"
PORTFOLIO_TOGGLE_ID = "pd-portfolio-toggle"
PORTFOLIO_MENU_ID = "pd-portfolio-menu"
MODEL_GROUP_ID = "pd-model-group"
MODEL_GROUP_TOGGLE_ID = "pd-model-group-toggle"
MODEL_GROUP_MENU_ID = "pd-model-group-menu"

# Per-chart range controls use pattern-matching ids so a single set of
# callbacks in callbacks.py can serve every chart's range selector.
RANGE_WINDOW_ID = "pd-range-window"
RANGE_FROM_ID = "pd-range-from"
RANGE_TO_ID = "pd-range-to"
TREND_HORIZON_ID = "pd-trend-horizon"

# Section sub-navigation (port of `#monitoring-pd-subnav`).
SUBNAV_ID = "pd-subnav"

# Section ids in scroll order, used by assets/js/monitoring_pd_subnav.js to highlight the
# sub-nav link for whichever section is currently at the top of the viewport
# (port of MONITORING_PD_SECTION_IDS / updateMonitoringPdSubnavActiveState).
OVERVIEW_LINKS = [
    ("pd-dashboard-overview", "Main Overview"),
    ("pd-conclusions-verdict", "Conclusion"),
]
RAG_ASSIGNMENT_LINKS = [
    ("pd-analysis-scope", "RAG Assignment Overview"),
    ("pd-calibration-rag", "ECL PIT PD - Calibration Conservatism"),
    ("pd-discrimination-rag", "ECL PIT PD - Discriminatory Power"),
    ("pd-balance-sheet-calibration", "Balance Sheet PD - Calibration Conservatism"),
]
POST_SUBJECTIVE_REVIEW_LINKS = [
    ("pd-post-subjective-overview", "Post Subjective Review Analysis Overview"),
    ("pd-transition-matrix-distance", "Transition Matrix"),
    ("pd-population-stability-index", "PSI"),
    ("pd-scenario-ranking", "Scenario Ranking"),
    ("pd-sensitivity-analysis", "Sensitivity Analysis"),
    ("pd-mev-range", "MEV Range"),
]


def resolve_monitoring_point_value(options: list[str] | None, value: str | None) -> str:
    """Use the current monitoring point when valid, otherwise fall back to the latest one."""
    options = options or []
    if value in options:
        return value or ""
    return options[-1] if options else ""


# ---------------------------------------------------------------------------
# Reusable dropdown builders
# ---------------------------------------------------------------------------


def build_single_select_option_buttons(
    options: list[dict],
    value: str | None,
    filter_key: str,
) -> list[html.Button]:
    """The clickable option-button list inside a single-select menu.

    Factored out of :func:`build_single_select_dropdown` so a callback can
    rebuild just the menu's ``children`` (e.g. to narrow a cascading filter's
    options) without duplicating the button markup.
    """
    return [
        html.Button(
            [
                html.Span(option["label"], className="single-select-option-label"),
                html.Span("✓", className="single-select-option-check", **{"aria-hidden": "true"}),
            ],
            id={"type": SINGLE_SELECT_OPTION_ID, "filter": filter_key, "value": option["value"]},
            type="button",
            n_clicks=0,
            className="single-select-option is-selected" if option["value"] == value else "single-select-option",
        )
        for option in options
    ]


def build_single_select_dropdown(
    *,
    value_id: str,
    toggle_id: str,
    menu_id: str,
    filter_key: str,
    options: list[dict],
    value: str,
    disabled: bool = False,
) -> html.Div:
    """Custom single-select dropdown with a toggle button and option list.

    Used by the global filter bar (Monitoring Point, Segment) and the MEV
    chart-filter row (PD Model).  Each instance needs its own ``filter_key``
    so the shared :data:`SINGLE_SELECT_OPTION_ID` pattern-matching callbacks
    can route clicks to the correct hidden ``dcc.Dropdown``.
    """
    selected_label = next((option["label"] for option in options if option["value"] == value), value)

    return html.Div(
        className="checkbox-dropdown single-select-dropdown",
        children=[
            dcc.Dropdown(
                id=value_id,
                options=options,
                value=value,
                clearable=False,
                searchable=False,
                style={"display": "none"},
            ),
            html.Button(
                selected_label,
                id=toggle_id,
                type="button",
                n_clicks=0,
                className="checkbox-dropdown-toggle",
                disabled=disabled,
            ),
            html.Div(
                id=menu_id,
                className="checkbox-dropdown-menu single-select-menu",
                children=build_single_select_option_buttons(options, value, filter_key),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Global filter bar
# ---------------------------------------------------------------------------


def build_global_filters(data: dict, extra_controls=None) -> html.Div:
    """The top filter bar: region, portfolio, model group, model, segment,
    model use case / cycle, monitoring point, scenario -- primary (cascading)
    row followed by a secondary row, mirroring SAAS's own two-row layout."""
    from ..domain.mev_range import model_field_values
    from ..repositories.filters_config import (
        load_filter_config, model_names as cfg_model_names, segment_values as cfg_segment_values,
    )

    cfg = load_filter_config()
    quarters_desc = sorted(data["quarters"], reverse=True)
    latest_quarter = quarters_desc[0] if quarters_desc else ""
    model_names = cfg_model_names("pd")
    segment_values = cfg_segment_values()
    monitoring_point_options = [{"label": q, "value": q} for q in quarters_desc]
    segment_options = [{"label": "All", "value": "all"}] + [{"label": value, "value": value} for value in segment_values]

    mev_catalog = data.get("mev_catalog") or {}
    region_options = [{"label": "All", "value": "All"}] + [
        {"label": value, "value": value} for value in model_field_values(mev_catalog, "region", model_names)
    ]
    portfolio_options = [{"label": "All", "value": "All"}] + [
        {"label": value, "value": value} for value in model_field_values(mev_catalog, "portfolio", model_names)
    ]

    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    scenario_options = [{"label": s["label"], "value": s["value"]} for s in cfg["scenarios"]]
    default_cycle = reporting_cycle_options[0]["value"]
    default_scenario = scenario_options[0]["value"]

    primary_row = html.Div(
        className="monitoring-controls saas-top-filter-row monitoring-primary-filter-row",
        children=[
            html.Div(
                className="monitoring-filter",
                children=[
                    html.Label("Region", htmlFor=REGION_TOGGLE_ID),
                    build_single_select_dropdown(
                        value_id=REGION_ID,
                        toggle_id=REGION_TOGGLE_ID,
                        menu_id=REGION_MENU_ID,
                        filter_key="region",
                        options=region_options,
                        value="All",
                    ),
                ],
            ),
            html.Div(
                className="monitoring-filter",
                children=[
                    html.Label("Portfolio", htmlFor=PORTFOLIO_TOGGLE_ID),
                    build_single_select_dropdown(
                        value_id=PORTFOLIO_ID,
                        toggle_id=PORTFOLIO_TOGGLE_ID,
                        menu_id=PORTFOLIO_MENU_ID,
                        filter_key="portfolio",
                        options=portfolio_options,
                        value="All",
                    ),
                ],
            ),
            html.Div(
                className="monitoring-filter",
                children=[
                    html.Label("Model Group", htmlFor=MODEL_GROUP_TOGGLE_ID),
                    build_single_select_dropdown(
                        value_id=MODEL_GROUP_ID,
                        toggle_id=MODEL_GROUP_TOGGLE_ID,
                        menu_id=MODEL_GROUP_MENU_ID,
                        filter_key="model-group",
                        options=[{"label": "PD", "value": "PD"}],
                        value="PD",
                    ),
                ],
            ),
            html.Div(
                className="monitoring-filter",
                children=[
                    html.Label("Model", htmlFor=MODELS_TOGGLE_ID),
                    build_single_select_dropdown(
                        value_id=MODELS_ID,
                        toggle_id=MODELS_TOGGLE_ID,
                        menu_id=MODELS_MENU_ID,
                        filter_key="specific-models",
                        options=[{"label": "Select model", "value": ""}] + [{"label": name, "value": name} for name in model_names],
                        value="",
                    ),
                ],
            ),
            html.Div(
                className="monitoring-filter",
                children=[
                    html.Label("Segment", htmlFor=PORTFOLIO_SEGMENT_TOGGLE_ID),
                    build_single_select_dropdown(
                        value_id=PORTFOLIO_SEGMENT_ID,
                        toggle_id=PORTFOLIO_SEGMENT_TOGGLE_ID,
                        menu_id=PORTFOLIO_SEGMENT_MENU_ID,
                        filter_key="portfolio-segment",
                        options=segment_options,
                        value="",
                    ),
                ],
            ),
        ],
    )

    secondary_children = [
        html.Div(
            className="monitoring-filter",
            children=[
                html.Label("Model Use Case / Cycle", htmlFor=REPORTING_CYCLE_TOGGLE_ID),
                build_single_select_dropdown(
                    value_id=REPORTING_CYCLE_ID,
                    toggle_id=REPORTING_CYCLE_TOGGLE_ID,
                    menu_id=REPORTING_CYCLE_MENU_ID,
                    filter_key="reporting-cycle",
                    options=reporting_cycle_options,
                    value=default_cycle,
                ),
            ],
        ),
        html.Div(
            className="monitoring-filter",
            children=[
                html.Label("Monitoring Point", htmlFor=MONITORING_POINT_TOGGLE_ID),
                build_single_select_dropdown(
                    value_id=MONITORING_POINT_ID,
                    toggle_id=MONITORING_POINT_TOGGLE_ID,
                    menu_id=MONITORING_POINT_MENU_ID,
                    filter_key="monitoring-point",
                    options=monitoring_point_options,
                    value=latest_quarter,
                ),
            ],
        ),
        html.Div(
            className="monitoring-filter",
            children=[
                html.Label("Scenario", htmlFor=SCENARIO_TOGGLE_ID),
                build_single_select_dropdown(
                    value_id=SCENARIO_ID,
                    toggle_id=SCENARIO_TOGGLE_ID,
                    menu_id=SCENARIO_MENU_ID,
                    filter_key="scenario",
                    options=scenario_options,
                    value=default_scenario,
                ),
            ],
        ),
    ]
    if extra_controls is not None:
        secondary_children.append(extra_controls)

    secondary_row = html.Div(
        className="monitoring-controls saas-top-filter-row saas-secondary-filter-row",
        children=secondary_children,
    )

    return html.Div(children=[primary_row, secondary_row, build_section_subnav()])


# ---------------------------------------------------------------------------
# Section sub-navigation (port of `#monitoring-pd-subnav`)
# ---------------------------------------------------------------------------


def _subnav_link(section_id: str, label: str, active: bool) -> html.Button:
    return html.Button(
        label,
        type="button",
        className="active" if active else "",
        **{"data-pd-subnav-target": section_id, "aria-current": "location" if active else "false"},
    )


def build_section_subnav() -> html.Div:
    """Overview / RAG Assignment / Post Subjective jump links.

    Port of the `#monitoring-pd-subnav` markup. Clicking a link scrolls to
    the corresponding section; the active link/group is kept in sync with
    scroll position by ``assets/js/monitoring_pd_subnav.js`` (port of
    ``setMonitoringPdSubnavActive`` / ``updateMonitoringPdSubnavActiveState``).
    """
    return html.Div(
        id=SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-overview active",
                children=[
                    html.Div("Overview & Conclusion", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link(section_id, label, active=index == 0)
                            for index, (section_id, label) in enumerate(OVERVIEW_LINKS)
                        ],
                    ),
                ],
            ),
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-rag",
                children=[
                    html.Div("Chapter 1: RAG Assignment", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link(section_id, label, active=False)
                            for section_id, label in RAG_ASSIGNMENT_LINKS
                        ],
                    ),
                ],
            ),
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-post-review",
                children=[
                    html.Div("Chapter 2: Post Subjective Review Analysis", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link(section_id, label, active=False)
                            for section_id, label in POST_SUBJECTIVE_REVIEW_LINKS
                        ],
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Per-chart range controls (buildPdRangeControls / buildPdPeriodOptions)
# ---------------------------------------------------------------------------


def build_pd_period_options(periods: list[str], all_label: str) -> list[dict]:
    return [{"label": all_label, "value": ""}] + [
        {"label": format_pd_compact_quarter_label(period), "value": period}
        for period in periods
    ]


def build_range_controls(range_key: str, periods: list[str], range_value: dict | None = None) -> html.Div:
    """Window / From / To controls for a chart's visible time range.

    ``range_value`` is ``{"from": "...", "to": "..."}`` (empty strings mean
    unbounded), normally read from a ``dcc.Store``.
    """
    selection = get_pd_range_selection(range_value, periods)
    preset = get_pd_range_preset(range_value, periods)

    return html.Div(
        className="pd-range-controls",
        **{"aria-label": "Visible time range"},
        children=[
            html.Label([
                html.Span("Window"),
                dcc.Dropdown(
                    id={"type": RANGE_WINDOW_ID, "key": range_key},
                    options=[
                        {"label": "All periods", "value": "all"},
                        {"label": "Last 4 quarters", "value": "last-4"},
                        {"label": "Last 8 quarters", "value": "last-8"},
                        {"label": "Last 12 quarters", "value": "last-12"},
                        {"label": "Custom range", "value": "custom", "disabled": True},
                    ],
                    value=preset,
                    clearable=False,
                ),
            ]),
            html.Label([
                html.Span("From"),
                dcc.Dropdown(
                    id={"type": RANGE_FROM_ID, "key": range_key},
                    options=build_pd_period_options(periods, "Earliest"),
                    value=selection["from"],
                    clearable=False,
                ),
            ]),
            html.Label([
                html.Span("To"),
                dcc.Dropdown(
                    id={"type": RANGE_TO_ID, "key": range_key},
                    options=build_pd_period_options(periods, "Latest"),
                    value=selection["to"],
                    clearable=False,
                ),
            ]),
        ],
    )


# ---------------------------------------------------------------------------
# Trend PD-horizon controls (buildPdCalibrationTrendHorizonControl / ...)
# ---------------------------------------------------------------------------


def build_trend_horizon_control(control_key: str, value: str = "1y") -> html.Div:
    """Selectable 1y/2y PD-horizon control for the calibration/discrimination trend charts."""
    return html.Div(
        className="pd-range-controls",
        **{"aria-label": "PD Horizon"},
        children=[
            html.Label([
                html.Span("PD Horizon"),
                dcc.Dropdown(
                    id={"type": TREND_HORIZON_ID, "key": control_key},
                    options=[
                        {"label": "1 year", "value": "1y"},
                        {"label": "2 years", "value": "2y"},
                    ],
                    value=value,
                    clearable=False,
                ),
            ]),
        ],
    )


def build_frozen_horizon_control(label: str = "PD Horizon") -> html.Div:
    """Disabled "1 year" control (port of ``buildPdFrozenOneYearHorizonControl``)."""
    return html.Div(
        className="pd-range-controls",
        **{"aria-label": label},
        children=[
            html.Label([
                html.Span("PD Horizon"),
                dcc.Dropdown(
                    options=[{"label": "1 year", "value": "1y"}],
                    value="1y",
                    clearable=False,
                    disabled=True,
                ),
            ]),
        ],
    )


# ---------------------------------------------------------------------------
# Section-level range toolbar
# ---------------------------------------------------------------------------


def _as_children_list(component) -> list:
    children = getattr(component, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def build_section_filter_item(
    label: str | None,
    *,
    range_key: str | None = None,
    periods: list[str] | None = None,
    range_value: dict | None = None,
    extra_controls=None,
) -> html.Div:
    actions = []
    if extra_controls is not None and range_key:
        range_controls = build_range_controls(range_key, periods or [], range_value)
        actions.append(
            html.Div(
                className="pd-range-controls",
                children=[*_as_children_list(extra_controls), *_as_children_list(range_controls)],
                **{"aria-label": "Section filters"},
            )
        )
    else:
        if extra_controls is not None:
            actions.append(extra_controls)
        if range_key:
            actions.append(build_range_controls(range_key, periods or [], range_value))

    children = []
    if label:
        children.append(html.Div(label, className="pd-section-filter-item-label"))
    children.append(html.Div(className="pd-section-filter-item-actions", children=actions))
    return html.Div(
        className="pd-section-filter-item",
        children=children,
    )


def build_section_filter_bar(items: list[html.Div]) -> html.Div:
    return html.Div(className="pd-section-filter-bar", children=items)


# ---------------------------------------------------------------------------
# Chart header (buildPdChartHeader)
# ---------------------------------------------------------------------------


def build_chart_header(title: str, subtitle: str, range_key: str | None = None, periods: list[str] | None = None, range_value: dict | None = None, extra_controls=None) -> html.Div:
    actions = []
    if extra_controls is not None:
        actions.append(extra_controls)
    if range_key:
        actions.append(build_range_controls(range_key, periods or [], range_value))

    return html.Div(
        className="pd-chart-heading",
        children=[
            html.Div(
                className="pd-chart-heading-copy",
                children=[
                    html.Div(title, className="section-title"),
                    html.Div(subtitle, className="pd-section-subtitle"),
                ],
            ),
            html.Div(className="pd-chart-actions", children=actions),
        ],
    )
