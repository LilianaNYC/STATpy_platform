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
from ....shared.theme import APP_THEME_ID, URL_ID
from ....shared.domain.calculations import PdFilterContext, ctx_store_keys, set_precomputed_metrics
from ....shared.domain.mev_range import model_field_values, models_matching
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
    pd_model_segments = data.get("pd_model_segments") or {}
    pd_model_segment_cycles = data.get("pd_model_segment_cycles") or {}
    mev_catalog = data.get("mev_catalog") or {}
    all_pd_segments = sorted({segment for segments in pd_model_segments.values() for segment in segments})

    mev_scenarios_by_cycle = data.get("mev_scenarios_by_cycle") or {}

    from ....shared.repositories.filters_config import load_filter_config as _load_filter_config
    _cfg = _load_filter_config()
    _cfg_cycle_options = [{"label": c["label"], "value": c["value"]} for c in _cfg["reporting_cycles"]]
    _cfg_scenario_options = [{"label": s["label"], "value": s["value"]} for s in _cfg["scenarios"]]

    def _narrow_pd_cycle_options(cycles: list[str] | None) -> list[dict[str, str]]:
        if cycles is None:
            return _cfg_cycle_options
        allowed = set(cycles)
        narrowed = [option for option in _cfg_cycle_options if option["value"] in allowed]
        return narrowed or _cfg_cycle_options

    # -----------------------------------------------------------------
    # Region, Portfolio, Model Group: brand new filters, registered through
    # the shared single-select machinery (open/close, click-to-value, and
    # menu-rebuild-on-options-change all come for free -- unlike Model/
    # Segment above, there's no legacy hand-rolled callback set to conflict
    # with here).
    # -----------------------------------------------------------------
    for value_id, toggle_id, menu_id, filter_key in (
        (controls.REGION_ID, controls.REGION_TOGGLE_ID, controls.REGION_MENU_ID, "region"),
        (controls.PORTFOLIO_ID, controls.PORTFOLIO_TOGGLE_ID, controls.PORTFOLIO_MENU_ID, "portfolio"),
        (controls.MODEL_GROUP_ID, controls.MODEL_GROUP_TOGGLE_ID, controls.MODEL_GROUP_MENU_ID, "model-group"),
    ):
        filter_shell.register_single_select_callbacks(
            app, value_id=value_id, toggle_id=toggle_id, menu_id=menu_id, filter_key=filter_key,
        )

    @app.callback(
        Output(controls.PORTFOLIO_ID, "options"),
        Output(controls.PORTFOLIO_ID, "value"),
        Input(controls.REGION_ID, "value"),
        State(controls.PORTFOLIO_ID, "value"),
    )
    def sync_pd_region_to_portfolio_options(region, current_portfolio):
        matches = models_matching(mev_catalog, "PD", region, None, data["model_names"])
        portfolios = model_field_values(mev_catalog, "portfolio", matches)
        options = [{"label": "All", "value": "All"}] + [{"label": p, "value": p} for p in portfolios]
        value = current_portfolio if current_portfolio in portfolios or current_portfolio == "All" else "All"
        return options, value

    @app.callback(
        Output(controls.MODELS_ID, "options"),
        Output(controls.MODELS_ID, "value"),
        Input(controls.REGION_ID, "value"),
        Input(controls.PORTFOLIO_ID, "value"),
        State(controls.MODELS_ID, "value"),
    )
    def sync_pd_region_portfolio_to_model_options(region, portfolio, current_model):
        matches = models_matching(mev_catalog, "PD", region, portfolio, data["model_names"])
        options = [{"label": "Select model", "value": ""}] + [{"label": m, "value": m} for m in matches]
        value = current_model if current_model in matches else ""
        return options, value

    # -----------------------------------------------------------------
    # Discard unsaved review-flow state whenever the PD page is (re)entered.
    #
    # Unlike LGD/EAD (whose stores are page-local and reset on navigation), the
    # PD stores live in the shared app shell, so a staged-but-unsaved RAG pick,
    # a draft sign-off, or a stale save-status message would otherwise survive
    # navigating away and re-appear on return. Clearing them on entry means
    # leaving the page always drops staged edits -- only saved (factual) values
    # are shown when you come back.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data", allow_duplicate=True),
        Output(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data", allow_duplicate=True),
        Input(URL_ID, "pathname"),
        prevent_initial_call=True,
    )
    def discard_pd_staged_state_on_entry(pathname):
        # Only reset when the PD page itself is on screen (its path is "/"), so
        # the master re-render that this triggers has a live content container to
        # write into rather than firing against a page that has been swapped out.
        if pathname != "/":
            return no_update, no_update, no_update
        return {}, "", ""

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
            # Latest-first. dcc.Dropdown resets its value to the first option when
            # the options list changes (as it does here when the reporting cycle
            # rebuilds the monitoring-point list on load), so ordering latest-first
            # makes that reset land on the latest quarter -- keeping the hidden
            # value in sync with the "latest" default the toggle shows, instead of
            # silently snapping back to the earliest quarter.
            quarters = sorted(allowed, reverse=True)
        options = [{"label": q, "value": q} for q in quarters]
        value = current_mp if current_mp in quarters else (quarters[0] if quarters else "")
        return options, value

    # -----------------------------------------------------------------
    # Segment is never disabled/blocked by Model: with a model chosen, its
    # options narrow to that model's own real segments (unchanged). With no
    # model chosen, Segment still works -- it shows every segment across all
    # PD models plus a "Select segment" placeholder (mirroring Model's own
    # "Select model" placeholder) so Segment can be Browse/picked first.
    # Models is never disabled by Segment either way.
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.PORTFOLIO_SEGMENT_ID, "options"),
        Output(controls.PORTFOLIO_SEGMENT_ID, "value"),
        Input(controls.MODELS_ID, "value"),
        State(controls.PORTFOLIO_SEGMENT_ID, "value"),
    )
    def sync_pd_model_to_segment_options(model, current_segment):
        if model:
            segments = pd_model_segments.get(model, [])
            options = [{"label": "All", "value": "all"}] + [{"label": s, "value": s} for s in segments]
            value = current_segment if current_segment in segments else "all"
        else:
            options = (
                [{"label": "Select segment", "value": ""}, {"label": "All", "value": "all"}]
                + [{"label": s, "value": s} for s in all_pd_segments]
            )
            value = current_segment if current_segment in all_pd_segments or current_segment == "all" else ""
        return options, value

    # -----------------------------------------------------------------
    # Model Use Case / Cycle narrows to whichever reporting cycles actually
    # have data for the selected Model/Segment population -- e.g. PD Model C
    # only has CCAR 2025/2026 rows (no BAU 2025Q1), and PD Model B's Cyclical/
    # Defensive segment breakdown starts later than its own "All" aggregate.
    # With no Model chosen but a real Segment picked, cycles are pooled across
    # every model that has that segment; with neither chosen, the full global
    # cycle list shows (unchanged from before this cascade existed).
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.REPORTING_CYCLE_ID, "options"),
        Output(controls.REPORTING_CYCLE_ID, "value"),
        Input(controls.MODELS_ID, "value"),
        Input(controls.PORTFOLIO_SEGMENT_ID, "value"),
        State(controls.REPORTING_CYCLE_ID, "value"),
    )
    def sync_pd_population_to_cycle_options(model, segment, current_cycle):
        segment_key = segment if segment and segment != "all" else "All"
        if model:
            cycles = pd_model_segment_cycles.get((model, segment_key))
            if cycles is None:
                cycles = pd_model_segment_cycles.get((model, "All"), [])
        elif segment and segment != "all":
            cycles = sorted({
                cycle
                for (population_model, population_segment), population_cycles in pd_model_segment_cycles.items()
                if population_segment == segment
                for cycle in population_cycles
            })
        else:
            cycles = None
        options = _narrow_pd_cycle_options(cycles)
        allowed_values = {option["value"] for option in options}
        value = current_cycle if current_cycle in allowed_values else (options[0]["value"] if options else "")
        return options, value

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
        prevent_initial_call=True,
    )
    def toggle_segment_menu(_n_clicks, current_class):
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
        # The option buttons are re-created whenever Models changes (the Segment
        # menu narrows to that model's own segments), so this pattern-matching
        # callback can fire on that remount with ctx.triggered_id pointing at an
        # option whose n_clicks never actually incremented. Only act on a real
        # click (mirrors ui/common.py's select_single_select_option).
        triggered = ctx.triggered_id
        if not triggered or not any(_clicks or []):
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    # -----------------------------------------------------------------
    # Single-select dropdown shell sync (toggle label + full menu rebuild --
    # the Segment menu's option set now changes per selected model, so the
    # menu itself must be rebuilt rather than just re-highlighting a fixed
    # button set; mirrors sync_monitoring_point_shell above).
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.PORTFOLIO_SEGMENT_TOGGLE_ID, "children"),
        Output(controls.PORTFOLIO_SEGMENT_MENU_ID, "children"),
        Input(controls.PORTFOLIO_SEGMENT_ID, "value"),
        Input(controls.PORTFOLIO_SEGMENT_ID, "options"),
    )
    def sync_segment_shell(value, options):
        return filter_shell.build_single_select_shell(
            options=options,
            value=value,
            filter_key="portfolio-segment",
        )

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
        # The option buttons are re-created whenever Model/Segment changes (the
        # Cycle menu narrows to that population's real cycles), so this
        # pattern-matching callback can fire on that remount with
        # ctx.triggered_id pointing at an option whose n_clicks never actually
        # incremented. Only act on a real click (mirrors select_model/select_segment).
        triggered = ctx.triggered_id
        if not triggered or not any(_clicks or []):
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    # -----------------------------------------------------------------
    # Single-select dropdown shell sync (toggle label + full menu rebuild --
    # the Cycle menu's option set now changes per selected Model/Segment, so
    # the menu itself must be rebuilt rather than just re-highlighting a
    # fixed button set; mirrors sync_monitoring_point_shell/sync_segment_shell).
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.REPORTING_CYCLE_TOGGLE_ID, "children"),
        Output(controls.REPORTING_CYCLE_MENU_ID, "children"),
        Input(controls.REPORTING_CYCLE_ID, "value"),
        Input(controls.REPORTING_CYCLE_ID, "options"),
    )
    def sync_reporting_cycle_shell(value, options):
        return filter_shell.build_single_select_shell(
            options=options,
            value=value,
            filter_key="reporting-cycle",
        )

    # -----------------------------------------------------------------
    # Scenario options come from dummy_mev_data.xlsx's "scenario" sheet: the
    # distinct "Scenario" values available for the "Run For" cycle matching
    # the selected Model Use Case / Cycle (not a static config list). Falls
    # back to the full config list for cycles with no scenario-sheet rows
    # (e.g. BAU 2025Q1, which the sheet doesn't cover at all).
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.SCENARIO_ID, "options"),
        Output(controls.SCENARIO_ID, "value"),
        Input(controls.REPORTING_CYCLE_ID, "value"),
        State(controls.SCENARIO_ID, "value"),
    )
    def sync_pd_cycle_to_scenario_options(cycle, current_scenario):
        scenarios = mev_scenarios_by_cycle.get(cycle)
        if scenarios:
            options = [option for option in _cfg_scenario_options if option["value"] in set(scenarios)] or _cfg_scenario_options
        else:
            options = _cfg_scenario_options
        allowed_values = {option["value"] for option in options}
        value = current_scenario if current_scenario in allowed_values else (options[0]["value"] if options else "")
        return options, value

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
        # The option buttons are re-created whenever Model Use Case / Cycle
        # changes (the Scenario menu narrows to that cycle's real scenarios),
        # so this pattern-matching callback can fire on that remount with
        # ctx.triggered_id pointing at an option whose n_clicks never actually
        # incremented. Only act on a real click (mirrors select_model/select_segment).
        triggered = ctx.triggered_id
        if not triggered or not any(_clicks or []):
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    # -----------------------------------------------------------------
    # Single-select dropdown shell sync (toggle label + full menu rebuild --
    # the Scenario menu's option set now changes per selected Cycle, so the
    # menu itself must be rebuilt rather than just re-highlighting a fixed
    # button set; mirrors sync_reporting_cycle_shell above).
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.SCENARIO_TOGGLE_ID, "children"),
        Output(controls.SCENARIO_MENU_ID, "children"),
        Input(controls.SCENARIO_ID, "value"),
        Input(controls.SCENARIO_ID, "options"),
    )
    def sync_scenario_shell(value, options):
        return filter_shell.build_single_select_shell(
            options=options,
            value=value,
            filter_key="scenario",
        )

    # Models toggle
    @app.callback(
        Output(controls.MODELS_MENU_ID, "className"),
        Input(controls.MODELS_TOGGLE_ID, "n_clicks"),
        State(controls.MODELS_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_models_menu(_n_clicks, current_class):
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
        # The option buttons are re-created whenever Region/Portfolio changes
        # (the Model menu narrows to matching models), so this pattern-matching
        # callback can fire on that remount with ctx.triggered_id pointing at an
        # option whose n_clicks never actually incremented. Only act on a real
        # click (mirrors ui/common.py's select_single_select_option).
        triggered = ctx.triggered_id
        if not triggered or not any(_clicks or []):
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    # -----------------------------------------------------------------
    # Single-select dropdown shell sync (toggle label + full menu rebuild --
    # the Model menu's option set now changes per selected Region/Portfolio,
    # so the menu itself must be rebuilt rather than just re-highlighting a
    # fixed button set; mirrors sync_monitoring_point_shell/sync_segment_shell).
    # -----------------------------------------------------------------
    @app.callback(
        Output(controls.MODELS_TOGGLE_ID, "children"),
        Output(controls.MODELS_MENU_ID, "children"),
        Input(controls.MODELS_ID, "value"),
        Input(controls.MODELS_ID, "options"),
    )
    def sync_models_shell(value, options):
        return filter_shell.build_single_select_shell(
            options=options,
            value=value,
            filter_key="specific-models",
        )

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
    # Apply is gated on a Model being selected: Segment can be browsed/picked
    # freely with no model chosen, but the dashboard itself always needs one
    # explicit model to resolve data against, so the button stays disabled
    # (and the callback below no-ops even if clicked via a stale event) until
    # the user picks one.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLY_FILTERS_ID, "disabled"),
        Input(controls.MODELS_ID, "value"),
    )
    def sync_pd_apply_button_availability(model):
        return not bool(model)

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

        Guard against spurious fires when the page is (re)inserted by the router
        (no click yet) or when no Model is selected (the button should already be
        disabled in that case, but a stale click event is still guarded here).
        """
        if not _n_clicks or not models:
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
        model, segment = ctx_store_keys(filter_ctx)

        saved_fields = []
        for field, new_value in (pending or {}).items():
            if new_value not in ("Green", "Amber", "Red"):
                continue
            column = layout.PD_REVIEW_FLOW_COLUMNS.get(field)
            if not column:
                continue
            ok = data_service.save_pd_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point, column, new_value,
            )
            if ok:
                saved_fields.append(field)

        saved_commentary = layout.pd_reviewer_commentary(filter_ctx, monitoring_point)
        if (conclusions_notes or "") != (saved_commentary or ""):
            ok = data_service.save_pd_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point,
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
