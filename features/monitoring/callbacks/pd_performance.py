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

from ..ui import common as filter_shell
from ..ui.views import pd_performance as layout
from ....shared.ui import controls
from ....shared.theme import APP_THEME_ID
from ....shared.domain.calculations import PdFilterContext, ctx_store_keys, set_precomputed_metrics
from ....shared.registration import already_registered
from ..data_access import PD_PERFORMANCE_DATA
from ..services import data_service

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def _resolve_pd_scope(data: dict, applied: dict | None) -> tuple[PdFilterContext, str, str]:
    """Resolve (filter_ctx, reporting_cycle, monitoring_point) from the applied-filters store.

    Shared by the review-flow Save callback and the save-bar sync callback so both always agree on
    which portfolio-file row a read/write targets (the master render callback resolves this itself
    inline, since it also needs the cycle's observations/metrics_store alongside it).
    """
    from ....shared.repositories.filters_config import load_filter_config
    cfg = load_filter_config()
    default_cycle = cfg["reporting_cycles"][0]["value"] if cfg["reporting_cycles"] else "CCAR 2026"

    applied = applied or {}
    reporting_cycle = applied.get("reporting_cycle") or default_cycle
    cycle_data = (data.get("observations_by_cycle") or {}).get(reporting_cycle) or {}
    quarters = cycle_data.get("quarters") or data["quarters"]

    segment = applied.get("segment") or "all"
    models_value = applied.get("models") or ""
    if models_value:
        models = {models_value}
    elif segment == "all":
        models = {data["model_names"][0]} if data["model_names"] else set()
    else:
        models = set()
    monitoring_point = applied.get("monitoring_point") or (quarters[-1] if quarters else "")
    filter_ctx = PdFilterContext(
        quarters=quarters, models=models, segment=segment, monitoring_point=monitoring_point,
    )
    return filter_ctx, reporting_cycle, monitoring_point


def register_callbacks(app) -> None:
    """Register all PD Performance callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.pd_performance"):
        return

    data = PD_PERFORMANCE_DATA
    segment_labels = {"all": "All", **{value: value for value in data["segment_values"]}}

    # -----------------------------------------------------------------
    # Reporting Cycle -> Monitoring Point options
    # -----------------------------------------------------------------
    all_quarters_desc = sorted(data["quarters"], reverse=True)

    @app.callback(
        Output(controls.MONITORING_POINT_ID, "options"),
        Output(controls.MONITORING_POINT_ID, "value"),
        Input(controls.REPORTING_CYCLE_ID, "value"),
        State(controls.MONITORING_POINT_ID, "value"),
    )
    def sync_reporting_cycle_to_monitoring_point(cycle, current_mp):
        allowed = controls.REPORTING_CYCLE_QUARTERS.get(cycle)
        if allowed is None:
            quarters = all_quarters_desc
        else:
            quarters = list(allowed)
        options = [{"label": q, "value": q} for q in quarters]
        value = filter_shell.resolve_monitoring_point_value(quarters, current_mp)
        return options, value

    # -----------------------------------------------------------------
    # Portfolio segment <-> specific models mutual exclusivity
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.PORTFOLIO_SEGMENT_ID, "disabled"),
        Output(controls.PORTFOLIO_SEGMENT_TOGGLE_ID, "disabled"),
        Output(controls.MODELS_TOGGLE_ID, "disabled"),
        Input(controls.PORTFOLIO_SEGMENT_ID, "value"),
        Input(controls.MODELS_ID, "value"),
    )
    def sync_pd_segment_model_exclusivity(segment, model):
        has_segment_selection = segment != "all"
        has_specific_model_selection = model not in (None, "")

        return (
            has_specific_model_selection,  # disable Segment when a specific model is chosen
            has_specific_model_selection,  # ...and its toggle
            has_segment_selection,         # disable Models when a segment is chosen
        )

    # -----------------------------------------------------------------
    # Single-select dropdown open/close toggles
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.MONITORING_POINT_MENU_ID, "className"),
        Input(controls.MONITORING_POINT_TOGGLE_ID, "n_clicks"),
        State(controls.MONITORING_POINT_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_monitoring_point_menu(_n_clicks, current_class):
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu single-select-menu"
        return "checkbox-dropdown-menu single-select-menu open"

    @app.callback(
        Output(controls.PORTFOLIO_SEGMENT_MENU_ID, "className"),
        Input(controls.PORTFOLIO_SEGMENT_TOGGLE_ID, "n_clicks"),
        State(controls.PORTFOLIO_SEGMENT_MENU_ID, "className"),
        State(controls.PORTFOLIO_SEGMENT_TOGGLE_ID, "disabled"),
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
        Output(controls.MONITORING_POINT_ID, "value", allow_duplicate=True),
        Output(controls.MONITORING_POINT_MENU_ID, "className", allow_duplicate=True),
        Input({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "monitoring-point", "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_monitoring_point(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        value = triggered["value"]
        return value, "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(controls.MONITORING_POINT_TOGGLE_ID, "children"),
        Output(controls.MONITORING_POINT_MENU_ID, "children"),
        Input(controls.MONITORING_POINT_ID, "value"),
        Input(controls.MONITORING_POINT_ID, "options"),
    )
    def sync_monitoring_point_shell(value, options):
        return filter_shell.build_single_select_shell(
            options=options,
            value=value,
            filter_key="monitoring-point",
        )

    @app.callback(
        Output(controls.PORTFOLIO_SEGMENT_ID, "value"),
        Output(controls.PORTFOLIO_SEGMENT_MENU_ID, "className", allow_duplicate=True),
        Input({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "portfolio-segment", "value": ALL}, "n_clicks"),
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
        Output(controls.PORTFOLIO_SEGMENT_TOGGLE_ID, "children"),
        Output({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "portfolio-segment", "value": ALL}, "className"),
        Input(controls.PORTFOLIO_SEGMENT_ID, "value"),
        State({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "portfolio-segment", "value": ALL}, "id"),
    )
    def sync_segment_shell(value, option_ids):
        label = segment_labels.get(value, value or "Select")
        classes = [
            "single-select-option is-selected" if option_id["value"] == value else "single-select-option"
            for option_id in option_ids
        ]
        return label, classes

    # Reporting Cycle toggle
    @app.callback(
        Output(controls.REPORTING_CYCLE_MENU_ID, "className"),
        Input(controls.REPORTING_CYCLE_TOGGLE_ID, "n_clicks"),
        State(controls.REPORTING_CYCLE_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_reporting_cycle_menu(_n_clicks, current_class):
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu single-select-menu"
        return "checkbox-dropdown-menu single-select-menu open"

    @app.callback(
        Output(controls.REPORTING_CYCLE_ID, "value"),
        Output(controls.REPORTING_CYCLE_MENU_ID, "className", allow_duplicate=True),
        Input({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "reporting-cycle", "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_reporting_cycle(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(controls.REPORTING_CYCLE_TOGGLE_ID, "children"),
        Output({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "reporting-cycle", "value": ALL}, "className"),
        Input(controls.REPORTING_CYCLE_ID, "value"),
        State({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "reporting-cycle", "value": ALL}, "id"),
    )
    def sync_reporting_cycle_shell(value, option_ids):
        classes = [
            "single-select-option is-selected" if option_id["value"] == value else "single-select-option"
            for option_id in option_ids
        ]
        return value or "Select", classes

    # Scenario toggle
    scenario_labels = {"intsevere": "intsevere", "baseline": "baseline", "other": "other"}

    @app.callback(
        Output(controls.SCENARIO_MENU_ID, "className"),
        Input(controls.SCENARIO_TOGGLE_ID, "n_clicks"),
        State(controls.SCENARIO_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_scenario_menu(_n_clicks, current_class):
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu single-select-menu"
        return "checkbox-dropdown-menu single-select-menu open"

    @app.callback(
        Output(controls.SCENARIO_ID, "value"),
        Output(controls.SCENARIO_MENU_ID, "className", allow_duplicate=True),
        Input({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "scenario", "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_scenario(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(controls.SCENARIO_TOGGLE_ID, "children"),
        Output({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "scenario", "value": ALL}, "className"),
        Input(controls.SCENARIO_ID, "value"),
        State({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "scenario", "value": ALL}, "id"),
    )
    def sync_scenario_shell(value, option_ids):
        label = scenario_labels.get(value, value or "Select")
        classes = [
            "single-select-option is-selected" if option_id["value"] == value else "single-select-option"
            for option_id in option_ids
        ]
        return label, classes

    # Models toggle
    @app.callback(
        Output(controls.MODELS_MENU_ID, "className"),
        Input(controls.MODELS_TOGGLE_ID, "n_clicks"),
        State(controls.MODELS_MENU_ID, "className"),
        State(controls.MODELS_TOGGLE_ID, "disabled"),
        prevent_initial_call=True,
    )
    def toggle_models_menu(_n_clicks, current_class, is_disabled):
        if is_disabled:
            return "checkbox-dropdown-menu single-select-menu"
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu single-select-menu"
        return "checkbox-dropdown-menu single-select-menu open"

    @app.callback(
        Output(controls.MODELS_ID, "value"),
        Output(controls.MODELS_MENU_ID, "className", allow_duplicate=True),
        Input({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "specific-models", "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_model(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    model_labels = {"": "Select model", **{name: name for name in data["model_names"]}}

    @app.callback(
        Output(controls.MODELS_TOGGLE_ID, "children"),
        Output({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "specific-models", "value": ALL}, "className"),
        Input(controls.MODELS_ID, "value"),
        State({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": "specific-models", "value": ALL}, "id"),
    )
    def sync_models_shell(value, option_ids):
        label = model_labels.get(value, value or "Select")
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
    def update_pd_range_store(
        window_values, from_values, to_values, window_ids, from_ids, to_ids, from_options_list, range_store,
    ):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update

        range_key = triggered["key"]
        range_store = dict(range_store or {})

        if triggered["type"] == controls.RANGE_WINDOW_ID:
            preset = window_values[window_ids.index(triggered)]
            from_idx = from_ids.index({"type": controls.RANGE_FROM_ID, "key": range_key})
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
        Input({"type": controls.TREND_HORIZON_ID, "key": ALL}, "value"),
        State({"type": controls.TREND_HORIZON_ID, "key": ALL}, "id"),
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
    # Scenario Ranking selector -> pd-scenario-ranking-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.SCENARIO_RANKING_STORE_ID, "data"),
        Input(layout.SCENARIO_RANKING_FILTER_ID, "value"),
        prevent_initial_call=True,
    )
    def update_pd_scenario_ranking_store(selected_scenarios):
        return {"scenarios": selected_scenarios or []}

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data", allow_duplicate=True),
        Output(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data", allow_duplicate=True),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(controls.MONITORING_POINT_ID, "value"),
        State(controls.PORTFOLIO_SEGMENT_ID, "value"),
        State(controls.MODELS_ID, "value"),
        State(controls.REPORTING_CYCLE_ID, "value"),
        State(controls.SCENARIO_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_pd_filters(_n_clicks, monitoring_point, segment, models, reporting_cycle, scenario):
        """Snapshot the current top filters so the content renders only on Apply.

        Also discards the scope-specific review-flow state: the unsaved
        reviewer sign-off draft, any staged (not-yet-saved) RAG picks, and the
        last save-status message. All three describe the scope that was on
        screen before the click, so carrying them across an Apply would show
        them against a different model/segment/quarter. Clearing them here
        (same callback as the applied-filters snapshot) guarantees the
        re-render reads the cleared values and falls back to the new scope's
        saved values from the portfolio file.

        Guard against spurious fires when the page is (re)inserted by the router:
        only snapshot once the button has actually been clicked.
        """
        if not _n_clicks:
            return no_update, no_update, no_update, no_update
        return {
            "monitoring_point": monitoring_point,
            "segment": segment,
            "models": models,
            "reporting_cycle": reporting_cycle,
            "scenario": scenario,
        }, "", {}, ""

    # -----------------------------------------------------------------
    # Master re-render: applied store + per-chart stores -> pd-performance-content
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.RANGE_STORE_ID, "data"),
        Input(layout.TREND_HORIZON_STORE_ID, "data"),
        Input(layout.MEV_FILTER_STORE_ID, "data"),
        Input(layout.SCENARIO_RANKING_STORE_ID, "data"),
        Input(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        Input(APP_THEME_ID, "value"),
        State(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        State(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def render_pd_performance_content(
        applied, range_store, trend_horizon_store, mev_filter_store, scenario_ranking_store,
        review_flow_pending_edits, theme_value, conclusions_notes, review_flow_save_status,
    ):
        # Until the user clicks "Apply filters", keep the getting-started guide
        # that ``page_layout`` rendered into the content container.
        if not applied:
            return layout.build_pd_apply_prompt()

        from ....shared.repositories.filters_config import load_filter_config
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"] if cfg["reporting_cycles"] else "CCAR 2026"
        default_scenario = cfg["scenarios"][0]["value"] if cfg["scenarios"] else "intsevere"

        applied = applied or {}
        reporting_cycle = applied.get("reporting_cycle") or default_cycle
        scenario = applied.get("scenario") or default_scenario

        cycle_data = (data.get("observations_by_cycle") or {}).get(reporting_cycle)
        if cycle_data:
            quarters = cycle_data["quarters"]
            performance_observations = cycle_data["performance_observations"]
            rating_migration_observations = cycle_data["rating_migration_observations"]
            metrics_store = cycle_data.get("metrics_store")
        else:
            quarters = data["quarters"]
            performance_observations = data["performance_observations"]
            rating_migration_observations = data["rating_migration_observations"]
            metrics_store = None

        # The PD Performance tab reads every metric straight from the workbook.
        set_precomputed_metrics(metrics_store)

        render_data = {**data, "quarters": quarters, "performance_observations": performance_observations, "rating_migration_observations": rating_migration_observations}

        monitoring_point = applied.get("monitoring_point") or (quarters[-1] if quarters else "")
        segment = applied.get("segment") or "all"
        models_value = applied.get("models") or ""
        if models_value:
            models = {models_value}
        elif segment == "all":
            models = {data["model_names"][0]} if data["model_names"] else set()
        else:
            models = set()
        filter_ctx = PdFilterContext(
            quarters=quarters,
            models=models,
            segment=segment,
            monitoring_point=monitoring_point,
        )
        return layout.render_pd_performance_content(
            render_data, filter_ctx, range_store or {}, trend_horizon_store or {}, mev_filter_store or {},
            scenario_ranking_store or {},
            theme_value=theme_value, reporting_cycle=reporting_cycle, scenario=scenario,
            conclusions_notes=conclusions_notes or "",
            review_flow_pending_edits=review_flow_pending_edits or {},
            review_flow_save_status=review_flow_save_status or "",
        )

    # -----------------------------------------------------------------
    # Reviewer conclusions textarea -> pd-conclusions-notes-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        Input(layout.CONCLUSIONS_NOTES_ID, "value"),
        prevent_initial_call=True,
    )
    def save_pd_conclusions_notes(value):
        return value or ""

    # -----------------------------------------------------------------
    # Review-flow RAG pickers (Post Subjective Review / Pre-/Post-Mitigation)
    # -> pd-review-flow-pending-store (staged only, not yet written to disk)
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        Input({"type": layout.PD_REVIEW_FLOW_OPTION_ID, "field": ALL}, "value"),
        State(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def stage_pd_review_flow_rag(_values, pending):
        # These dropdowns live inside the re-rendered content area, so they get torn down and
        # recreated on every master re-render -- which, per a Dash quirk, fires this callback once as
        # a "component just appeared" reconciliation even with prevent_initial_call=True. They always
        # mount with value=None (a "Change RAG to..." action, not a live display), so that
        # reconciliation firing always reports a None value and is caught by the guard below; only a
        # genuine pick ever sets a real Green/Amber/Red value.
        triggered = ctx.triggered_id
        if not triggered or not ctx.triggered:
            return no_update
        new_value = ctx.triggered[0]["value"]
        if not new_value:
            return no_update
        pending = dict(pending or {})
        pending[triggered["field"]] = new_value
        return pending

    # -----------------------------------------------------------------
    # Save staged review-flow RAG edits -> portfolio.xlsx (source of truth),
    # then clear the pending store so the master re-render above shows the
    # newly-saved values as "current" instead of "staged".
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        Input(layout.PD_REVIEW_FLOW_SAVE_ID, "n_clicks"),
        State(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def save_pd_review_flow_rag_changes(n_clicks, pending, applied, conclusions_notes):
        # Same dynamic-mount quirk as the picker above: the Save button only exists once there's a
        # pending edit or commentary change, so it "just appeared" at least once and could fire
        # without a real click.
        if not n_clicks:
            return no_update, no_update

        filter_ctx, reporting_cycle, monitoring_point = _resolve_pd_scope(data, applied)
        level, value = ctx_store_keys(filter_ctx)

        saved_fields = []
        for field, new_value in (pending or {}).items():
            if new_value not in ("Green", "Amber", "Red"):
                continue
            column = layout.PD_REVIEW_FLOW_COLUMNS.get(field)
            if not column:
                continue
            ok = data_service.save_pd_review_flow_rag(
                data, reporting_cycle, level, value, monitoring_point, column, new_value,
            )
            if ok:
                saved_fields.append(field)

        saved_commentary = layout.pd_reviewer_commentary(filter_ctx, monitoring_point)
        if (conclusions_notes or "") != (saved_commentary or ""):
            ok = data_service.save_pd_review_flow_rag(
                data, reporting_cycle, level, value, monitoring_point,
                layout.REVIEWER_COMMENTARY_COLUMN, conclusions_notes or "",
            )
            if ok:
                saved_fields.append("reviewer_commentary")

        if not saved_fields:
            return no_update, (
                "Could not save -- no matching rows were found in the portfolio file for the current scope."
            )

        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        count = len(saved_fields)
        return {}, f"Saved {count} change{'s' if count != 1 else ''} to portfolio.xlsx at {timestamp}."

    # -----------------------------------------------------------------
    # Keep the "Unsaved changes" bar in sync with commentary keystrokes without
    # rebuilding the whole tab (which would drop the textarea's cursor/focus).
    # RAG picks already rebuild the whole tab (layout.PD_REVIEW_FLOW_PENDING_STORE_ID
    # is an Input there), so this callback only needs to add live text typing to the mix.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.PD_REVIEW_FLOW_SAVE_BAR_ID, "children"),
        Input(layout.CONCLUSIONS_NOTES_ID, "value"),
        Input(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def sync_pd_review_flow_save_bar(conclusions_notes, pending, applied, save_status):
        filter_ctx, _reporting_cycle, monitoring_point = _resolve_pd_scope(data, applied)
        review_flow_rags = layout.pd_review_flow_rags(filter_ctx, monitoring_point)
        saved_commentary = layout.pd_reviewer_commentary(filter_ctx, monitoring_point)
        commentary_changed = (conclusions_notes or "") != (saved_commentary or "")
        save_bar = layout.build_pd_review_flow_save_bar(
            pending or {}, review_flow_rags, save_status, commentary_changed,
        )
        return [save_bar] if save_bar is not None else []
