"""Callbacks wiring the PD Performance dashboard's interactive state.

The original page mutated module-level globals (``MONITORING_POINT``,
``MONITORING_MODELS``, ``PD_TIME_RANGES``, ``PD_CALIBRATION_TREND_HORIZON``,
``PD_MEV_FILTER_*``, ...) and called ``renderPdModels()`` after every change.
Here that state lives in the global filter controls plus three
``dcc.Store`` components (:data:`layout.RANGE_STORE_ID`,
:data:`layout.TREND_HORIZON_STORE_ID`, :data:`layout.MEV_FILTER_STORE_ID``),
and a single callback re-runs :func:`layout.render_pd_performance_content`
whenever any of it changes.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from . import page as layout
from .....components import filters
from .....data.analytics.calculations import PdFilterContext
from .....shared.registration import already_registered
from ...data_access import PD_PERFORMANCE_DATA

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def register_callbacks(app) -> None:
    """Register all PD Performance callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.pd_performance"):
        return

    data = PD_PERFORMANCE_DATA
    monitoring_point_labels = {quarter: quarter for quarter in sorted(data["quarters"], reverse=True)}
    segment_labels = {"all": "All", **{value: value for value in data["segment_values"]}}

    # -----------------------------------------------------------------
    # Models checklist <-> "All" select-all checkbox
    # -----------------------------------------------------------------
    @app.callback(
        Output(filters.MODELS_ID, "value"),
        Output(filters.MODELS_SELECT_ALL_ID, "value"),
        Input(filters.MODELS_SELECT_ALL_ID, "value"),
        Input(filters.MODELS_ID, "value"),
        State(filters.MODELS_ID, "options"),
        prevent_initial_call=True,
    )
    def sync_pd_model_selection(select_all_value, models_value, models_options):
        all_names = [option["value"] for option in models_options]
        if ctx.triggered_id == filters.MODELS_SELECT_ALL_ID:
            if "all" in (select_all_value or []):
                return all_names, no_update
            return [], no_update
        select_all = ["all"] if all_names and set(models_value or []) == set(all_names) else []
        return no_update, select_all

    # -----------------------------------------------------------------
    # Portfolio segment <-> specific models mutual exclusivity
    # (port of syncMonitoringFilterControls's isPerformanceTab branch)
    # -----------------------------------------------------------------
    @app.callback(
        Output(filters.PORTFOLIO_SEGMENT_ID, "disabled"),
        Output(filters.PORTFOLIO_SEGMENT_TOGGLE_ID, "disabled"),
        Output(filters.MODELS_ID, "options"),
        Output(filters.MODELS_SELECT_ALL_ID, "options"),
        Output(filters.MODELS_TOGGLE_ID, "children"),
        Output(filters.MODELS_TOGGLE_ID, "disabled"),
        Output(filters.FILTER_HELP_ID, "children"),
        Input(filters.PORTFOLIO_SEGMENT_ID, "value"),
        Input(filters.MODELS_ID, "value"),
        State(filters.MODELS_ID, "options"),
        State(filters.MODELS_SELECT_ALL_ID, "options"),
    )
    def sync_pd_segment_model_exclusivity(segment, models_value, models_options, select_all_options):
        all_names = [option["value"] for option in models_options]
        models_value = models_value or []
        has_segment_selection = segment != "all"
        has_specific_model_selection = 0 < len(models_value) < len(all_names)

        new_models_options = [{**option, "disabled": has_segment_selection} for option in models_options]
        new_select_all_options = [{**option, "disabled": has_segment_selection} for option in select_all_options]

        if has_segment_selection:
            toggle_label = "Disabled while Segment is selected"
        elif not models_value:
            toggle_label = "Select models"
        elif len(models_value) == len(all_names):
            toggle_label = "All models"
        elif len(models_value) == 1:
            toggle_label = models_value[0]
        else:
            toggle_label = f"{len(models_value)} models selected"

        if has_segment_selection:
            help_text = "Segment filtering is active. Reset Segment to All to select specific models."
        elif has_specific_model_selection:
            help_text = "Specific Models filtering is active. Reset models to All to select a portfolio segment."
        else:
            help_text = "Choose a portfolio segment or specific models. These filters cannot be combined."

        return (
            has_specific_model_selection,
            has_specific_model_selection,
            new_models_options,
            new_select_all_options,
            toggle_label,
            has_segment_selection,
            help_text,
        )

    # -----------------------------------------------------------------
    # Checkbox-dropdown open/close toggles
    # -----------------------------------------------------------------
    @app.callback(
        Output(filters.MODELS_MENU_ID, "className"),
        Input(filters.MODELS_TOGGLE_ID, "n_clicks"),
        State(filters.MODELS_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_pd_models_menu(_n_clicks, current_class):
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu"
        return "checkbox-dropdown-menu open"

    # -----------------------------------------------------------------
    # Single-select dropdown open/close toggles
    # -----------------------------------------------------------------
    @app.callback(
        Output(filters.MONITORING_POINT_MENU_ID, "className"),
        Input(filters.MONITORING_POINT_TOGGLE_ID, "n_clicks"),
        State(filters.MONITORING_POINT_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_monitoring_point_menu(_n_clicks, current_class):
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu single-select-menu"
        return "checkbox-dropdown-menu single-select-menu open"

    @app.callback(
        Output(filters.PORTFOLIO_SEGMENT_MENU_ID, "className"),
        Input(filters.PORTFOLIO_SEGMENT_TOGGLE_ID, "n_clicks"),
        State(filters.PORTFOLIO_SEGMENT_MENU_ID, "className"),
        State(filters.PORTFOLIO_SEGMENT_TOGGLE_ID, "disabled"),
        prevent_initial_call=True,
    )
    def toggle_segment_menu(_n_clicks, current_class, is_disabled):
        if is_disabled:
            return "checkbox-dropdown-menu single-select-menu"
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu single-select-menu"
        return "checkbox-dropdown-menu single-select-menu open"

    # -----------------------------------------------------------------
    # Single-select dropdown option clicks -> value + close
    # Each filter_key routes to its own hidden dcc.Dropdown value.
    # -----------------------------------------------------------------
    @app.callback(
        Output(filters.MONITORING_POINT_ID, "value"),
        Output(filters.MONITORING_POINT_MENU_ID, "className", allow_duplicate=True),
        Input({"type": filters.SINGLE_SELECT_OPTION_ID, "filter": "monitoring-point", "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_monitoring_point(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(filters.PORTFOLIO_SEGMENT_ID, "value"),
        Output(filters.PORTFOLIO_SEGMENT_MENU_ID, "className", allow_duplicate=True),
        Input({"type": filters.SINGLE_SELECT_OPTION_ID, "filter": "portfolio-segment", "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_segment(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    # -----------------------------------------------------------------
    # Single-select dropdown shell sync (toggle label + option highlights)
    # -----------------------------------------------------------------
    @app.callback(
        Output(filters.MONITORING_POINT_TOGGLE_ID, "children"),
        Output({"type": filters.SINGLE_SELECT_OPTION_ID, "filter": "monitoring-point", "value": ALL}, "className"),
        Input(filters.MONITORING_POINT_ID, "value"),
        State({"type": filters.SINGLE_SELECT_OPTION_ID, "filter": "monitoring-point", "value": ALL}, "id"),
    )
    def sync_monitoring_point_shell(value, option_ids):
        label = monitoring_point_labels.get(value, value or "Select")
        classes = [
            "single-select-option is-selected" if option_id["value"] == value else "single-select-option"
            for option_id in option_ids
        ]
        return label, classes

    @app.callback(
        Output(filters.PORTFOLIO_SEGMENT_TOGGLE_ID, "children"),
        Output({"type": filters.SINGLE_SELECT_OPTION_ID, "filter": "portfolio-segment", "value": ALL}, "className"),
        Input(filters.PORTFOLIO_SEGMENT_ID, "value"),
        State({"type": filters.SINGLE_SELECT_OPTION_ID, "filter": "portfolio-segment", "value": ALL}, "id"),
    )
    def sync_segment_shell(value, option_ids):
        label = segment_labels.get(value, value or "Select")
        classes = [
            "single-select-option is-selected" if option_id["value"] == value else "single-select-option"
            for option_id in option_ids
        ]
        return label, classes

    # -----------------------------------------------------------------
    # Per-chart range controls (Window / From / To) -> pd-range-store
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
    def update_pd_range_store(
        window_values, from_values, to_values, window_ids, from_ids, to_ids, from_options_list, range_store,
    ):
        triggered = ctx.triggered_id
        if not triggered:
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

    # -----------------------------------------------------------------
    # Calibration / discrimination trend PD-horizon controls -> pd-trend-horizon-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.TREND_HORIZON_STORE_ID, "data"),
        Input({"type": filters.TREND_HORIZON_ID, "key": ALL}, "value"),
        State({"type": filters.TREND_HORIZON_ID, "key": ALL}, "id"),
        State(layout.TREND_HORIZON_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_pd_trend_horizon_store(values, ids, trend_horizon_store):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update

        group = layout.TREND_HORIZON_GROUPS.get(triggered["key"])
        value = values[ids.index(triggered)]
        if not group or value not in ("1y", "2y"):
            return no_update

        trend_horizon_store = dict(trend_horizon_store or {})
        trend_horizon_store[group] = value
        return trend_horizon_store

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(filters.MONITORING_POINT_ID, "value"),
        State(filters.PORTFOLIO_SEGMENT_ID, "value"),
        State(filters.MODELS_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_pd_filters(_n_clicks, monitoring_point, segment, models):
        """Snapshot the current top filters so the content renders only on Apply."""
        return {
            "monitoring_point": monitoring_point,
            "segment": segment,
            "models": models,
        }

    # -----------------------------------------------------------------
    # Master re-render: applied store + per-chart stores -> pd-performance-content
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.RANGE_STORE_ID, "data"),
        Input(layout.TREND_HORIZON_STORE_ID, "data"),
        Input(layout.MEV_FILTER_STORE_ID, "data"),
        Input(layout.APP_THEME_ID, "value"),
    )
    def render_pd_performance_content(
        applied, range_store, trend_horizon_store, mev_filter_store, theme_value,
    ):
        applied = applied or {}
        monitoring_point = applied.get("monitoring_point") or data.get("latest_quarter") or ""
        segment = applied.get("segment") or "all"
        models = applied.get("models") or data["model_names"]
        filter_ctx = PdFilterContext(
            quarters=data["quarters"],
            models=set(models),
            segment=segment,
            monitoring_point=monitoring_point,
        )
        return layout.render_pd_performance_content(
            data, filter_ctx, range_store or {}, trend_horizon_store or {}, mev_filter_store or {},
            theme_value=theme_value,
        )
