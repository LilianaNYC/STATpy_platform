"""Callbacks for the EAD Performance page."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import ead_performance as layout
from ....components import filters
from ..domain.ead import (
    get_ead_monitoring_point_options,
    get_ead_segments_for_model,
    resolve_ead_segment,
)
from ....shared.registration import already_registered
from ..data_access import PD_PERFORMANCE_DATA

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def _dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def register_callbacks(app) -> None:
    """Register all EAD Performance callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.ead_performance"):
        return

    data = PD_PERFORMANCE_DATA

    for value_id, toggle_id, menu_id, filter_key in (
        (layout.REPORTING_CYCLE_ID, layout.REPORTING_CYCLE_TOGGLE_ID, layout.REPORTING_CYCLE_MENU_ID, layout.REPORTING_CYCLE_FILTER_KEY),
        (layout.SCENARIO_ID, layout.SCENARIO_TOGGLE_ID, layout.SCENARIO_MENU_ID, layout.SCENARIO_FILTER_KEY),
        (layout.MONITORING_POINT_DROPDOWN_ID, layout.MONITORING_POINT_TOGGLE_ID, layout.MONITORING_POINT_MENU_ID, layout.MONITORING_POINT_FILTER_KEY),
        (layout.SEGMENT_DROPDOWN_ID, layout.SEGMENT_TOGGLE_ID, layout.SEGMENT_MENU_ID, layout.SEGMENT_FILTER_KEY),
        (layout.MODEL_DROPDOWN_ID, layout.MODEL_TOGGLE_ID, layout.MODEL_MENU_ID, layout.MODEL_FILTER_KEY),
    ):
        filter_shell.register_single_select_callbacks(
            app,
            value_id=value_id,
            toggle_id=toggle_id,
            menu_id=menu_id,
            filter_key=filter_key,
        )

    def _install_ead_store(reporting_cycle):
        from ..domain.ead import set_ead_metrics
        cycle_data = (data.get("ead_observations_by_cycle") or {}).get(reporting_cycle)
        if cycle_data:
            set_ead_metrics(cycle_data.get("metrics_store"), cycle_data.get("quarters"))
        else:
            set_ead_metrics(None, [])
        return cycle_data

    # -----------------------------------------------------------------
    # Range-window store (calibration / discrimination RAG trend ranges)
    # -----------------------------------------------------------------
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
        allow_duplicate=True,
    )
    def update_ead_range_store(
        window_values,
        from_values,
        to_values,
        window_ids,
        from_ids,
        to_ids,
        from_options_list,
        range_store,
    ):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update

        range_key = triggered["key"]
        range_store = dict(range_store or {})

        if triggered["type"] == filters.RANGE_WINDOW_ID:
            preset = window_values[window_ids.index(triggered)]
            from_id = {"type": filters.RANGE_FROM_ID, "key": range_key}
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
        elif triggered["type"] in (filters.RANGE_FROM_ID, filters.RANGE_TO_ID):
            boundary = "from" if triggered["type"] == filters.RANGE_FROM_ID else "to"
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
    # Segment dropdown syncs with model selection
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.SEGMENT_DROPDOWN_ID, "options"),
        Output(layout.SEGMENT_DROPDOWN_ID, "value"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
        Input(layout.SEGMENT_DROPDOWN_ID, "value"),
    )
    def sync_ead_segment_dropdown(selected_model, selected_segment):
        segments = get_ead_segments_for_model(data, selected_model)
        value = resolve_ead_segment(data, selected_model, selected_segment)
        return _dropdown_options(segments), value

    # -----------------------------------------------------------------
    # Monitoring-point dropdown syncs with reporting cycle
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "options"),
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
    )
    def sync_ead_monitoring_point_dropdown(reporting_cycle, selected_monitoring_point):
        options = filters.REPORTING_CYCLE_QUARTERS.get(reporting_cycle, [])
        value = selected_monitoring_point if selected_monitoring_point in options else (options[0] if options else "")
        return _dropdown_options(options), value

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.SCENARIO_ID, "value"),
        State(layout.MODEL_DROPDOWN_ID, "value"),
        State(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_ead_filters(_n_clicks, reporting_cycle, scenario, selected_model, selected_segment, selected_monitoring_point):
        if not _n_clicks:
            return no_update
        return {
            "reporting_cycle": reporting_cycle,
            "scenario": scenario,
            "model": selected_model,
            "segment": selected_segment,
            "monitoring_point": selected_monitoring_point,
        }

    # -----------------------------------------------------------------
    # Master re-render: applied store + range store -> ead-dashboard-content
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.RANGE_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def render_ead_content(applied, range_store):
        if not applied:
            return layout.build_ead_apply_prompt()

        from ....data.monitoring.filters_config import load_filter_config
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"] if cfg["reporting_cycles"] else "CCAR 2026"
        default_scenario = cfg["scenarios"][0]["value"] if cfg["scenarios"] else "intsevere"

        reporting_cycle = applied.get("reporting_cycle") or default_cycle
        scenario = applied.get("scenario") or default_scenario

        _install_ead_store(reporting_cycle)

        return layout.render_ead_performance_content(
            data,
            applied.get("model"),
            applied.get("segment"),
            applied.get("monitoring_point"),
            range_store or {},
            reporting_cycle=reporting_cycle,
            scenario=scenario,
        )
