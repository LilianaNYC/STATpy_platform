"""Callbacks for the Backtesting page.

Wiring only in this milestone: filter shells, the Segment/Model cascade, the
apply-filters snapshot, and the theme-driven re-render. No figures yet.

The four callback-wiring rules in ``CLAUDE.md`` apply here, and the
Segment/Model cascade is squarely the rule-2 case (Segment narrows Model *and*
Model narrows Segment). See :func:`_register_cascade_callbacks` for how each
trap is avoided.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ....shared import theme
from ....shared.registration import already_registered
from ....shared.ui import controls as shared_filters
from ...monitoring.ui.common import (
    build_single_select_options,
    register_single_select_callbacks,
)
from ..ui.views import backtesting as layout

# Every filter shell on the page: (value id, toggle id, menu id, filter key).
_FILTER_SHELLS = (
    (layout.REGION_ID, layout.REGION_TOGGLE_ID, layout.REGION_MENU_ID, layout.REGION_FILTER_KEY),
    (layout.PORTFOLIO_ID, layout.PORTFOLIO_TOGGLE_ID, layout.PORTFOLIO_MENU_ID, layout.PORTFOLIO_FILTER_KEY),
    (layout.MODEL_GROUP_ID, layout.MODEL_GROUP_TOGGLE_ID, layout.MODEL_GROUP_MENU_ID, layout.MODEL_GROUP_FILTER_KEY),
    (layout.SEGMENT_ID, layout.SEGMENT_TOGGLE_ID, layout.SEGMENT_MENU_ID, layout.SEGMENT_FILTER_KEY),
    (layout.MODEL_ID, layout.MODEL_TOGGLE_ID, layout.MODEL_MENU_ID, layout.MODEL_FILTER_KEY),
    (layout.RUN_FOR_ID, layout.RUN_FOR_TOGGLE_ID, layout.RUN_FOR_MENU_ID, layout.RUN_FOR_FILTER_KEY),
    (layout.SCENARIO_ID, layout.SCENARIO_TOGGLE_ID, layout.SCENARIO_MENU_ID, layout.SCENARIO_FILTER_KEY),
    (layout.JN_FLAG_ID, layout.JN_FLAG_TOGGLE_ID, layout.JN_FLAG_MENU_ID, layout.JN_FLAG_FILTER_KEY),
    (layout.SNAPSHOT_ID, layout.SNAPSHOT_TOGGLE_ID, layout.SNAPSHOT_MENU_ID, layout.SNAPSHOT_FILTER_KEY),
)


def _clicked_value(clicks) -> str | None:
    """The option value a real click landed on, or ``None``.

    Two rule-2 traps handled together:

    * The value is read from ``ctx.triggered_id``, **not** from the dropdown's
      ``State``. ``select_single_select_option`` writes that value in the same
      round trip, so ``State`` still holds the *previous* value and the
      narrowing would silently do nothing.
    * Option buttons are re-created whenever a menu is rebuilt, and the remount
      fires this pattern-matching ``Input`` with every ``n_clicks`` still 0.
      Without the ``any()`` guard that spurious fire would narrow the sibling
      filter against whichever option mounted first.
    """
    # Click check first: the remount fire needs no trigger context, so this
    # short-circuits before touching ``ctx`` at all.
    if not any(clicks or []):
        return None
    triggered = ctx.triggered_id
    if not triggered:
        return None
    return triggered.get("value")


def _register_filter_shells(app) -> None:
    """Wire each single-select shell using monitoring's shared helpers.

    Cross-feature import: ``features/monitoring/ui/common.py`` owns the
    single-select shell wiring (menu toggle, option click, label sync) and both
    dashboards use it rather than each growing its own dropdown code.
    """
    for value_id, toggle_id, menu_id, filter_key in _FILTER_SHELLS:
        register_single_select_callbacks(
            app,
            value_id=value_id,
            toggle_id=toggle_id,
            menu_id=menu_id,
            filter_key=filter_key,
        )


def _register_cascade_callbacks(app) -> None:
    """The scope cascade: Region -> Portfolio -> Model Group -> Model <-> Segment.

    ``CLAUDE.md`` callback rule 2 in full. Model narrows Segment *and* Segment
    narrows Model, so reading either filter's ``value`` as an ``Input`` would
    close the loop and produce a dependency cycle. Everything therefore triggers
    on the **option buttons'** ``n_clicks``.

    One callback, not five. Every single-select option button shares the same
    pattern ``type``, so a single pattern ``Input`` matching *all* of this page's
    filters catches the click and dispatches on ``ctx.triggered_id["filter"]``.
    Five separate callbacks would each need to write Model's and Segment's
    options, and Dash would then have four callbacks fighting over one output.

    Rule 3 is satisfied trivially: the callback's only ``Input`` is that one
    pattern, so nothing from outside a callback-rendered container is mixed in.
    Current values arrive as ``State`` purely to preserve still-valid picks.
    """

    # Filters whose click reshapes the scope, in narrowing order.
    _SCOPE_KEYS = (
        layout.REGION_FILTER_KEY,
        layout.PORTFOLIO_FILTER_KEY,
        layout.MODEL_GROUP_FILTER_KEY,
        layout.MODEL_FILTER_KEY,
        layout.SEGMENT_FILTER_KEY,
    )

    @app.callback(
        Output(layout.PORTFOLIO_ID, "options"),
        Output(layout.PORTFOLIO_ID, "value", allow_duplicate=True),
        Output(layout.MODEL_GROUP_ID, "options"),
        Output(layout.MODEL_GROUP_ID, "value", allow_duplicate=True),
        Output(layout.MODEL_ID, "options"),
        Output(layout.MODEL_ID, "value", allow_duplicate=True),
        Output(layout.SEGMENT_ID, "options"),
        Output(layout.SEGMENT_ID, "value", allow_duplicate=True),
        Input(
            {"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": ALL, "value": ALL},
            "n_clicks",
        ),
        State(layout.REGION_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
        State(layout.MODEL_GROUP_ID, "value"),
        State(layout.MODEL_ID, "value"),
        State(layout.SEGMENT_ID, "value"),
        prevent_initial_call=True,
    )
    def cascade_scope_filters(clicks, region, portfolio, model_group, model, segment):
        picked = _clicked_value(clicks)
        triggered = ctx.triggered_id if picked is not None else None
        filter_key = (triggered or {}).get("filter")
        if picked is None or filter_key not in _SCOPE_KEYS:
            # Either the remount fire, or a click on a filter that does not
            # reshape the scope (Scenario, J/N Flag, ...).
            return (no_update,) * 8

        # The clicked filter's own State still holds the *previous* value in this
        # round trip, so overlay the picked value before recomputing anything.
        selection = {
            layout.REGION_FILTER_KEY: region,
            layout.PORTFOLIO_FILTER_KEY: portfolio,
            layout.MODEL_GROUP_FILTER_KEY: model_group,
            layout.MODEL_FILTER_KEY: model,
            layout.SEGMENT_FILTER_KEY: segment,
        }
        selection[filter_key] = picked

        region = selection[layout.REGION_FILTER_KEY]
        portfolio = selection[layout.PORTFOLIO_FILTER_KEY]
        model_group = selection[layout.MODEL_GROUP_FILTER_KEY]
        model = selection[layout.MODEL_FILTER_KEY]
        segment = selection[layout.SEGMENT_FILTER_KEY]

        def _clamp(value, options):
            """Keep a still-valid pick; otherwise fall back to All."""
            allowed = {option["value"] for option in options}
            return value if value in allowed else layout.ALL_VALUE

        portfolio_options = layout.portfolio_options(region)
        portfolio = _clamp(portfolio, portfolio_options)

        model_group_options = layout.model_group_options(region, portfolio)
        model_group = _clamp(model_group, model_group_options)

        attribute_filters = {
            "region": region,
            "portfolio": portfolio,
            "model_group": model_group,
        }

        # Segment narrows Model and Model narrows Segment. Whichever the user
        # just clicked is the one that wins; the other is recomputed from it.
        if filter_key == layout.SEGMENT_FILTER_KEY:
            model_options = layout.model_options_for_segment(segment, **attribute_filters)
            model = _clamp(model, model_options)
            segment_options = layout.segment_options(**attribute_filters, model=layout.ALL_VALUE)
        else:
            model_options = layout.model_options(**attribute_filters)
            model = _clamp(model, model_options)
            segment_options = layout.segment_options(**attribute_filters, model=model)
            segment = _clamp(segment, segment_options)

        # Never rewrite the filter the user just clicked: select_single_select_option
        # owns that value for this round trip.
        def _own(key, options, value):
            return (no_update, no_update) if key == filter_key else (options, value)

        return (
            *_own(layout.PORTFOLIO_FILTER_KEY, portfolio_options, portfolio),
            *_own(layout.MODEL_GROUP_FILTER_KEY, model_group_options, model_group),
            *_own(layout.MODEL_FILTER_KEY, model_options, model),
            *_own(layout.SEGMENT_FILTER_KEY, segment_options, segment),
        )


def _register_apply_callbacks(app) -> None:
    """Snapshot the top-bar selections into the applied-filters store.

    Nothing renders from the live filter values: the page reads the applied
    snapshot, so a half-edited filter set never drives the content. Same
    interaction model as the SAAS workspace and the PD page.
    """

    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Output(layout.FILTER_HELP_ID, "children"),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(layout.REGION_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
        State(layout.MODEL_GROUP_ID, "value"),
        State(layout.SEGMENT_ID, "value"),
        State(layout.MODEL_ID, "value"),
        State(layout.RUN_FOR_ID, "value"),
        State(layout.SCENARIO_ID, "value"),
        State(layout.JN_FLAG_ID, "value"),
        State(layout.SNAPSHOT_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_backtesting_filters(
        _n_clicks, region, portfolio, model_group, segment, model, run_for,
        scenario, jn_flag, snapshot,
    ):
        applied = {
            "region": region,
            "portfolio": portfolio,
            "model_group": model_group,
            "segment": segment,
            "model": model,
            "run_for": run_for,
            "scenario": scenario,
            "jn_flag": jn_flag,
            "snapshot": snapshot,
        }
        return applied, layout.build_scope_summary(applied)


def _register_render_callbacks(app) -> None:
    """Re-render the section stack from the applied filters and active theme.

    The theme Input is what makes the page follow the app toggle exactly as the
    SAAS workspace does: chart figures (once they exist) are rebuilt for the new
    theme rather than restyled in CSS.
    """

    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(theme.APP_THEME_ID, "value"),
    )
    def render_backtesting_content(applied_filters, theme_value):
        return layout.build_page_content(
            applied_filters=applied_filters,
            theme_value=theme.normalize_theme_value(theme_value),
        )


def register_callbacks(app) -> None:
    """Register the Backtesting page's callbacks (idempotent)."""
    if already_registered(app, "page:backtesting.backtesting"):
        return

    _register_filter_shells(app)
    _register_cascade_callbacks(app)
    _register_apply_callbacks(app)
    _register_render_callbacks(app)


# Re-exported so tests and future sibling modules can build option buttons
# without importing monitoring directly.
build_single_select_options = build_single_select_options
