"""Layout for the Backtesting page.

Dash composition only -- no calculations, no I/O. Filter options come from the
loader payload (:data:`BACKTESTING_PAGE_DATA`), never hard-coded, so adding a
new ``Run For`` value to the workbook populates the filter on the next process
restart.

Chrome notes, so the next reader does not mistake reuse for coincidence:

* The top bar is composed from ``shared.ui.controls.build_single_select_dropdown``
  wrapped in the platform's ``monitoring-controls`` / ``monitoring-filter``
  classes -- the same way ``features/saas/ui/views/workspace.py`` builds its own
  rows. ``build_global_filters`` is *not* used: it is hard-wired to monitoring's
  filter config and element ids (``pd-region``, ``pd-models``, ...), so reusing
  it here would put monitoring's ids on this page and let monitoring's callbacks
  fire against it, while still not offering Run For / J/N Flag / Month End
  Snapshot.
* Section and chapter headings come from ``shared.ui.cards``. Those builders
  emit ``pd-*`` class names; read ``pd-`` as "platform default card chrome",
  not as a claim about the PD page.
* Placeholder cards use the same ``section-card pd-mev-empty-state`` treatment
  SAAS uses for its pre-apply state, so the page looks finished rather than
  broken while the chart milestones are outstanding.
"""

from __future__ import annotations

from dash import dcc, html

from .....shared.ui import controls as shared_filters
from .....shared.ui.cards import build_chapter_heading, build_section_heading
from .....shared.ui.loading import build_dashboard_loading_shell
from .....shared.domain import constants as config
from ...data_access import BACKTESTING_PAGE_DATA
from ...domain import selectors, vintages
from ...services import backtesting_service
from . import figures

# --- Element ids ------------------------------------------------------------
# All page ids carry a ``bt-`` prefix so nothing collides with monitoring's
# ``pd-*`` ids or SAAS's ``saas-*`` ids.
REGION_ID = "bt-region"
REGION_TOGGLE_ID = "bt-region-toggle"
REGION_MENU_ID = "bt-region-menu"
REGION_FILTER_KEY = "bt-region"

PORTFOLIO_ID = "bt-portfolio"
PORTFOLIO_TOGGLE_ID = "bt-portfolio-toggle"
PORTFOLIO_MENU_ID = "bt-portfolio-menu"
PORTFOLIO_FILTER_KEY = "bt-portfolio"

MODEL_GROUP_ID = "bt-model-group"
MODEL_GROUP_TOGGLE_ID = "bt-model-group-toggle"
MODEL_GROUP_MENU_ID = "bt-model-group-menu"
MODEL_GROUP_FILTER_KEY = "bt-model-group"

SEGMENT_ID = "bt-segment"
SEGMENT_TOGGLE_ID = "bt-segment-toggle"
SEGMENT_MENU_ID = "bt-segment-menu"
SEGMENT_FILTER_KEY = "bt-segment"

MODEL_ID = "bt-model"
MODEL_TOGGLE_ID = "bt-model-toggle"
MODEL_MENU_ID = "bt-model-menu"
MODEL_FILTER_KEY = "bt-model"

RUN_FOR_ID = "bt-run-for"
RUN_FOR_TOGGLE_ID = "bt-run-for-toggle"
RUN_FOR_MENU_ID = "bt-run-for-menu"
RUN_FOR_FILTER_KEY = "bt-run-for"

SCENARIO_ID = "bt-scenario"
SCENARIO_TOGGLE_ID = "bt-scenario-toggle"
SCENARIO_MENU_ID = "bt-scenario-menu"
SCENARIO_FILTER_KEY = "bt-scenario"

JN_FLAG_ID = "bt-jn-flag"
JN_FLAG_TOGGLE_ID = "bt-jn-flag-toggle"
JN_FLAG_MENU_ID = "bt-jn-flag-menu"
JN_FLAG_FILTER_KEY = "bt-jn-flag"

SNAPSHOT_ID = "bt-snapshot"
SNAPSHOT_TOGGLE_ID = "bt-snapshot-toggle"
SNAPSHOT_MENU_ID = "bt-snapshot-menu"
SNAPSHOT_FILTER_KEY = "bt-snapshot"

APPLY_FILTERS_ID = "bt-apply-filters"
FILTER_HELP_ID = "bt-filter-help"
APPLIED_FILTERS_STORE_ID = "bt-applied-filters-store"
CONTENT_ID = "bt-content"
SUBNAV_ID = "bt-subnav"

# --- Section anchors --------------------------------------------------------
# Ordered as they appear on the page; the sub-nav script tracks these ids.
SECTION_OVERVIEW = "bt-overview"
SECTION_PD = "bt-pd"
SECTION_PD_CRR = "bt-pd-crr"
SECTION_LGD = "bt-lgd"
SECTION_EAD = "bt-ead"
SECTION_NCO = "bt-nco"

SUBNAV_GROUPS = (
    ("Overview", ((SECTION_OVERVIEW, "Backtest Overview"),)),
    (
        "Metrics",
        (
            (SECTION_PD, "PD"),
            (SECTION_PD_CRR, "PD CRR"),
            (SECTION_LGD, "LGD"),
            (SECTION_EAD, "EAD"),
            (SECTION_NCO, "NCO"),
        ),
    ),
)

SECTION_IDS = tuple(
    section_id for _, links in SUBNAV_GROUPS for section_id, _ in links
)

# Metric sections, in page order:
# (anchor, index label, title, description, metric key).
METRIC_SECTIONS = (
    (
        SECTION_PD,
        "1.1",
        "PD",
        "Exposure-weighted probability of default, forecast against the realised "
        "anchor for each target quarter. Covers the facilities scored by this "
        "dashboard's PD model population.",
        config.BACKTESTING_METRIC_PD,
    ),
    (
        SECTION_PD_CRR,
        "1.2",
        "PD CRR",
        "The same measure over the complementary facility population, whose PD "
        "comes from the second PD model. The two populations are disjoint, so a "
        "portfolio view reads both together.",
        config.BACKTESTING_METRIC_PD_CRR,
    ),
    (
        SECTION_LGD,
        "1.3",
        "LGD",
        "Exposure-weighted loss given default. Weighted by EAD so a small "
        "facility cannot count as much as a large one.",
        config.BACKTESTING_METRIC_LGD,
    ),
    (
        SECTION_EAD,
        "1.4",
        "EAD",
        "Exposure at default, summed across the facility population rather than "
        "averaged -- it is an amount, not a rate.",
        config.BACKTESTING_METRIC_EAD,
    ),
    (
        SECTION_NCO,
        "1.5",
        "NCO",
        "Net charge-off, summed across the population. Reconciles to "
        "PD x LGD x EAD for each facility and quarter.",
        config.BACKTESTING_METRIC_NCO,
    ),
)

ALL_VALUE = "all"

# Same graph chrome the other dashboards use: no mode bar, responsive resize.
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def _options_with_all(values, all_label: str = "All") -> list[dict]:
    return [{"label": all_label, "value": ALL_VALUE}] + [
        {"label": str(value), "value": str(value)} for value in values if value
    ]


def _model_option(model: str) -> dict:
    """A model option: descriptive label from the catalogue, key as the value.

    The value stays the raw model key so it can be matched against the workbook
    without a reverse lookup; only what the user reads changes.
    """
    return {"label": selectors.model_label(model), "value": model}


def region_options() -> list[dict]:
    return _options_with_all(selectors.region_values())


def portfolio_options(region=None) -> list[dict]:
    return _options_with_all(selectors.portfolio_values(region=region))


def model_group_options(region=None, portfolio=None) -> list[dict]:
    return _options_with_all(
        selectors.model_group_values(region=region, portfolio=portfolio)
    )


def segment_options(**filters) -> list[dict]:
    return _options_with_all(selectors.segments_for_filters(**filters))


def model_options(**filters) -> list[dict]:
    """Models matching the attribute filters, shown by descriptive name."""
    models = selectors.models_matching(**filters) if filters else selectors.all_models()
    return [{"label": "All", "value": ALL_VALUE}] + [_model_option(model) for model in models]


def run_for_options() -> list[dict]:
    return _options_with_all(BACKTESTING_PAGE_DATA.get("run_for_values") or [])


def scenario_options() -> list[dict]:
    """Scenario options, base first.

    A backtest scores the base scenario: the others are deliberately
    conservative, so comparing them to realised outcomes measures the
    conservatism buffer rather than model accuracy. They stay selectable for
    context, and the default is base.
    """
    values = list(BACKTESTING_PAGE_DATA.get("scenario_values") or [])
    base = config.BACKTESTING_BASE_SCENARIO
    ordered = ([base] if base in values else []) + [value for value in values if value != base]
    return [{"label": str(value), "value": str(value)} for value in ordered]


def jn_flag_options() -> list[dict]:
    return _options_with_all(BACKTESTING_PAGE_DATA.get("jn_flag_values") or [])


def snapshot_options() -> list[dict]:
    """Month End Snapshot options, labelled as quarters, newest first.

    Labels go through the shared quarter helpers so they read identically to
    every other dashboard's quarter labels; the value keeps the ISO date so a
    callback can filter the frame without re-parsing a label.
    """
    options = [{"label": "All", "value": ALL_VALUE}]
    for value in reversed(BACKTESTING_PAGE_DATA.get("snapshot_dates") or []):
        label = vintages.quarter_label_for_date(value)
        iso = str(getattr(value, "date", lambda: value)())[:10]
        options.append({"label": vintages.compact_quarter_label(label) or iso, "value": iso})
    return options


DEFAULT_SCENARIO = next(
    (option["value"] for option in scenario_options()), config.BACKTESTING_BASE_SCENARIO
)


def model_options_for_segment(segment, **filters) -> list[dict]:
    """Model options narrowed to ``segment`` (see the cascade in callbacks)."""
    models = selectors.models_for_segment(segment, **filters)
    return [{"label": "All", "value": ALL_VALUE}] + [_model_option(model) for model in models]


def segment_options_for_model(model) -> list[dict]:
    """Segment options narrowed to ``model``."""
    return _options_with_all(selectors.segments_for_model(model))


def build_scope_summary(applied: dict | None) -> str:
    """The top bar's help line describing the applied scope."""
    return selectors.describe_scope(applied)


def _build_filter(
    label: str,
    *,
    value_id: str,
    toggle_id: str,
    menu_id: str,
    filter_key: str,
    options: list[dict],
    value: str,
    min_width: str = "200px",
) -> html.Div:
    """One labelled single-select filter cell, in the platform's own chrome."""
    return html.Div(
        className="monitoring-filter",
        style={"minWidth": min_width, "maxWidth": "420px"},
        children=[
            html.Label(label, htmlFor=toggle_id),
            shared_filters.build_single_select_dropdown(
                value_id=value_id,
                toggle_id=toggle_id,
                menu_id=menu_id,
                filter_key=filter_key,
                options=options,
                value=value,
            ),
        ],
    )


def _build_section_subnav() -> html.Div:
    """Jump links, in the same markup the PD page's sub-nav uses.

    ``assets/js/backtesting_subnav.js`` keeps the active link in sync with
    scroll position; it keys off ``data-bt-subnav-target``.
    """
    groups = []
    first = True
    for group_label, links in SUBNAV_GROUPS:
        group_class = "monitoring-section-subnav-group bt-subnav-group"
        if first:
            group_class += " active"
        groups.append(
            html.Div(
                className=group_class,
                children=[
                    html.Div(group_label, className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            html.Button(
                                link_label,
                                type="button",
                                className="active" if (first and index == 0) else "",
                                **{
                                    "data-bt-subnav-target": section_id,
                                    "aria-current": "location" if (first and index == 0) else "false",
                                },
                            )
                            for index, (section_id, link_label) in enumerate(links)
                        ],
                    ),
                ],
            )
        )
        first = False
    return html.Div(id=SUBNAV_ID, className="monitoring-section-subnav", children=groups)


def _build_top_bar() -> html.Div:
    return html.Div(
        className="top-bar",
        children=[
            html.Div(
                style={"flex": "1"},
                children=[
                    html.Div("Backtesting", className="monitoring-dashboard-title"),
                    html.Div(
                        className="monitoring-controls saas-top-filter-row monitoring-primary-filter-row",
                        children=[
                            _build_filter(
                                "Region",
                                value_id=REGION_ID,
                                toggle_id=REGION_TOGGLE_ID,
                                menu_id=REGION_MENU_ID,
                                filter_key=REGION_FILTER_KEY,
                                options=region_options(),
                                value=ALL_VALUE,
                                min_width="160px",
                            ),
                            _build_filter(
                                "Portfolio",
                                value_id=PORTFOLIO_ID,
                                toggle_id=PORTFOLIO_TOGGLE_ID,
                                menu_id=PORTFOLIO_MENU_ID,
                                filter_key=PORTFOLIO_FILTER_KEY,
                                options=portfolio_options(),
                                value=ALL_VALUE,
                                min_width="170px",
                            ),
                            _build_filter(
                                "Model Group",
                                value_id=MODEL_GROUP_ID,
                                toggle_id=MODEL_GROUP_TOGGLE_ID,
                                menu_id=MODEL_GROUP_MENU_ID,
                                filter_key=MODEL_GROUP_FILTER_KEY,
                                options=model_group_options(),
                                value=ALL_VALUE,
                                min_width="170px",
                            ),
                            _build_filter(
                                "Model",
                                value_id=MODEL_ID,
                                toggle_id=MODEL_TOGGLE_ID,
                                menu_id=MODEL_MENU_ID,
                                filter_key=MODEL_FILTER_KEY,
                                options=model_options(),
                                value=ALL_VALUE,
                                min_width="200px",
                            ),
                            _build_filter(
                                "Segment",
                                value_id=SEGMENT_ID,
                                toggle_id=SEGMENT_TOGGLE_ID,
                                menu_id=SEGMENT_MENU_ID,
                                filter_key=SEGMENT_FILTER_KEY,
                                options=segment_options(),
                                value=ALL_VALUE,
                                min_width="180px",
                            ),
                        ],
                    ),
                    html.Div(
                        "",
                        id=FILTER_HELP_ID,
                        className="monitoring-filter-help",
                    ),
                    html.Div(
                        className="monitoring-controls saas-top-filter-row saas-secondary-filter-row",
                        children=[
                            _build_filter(
                                # UI-only rename, matching the platform
                                # convention: the element id (bt-run-for), the
                                # applied-filter key (run_for) and the workbook
                                # column ("Run For") are all unchanged.
                                "Model Use Case / Cycle",
                                value_id=RUN_FOR_ID,
                                toggle_id=RUN_FOR_TOGGLE_ID,
                                menu_id=RUN_FOR_MENU_ID,
                                filter_key=RUN_FOR_FILTER_KEY,
                                options=run_for_options(),
                                value=ALL_VALUE,
                                min_width="240px",
                            ),
                            _build_filter(
                                "Scenario",
                                value_id=SCENARIO_ID,
                                toggle_id=SCENARIO_TOGGLE_ID,
                                menu_id=SCENARIO_MENU_ID,
                                filter_key=SCENARIO_FILTER_KEY,
                                options=scenario_options(),
                                value=DEFAULT_SCENARIO,
                            ),
                            _build_filter(
                                "J/N Flag",
                                value_id=JN_FLAG_ID,
                                toggle_id=JN_FLAG_TOGGLE_ID,
                                menu_id=JN_FLAG_MENU_ID,
                                filter_key=JN_FLAG_FILTER_KEY,
                                options=jn_flag_options(),
                                value=ALL_VALUE,
                            ),
                            _build_filter(
                                "Month End Snapshot",
                                value_id=SNAPSHOT_ID,
                                toggle_id=SNAPSHOT_TOGGLE_ID,
                                menu_id=SNAPSHOT_MENU_ID,
                                filter_key=SNAPSHOT_FILTER_KEY,
                                options=snapshot_options(),
                                value=ALL_VALUE,
                                min_width="220px",
                            ),
                            html.Div(
                                className="monitoring-filter bt-top-filter-action",
                                children=[
                                    html.Div(
                                        className="pd-mev-filter-actions",
                                        children=[
                                            html.Button(
                                                "Apply filters",
                                                id=APPLY_FILTERS_ID,
                                                className="btn pd-mev-filter-reset bt-apply-filters",
                                                n_clicks=0,
                                                type="button",
                                                title="Load the backtesting sections using the selected filters.",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    _build_section_subnav(),
                ],
            ),
        ],
    )


def build_empty_state(title: str, copy: str) -> html.Div:
    """Placeholder card, in the same treatment SAAS uses pre-apply."""
    return html.Div(
        className="section-card pd-mev-empty-state",
        children=[
            html.Div(title, className="pd-mev-chart-title"),
            html.P(copy, className="pd-section-subtitle"),
        ],
    )


def _format_stat(value, fmt: str) -> str:
    """A summary statistic, or an em dash when it has nothing to measure.

    ``None`` and ``0.0`` mean different things here -- "nothing scored" versus
    "scored, and perfect" -- so the empty case must not render as a number.
    """
    if value is None:
        return "—"
    try:
        return format(value, fmt)
    except (TypeError, ValueError):
        return "—"


def _build_summary_strip(view: dict) -> html.Div:
    """Headline error statistics for a metric, in the platform's meta chrome."""
    summary = view.get("summary") or {}
    items = [
        ("Scored forecasts", _format_stat(summary.get("count"), ",")),
        ("Bias", _format_stat(summary.get("bias"), "+,.4f")),
        ("MAPE", _format_stat(summary.get("mape"), ".1%")),
        ("RMSE", _format_stat(summary.get("rmse"), ",.4f")),
        ("Hit rate (±10%)", _format_stat(summary.get("hit_rate"), ".0%")),
    ]
    children = [
        html.Span([html.Span(f"{label}: "), html.Strong(value)], className="bt-stat")
        for label, value in items
    ]

    unscored = view.get("unscored") or 0
    if unscored:
        # Not an error: the most recent horizons genuinely have no actual yet.
        children.append(
            html.Span(
                f"{unscored:,} forecast(s) not yet scored — their target quarter "
                "has no realised outcome.",
                className="bt-stat bt-stat-note",
            )
        )

    coverage = view.get("coverage") or {}
    row_coverage = coverage.get("row_coverage")
    if row_coverage is not None and row_coverage < 1.0:
        children.append(
            html.Span(
                f"Exposure coverage: {row_coverage:.0%} of rows carried a weight.",
                className="bt-stat bt-stat-note",
            )
        )

    return html.Div(children, className="pd-mev-chart-meta bt-summary-strip")


def _build_metric_charts(view: dict, metric_label: str, theme_value: str | None) -> list:
    """The two chart cards for one metric section."""
    theme = theme_value or "light"
    return [
        html.Div(
            className="section-card bt-chart-card",
            children=[
                html.Div(
                    className="pd-mev-chart-header",
                    children=[
                        html.Div(
                            f"{metric_label} forecast vs actual",
                            className="pd-mev-chart-title",
                        ),
                        html.P(
                            "Realised outcome against every vintage's forecast of it. "
                            "Each dashed path is one Month End Snapshot; the right panel "
                            "shows each forecast's percentage error.",
                            className="pd-section-subtitle",
                        ),
                    ],
                ),
                _build_summary_strip(view),
                dcc.Graph(
                    figure=figures.build_forecast_actual_figure(view, theme=theme),
                    config=GRAPH_CONFIG,
                    className="chart-box bt-chart",
                ),
            ],
        ),
        html.Div(
            className="section-card bt-chart-card",
            children=[
                html.Div(
                    className="pd-mev-chart-header",
                    children=[
                        html.Div(
                            f"{metric_label} error by projection horizon",
                            className="pd-mev-chart-title",
                        ),
                        html.P(
                            "Mean absolute percentage error by horizon, with the mean "
                            "signed error beside it — magnitude on the left, direction "
                            "on the right.",
                            className="pd-section-subtitle",
                        ),
                    ],
                ),
                dcc.Graph(
                    figure=figures.build_horizon_error_figure(view, theme=theme),
                    config=GRAPH_CONFIG,
                    className="chart-box bt-chart",
                ),
            ],
        ),
        _build_chart_card(
            f"{metric_label} by vintage",
            "Each Month End Snapshot's projected path, aligned at age 0 and drawn "
            "against horizon rather than calendar quarter, so cohorts compare "
            "directly. Unlike the charts above this keeps every horizon, "
            "including those with no realised outcome yet.",
            figures.build_vintage_curve_figure(view, theme=theme),
        ),
    ]


def _build_chart_card(title: str, subtitle: str, figure, *, extra_children=()) -> html.Div:
    """One chart in the platform's card chrome."""
    return html.Div(
        className="section-card bt-chart-card",
        children=[
            html.Div(
                className="pd-mev-chart-header",
                children=[
                    html.Div(title, className="pd-mev-chart-title"),
                    html.P(subtitle, className="pd-section-subtitle"),
                ],
            ),
            *extra_children,
            dcc.Graph(figure=figure, config=GRAPH_CONFIG, className="chart-box bt-chart"),
        ],
    )


def _build_loss_curve_cards(applied_filters: dict | None, theme_value: str | None) -> list:
    """The static-pool view, cumulative and periodic.

    Both share a denominator -- the vintage's opening exposure -- so they can be
    read against each other. The cumulative curve answers "how much has this
    cohort lost by this age"; the periodic one answers "when did the losses
    arrive", which a cumulative curve cannot show because it only ever rises.
    """
    theme = theme_value or "light"
    cumulative = backtesting_service.build_loss_curve_series(applied_filters, cumulative=True)
    periodic = backtesting_service.build_loss_curve_series(applied_filters, cumulative=False)
    return [
        _build_chart_card(
            "Cumulative loss performance",
            "Net charge-off accumulated through each horizon, as a share of that "
            "vintage's opening exposure. Every vintage is aligned at age 0, so a "
            "later cohort can be read against an earlier one at the same point in "
            "its life.",
            figures.build_cumulative_loss_figure(cumulative, theme=theme),
        ),
        _build_chart_card(
            "Periodic loss performance",
            "The same curves undifferenced: loss arising in each individual "
            "quarter, on the same opening-exposure denominator. This is where the "
            "timing of a cohort's losses shows up — two vintages can reach the "
            "same cumulative total on very different paths.",
            figures.build_periodic_loss_figure(periodic, theme=theme),
        ),
    ]


def _build_overview_section(applied_filters: dict | None, theme_value: str | None = None) -> html.Section:
    if applied_filters:
        body = _build_loss_curve_cards(applied_filters, theme_value)
    else:
        body = [build_empty_state(
            "Apply filters to run the backtest",
            "Narrow the scope in the top bar -- Region, Portfolio and Model "
            "Group filter the models available, then pick a Model or Segment, a "
            "Model Use Case / Cycle, Scenario, J/N Flag and Month End Snapshot "
            "-- and click Apply filters. Each metric section below then reports "
            "forecast-versus-actual error for the selected scope.",
        )]

    return html.Section(
        id=SECTION_OVERVIEW,
        className="pd-content-section pd-live-section",
        children=[
            build_chapter_heading(
                "Chapter 1",
                "Backtesting",
                "Compares each model's projections against the outcome that was "
                "actually realised, by vintage and projection horizon.",
            ),
            build_section_heading(
                "1.0",
                "Backtest Overview",
                "Forecast accuracy across every metric, vintage and horizon in the "
                "applied scope.",
                "N/A",
                options={"show_rag": False},
            ),
            *body,
        ],
    )


def _build_metric_section(
    anchor: str, index: str, title: str, description: str,
    *, view: dict | None, theme_value: str | None,
) -> html.Section:
    if view is None:
        body = [build_empty_state(
            f"{title} — apply filters to score this metric",
            "Forecast-versus-actual charts render here once a scope is applied.",
        )]
    else:
        body = _build_metric_charts(view, title, theme_value)

    return html.Section(
        id=anchor,
        className="pd-content-section pd-live-section",
        children=[
            build_section_heading(index, title, description, "N/A", options={"show_rag": False}),
            *body,
        ],
    )


def build_page_content(applied_filters: dict | None = None, theme_value: str | None = None) -> list:
    """Every section, in page order. Pure function of the applied scope.

    ``theme_value`` is accepted now and unused: the render callback already
    passes the active theme so the chart milestone can build theme-aware figures
    here without changing the callback's signature.
    """
    # The service is called once per render, not once per section, so all five
    # metrics share one pass over the scoped frames.
    views = backtesting_service.build_dashboard_view(applied_filters) if applied_filters else {}

    return [
        _build_overview_section(applied_filters, theme_value),
        *(
            _build_metric_section(
                anchor, index, title, description,
                view=views.get(metric), theme_value=theme_value,
            )
            for anchor, index, title, description, metric in METRIC_SECTIONS
        ),
    ]


def page_layout() -> list:
    """Top bar + the backtesting section stack."""
    return [
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
        _build_top_bar(),
        html.Div(
            className="content",
            children=[
                html.Div(
                    id="tab-backtesting",
                    className="tab-panel active pd-performance-app bt-page",
                    children=[
                        build_dashboard_loading_shell(
                            content_id=CONTENT_ID,
                            content_class_name="bt-section-stack",
                            scope_label="Backtesting",
                            title="Refreshing backtest",
                            note="Recomputing forecast-versus-actual error for the selected scope.",
                            children=build_page_content(),
                        ),
                    ],
                ),
            ],
        ),
    ]
