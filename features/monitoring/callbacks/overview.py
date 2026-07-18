"""Callbacks for the Overview page."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import overview as layout
from ....shared.ui import controls
from ....shared.registration import already_registered
from ....shared.theme import APP_THEME_ID, URL_ID, normalize_theme_value
from ..data_access import PD_PERFORMANCE_DATA

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}
_OVERVIEW_PATH = "/overview"


def _overview_filter_snapshot(
    reporting_cycle: str | None,
    monitoring_point: str | None,
    segment_model_group: str | None,
) -> dict[str, str]:
    """Build an applied snapshot that matches the values visible in the top bar."""
    cycle = str(reporting_cycle or "").strip()
    valid_points = controls.REPORTING_CYCLE_QUARTERS.get(cycle, [])
    resolved_point = filter_shell.resolve_monitoring_point_value(valid_points, monitoring_point)
    return {
        "reporting_cycle": cycle,
        "monitoring_point": resolved_point,
        "segment_model_group": str(segment_model_group or "All"),
    }


def _checked_monitoring_point(
    option_ids: list[dict] | None,
    option_classes: list[str] | None,
    fallback: str | None,
) -> str | None:
    """Return the quarter whose custom-dropdown option displays the checkmark."""
    for option_id, class_name in zip(option_ids or [], option_classes or []):
        if "is-selected" in str(class_name or "").split():
            return option_id.get("value") or fallback
    return fallback


def _resolve_rag_flow_current_rows(
    scoped_rows: list[dict] | None,
    segment_scoped_rows: list[dict] | None,
    applied: dict | None,
) -> tuple[list[dict], list[dict]]:
    """Return the exact current-state rows used by the initial Sankey render."""
    monitoring_point = (applied or {}).get("monitoring_point") or "All"
    return (
        layout.resolve_current_rows(scoped_rows or [], monitoring_point),
        layout.resolve_current_segment_rows(segment_scoped_rows or [], monitoring_point),
    )


def register_callbacks(app) -> None:
    """Register Overview callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.overview"):
        return

    data = PD_PERFORMANCE_DATA

    for value_id, toggle_id, menu_id, filter_key in (
        (layout.REPORTING_CYCLE_ID, layout.REPORTING_CYCLE_TOGGLE_ID, layout.REPORTING_CYCLE_MENU_ID, layout.REPORTING_CYCLE_FILTER_KEY),
        (layout.MONITORING_POINT_ID, layout.MONITORING_POINT_TOGGLE_ID, layout.MONITORING_POINT_MENU_ID, layout.MONITORING_POINT_FILTER_KEY),
        (layout.SEGMENT_MODEL_GROUP_ID, layout.SEGMENT_MODEL_GROUP_TOGGLE_ID, layout.SEGMENT_MODEL_GROUP_MENU_ID, layout.SEGMENT_MODEL_GROUP_FILTER_KEY),
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
    def sync_overview_monitoring_point_dropdown(reporting_cycle, selected_monitoring_point):
        options = controls.REPORTING_CYCLE_QUARTERS.get(reporting_cycle, [])
        value = filter_shell.resolve_monitoring_point_value(options, selected_monitoring_point)
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
    def update_overview_range_store(
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
        Input(URL_ID, "pathname"),
        State(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.MONITORING_POINT_ID, "value"),
        State(layout.SEGMENT_MODEL_GROUP_ID, "value"),
        State(
            {
                "type": controls.SINGLE_SELECT_OPTION_ID,
                "filter": layout.MONITORING_POINT_FILTER_KEY,
                "value": ALL,
            },
            "id",
        ),
        State(
            {
                "type": controls.SINGLE_SELECT_OPTION_ID,
                "filter": layout.MONITORING_POINT_FILTER_KEY,
                "value": ALL,
            },
            "className",
        ),
    )
    def apply_overview_filters(
        _n_clicks,
        pathname,
        reporting_cycle,
        monitoring_point,
        segment_model_group,
        monitoring_point_option_ids,
        monitoring_point_option_classes,
    ):
        triggered = ctx.triggered_id
        if triggered in (None, URL_ID):
            return None if pathname == _OVERVIEW_PATH else no_update
        if triggered == layout.APPLY_FILTERS_ID and not _n_clicks:
            return no_update
        if pathname != _OVERVIEW_PATH:
            return no_update
        checked_monitoring_point = _checked_monitoring_point(
            monitoring_point_option_ids,
            monitoring_point_option_classes,
            monitoring_point,
        )
        return _overview_filter_snapshot(
            reporting_cycle,
            checked_monitoring_point,
            segment_model_group,
        )

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
    def render_overview_content(applied, theme_value, range_store):
        if not applied:
            return layout.build_overview_apply_prompt(), [], []

        from ....shared.repositories.filters_config import load_filter_config
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"] if cfg["reporting_cycles"] else "CCAR 2026"

        reporting_cycle = applied.get("reporting_cycle") or default_cycle

        children, scoped_rows, segment_scoped_rows = layout.render_overview_content(
            data,
            reporting_cycle,
            applied.get("monitoring_point") or "All",
            "Overall RAG",
            "Overall RAG",
            range_store or {},
            theme_value=theme_value,
            segment_model_group=applied.get("segment_model_group") or "All",
        )
        return children, scoped_rows, segment_scoped_rows

    # -----------------------------------------------------------------
    # Interactive RAG journey: aggregate counts -> RAG bucket -> entity.
    # Both responsive graph variants share one selection store so a resize
    # never loses the user's current focus.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.RAG_FLOW_SELECTION_STORE_ID, "data"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.RAG_FLOW_MODEL_DESKTOP_ID, "clickData"),
        Input(layout.RAG_FLOW_MODEL_COMPACT_ID, "clickData"),
        Input(layout.RAG_FLOW_SEGMENT_DESKTOP_ID, "clickData"),
        Input(layout.RAG_FLOW_SEGMENT_COMPACT_ID, "clickData"),
        Input(
            {
                "type": layout.RAG_FLOW_ENTITY_BUTTON_TYPE,
                "scope": ALL,
                "entity": ALL,
            },
            "n_clicks",
        ),
        Input(
            {
                "type": layout.RAG_FLOW_RESET_BUTTON_TYPE,
                "scope": ALL,
            },
            "n_clicks",
        ),
        Input(
            {
                "type": layout.RAG_FLOW_SHOW_ALL_BUTTON_TYPE,
                "scope": ALL,
            },
            "n_clicks",
        ),
        State(layout.RAG_FLOW_SELECTION_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_rag_flow_selection(
        _applied,
        model_desktop_click,
        model_compact_click,
        segment_desktop_click,
        segment_compact_click,
        entity_clicks,
        reset_clicks,
        show_all_clicks,
        selection_store,
    ):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update

        if triggered == layout.APPLIED_FILTERS_STORE_ID:
            return {"model": None, "segment": None}

        store = dict(selection_store or {"model": None, "segment": None})
        graph_clicks = {
            layout.RAG_FLOW_MODEL_DESKTOP_ID: ("model", model_desktop_click),
            layout.RAG_FLOW_MODEL_COMPACT_ID: ("model", model_compact_click),
            layout.RAG_FLOW_SEGMENT_DESKTOP_ID: ("segment", segment_desktop_click),
            layout.RAG_FLOW_SEGMENT_COMPACT_ID: ("segment", segment_compact_click),
        }
        if isinstance(triggered, str) and triggered in graph_clicks:
            scope, click_data = graph_clicks[triggered]
            points = (click_data or {}).get("points") or []
            customdata = points[0].get("customdata") if points else None
            if not isinstance(customdata, (list, tuple)) or len(customdata) < 4:
                return no_update
            if customdata[0] != "rag-bucket":
                return no_update
            try:
                stage_index = int(customdata[1])
            except (TypeError, ValueError):
                return no_update
            tone = str(customdata[2] or "")
            if stage_index not in range(len(layout._RAG_FLOW_STAGES)) or tone not in layout._RAG_FLOW_VALID_TONES:
                return no_update
            store[scope] = {
                "stage_index": stage_index,
                "tone": tone,
                "entity": None,
            }
            return store

        if isinstance(triggered, dict) and triggered.get("type") == layout.RAG_FLOW_ENTITY_BUTTON_TYPE:
            if not any(entity_clicks or []):
                return no_update
            scope = triggered.get("scope")
            if scope not in ("model", "segment") or not store.get(scope):
                return no_update
            current = dict(store[scope])
            current["entity"] = str(triggered.get("entity", "") or "")
            store[scope] = current
            return store

        if isinstance(triggered, dict) and triggered.get("type") == layout.RAG_FLOW_RESET_BUTTON_TYPE:
            if not any(reset_clicks or []):
                return no_update
            scope = triggered.get("scope")
            if scope not in ("model", "segment"):
                return no_update
            store[scope] = None
            return store

        if isinstance(triggered, dict) and triggered.get("type") == layout.RAG_FLOW_SHOW_ALL_BUTTON_TYPE:
            if not any(show_all_clicks or []):
                return no_update
            scope = triggered.get("scope")
            if scope not in ("model", "segment"):
                return no_update
            # "See all" -- list every journey without focusing a bucket.
            store[scope] = {"all": True, "entity": None}
            return store

        return no_update

    @app.callback(
        Output(layout.RAG_FLOW_MODEL_DESKTOP_ID, "figure"),
        Output(layout.RAG_FLOW_MODEL_COMPACT_ID, "figure"),
        Output(layout.RAG_FLOW_MODEL_BROWSER_ID, "children"),
        Output(layout.RAG_FLOW_SEGMENT_DESKTOP_ID, "figure"),
        Output(layout.RAG_FLOW_SEGMENT_COMPACT_ID, "figure"),
        Output(layout.RAG_FLOW_SEGMENT_BROWSER_ID, "children"),
        Input(layout.RAG_FLOW_SELECTION_STORE_ID, "data"),
        Input(layout.SCOPED_ROWS_STORE_ID, "data"),
        Input(layout.SEGMENT_SCOPED_ROWS_STORE_ID, "data"),
        Input(APP_THEME_ID, "value"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def render_interactive_rag_flows(
        selection_store,
        scoped_rows,
        segment_scoped_rows,
        theme_value,
        applied,
    ):
        if not scoped_rows and not segment_scoped_rows:
            return (no_update,) * 6

        theme = normalize_theme_value(theme_value)
        selections = selection_store or {}
        model_selection = selections.get("model")
        segment_selection = selections.get("segment")
        # The stores contain the full reporting-cycle history for trend charts.
        # The Sankey must stay on the same current monitoring-point slice used
        # by the initial Overview render; otherwise a click would multiply
        # entities across quarters and produce misleading counts.
        model_rows, segment_rows = _resolve_rag_flow_current_rows(
            scoped_rows,
            segment_scoped_rows,
            applied,
        )

        return (
            layout._rag_flow_sankey_figure(
                model_rows,
                theme,
                selection=model_selection,
                entity_kind="model",
            ),
            layout._rag_flow_sankey_figure(
                model_rows,
                theme,
                compact=True,
                selection=model_selection,
                entity_kind="model",
            ),
            layout._rag_flow_entity_browser(model_rows, model_selection, "model"),
            layout._rag_flow_sankey_figure(
                segment_rows,
                theme,
                selection=segment_selection,
                entity_kind="segment",
            ),
            layout._rag_flow_sankey_figure(
                segment_rows,
                theme,
                compact=True,
                selection=segment_selection,
                entity_kind="segment",
            ),
            layout._rag_flow_entity_browser(segment_rows, segment_selection, "segment"),
        )

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
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_overview_trend_chart(rag_trend_metric, range_store, scoped_rows, theme_value, applied):
        if not scoped_rows:
            return no_update
        theme = normalize_theme_value(theme_value)
        monitoring_point = (applied or {}).get("monitoring_point") or "All"
        return layout.build_trend_figure(scoped_rows, rag_trend_metric or "Overall RAG", range_store or {}, theme, monitoring_point)

    @app.callback(
        Output(layout.SEGMENT_RAG_TREND_CHART_ID, "figure"),
        Input(layout.SEGMENT_RAG_TREND_METRIC_ID, "value"),
        Input(layout.RANGE_STORE_ID, "data"),
        State(layout.SEGMENT_SCOPED_ROWS_STORE_ID, "data"),
        State(APP_THEME_ID, "value"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_overview_segment_trend_chart(rag_trend_metric, range_store, segment_scoped_rows, theme_value, applied):
        if not segment_scoped_rows:
            return no_update
        theme = normalize_theme_value(theme_value)
        monitoring_point = (applied or {}).get("monitoring_point") or "All"
        return layout.build_segment_trend_figure(segment_scoped_rows, rag_trend_metric or "Overall RAG", range_store or {}, theme, monitoring_point)
