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
from ....shared.domain.filter_order import alphabetical
from ....shared.registration import already_registered
from ....shared.repositories.filters_config import cycle_family
from ..data_access import PD_PERFORMANCE_DATA
from ..services import data_service

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def _merge_same_family_pd_cycle_data(observations_by_cycle: dict, reporting_cycle: str) -> dict:
    """Pool ``observations_by_cycle`` across every cycle in the same family as
    ``reporting_cycle`` (e.g. "CCAR 2025" + "CCAR 2026", never "CECL 2025Q1")
    so trend charts can show history from prior same-family cycles, not just
    the selected one. Every chart that reads ``ctx.quarters`` already trims
    to ``<= snapshot_quarter`` (see ``get_pd_range_periods`` and
    ``build_pd_performance_trend_for_horizon``), so widening the pool here is
    the only change needed -- the existing "up to the monitoring point"
    trimming does the rest.
    """
    family = cycle_family(reporting_cycle)
    quarters: set[str] = set()
    performance_observations: list = []
    rating_migration_observations: list = []
    metrics_store: dict = {}
    quarter_cycle_map: dict[str, str] = {}
    for cycle, cycle_data in (observations_by_cycle or {}).items():
        if cycle_family(cycle) != family:
            continue
        cycle_quarters = cycle_data.get("quarters") or []
        quarters.update(cycle_quarters)
        performance_observations.extend(cycle_data.get("performance_observations") or [])
        rating_migration_observations.extend(cycle_data.get("rating_migration_observations") or [])
        metrics_store.update(cycle_data.get("metrics_store") or {})
        for quarter in cycle_quarters:
            quarter_cycle_map[quarter] = cycle
    return {
        "quarters": sorted(quarters),
        "performance_observations": performance_observations,
        "rating_migration_observations": rating_migration_observations,
        "metrics_store": metrics_store,
        "quarter_cycle_map": quarter_cycle_map,
    }


def _resolve_pd_scope(data: dict, applied: dict | None) -> tuple[PdFilterContext, str, str]:
    """Resolve (filter_ctx, reporting_cycle, monitoring_point) from the applied-filters store.

    Shared by the review-flow Save callback and the save-bar sync callback so both always agree on
    which portfolio-file row a read/write targets (the master render callback resolves this itself
    inline, since it also needs the cycle's observations/metrics_store alongside it).
    """
    from ....shared.repositories.filters_config import load_filter_config
    cfg = load_filter_config()
    default_cycle = cfg["reporting_cycles"][0]["value"]

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
    pd_segment_models = data.get("pd_segment_models") or {}
    pd_model_segment_cycles = data.get("pd_model_segment_cycles") or {}
    mev_catalog = data.get("mev_catalog") or {}
    all_pd_segments = alphabetical({segment for segments in pd_model_segments.values() for segment in segments})
    # Which models actually have a literal (model, "All") row in each cycle's
    # precomputed store -- e.g. "PD Corp Model" in CCAR 2025 only has a
    # "Cyclical" row, no "All" aggregate. Picking "All" for such a model
    # silently resolves to a missing store key and every metric on the tab
    # goes blank, so sync_pd_model_to_segment_options below omits "All" from
    # the Segment dropdown whenever it wouldn't actually return data.
    pd_models_with_all_by_cycle: dict[str, set[str]] = {
        cycle: {model for (model, segment, _quarter, _horizon) in (cycle_data.get("metrics_store") or {}) if segment == "All"}
        for cycle, cycle_data in (data.get("observations_by_cycle") or {}).items()
    }
    # A model's own quarters for a cycle, pooled across its segments -- e.g.
    # "PD Corp Model" was deliberately left out of a portfolio-wide quarter
    # cleanup, so its CCAR 2025 footprint (2024Q3-2025Q2) differs from other
    # PD models' (2024Q4-2025Q3). Picking Monitoring Point options from the
    # tab-pooled PD_REPORTING_CYCLE_QUARTERS instead of this would offer
    # quarters the selected model has no data for (and hide ones it does).
    pd_model_cycle_quarters: dict[tuple[str, str], set[str]] = {}
    # The same, further scoped to (model, segment, cycle) -- a model's
    # segments can themselves have different footprints within a cycle, so
    # once a real segment is picked its own quarters take precedence over
    # the model-wide pool above.
    pd_model_segment_cycle_quarters: dict[tuple[str, str, str], set[str]] = {}
    for cycle, cycle_data in (data.get("observations_by_cycle") or {}).items():
        for (model, segment, quarter, _horizon) in (cycle_data.get("metrics_store") or {}):
            pd_model_cycle_quarters.setdefault((model, cycle), set()).add(quarter)
            pd_model_segment_cycle_quarters.setdefault((model, segment, cycle), set()).add(quarter)

    from ....shared.repositories.filters_config import (
        cycle_options_for_cycles,
        load_filter_config as _load_filter_config,
        use_case_options_for_cycles,
    )
    _cfg = _load_filter_config()
    _cfg_cycle_options = [{"label": c["label"], "value": c["value"]} for c in _cfg["reporting_cycles"]]

    def _narrow_pd_cycle_options(cycles: list[str] | None, use_case: str | None = None) -> list[dict[str, str]]:
        """Cycle options for a population, scoped to the selected Model Use Case.

        Labels are the bare cycle; values stay the composite.
        """
        return controls.with_placeholder(
            cycle_options_for_cycles(cycles, use_case), "reporting-cycle")

    # -----------------------------------------------------------------
    # Every top-bar filter's open/close, click-to-value, and menu-rebuild-
    # on-options-change behaviour is registered through the shared
    # single-select machinery (mirrors LGD/EAD/Loss/Overview) -- each
    # filter's own narrowing callback (sync_pd_filters_to_model_options,
    # sync_pd_model_to_segment_options, sync_pd_population_to_cycle_options,
    # sync_reporting_cycle_to_monitoring_point, sync_pd_cycle_to_scenario_options,
    # below) is unaffected and still separately owns each filter's
    # ``options``/``value`` outputs; this loop only owns the shell chrome.
    # -----------------------------------------------------------------
    for value_id, toggle_id, menu_id, filter_key, search_id in (
        (controls.REGION_ID, controls.REGION_TOGGLE_ID, controls.REGION_MENU_ID, "region", None),
        (controls.PORTFOLIO_ID, controls.PORTFOLIO_TOGGLE_ID, controls.PORTFOLIO_MENU_ID, "portfolio", None),
        # Only Model carries a search box; the rest keep the plain menu.
        (controls.MODELS_ID, controls.MODELS_TOGGLE_ID, controls.MODELS_MENU_ID, "specific-models",
         controls.MODELS_SEARCH_ID),
        (controls.PORTFOLIO_SEGMENT_ID, controls.PORTFOLIO_SEGMENT_TOGGLE_ID, controls.PORTFOLIO_SEGMENT_MENU_ID, "portfolio-segment", None),
        (controls.MODEL_USE_CASE_ID, controls.MODEL_USE_CASE_TOGGLE_ID, controls.MODEL_USE_CASE_MENU_ID, "model-use-case", None),
        (controls.REPORTING_CYCLE_ID, controls.REPORTING_CYCLE_TOGGLE_ID, controls.REPORTING_CYCLE_MENU_ID, "reporting-cycle", None),
        (controls.MONITORING_POINT_ID, controls.MONITORING_POINT_TOGGLE_ID, controls.MONITORING_POINT_MENU_ID, "monitoring-point", None),
    ):
        filter_shell.register_single_select_callbacks(
            app, value_id=value_id, toggle_id=toggle_id, menu_id=menu_id,
            filter_key=filter_key, search_id=search_id,
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
        # with_placeholder on every rewrite: the value "" must match an option,
        # or the shell's toggle falls back to a bare "Select" (see _option_label).
        # No "All" here: Region/Portfolio offer only values that have data, and
        # this callback used to re-add one (and default to it) behind the view's back.
        options = controls.with_placeholder(
            [{"label": p, "value": p} for p in portfolios], "portfolio")
        value = controls.keep_or_unselected(options, current_portfolio)
        return options, value

    # Segment narrows Models, and sync_pd_model_to_segment_options below narrows
    # Segment from Models -- a deliberate two-way cascade, but reading
    # PORTFOLIO_SEGMENT_ID's *value* here closed a dependency cycle
    # (Model -> Segment -> Model) that Dash reports as "Dependency Cycle Found".
    #
    # Listening to the Segment option *buttons* instead breaks it: a user picking
    # a segment still re-narrows Models, while Segment being rewritten
    # programmatically -- which is the half that closed the loop -- no longer
    # feeds back.
    #
    # The picked segment comes from the triggering button's own id, not from
    # PORTFOLIO_SEGMENT_ID's State: select_single_select_option writes that value
    # in the same round trip, so the State still holds the *previous* segment here.
    @app.callback(
        Output(controls.MODELS_ID, "options"),
        Output(controls.MODELS_ID, "value"),
        Input(controls.REGION_ID, "value"),
        Input(controls.PORTFOLIO_ID, "value"),
        Input(controls.REPORTING_CYCLE_ID, "value"),
        Input(
            {
                "type": controls.SINGLE_SELECT_OPTION_ID,
                "filter": controls.PORTFOLIO_SEGMENT_FILTER_KEY,
                "value": ALL,
            },
            "n_clicks",
        ),
        State(controls.PORTFOLIO_SEGMENT_ID, "value"),
        State(controls.MODELS_ID, "value"),
    )
    def sync_pd_filters_to_model_options(region, portfolio, reporting_cycle, segment_clicks, segment, current_model):
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == controls.SINGLE_SELECT_OPTION_ID:
            # Option buttons are re-created whenever the Segment menu is rebuilt,
            # and that remount fires this pattern-matching Input with every
            # n_clicks still 0 -- see select_single_select_option. Only a real
            # click carries a new segment.
            if not any(segment_clicks or []):
                return no_update, no_update
            segment = triggered.get("value")
        matches = models_matching(mev_catalog, "PD", region, portfolio, data["model_names"])
        if segment and segment != "all":
            segment_models = set(pd_segment_models.get(segment, []))
            matches = [m for m in matches if m in segment_models]
        # Reporting Cycle sits to the LEFT of Model in the bar, so it narrows
        # Model -- drop models with no rows for the chosen cycle. It was already
        # an Input here but went unused, which let the bar offer a model/cycle
        # pair with no data behind it. Harmless while Apply only needed a Model;
        # now that Apply also needs a Monitoring Point it was a dead end, since
        # such a pair leaves the Monitoring Point list empty and Apply can never
        # enable. Skipped while the cycle is unanswered -- nothing to narrow by.
        if reporting_cycle:
            matches = [m for m in matches if pd_model_cycle_quarters.get((m, reporting_cycle))]

        options = controls.with_placeholder(
            [{"label": m, "value": m} for m in matches], "specific-models")
        value = controls.keep_or_unselected(options, current_model)
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
        Output(layout.COMPENSATING_CONTROLS_STORE_ID, "data", allow_duplicate=True),
        Output(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data", allow_duplicate=True),
        Input(URL_ID, "pathname"),
        prevent_initial_call=True,
    )
    def discard_pd_staged_state_on_entry(pathname):
        # Only reset when the PD page itself is on screen (its path is "/"), so
        # the master re-render that this triggers has a live content container to
        # write into rather than firing against a page that has been swapped out.
        if pathname != "/":
            return no_update, no_update, no_update, no_update
        return {}, "", "", ""

    # -----------------------------------------------------------------
    # Reporting Cycle -> Monitoring Point options
    # -----------------------------------------------------------------
    all_quarters_asc = sorted(data["quarters"])

    @app.callback(
        Output(controls.MONITORING_POINT_ID, "options"),
        Output(controls.MONITORING_POINT_ID, "value"),
        Input(controls.REPORTING_CYCLE_ID, "value"),
        Input(controls.MODELS_ID, "value"),
        Input(controls.PORTFOLIO_SEGMENT_ID, "value"),
        State(controls.MONITORING_POINT_ID, "value"),
    )
    def sync_reporting_cycle_to_monitoring_point(cycle, model, segment, current_mp):
        if model:
            model_quarters = None
            if segment:
                segment_key = "All" if segment == "all" else segment
                model_quarters = pd_model_segment_cycle_quarters.get((model, segment_key, cycle))
            if not model_quarters:
                model_quarters = pd_model_cycle_quarters.get((model, cycle))
            allowed = sorted(model_quarters)[-controls.MONITORING_POINT_WINDOW:] if model_quarters else None
        else:
            allowed = controls.PD_REPORTING_CYCLE_QUARTERS.get(cycle)
        # Most-recent-first, matching Reporting Cycle beside it and the other
        # monitoring tabs. resolve_monitoring_point_value picks by max() rather
        # than by position, so presenting the reverse cannot change which
        # quarter is selected when the current one falls out of range.
        quarters = all_quarters_asc if allowed is None else sorted(allowed)
        options = controls.with_placeholder(
            [{"label": q, "value": q} for q in reversed(quarters)], "monitoring-point")
        # Not resolve_monitoring_point_value: it answers the filter with the
        # latest quarter, which on the empty first render fills it in unasked.
        value = controls.keep_or_unselected(options, current_mp)
        return options, value

    # -----------------------------------------------------------------
    # Segment is never disabled/blocked by Model: with a model chosen, its
    # options narrow to that model's own real segments (unchanged). With no
    # model chosen, Segment still works -- it shows every segment across all
    # PD models plus a "Select segment" placeholder (mirroring Model's own
    # "Select model" placeholder) so Segment can be Browse/picked first.
    # Models is narrowed by Segment (see sync_pd_filters_to_model_options
    # above) -- picking a segment restricts Models to models that actually
    # own it, clearing a now-invalid selection.
    # -----------------------------------------------------------------
    # reporting_cycle is read as State, not Input: sync_pd_population_to_cycle_options
    # below already reacts to PORTFOLIO_SEGMENT_ID and writes REPORTING_CYCLE_ID,
    # so making this callback also react to REPORTING_CYCLE_ID would form a cycle
    # (Segment -> Cycle -> Segment -> ...), which Dash rejects at registration.
    @app.callback(
        Output(controls.PORTFOLIO_SEGMENT_ID, "options"),
        Output(controls.PORTFOLIO_SEGMENT_ID, "value"),
        Input(controls.MODELS_ID, "value"),
        State(controls.REPORTING_CYCLE_ID, "value"),
        State(controls.PORTFOLIO_SEGMENT_ID, "value"),
    )
    def sync_pd_model_to_segment_options(model, reporting_cycle, current_segment):
        if model:
            segments = pd_model_segments.get(model, [])
            has_all = model in pd_models_with_all_by_cycle.get(reporting_cycle, set())
            options = controls.with_placeholder(
                ([{"label": "All", "value": "all"}] if has_all else [])
                + [{"label": s, "value": s} for s in segments],
                "portfolio-segment",
            )
        else:
            options = controls.with_placeholder(
                [{"label": "All", "value": "all"}]
                + [{"label": s, "value": s} for s in all_pd_segments],
                "portfolio-segment",
            )
        value = controls.keep_or_unselected(options, current_segment)
        return options, value

    # -----------------------------------------------------------------
    # Model Use Case / Cycle narrows to whichever reporting cycles actually
    # have data for the selected Model/Segment population -- e.g. PD Model C
    # only has CCAR 2025/2026 rows (no CECL 2025Q1), and PD Model B's Cyclical/
    # Defensive segment breakdown starts later than its own "All" aggregate.
    # With no Model chosen but a real Segment picked, cycles are pooled across
    # every model that has that segment; with neither chosen, the full global
    # cycle list shows (unchanged from before this cascade existed).
    # -----------------------------------------------------------------
    def _pd_population_cycles(model, segment) -> list[str] | None:
        """Cycles the selected Model/Segment population has data for.

        ``None`` means "no population narrowing". Shared by the Model Use Case
        and Reporting Cycle callbacks so the two cannot disagree.
        """
        segment_key = segment if segment and segment != "all" else "All"
        if model:
            cycles = pd_model_segment_cycles.get((model, segment_key))
            if cycles is None:
                cycles = pd_model_segment_cycles.get((model, "All"), [])
            return cycles
        if segment and segment != "all":
            return sorted({
                cycle
                for (population_model, population_segment), population_cycles in pd_model_segment_cycles.items()
                if population_segment == segment
                for cycle in population_cycles
            })
        return None

    # -----------------------------------------------------------------
    # The bar narrows left to right: Region -> Portfolio -> Model Use Case ->
    # Reporting Cycle -> Model Group -> Model -> Segment -> Monitoring Point ->
    # Scenario. Reporting Cycle now sits LEFT of Model/Segment, so it is scoped
    # by the Use Case alone and in turn narrows the Model list below. Reading
    # the population back here would write a filter to the left of its own
    # inputs -- the loop callback rule 2 forbids.
    # -----------------------------------------------------------------
    # Model Use Case is narrowed by Region/Portfolio too, matching Overview.
    # Without it the bar offered a programme the chosen region/portfolio has no
    # data for, and picking it emptied Reporting Cycle -- a dead end now that
    # Apply requires the whole scope. Region and Portfolio sit to the LEFT of
    # Model Use Case, so this stays a one-way cascade (callback rule 2).
    @app.callback(
        Output(controls.MODEL_USE_CASE_ID, "options"),
        Output(controls.MODEL_USE_CASE_ID, "value"),
        Input(controls.REGION_ID, "value"),
        Input(controls.PORTFOLIO_ID, "value"),
        State(controls.MODEL_USE_CASE_ID, "value"),
    )
    def sync_pd_scope_to_use_case_options(region, portfolio, current_use_case):
        in_scope = models_matching(mev_catalog, "PD", region, portfolio, data["model_names"])
        cycles_with_data = {
            cycle for (model, cycle) in pd_model_cycle_quarters
            if model in in_scope and pd_model_cycle_quarters[(model, cycle)]
        }
        options = controls.with_placeholder(
            use_case_options_for_cycles(cycles_with_data or None), "model-use-case")
        return options, controls.keep_or_unselected(options, current_use_case)

    @app.callback(
        Output(controls.REPORTING_CYCLE_ID, "options"),
        Output(controls.REPORTING_CYCLE_ID, "value"),
        Input(controls.REGION_ID, "value"),
        Input(controls.PORTFOLIO_ID, "value"),
        Input(controls.MODEL_USE_CASE_ID, "value"),
        State(controls.REPORTING_CYCLE_ID, "value"),
    )
    def sync_pd_use_case_to_cycle_options(region, portfolio, model_use_case, current_cycle):
        # Also narrowed by Region/Portfolio, matching Overview. Without it the
        # bar offered cycles with no model behind them for the chosen
        # region/portfolio, and picking one emptied the Model list -- a dead
        # end now that Apply requires both a Model and a Monitoring Point.
        # Region and Portfolio sit to the LEFT of Reporting Cycle, so reading
        # them here keeps the cascade one-way (callback rule 2).
        in_scope = models_matching(mev_catalog, "PD", region, portfolio, data["model_names"])
        cycles_with_data = {
            cycle for (model, cycle) in pd_model_cycle_quarters
            if model in in_scope and pd_model_cycle_quarters[(model, cycle)]
        }
        options = [
            option for option in _narrow_pd_cycle_options(None, model_use_case)
            if not option["value"] or option["value"] in cycles_with_data
        ]
        allowed_values = {option["value"] for option in options}
        value = controls.keep_or_unselected(options, current_cycle)
        return options, value

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
    # The page opens with every filter unanswered, so Apply stays disabled until
    # all of them have a real value -- nothing can be applied against a
    # half-specified scope. Model Group is included for completeness; on this tab
    # it has a single fixed value and is therefore always satisfied.
    @app.callback(
        Output(layout.APPLY_FILTERS_ID, "disabled"),
        Input(controls.REGION_ID, "value"),
        Input(controls.PORTFOLIO_ID, "value"),
        Input(controls.MODEL_USE_CASE_ID, "value"),
        Input(controls.REPORTING_CYCLE_ID, "value"),
        Input(controls.MODELS_ID, "value"),
        Input(controls.PORTFOLIO_SEGMENT_ID, "value"),
        Input(controls.MONITORING_POINT_ID, "value"),
    )
    def sync_pd_apply_button_availability(*filter_values):
        return not controls.all_selected(*filter_values)

    # -----------------------------------------------------------------
    # MEV Range's own Scenario picker -> its store. Pattern-matching because
    # the control lives inside the callback-rendered content: a plain id would
    # make the renderer fail to gather this Input before the section exists.
    # Writes only the store, which the master render reads, so changing it
    # re-renders immediately -- the same live behaviour as the Window/From/To
    # controls it sits beside.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.SCENARIO_STORE_ID, "data"),
        Input({"type": layout.MEV_SCENARIO_ID, "key": ALL}, "value"),
        prevent_initial_call=True,
    )
    def update_pd_mev_scenario_store(values):
        picked = next((value for value in (values or []) if value), None)
        return picked if picked else no_update

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data", allow_duplicate=True),
        Output(layout.COMPENSATING_CONTROLS_STORE_ID, "data", allow_duplicate=True),
        Output(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data", allow_duplicate=True),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(controls.MONITORING_POINT_ID, "value"),
        State(controls.PORTFOLIO_SEGMENT_ID, "value"),
        State(controls.MODELS_ID, "value"),
        State(controls.REPORTING_CYCLE_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_pd_filters(_n_clicks, monitoring_point, segment, models, reporting_cycle):
        """Snapshot the current top filters so the content renders only on Apply.

        Also discards the scope-specific review-flow state: the unsaved
        reviewer sign-off draft, the unsaved compensating-controls draft, any
        staged (not-yet-saved) RAG picks, and the last save-status message.
        All of these describe the scope that was on
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
            return no_update, no_update, no_update, no_update, no_update
        return {
            "monitoring_point": monitoring_point,
            "segment": segment,
            "models": models,
            "reporting_cycle": reporting_cycle,
        }, "", "", {}, ""

    # -----------------------------------------------------------------
    # Master re-render: applied store + per-chart stores -> pd-performance-content
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.PD_DEEP_LINK_STORE_ID, "data"),
        Input(layout.RANGE_STORE_ID, "data"),
        Input(layout.TREND_HORIZON_STORE_ID, "data"),
        Input(layout.MEV_FILTER_STORE_ID, "data"),
        Input(layout.SCENARIO_STORE_ID, "data"),
        Input(layout.SCENARIO_RANKING_STORE_ID, "data"),
        Input(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        Input(APP_THEME_ID, "value"),
        State(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        State(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        State(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        # Not prevent_initial_call: PD_DEEP_LINK_STORE_ID (see its own comment
        # in ui/views/pd_performance.py) bakes a deep link's scope directly
        # into this page's initial layout, and a full page load's very first
        # callback batch is exactly the "initial call" this flag would
        # otherwise suppress. With no deep link and nothing yet Applied this
        # session, both stores are empty and this just re-renders the same
        # getting-started prompt page_layout already server-rendered.
    )
    def render_pd_performance_content(
        applied, deep_link_applied, range_store, trend_horizon_store, mev_filter_store, scenario_store,
        scenario_ranking_store,
        review_flow_pending_edits, theme_value, conclusions_notes, compensating_controls, review_flow_save_status,
    ):
        # Prefer an explicit Apply click this session over the deep-link
        # snapshot from page load -- once the user applies for real, that
        # should win even if they arrived via a deep link.
        applied = applied or deep_link_applied
        # Until either applies, keep the getting-started guide that
        # ``page_layout`` rendered into the content container.
        if not applied:
            return layout.build_pd_apply_prompt()

        from ....shared.repositories.filters_config import load_filter_config
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"]
        default_scenario = cfg["scenarios"][0]["value"]
        # From the MEV Range section's own store, not the applied scope: it is a
        # display control for that section, so it re-renders live rather than
        # waiting for Apply.

        applied = applied or {}
        reporting_cycle = applied.get("reporting_cycle") or default_cycle
        # In-section pick wins; otherwise the deep link's ?scenario=, which
        # still rides in the applied/deep-link store; otherwise the default.
        scenario = scenario_store or applied.get("scenario") or default_scenario

        observations_by_cycle = data.get("observations_by_cycle") or {}
        cycle_data = observations_by_cycle.get(reporting_cycle)
        if cycle_data:
            merged = _merge_same_family_pd_cycle_data(observations_by_cycle, reporting_cycle)
            quarters = merged["quarters"]
            performance_observations = merged["performance_observations"]
            rating_migration_observations = merged["rating_migration_observations"]
            metrics_store = merged["metrics_store"]
            quarter_cycle_map = merged["quarter_cycle_map"]
        else:
            quarters = data["quarters"]
            performance_observations = data["performance_observations"]
            rating_migration_observations = data["rating_migration_observations"]
            metrics_store = None
            quarter_cycle_map = {}

        # The PD Performance tab reads every metric straight from the workbook.
        set_precomputed_metrics(metrics_store)

        render_data = {
            **data,
            "quarters": quarters,
            "performance_observations": performance_observations,
            "rating_migration_observations": rating_migration_observations,
            "quarter_cycle_map": quarter_cycle_map,
        }

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
            compensating_controls=compensating_controls or "",
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
    # Compensating-controls textarea -> pd-compensating-controls-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        Input(layout.COMPENSATING_CONTROLS_ID, "value"),
        prevent_initial_call=True,
    )
    def save_pd_compensating_controls(value):
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
        State(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        State(layout.SCENARIO_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def save_pd_review_flow_rag_changes(n_clicks, pending, applied, conclusions_notes, compensating_controls, scenario_store):
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

        saved_compensating = layout.pd_compensating_controls(filter_ctx, monitoring_point)
        if (compensating_controls or "") != (saved_compensating or ""):
            ok = data_service.save_pd_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point,
                layout.COMPENSATING_CONTROLS_COLUMN, compensating_controls or "",
            )
            if ok:
                saved_fields.append("compensating_controls")

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

        # Also persist the Scenario filter value in effect for this save, so
        # Overview's MEV Range can look up the scenario this row was actually
        # reviewed under instead of assuming a single portfolio-wide default
        # (see shared.repositories.filters_config.load_filter_config and
        # augment_rows_with_post_subjective in ui/views/overview.py). Not
        # counted in saved_fields/the status message -- it's metadata, not a
        # reviewer-facing field edit.
        from ....shared.repositories.filters_config import load_filter_config
        default_scenario = load_filter_config()["scenarios"][0]["value"]
        # The in-section pick wins: Scenario now lives in MEV Range and changes
        # without Apply, so the applied scope can be stale by the time of a save.
        scenario = scenario_store or (applied or {}).get("scenario") or default_scenario
        data_service.save_pd_review_flow_rag(data, reporting_cycle, model, segment, monitoring_point, "scenario", scenario)

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
        Input(layout.COMPENSATING_CONTROLS_ID, "value"),
        Input(layout.PD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.PD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def sync_pd_review_flow_save_bar(conclusions_notes, compensating_controls, pending, applied, save_status):
        filter_ctx, _reporting_cycle, monitoring_point = _resolve_pd_scope(data, applied)
        review_flow_rags = layout.pd_review_flow_rags(filter_ctx, monitoring_point)
        saved_commentary = layout.pd_reviewer_commentary(filter_ctx, monitoring_point)
        saved_compensating = layout.pd_compensating_controls(filter_ctx, monitoring_point)
        commentary_changed = (conclusions_notes or "") != (saved_commentary or "")
        compensating_changed = (compensating_controls or "") != (saved_compensating or "")
        save_bar = layout.build_pd_review_flow_save_bar(
            pending or {}, review_flow_rags, save_status, commentary_changed, compensating_changed,
        )
        return [save_bar] if save_bar is not None else []
