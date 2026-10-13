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
from ..repositories.filters_config import MONITORING_POINT_WINDOW, monitoring_points_by_cycle

# ---------------------------------------------------------------------------
# Component ids
# ---------------------------------------------------------------------------

MODEL_USE_CASE_ID = "pd-model-use-case"
MODEL_USE_CASE_TOGGLE_ID = "pd-model-use-case-toggle"
MODEL_USE_CASE_MENU_ID = "pd-model-use-case-menu"
# Reporting Cycle keeps its element IDs: the value stays the composite,
# the join key downstream; only the label is now the bare cycle.
REPORTING_CYCLE_ID = "pd-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "pd-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "pd-reporting-cycle-menu"

# Monitoring points available per reporting cycle, scoped to each tab's own
# ``_Performance_Metrics`` sheet -- a tab only ever offers a quarter that
# actually exists in its own raw data. ``ALL_REPORTING_CYCLE_QUARTERS`` pools
# every tab's sheet together, for the cross-portfolio Overview page.
PD_REPORTING_CYCLE_QUARTERS = monitoring_points_by_cycle("pd")
LGD_REPORTING_CYCLE_QUARTERS = monitoring_points_by_cycle("lgd")
EAD_REPORTING_CYCLE_QUARTERS = monitoring_points_by_cycle("ead")
LOSS_REPORTING_CYCLE_QUARTERS = monitoring_points_by_cycle("loss")
ALL_REPORTING_CYCLE_QUARTERS = monitoring_points_by_cycle("all")
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
MODELS_SEARCH_ID = "pd-models-search"
SINGLE_SELECT_OPTION_ID = "pd-single-select-option"
#: ``filter`` key on the Segment dropdown's option buttons. Named here because
#: sync_pd_filters_to_model_options listens to those buttons' clicks rather than
#: to PORTFOLIO_SEGMENT_ID's value -- see the comment on that callback.
PORTFOLIO_SEGMENT_FILTER_KEY = "portfolio-segment"

REGION_ID = "pd-region"
REGION_TOGGLE_ID = "pd-region-toggle"
REGION_MENU_ID = "pd-region-menu"
PORTFOLIO_ID = "pd-portfolio"
PORTFOLIO_TOGGLE_ID = "pd-portfolio-toggle"
PORTFOLIO_MENU_ID = "pd-portfolio-menu"

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
    """Use the current monitoring point when valid, otherwise fall back to the latest one.

    "Latest" is ``max()``, not ``options[-1]``: quarter labels are fixed-width
    ``YYYYQN`` and so sort correctly as plain strings, which makes this
    independent of the order the options happen to be presented in. Overview
    lists them most-recent-first to match its Reporting Cycle filter, and with a
    positional fallback that would have silently defaulted to the *oldest*
    quarter.
    """
    options = options or []
    if value in options:
        return value or ""
    return max(options) if options else ""


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


def single_select_option_list_id(menu_id: str) -> str:
    """Id of the container holding a searchable menu's option buttons.

    Only searchable menus have one. The shell callback rewrites *this* rather
    than the menu itself, so the search box -- a sibling -- stays mounted and
    keeps focus and its text while you type. Rewriting the menu's own children
    would destroy the input on every keystroke.
    """
    return f"{menu_id}-options"


def build_single_select_dropdown(
    *,
    value_id: str,
    toggle_id: str,
    menu_id: str,
    filter_key: str,
    options: list[dict],
    value: str,
    disabled: bool = False,
    search_id: str | None = None,
    search_placeholder: str = "Type to search…",
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
                children=(
                    build_single_select_option_buttons(options, value, filter_key)
                    if search_id is None
                    else [
                        dcc.Input(
                            id=search_id,
                            type="text",
                            placeholder=search_placeholder,
                            value="",
                            autoComplete="off",
                            className="pd-models-search",
                        ),
                        html.Div(
                            id=single_select_option_list_id(menu_id),
                            className="single-select-option-list",
                            children=build_single_select_option_buttons(options, value, filter_key),
                        ),
                    ]
                ),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# "Nothing selected yet" placeholders
# ---------------------------------------------------------------------------
# The page opens with no filter chosen: each one leads with a "Select …" entry
# whose value is the empty string, and Apply stays disabled until every filter
# has a real value. Two consequences worth knowing before changing a cascade:
#
#   * The placeholder is an *option*, not a `placeholder=` prop, because these
#     are custom button menus rather than <select> elements -- so it has to be
#     filtered out anywhere options are treated as the set of real values.
#   * Every cascade that rewrites a value when its options change must fall back
#     to UNSELECTED, never to `options[0]`. Falling back to the first option is
#     what the bar used to do, and it would silently re-fill a filter the user
#     has not answered -- defeating the empty start on the very first render.
UNSELECTED = ""

# Filter key -> the placeholder's wording.
#
# Kept short enough to fit a 160px control without ellipsis -- "Select model use
# case" and "Select monitoring point" both clipped. The label sits directly
# above each control and supplies the qualifier, so "Select use case" under
# MODEL USE CASE reads the same and fits. test_select_prompts_fit_their_control
# pins the length.
SELECT_PROMPTS = {
    "region": "Select region",
    "portfolio": "Select portfolio",
    "model-use-case": "Select use case",
    "reporting-cycle": "Select cycle",
    "model-group": "Select group",
    "specific-models": "Select model",
    "portfolio-segment": "Select segment",
    "monitoring-point": "Select point",
    "scenario": "Select scenario",
}


def placeholder_option(filter_key: str) -> dict:
    """The leading "Select …" entry for one filter."""
    return {"label": SELECT_PROMPTS.get(filter_key, "Select"), "value": UNSELECTED}


def with_placeholder(options: list[dict], filter_key: str) -> list[dict]:
    """``options`` led by its "Select …" entry, added at most once."""
    if options and options[0].get("value") == UNSELECTED:
        return options
    return [placeholder_option(filter_key)] + list(options)


def keep_or_unselected(options: list[dict], current) -> str:
    """The value a cascade should write when it rewrites a filter's options.

    Keeps the current pick when it survives the narrowing, otherwise leaves the
    filter **unanswered**. Never picks a value on the user's behalf -- see the
    note above.
    """
    allowed = {option.get("value") for option in options} - {UNSELECTED}
    return current if current in allowed else UNSELECTED


def all_selected(*values) -> bool:
    """True when every filter passed has a real value -- the Apply gate."""
    return all(bool(value) and value != UNSELECTED for value in values)


# ---------------------------------------------------------------------------
# Filter row captions
# ---------------------------------------------------------------------------
# The bar reads as two labelled rows. Row 1 is the **Scope** -- Region,
# Portfolio, Model Use Case, Reporting Cycle -- which decides what population
# everything below covers. Row 2 is the **Focus**: which model, segment,
# monitoring point and scenario within that scope is on screen.
FILTER_ROW_CAPTION_CLASS = "monitoring-filter-row-caption"
SCOPE_ROW_CAPTION = "Scope"
FOCUS_ROW_CAPTION = "Focus"
VIEW_ROW_CAPTION = "View"


def _build_filter_row_caption(text: str) -> html.Div:
    """A row caption, sitting in the row's leading grid track.

    Deliberately *not* a ``.monitoring-filter``. That class carries the grid's
    per-filter sizing and, more importantly, the cascade chevron, which
    ``styles.css`` draws before every ``.monitoring-filter`` that follows another
    one -- so reusing it would put an arrow between the caption and the first
    filter. The caption gets its own class and its own leading track, the same
    width on both rows, so the filter columns still line up across the divider.
    """
    return html.Div(text, className=FILTER_ROW_CAPTION_CLASS)


def build_scope_caption() -> html.Div:
    """Caption for the first filter row. Used by all five monitoring tabs."""
    return _build_filter_row_caption(SCOPE_ROW_CAPTION)


def build_focus_caption() -> html.Div:
    """Caption for the second filter row. Used by all five monitoring tabs."""
    return _build_filter_row_caption(FOCUS_ROW_CAPTION)


def build_view_caption() -> html.Div:
    """Caption for SAAS's third row.

    SAAS alone has one: its bar carries presentation controls (Snapshot Period,
    Reference Lines, MEV Label, Historical Statistics) that are neither scope
    nor focus. The monitoring tabs have no equivalent row.
    """
    return _build_filter_row_caption(VIEW_ROW_CAPTION)


# ---------------------------------------------------------------------------
# Global filter bar
# ---------------------------------------------------------------------------


def build_global_filters(data: dict, extra_controls=None, initial: dict | None = None) -> html.Div:
    """The top filter bar: region, portfolio, model group, model, segment,
    model use case / cycle, monitoring point, scenario -- primary (cascading)
    row followed by a secondary row, mirroring SAAS's own two-row layout.

    ``initial`` (from ``shared.deep_link.parse_deep_link_params``) lets a
    deep link from the Overview page's escalation cards pre-select Model/
    Segment/Model Use Case/Monitoring Point instead of the usual empty/latest
    defaults -- unrecognized values fall back to the normal default, so a
    stale or malformed link degrades gracefully rather than erroring."""
    from ..domain.mev_range import model_field_values
    from ..repositories.filters_config import (
        load_filter_config, model_names as cfg_model_names, segment_values as cfg_segment_values,
        cycle_options_for_cycles,
        use_case_options_for_cycles,
    )

    cfg = load_filter_config()
    quarters_asc = sorted(data["quarters"])
    latest_quarter = quarters_asc[-1] if quarters_asc else ""
    # The tab's own model list, from portfolio.xlsx -- the same source its
    # metrics, its callbacks and models_matching all use. Not the MEV
    # workbook's: that lists every PD model SAAS knows about, including ones
    # with no metrics, and offering those here produces a scope that renders
    # nothing. The two agreed until portfolio.xlsx was trimmed to the models
    # with complete data.
    model_names = list(data.get("model_names") or cfg_model_names("pd"))
    segment_values = cfg_segment_values()
    # Most-recent-first, matching Reporting Cycle beside it. The default is
    # still resolved from the ascending list via resolve_monitoring_point_value.
    monitoring_point_options = with_placeholder(
        [{"label": q, "value": q} for q in reversed(quarters_asc)], "monitoring-point")
    segment_options = with_placeholder(
        [{"label": "All", "value": "all"}] + [{"label": value, "value": value} for value in segment_values],
        "portfolio-segment")

    mev_catalog = data.get("mev_catalog") or {}
    # Region/Portfolio/Model Use Case/Reporting Cycle carry no "All": each offers
    # only values that have data, so the bar can never present a combination
    # with no rows behind it.
    region_options = with_placeholder([
        {"label": value, "value": value} for value in model_field_values(mev_catalog, "region", model_names)
    ], "region")
    portfolio_options = with_placeholder([
        {"label": value, "value": value} for value in model_field_values(mev_catalog, "portfolio", model_names)
    ], "portfolio")

    model_use_case_options = with_placeholder(use_case_options_for_cycles(None), "model-use-case")
    # Every cycle, not just one use case's: with no use case chosen yet there is
    # nothing to narrow by, and the cascade re-narrows the moment one is picked.
    reporting_cycle_options = with_placeholder(cycle_options_for_cycles(None), "reporting-cycle")
    scenario_options = with_placeholder(
        [{"label": s["label"], "value": s["value"]} for s in cfg["scenarios"]], "scenario")

    # ``initial`` restores a previously applied scope (the router re-enters the
    # page with it). Anything it does not carry stays UNSELECTED rather than
    # falling back to a first option -- that is the whole point of the empty
    # start; see the UNSELECTED note above.
    initial = initial or {}
    initial_model = initial.get("model", "") if initial.get("model") in model_names else UNSELECTED
    initial_segment = (
        initial.get("segment", "")
        if initial.get("segment") in segment_values or initial.get("segment") == "all"
        else UNSELECTED
    )
    initial_cycle = keep_or_unselected(reporting_cycle_options, initial.get("cycle"))
    initial_use_case = keep_or_unselected(model_use_case_options, initial.get("model_use_case"))
    initial_region = keep_or_unselected(region_options, initial.get("region"))
    initial_portfolio = keep_or_unselected(portfolio_options, initial.get("portfolio"))
    initial_monitoring_point = (
        initial.get("monitoring_point") if initial.get("monitoring_point") in set(quarters_asc)
        else UNSELECTED
    )
    initial_scenario = keep_or_unselected(scenario_options, initial.get("scenario"))

    primary_row = html.Div(
        className="monitoring-controls saas-top-filter-row monitoring-primary-filter-row",
        children=[
            build_scope_caption(),
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
                        value=initial_region,
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
                        value=initial_portfolio,
                    ),
                ],
            ),
        html.Div(
            className="monitoring-filter",
            children=[
                html.Label("Model Use Case", htmlFor=MODEL_USE_CASE_TOGGLE_ID),
                build_single_select_dropdown(
                    value_id=MODEL_USE_CASE_ID,
                    toggle_id=MODEL_USE_CASE_TOGGLE_ID,
                    menu_id=MODEL_USE_CASE_MENU_ID,
                    filter_key="model-use-case",
                    options=model_use_case_options,
                    value=initial_use_case,
                ),
            ],
        ),
        html.Div(
            className="monitoring-filter",
            children=[
                html.Label("Reporting Cycle", htmlFor=REPORTING_CYCLE_TOGGLE_ID),
                build_single_select_dropdown(
                    value_id=REPORTING_CYCLE_ID,
                    toggle_id=REPORTING_CYCLE_TOGGLE_ID,
                    menu_id=REPORTING_CYCLE_MENU_ID,
                    filter_key="reporting-cycle",
                    options=reporting_cycle_options,
                    value=initial_cycle,
                ),
            ],
        ),
        ],
    )

    # No Model Group filter here. This tab shows exactly one group, so the
    # control could only ever return "PD" -- its value drove nothing (the group
    # is hardcoded at every ``models_matching`` call site), and once the bar
    # started empty it became a required click with a foregone answer. The
    # sidebar, the page title and the URL all already name the group.
    # Overview keeps its Model Group: there it is a real choice.
    secondary_children = [
            build_focus_caption(),
            html.Div(
                # monitoring-model-filter widens the menu to fit the search
                # placeholder (styles.css); the other single-selects keep their
                # track width.
                className="monitoring-filter monitoring-model-filter",
                children=[
                    html.Label("Model", htmlFor=MODELS_TOGGLE_ID),
                    build_single_select_dropdown(
                        value_id=MODELS_ID,
                        toggle_id=MODELS_TOGGLE_ID,
                        menu_id=MODELS_MENU_ID,
                        filter_key="specific-models",
                        options=[{"label": "Select model", "value": ""}] + [{"label": name, "value": name} for name in model_names],
                        value=initial_model,
                        search_id=MODELS_SEARCH_ID,
                        search_placeholder="Type to search models…",
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
                        filter_key=PORTFOLIO_SEGMENT_FILTER_KEY,
                        options=segment_options,
                        value=initial_segment,
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
                    value=initial_monitoring_point,
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
                    value=initial_scenario,
                ),
            ],
        ),
    ]
    if extra_controls is not None:
        secondary_children.append(extra_controls)

    secondary_row = html.Div(
        className="monitoring-controls saas-top-filter-row saas-secondary-filter-row monitoring-focus-filter-row",
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
