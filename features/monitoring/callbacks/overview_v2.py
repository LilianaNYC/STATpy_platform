"""Callbacks for the Overview v2 page."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import overview_v2 as layout
from ....shared.ui import controls
from ....shared.registration import already_registered
from ....shared.theme import APP_THEME_ID, normalize_theme_value
from ..data_access import PD_PERFORMANCE_DATA

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def register_callbacks(app) -> None:
    """Register Overview v2 callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.overview_v2"):
        return

    data = PD_PERFORMANCE_DATA

    for value_id, toggle_id, menu_id, filter_key in (
        (layout.REPORTING_CYCLE_ID, layout.REPORTING_CYCLE_TOGGLE_ID, layout.REPORTING_CYCLE_MENU_ID, layout.REPORTING_CYCLE_FILTER_KEY),
        (layout.MONITORING_POINT_ID, layout.MONITORING_POINT_TOGGLE_ID, layout.MONITORING_POINT_MENU_ID, layout.MONITORING_POINT_FILTER_KEY),
        (layout.RAG_TREND_METRIC_ID, layout.RAG_TREND_METRIC_TOGGLE_ID, layout.RAG_TREND_METRIC_MENU_ID, layout.RAG_TREND_METRIC_FILTER_KEY),
        (layout.SEGMENT_RAG_TREND_METRIC_ID, layout.SEGMENT_RAG_TREND_METRIC_TOGGLE_ID, layout.SEGMENT_RAG_TREND_METRIC_MENU_ID, layout.SEGMENT_RAG_TREND_METRIC_FILTER_KEY),
    ):
        filter_shell.register_single_select_callbacks(
            app,
            value_id=value_id,
            toggle_id=toggle_id,
            menu_id=menu_id,
            filter_key=filter_key,
        )

    @app.callback(
        Output(layout.MONITORING_POINT_ID, "options"),
        Output(layout.MONITORING_POINT_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.MONITORING_POINT_ID, "value"),
    )
    def sync_overview_v2_monitoring_point_dropdown(reporting_cycle, selected_monitoring_point):
        options = controls.REPORTING_CYCLE_QUARTERS.get(reporting_cycle, [])
        value = selected_monitoring_point if selected_monitoring_point in options else (options[0] if options else "")
        return [{"label": option, "value": option} for option in options], value

    # -----------------------------------------------------------------
    # RAG trend range picker (on-page control, no re-Apply required).
    # Shared by both chapters -- each uses its own range_key
    # (RAG_TREND_RANGE_KEY / SEGMENT_RAG_TREND_RANGE_KEY) within the same store.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.RANGE_STORE_ID, "data"),
        Input({"type": controls.RANGE_WINDOW_ID, "key": ALL}, "value"),
        Input({"type": controls.RANGE_FROM_ID, "key": ALL}, "value"),
        Input({"type": controls.RANGE_TO_ID, "key": ALL}, "value"),
        State({"type": controls.RANGE_WINDOW_ID, "key": ALL}, "id"),
        State({"type": controls.RANGE_FROM_ID, "key": ALL}, "id"),
        State({"type": controls.RANGE_TO_ID, "key": ALL}, "id"),
        State({"type": controls.RANGE_FROM_ID, "key": ALL}, "options"),
        State(layout.RANGE_STORE_ID, "data"),
        prevent_initial_call=True,
        allow_duplicate=True,
    )
    def update_overview_v2_range_store(
        window_values, from_values, to_values, window_ids, from_ids, to_ids, from_options_list, range_store,
    ):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update

        range_key = triggered["key"]
        range_store = dict(range_store or {})

        if triggered["type"] == controls.RANGE_WINDOW_ID:
            preset = window_values[window_ids.index(triggered)]
            from_id = {"type": controls.RANGE_FROM_ID, "key": range_key}
            if from_id not in from_ids:
                return no_update
            from_idx = from_ids.index(from_id)
            periods = [option["value"] for option in from_options_list[from_idx] if option["value"]]
            if preset == "all":
                range_store[range_key] = {"from": "", "to": ""}
            else:
                count = _RANGE_PRESET_COUNTS.get(preset)
                if not count or not periods:
                    return no_update
                range_store[range_key] = {"from": periods[max(0, len(periods) - count)], "to": periods[-1]}
        elif triggered["type"] in (controls.RANGE_FROM_ID, controls.RANGE_TO_ID):
            boundary = "from" if triggered["type"] == controls.RANGE_FROM_ID else "to"
            ids = from_ids if boundary == "from" else to_ids
            values = from_values if boundary == "from" else to_values
            if triggered not in ids:
                return no_update
            value = values[ids.index(triggered)]

            current = dict(range_store.get(range_key) or {"from": "", "to": ""})
            current[boundary] = value
            if current["from"] and current["to"] and current["from"] > current["to"]:
                if boundary == "from":
                    current["to"] = current["from"]
                else:
                    current["from"] = current["to"]
            range_store[range_key] = current
        else:
            return no_update

        return range_store

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.MONITORING_POINT_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_overview_v2_filters(_n_clicks, reporting_cycle, monitoring_point):
        if not _n_clicks:
            return no_update
        return {
            "reporting_cycle": reporting_cycle,
            "monitoring_point": monitoring_point,
        }

    # -----------------------------------------------------------------
    # Master re-render: applied store + theme -> content.
    #
    # The RAG-trend dimension dropdowns and range controls live INSIDE this
    # callback's own output (they don't exist until content has rendered at
    # least once), so they cannot also be Inputs/State here -- that would be
    # a circular dependency that never fires on the first "Apply" click.
    # They're wired to their own mini-callbacks below instead, which read
    # the cached rows this callback writes to SCOPED_ROWS_STORE_ID /
    # SEGMENT_SCOPED_ROWS_STORE_ID.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Output(layout.SCOPED_ROWS_STORE_ID, "data"),
        Output(layout.SEGMENT_SCOPED_ROWS_STORE_ID, "data"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(APP_THEME_ID, "value"),
        State(layout.RANGE_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def render_overview_v2_content(applied, theme_value, range_store):
        if not applied:
            return layout.build_overview_v2_apply_prompt(), no_update, no_update

        from ....shared.repositories.filters_config import load_filter_config
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"] if cfg["reporting_cycles"] else "CCAR 2026"

        reporting_cycle = applied.get("reporting_cycle") or default_cycle

        children, scoped_rows, segment_scoped_rows = layout.render_overview_v2_content(
            data,
            reporting_cycle,
            applied.get("monitoring_point") or "All",
            "Overall RAG",
            "Overall RAG",
            range_store or {},
            theme_value=theme_value,
        )
        return children, scoped_rows, segment_scoped_rows

    # -----------------------------------------------------------------
    # RAG trend charts: each chapter's dimension picker + range controls
    # update just that chart, without recomputing/re-rendering the rest of
    # the page.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.RAG_TREND_CHART_ID, "figure"),
        Input(layout.RAG_TREND_METRIC_ID, "value"),
        Input(layout.RANGE_STORE_ID, "data"),
        State(layout.SCOPED_ROWS_STORE_ID, "data"),
        State(APP_THEME_ID, "value"),
        prevent_initial_call=True,
    )
    def update_overview_v2_trend_chart(rag_trend_metric, range_store, scoped_rows, theme_value):
        if not scoped_rows:
            return no_update
        theme = normalize_theme_value(theme_value)
        return layout.build_trend_figure(scoped_rows, rag_trend_metric or "Overall RAG", range_store or {}, theme)

    @app.callback(
        Output(layout.SEGMENT_RAG_TREND_CHART_ID, "figure"),
        Input(layout.SEGMENT_RAG_TREND_METRIC_ID, "value"),
        Input(layout.RANGE_STORE_ID, "data"),
        State(layout.SEGMENT_SCOPED_ROWS_STORE_ID, "data"),
        State(APP_THEME_ID, "value"),
        prevent_initial_call=True,
    )
    def update_overview_v2_segment_trend_chart(rag_trend_metric, range_store, segment_scoped_rows, theme_value):
        if not segment_scoped_rows:
            return no_update
        theme = normalize_theme_value(theme_value)
        return layout.build_segment_trend_figure(segment_scoped_rows, rag_trend_metric or "Overall RAG", range_store or {}, theme)
