"""Callbacks for the monitoring overview page.

Ported from ``integrated:callbacks/monitoring_overview_callbacks.py`` into
the main-branch page structure.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import overview as layout
from ....components import filters
from ..domain.overview import build_overview_rows, overview_filter_options
from ....shared.registration import already_registered
from ..data_access import PD_PERFORMANCE_DATA

_OVERVIEW_ROWS = build_overview_rows(PD_PERFORMANCE_DATA)

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def _dropdown_options(values: list[str]) -> list[dict]:
    return [{"label": value, "value": value} for value in values]


def _keep_valid(value: str | None, values: list[str]) -> str:
    return value if value in values else "All"


def register_callbacks(app) -> None:
    """Register all Overview callbacks against *app* (idempotent)."""
    if already_registered(app, "page:monitoring.overview"):
        return

    overview_rows = _OVERVIEW_ROWS
    data = PD_PERFORMANCE_DATA

    for value_id, toggle_id, menu_id, filter_key in (
        (layout.PERIOD_ID, layout.PERIOD_TOGGLE_ID, layout.PERIOD_MENU_ID, layout.PERIOD_FILTER_KEY),
        (layout.SEGMENT_ID, layout.SEGMENT_TOGGLE_ID, layout.SEGMENT_MENU_ID, layout.SEGMENT_FILTER_KEY),
        (
            layout.MODEL_GROUP_ID,
            layout.MODEL_GROUP_TOGGLE_ID,
            layout.MODEL_GROUP_MENU_ID,
            layout.MODEL_GROUP_FILTER_KEY,
        ),
    ):
        filter_shell.register_single_select_callbacks(
            app,
            value_id=value_id,
            toggle_id=toggle_id,
            menu_id=menu_id,
            filter_key=filter_key,
        )
    filter_shell.register_checkbox_dropdown_callbacks(
        app,
        checklist_id=layout.MODEL_ID,
        select_all_id=layout.MODEL_SELECT_ALL_ID,
        toggle_id=layout.MODEL_TOGGLE_ID,
        menu_id=layout.MODEL_MENU_ID,
    )

    @app.callback(
        Output(layout.RANGE_STORE_ID, "data"),
        Input({"type": filters.RANGE_WINDOW_ID, "key": ALL}, "value"),
        Input({"type": filters.RANGE_FROM_ID, "key": ALL}, "value"),
        Input({"type": filters.RANGE_TO_ID, "key": ALL}, "value"),
        State({"type": filters.RANGE_WINDOW_ID, "key": ALL}, "id"),
        State({"type": filters.RANGE_FROM_ID, "key": ALL}, "id"),
        State({"type": filters.RANGE_TO_ID, "key": ALL}, "id"),
        State({"type": filters.RANGE_FROM_ID, "key": ALL}, "options"),
        State(layout.RANGE_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_overview_range_store(
        window_values, from_values, to_values, window_ids, from_ids, to_ids, from_options_list, range_store,
    ):
        triggered = ctx.triggered_id
        if not triggered or triggered.get("key") != layout.RAG_TREND_RANGE_KEY:
            return no_update

        range_key = triggered["key"]
        range_store = dict(range_store or {})

        if triggered["type"] == filters.RANGE_WINDOW_ID:
            preset = window_values[window_ids.index(triggered)]
            from_idx = from_ids.index({"type": filters.RANGE_FROM_ID, "key": range_key})
            periods = [option["value"] for option in from_options_list[from_idx] if option["value"]]
            if preset == "all":
                range_store[range_key] = {"from": "", "to": ""}
            else:
                count = _RANGE_PRESET_COUNTS.get(preset)
                if not count or not periods:
                    return no_update
                range_store[range_key] = {"from": periods[max(0, len(periods) - count)], "to": periods[-1]}
        elif triggered["type"] in (filters.RANGE_FROM_ID, filters.RANGE_TO_ID):
            boundary = "from" if triggered["type"] == filters.RANGE_FROM_ID else "to"
            ids = from_ids if boundary == "from" else to_ids
            values = from_values if boundary == "from" else to_values
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

    @app.callback(
        Output(layout.MODEL_ID, "options"),
        Input(layout.MODEL_GROUP_ID, "value"),
    )
    def sync_overview_model_options(model_group):
        options = overview_filter_options(overview_rows, model_group or "All")
        model_values = [value for value in options["models"] if value != "All"]
        return _dropdown_options(model_values)

    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.PERIOD_ID, "value"),
        Input(layout.MODEL_GROUP_ID, "value"),
        Input(layout.MODEL_ID, "value"),
        Input(layout.SEGMENT_ID, "value"),
        Input(layout.RAG_TREND_METRIC_ID, "value"),
        Input(layout.RANGE_STORE_ID, "data"),
    )
    def update_overview_content(monitoring_period, model_group, model, segment, rag_trend_metric, range_store):
        return layout.render_overview_content(
            data,
            overview_rows,
            monitoring_period or "All",
            model_group or "All",
            model,
            segment or "All",
            rag_trend_metric or "Overall RAG",
            range_store or {},
        )
