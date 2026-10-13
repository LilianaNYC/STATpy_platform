"""Callbacks for the EAD Performance page."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import ead_performance as layout
from ....shared.ui import controls
from ....shared.domain.mev_range import model_field_values, models_matching
from ..domain.ead import (
    get_ead_model_options,
    get_ead_segments_for_model,
    ead_store_key,
    resolve_ead_models,
    resolve_ead_monitoring_point,
)
from ....shared.registration import already_registered
from ....shared.repositories.filters_config import cycle_family
from ....shared.theme import APP_THEME_ID
from ..data_access import PD_PERFORMANCE_DATA
from ..services import data_service

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def _dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _merge_same_family_ead_cycle_data(observations_by_cycle: dict, reporting_cycle: str) -> dict:
    """Pool ``ead_observations_by_cycle`` across every cycle in the same
    family as ``reporting_cycle`` -- see the equivalent
    ``_merge_same_family_lgd_cycle_data`` in ``lgd_performance.py``.
    """
    family = cycle_family(reporting_cycle)
    quarters: set[str] = set()
    metrics_store: dict[tuple[str, str], list[dict]] = {}
    quarter_cycle_map: dict[str, str] = {}
    for cycle, cycle_data in (observations_by_cycle or {}).items():
        if cycle_family(cycle) != family:
            continue
        cycle_quarters = cycle_data.get("quarters") or []
        quarters.update(cycle_quarters)
        for key, rows in (cycle_data.get("metrics_store") or {}).items():
            metrics_store.setdefault(key, []).extend(dict(row, reporting_cycle=cycle) for row in rows)
        for quarter in cycle_quarters:
            quarter_cycle_map[quarter] = cycle
    for rows in metrics_store.values():
        rows.sort(key=lambda row: row.get("Monitoring Period") or "")
    return {"quarters": sorted(quarters), "metrics_store": metrics_store, "quarter_cycle_map": quarter_cycle_map}


def _resolve_ead_scope(data: dict, applied: dict | None) -> tuple[str | None, str | None, str, str]:
    """Resolve (selected_model, selected_segment, monitoring_point, reporting_cycle) from the applied store.

    Shared by the review-flow Save callback and the save-bar sync callback so both always agree on which
    portfolio-file row a read/write targets. Assumes ``_EAD_STORE`` (installed by the master render
    callback whenever ``reporting_cycle`` changes) already matches ``reporting_cycle`` -- true here since
    both callbacks only ever fire after the tab has already rendered once for the current scope.
    """
    from ....shared.repositories.filters_config import load_filter_config
    cfg = load_filter_config()
    default_cycle = cfg["reporting_cycles"][0]["value"]

    applied = applied or {}
    reporting_cycle = applied.get("reporting_cycle") or default_cycle
    selected_model = applied.get("model")
    selected_segment = applied.get("segment")
    # Mirrors the same fallback in layout.render_ead_performance_content: with no explicit model and no
    # segment, the tab defaults to the first available EAD model rather than showing nothing. Without
    # this, a Save/sync here would resolve a different (empty) scope key than what's on screen.
    if (not selected_model or selected_model == "all") and (selected_segment in (None, "", "All", "all")):
        model_options = get_ead_model_options(data)
        selected_model = model_options[0] if model_options else selected_model
    monitoring_point = resolve_ead_monitoring_point(data, selected_model, selected_segment, applied.get("monitoring_point"))
    return selected_model, selected_segment, monitoring_point, reporting_cycle


def register_callbacks(app) -> None:
    """Register EAD Performance callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.ead_performance"):
        return

    data = PD_PERFORMANCE_DATA

    for value_id, toggle_id, menu_id, filter_key, search_id in (
        (layout.MODEL_USE_CASE_ID, layout.MODEL_USE_CASE_TOGGLE_ID, layout.MODEL_USE_CASE_MENU_ID, layout.MODEL_USE_CASE_FILTER_KEY, None),
        (layout.REPORTING_CYCLE_ID, layout.REPORTING_CYCLE_TOGGLE_ID, layout.REPORTING_CYCLE_MENU_ID, layout.REPORTING_CYCLE_FILTER_KEY, None),
        (layout.MONITORING_POINT_DROPDOWN_ID, layout.MONITORING_POINT_TOGGLE_ID, layout.MONITORING_POINT_MENU_ID, layout.MONITORING_POINT_FILTER_KEY, None),
        (layout.SEGMENT_DROPDOWN_ID, layout.SEGMENT_TOGGLE_ID, layout.SEGMENT_MENU_ID, layout.SEGMENT_FILTER_KEY, None),
        # Only Model carries a search box; the rest keep the plain menu.
        (layout.MODEL_DROPDOWN_ID, layout.MODEL_TOGGLE_ID, layout.MODEL_MENU_ID,
         layout.MODEL_FILTER_KEY, layout.MODEL_SEARCH_ID),
        (layout.REGION_ID, layout.REGION_TOGGLE_ID, layout.REGION_MENU_ID, layout.REGION_FILTER_KEY, None),
        (layout.PORTFOLIO_ID, layout.PORTFOLIO_TOGGLE_ID, layout.PORTFOLIO_MENU_ID, layout.PORTFOLIO_FILTER_KEY, None),
    ):
        filter_shell.register_single_select_callbacks(
            app,
            value_id=value_id,
            toggle_id=toggle_id,
            menu_id=menu_id,
            filter_key=filter_key,
            search_id=search_id,
        )

    mev_catalog = data.get("mev_catalog") or {}
    ead_model_options = get_ead_model_options(data)
    ead_model_segment_cycles = data.get("ead_model_segment_cycles") or {}
    ead_segment_models = data.get("ead_segment_models") or {}
    # A model's own quarters for a cycle, pooled across its segments -- see
    # the equivalent pd_model_cycle_quarters note in pd_performance.py.
    ead_model_cycle_quarters: dict[tuple[str, str], set[str]] = {}
    # The same, further scoped to (model, segment, cycle) -- once a real
    # segment is picked, its own quarters take precedence over the
    # model-wide pool above (segments can have different footprints).
    ead_model_segment_cycle_quarters: dict[tuple[str, str, str], set[str]] = {}
    for cycle, cycle_data in (data.get("ead_observations_by_cycle") or {}).items():
        for (model, segment), rows in (cycle_data.get("metrics_store") or {}).items():
            quarters = {row["Monitoring Period"] for row in rows if row.get("Monitoring Period")}
            ead_model_cycle_quarters.setdefault((model, cycle), set()).update(quarters)
            ead_model_segment_cycle_quarters.setdefault((model, segment, cycle), set()).update(quarters)

    from ....shared.repositories.filters_config import (
        cycle_options_for_cycles,
        load_filter_config as _load_filter_config,
        use_case_options_for_cycles,
    )
    _cfg = _load_filter_config()
    _cfg_cycle_options = [{"label": c["label"], "value": c["value"]} for c in _cfg["reporting_cycles"]]

    def _narrow_ead_cycle_options(cycles: list[str] | None, use_case: str | None = None) -> list[dict[str, str]]:
        """Cycle options for a population, scoped to the selected Model Use Case.

        Labels are the bare cycle; values stay the composite, which is what every
        store, figure and export downstream keys on.
        """
        return controls.with_placeholder(
            cycle_options_for_cycles(cycles, use_case), "reporting-cycle")

    @app.callback(
        Output(layout.PORTFOLIO_ID, "options"),
        Output(layout.PORTFOLIO_ID, "value"),
        Input(layout.REGION_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
    )
    def sync_ead_region_to_portfolio_options(region, current_portfolio):
        matches = models_matching(mev_catalog, "EAD", region, None, ead_model_options)
        portfolios = model_field_values(mev_catalog, "portfolio", matches)
        # No "All": Portfolio is always a concrete slice of the chosen Region.
        # with_placeholder on every rewrite: the value "" must match an option,
        # or the shell's toggle falls back to a bare "Select" (see _option_label).
        options = controls.with_placeholder(
            [{"label": p, "value": p} for p in portfolios], "portfolio")
        value = controls.keep_or_unselected(options, current_portfolio)
        return options, value

    # Segment narrows Model, and sync_ead_segment_dropdown below narrows Segment
    # from Model -- a deliberate two-way cascade, but reading SEGMENT_DROPDOWN_ID's
    # *value* here closed a dependency cycle (Model -> Segment -> Model) that Dash
    # reports as "Dependency Cycle Found". Listening to the Segment option
    # *buttons* breaks it: a user picking a segment still re-narrows Model, while
    # Segment being rewritten programmatically no longer feeds back.
    #
    # The picked segment comes from the triggering button's own id, not from
    # SEGMENT_DROPDOWN_ID's State: select_single_select_option writes that value in
    # the same round trip, so the State still holds the previous segment here.
    @app.callback(
        Output(layout.MODEL_DROPDOWN_ID, "options"),
        Output(layout.MODEL_DROPDOWN_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(
            {
                "type": controls.SINGLE_SELECT_OPTION_ID,
                "filter": layout.SEGMENT_FILTER_KEY,
                "value": ALL,
            },
            "n_clicks",
        ),
        State(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MODEL_DROPDOWN_ID, "value"),
    )
    def sync_ead_region_portfolio_to_model_options(region, portfolio, reporting_cycle, segment_clicks, segment, current_model):
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == controls.SINGLE_SELECT_OPTION_ID:
            # Option buttons are re-created whenever the Segment menu is rebuilt,
            # and that remount fires this pattern-matching Input with every
            # n_clicks still 0 -- see select_single_select_option. Only a real
            # click carries a new segment.
            if not any(segment_clicks or []):
                return no_update, no_update
            segment = triggered.get("value")
        matches = models_matching(mev_catalog, "EAD", region, portfolio, ead_model_options)
        if segment and segment not in ("All", ""):
            segment_models = set(ead_segment_models.get(segment, []))
            matches = [m for m in matches if m in segment_models]
        # Reporting Cycle sits to the LEFT of Model in the bar, so it narrows
        # Model -- drop models with no rows for the chosen cycle. It was already
        # an Input here but went unused, which let the bar offer a model/cycle
        # pair with no data behind it. Harmless while Apply only needed a Model;
        # now that Apply also needs a Monitoring Point it was a dead end, since
        # such a pair leaves the Monitoring Point list empty and Apply can never
        # enable. Skipped while the cycle is unanswered -- nothing to narrow by.
        if reporting_cycle:
            matches = [m for m in matches if ead_model_cycle_quarters.get((m, reporting_cycle))]

        options = controls.with_placeholder(
            [{"label": m, "value": m} for m in matches], "specific-models")
        value = controls.keep_or_unselected(options, current_model)
        return options, value

    def _install_ead_store(reporting_cycle):
        from ..domain.ead import set_ead_metrics
        observations_by_cycle = data.get("ead_observations_by_cycle") or {}
        cycle_data = observations_by_cycle.get(reporting_cycle)
        if cycle_data:
            merged = _merge_same_family_ead_cycle_data(observations_by_cycle, reporting_cycle)
            set_ead_metrics(merged["metrics_store"], merged["quarters"], merged["quarter_cycle_map"])
        else:
            set_ead_metrics(None, [])
        return cycle_data

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
    def update_ead_range_store(
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

    # Segment is never disabled/blocked by Model: picking a Model narrows its
    # options to that model's own segments, but never answers it. See the note
    # in the body.
    @app.callback(
        Output(layout.SEGMENT_DROPDOWN_ID, "options"),
        Output(layout.SEGMENT_DROPDOWN_ID, "value"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
        State(layout.SEGMENT_DROPDOWN_ID, "value"),
    )
    def sync_ead_segment_dropdown(selected_model, selected_segment):
        segments = get_ead_segments_for_model(data, selected_model)
        options = controls.with_placeholder(_dropdown_options(segments), "portfolio-segment")
        # Segment stays unanswered until the user answers it, exactly like every
        # other filter -- matching PD. Picking a Model used to run
        # resolve_ead_segment here, which never returns empty: it falls back to
        # "All", or to ``segments[0]`` when the model has no "All" aggregate row.
        # For a single-segment model that was harmless, but a model with five
        # segments had the choice made for it (LGD Model A silently became
        # "Cyclical"), which is the auto-selection the empty start removes.
        #
        # resolve_ead_segment is still the right call elsewhere -- the page
        # layout uses it for deep links, which name a scope deliberately.
        value = controls.keep_or_unselected(options, selected_segment)
        return options, value

    # -----------------------------------------------------------------
    # Model Use Case / Cycle narrows to whichever reporting cycles actually
    # have data for the selected Model/Segment population -- see
    # sync_pd_population_to_cycle_options for the rationale.
    # -----------------------------------------------------------------
    def _ead_population_cycles(selected_model, selected_segment) -> list[str] | None:
        """Cycles the selected Model/Segment population has data for.

        ``None`` means "no population narrowing". Shared by the Model Use Case
        and Reporting Cycle callbacks so the two cannot disagree.
        """
        has_model = bool(resolve_ead_models(data, selected_model))
        segment_key = selected_segment if selected_segment and selected_segment not in ("", "all", "All") else "All"
        if has_model:
            cycles = ead_model_segment_cycles.get((selected_model, segment_key))
            if cycles is None:
                cycles = ead_model_segment_cycles.get((selected_model, "All"), [])
        elif selected_segment and selected_segment not in ("", "all", "All"):
            cycles = sorted({
                cycle
                for (population_model, population_segment), population_cycles in ead_model_segment_cycles.items()
                if population_segment == selected_segment
                for cycle in population_cycles
            })
        else:
            cycles = None
        return cycles

    # -----------------------------------------------------------------
    # The bar narrows left to right: Region -> Portfolio -> Model Use Case ->
    # Reporting Cycle -> Model Group -> Model -> Segment -> Monitoring Point ->
    # Scenario. Reporting Cycle now sits LEFT of Model/Segment, so it is scoped
    # by the Use Case alone and in turn narrows the Model list below. Reading
    # the population back here would write a filter to the left of its own
    # inputs and close the loop callback rule 2 forbids.
    # -----------------------------------------------------------------
    # Model Use Case is narrowed by Region/Portfolio too, matching Overview.
    # Without it the bar offered a programme the chosen region/portfolio has no
    # data for, and picking it emptied Reporting Cycle -- a dead end now that
    # Apply requires the whole scope. Region and Portfolio sit to the LEFT of
    # Model Use Case, so this stays a one-way cascade (callback rule 2).
    @app.callback(
        Output(layout.MODEL_USE_CASE_ID, "options"),
        Output(layout.MODEL_USE_CASE_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        State(layout.MODEL_USE_CASE_ID, "value"),
    )
    def sync_ead_scope_to_use_case_options(region, portfolio, current_use_case):
        in_scope = models_matching(mev_catalog, "EAD", region, portfolio, ead_model_options)
        cycles_with_data = {
            cycle for (model, cycle) in ead_model_cycle_quarters
            if model in in_scope and ead_model_cycle_quarters[(model, cycle)]
        }
        options = controls.with_placeholder(
            use_case_options_for_cycles(cycles_with_data or None), "model-use-case")
        return options, controls.keep_or_unselected(options, current_use_case)

    @app.callback(
        Output(layout.REPORTING_CYCLE_ID, "options"),
        Output(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.MODEL_USE_CASE_ID, "value"),
        State(layout.REPORTING_CYCLE_ID, "value"),
    )
    def sync_ead_use_case_to_cycle_options(region, portfolio, model_use_case, current_cycle):
        # Also narrowed by Region/Portfolio, matching Overview. Without it the
        # bar offered cycles with no model behind them for the chosen
        # region/portfolio, and picking one emptied the Model list -- a dead
        # end now that Apply requires both a Model and a Monitoring Point.
        # Region and Portfolio sit to the LEFT of Reporting Cycle, so reading
        # them here keeps the cascade one-way (callback rule 2).
        in_scope = models_matching(mev_catalog, "EAD", region, portfolio, ead_model_options)
        cycles_with_data = {
            cycle for (model, cycle) in ead_model_cycle_quarters
            if model in in_scope and ead_model_cycle_quarters[(model, cycle)]
        }
        options = [
            option for option in _narrow_ead_cycle_options(None, model_use_case)
            if not option["value"] or option["value"] in cycles_with_data
        ]
        allowed_values = {option["value"] for option in options}
        value = controls.keep_or_unselected(options, current_cycle)
        return options, value

    @app.callback(
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "options"),
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
        Input(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
    )
    def sync_ead_monitoring_point_dropdown(reporting_cycle, selected_model, selected_segment, selected_monitoring_point):
        if selected_model:
            model_quarters = None
            if selected_segment:
                model_quarters = ead_model_segment_cycle_quarters.get((selected_model, selected_segment, reporting_cycle))
            if not model_quarters:
                model_quarters = ead_model_cycle_quarters.get((selected_model, reporting_cycle))
            options = sorted(model_quarters)[-controls.MONITORING_POINT_WINDOW:] if model_quarters else []
        else:
            options = controls.EAD_REPORTING_CYCLE_QUARTERS.get(reporting_cycle, [])
        # Display most-recent-first, matching Reporting Cycle. Not
        # resolve_monitoring_point_value: it answers the filter with the latest
        # quarter, which on the empty first render fills it in unasked.
        point_options = controls.with_placeholder(
            _dropdown_options(list(reversed(options))), "monitoring-point")
        return point_options, controls.keep_or_unselected(point_options, selected_monitoring_point)

    # -----------------------------------------------------------------
    # Scenario Ranking selector -> ead-scenario-ranking-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.SCENARIO_RANKING_STORE_ID, "data"),
        Input(layout.SCENARIO_RANKING_FILTER_ID, "value"),
        prevent_initial_call=True,
    )
    def update_ead_scenario_ranking_store(selected_scenarios):
        return {"scenarios": selected_scenarios or []}

    # -----------------------------------------------------------------
    # Apply is gated on a Model being selected: Segment can be browsed/picked
    # freely with no model chosen, but the dashboard itself always needs one
    # explicit model to resolve data against -- see apply_pd_filters.
    # -----------------------------------------------------------------
    # -----------------------------------------------------------------
    # Apply gate: the page opens with every filter unanswered, so Apply stays
    # disabled until all of them have a real value -- nothing can be applied
    # against a half-specified scope. Model Group is included for completeness;
    # on this tab it has a single fixed value and is therefore always satisfied.
    #
    # This only ever writes the button's own ``disabled`` prop, and nothing
    # reads that back, so it adds no edge to the filter cascade.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLY_FILTERS_ID, "disabled"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.MODEL_USE_CASE_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
        Input(layout.SEGMENT_DROPDOWN_ID, "value"),
        Input(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
    )
    def sync_ead_apply_button_availability(*filter_values):
        return not controls.all_selected(*filter_values)

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data", allow_duplicate=True),
        Output(layout.COMPENSATING_CONTROLS_STORE_ID, "data", allow_duplicate=True),
        Output(layout.EAD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.EAD_REVIEW_FLOW_STATUS_STORE_ID, "data", allow_duplicate=True),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.MODEL_DROPDOWN_ID, "value"),
        State(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_ead_filters(_n_clicks, reporting_cycle, selected_model, selected_segment, selected_monitoring_point):
        """Snapshot the current top filters so the content renders only on Apply.

        Also discards the scope-specific review-flow state (unsaved reviewer sign-off draft, unsaved
        compensating-controls draft, staged RAG picks, last save-status message) -- see ``apply_pd_filters``.
        """
        if not _n_clicks or not selected_model:
            return no_update, no_update, no_update, no_update, no_update
        return {
            "reporting_cycle": reporting_cycle,
            "model": selected_model,
            "segment": selected_segment,
            "monitoring_point": selected_monitoring_point,
        }, "", "", {}, ""

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
    def update_ead_mev_scenario_store(values):
        picked = next((value for value in (values or []) if value), None)
        return picked if picked else no_update

    # -----------------------------------------------------------------
    # Master re-render: applied store + range store -> ead-dashboard-content
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.RANGE_STORE_ID, "data"),
        Input(layout.SCENARIO_STORE_ID, "data"),
        Input(layout.SCENARIO_RANKING_STORE_ID, "data"),
        Input(layout.EAD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        Input(APP_THEME_ID, "value"),
        State(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        State(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        State(layout.EAD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        # Not prevent_initial_call: see the matching comment in
        # callbacks/lgd_performance.py's render_lgd_content -- a deep-linked
        # APPLIED_FILTERS_STORE_ID is baked into this page's initial layout,
        # and needs this callback's first ("initial call") batch to fire.
    )
    def render_ead_content(
        applied, range_store, scenario_store, scenario_ranking_store, review_flow_pending_edits, theme_value,
        conclusions_notes, compensating_controls, review_flow_save_status,
    ):
        if not applied:
            return layout.build_ead_apply_prompt()

        from ....shared.repositories.filters_config import (
            default_scenario as cfg_default_scenario,
            load_filter_config,
        )
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"]
        default_scenario = cfg_default_scenario()

        reporting_cycle = applied.get("reporting_cycle") or default_cycle
        # In-section pick wins; otherwise the deep link's ?scenario=, which
        # still rides in the applied store; otherwise the default.
        scenario = scenario_store or applied.get("scenario") or default_scenario

        _install_ead_store(reporting_cycle)

        return layout.render_ead_performance_content(
            data,
            applied.get("model"),
            applied.get("segment"),
            applied.get("monitoring_point"),
            range_store or {},
            reporting_cycle=reporting_cycle,
            scenario=scenario,
            scenario_ranking_store=scenario_ranking_store or {},
            theme_value=theme_value,
            conclusions_notes=conclusions_notes or "",
            compensating_controls=compensating_controls or "",
            review_flow_pending_edits=review_flow_pending_edits or {},
            review_flow_save_status=review_flow_save_status or "",
        )

    # -----------------------------------------------------------------
    # Reviewer conclusions textarea -> ead-conclusions-notes-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        Input(layout.CONCLUSIONS_NOTES_ID, "value"),
        prevent_initial_call=True,
    )
    def save_ead_conclusions_notes(value):
        return value or ""

    # -----------------------------------------------------------------
    # Compensating-controls textarea -> ead-compensating-controls-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        Input(layout.COMPENSATING_CONTROLS_ID, "value"),
        prevent_initial_call=True,
    )
    def save_ead_compensating_controls(value):
        return value or ""

    # -----------------------------------------------------------------
    # Review-flow RAG pickers (Post Subjective Review / Pre-/Post-Mitigation)
    # -> ead-review-flow-pending-store (staged only, not yet written to disk)
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.EAD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        Input({"type": layout.EAD_REVIEW_FLOW_OPTION_ID, "field": ALL}, "value"),
        State(layout.EAD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def stage_ead_review_flow_rag(_values, pending):
        # These dropdowns live inside the re-rendered content area, so they get torn down and
        # recreated on every master re-render -- which fires this callback once as a "component just
        # appeared" reconciliation even with prevent_initial_call=True. They always mount with
        # value=None (a "Change RAG to..." action, not a live display), so that reconciliation firing
        # always reports a None value and is caught by the guard below; only a genuine pick ever sets a
        # real Green/Amber/Red value.
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
        Output(layout.EAD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.EAD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        Input(layout.EAD_REVIEW_FLOW_SAVE_ID, "n_clicks"),
        State(layout.EAD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        State(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        State(layout.SCENARIO_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def save_ead_review_flow_rag_changes(n_clicks, pending, applied, conclusions_notes, compensating_controls, scenario_store):
        # Same dynamic-mount quirk as the picker above: the Save button only exists once there's a
        # pending edit or commentary change, so it "just appeared" at least once and could fire
        # without a real click.
        if not n_clicks:
            return no_update, no_update

        selected_model, selected_segment, monitoring_point, reporting_cycle = _resolve_ead_scope(data, applied)
        model, segment = ead_store_key(selected_model, selected_segment)

        saved_fields = []
        for field, new_value in (pending or {}).items():
            if new_value not in ("Green", "Amber", "Red"):
                continue
            column = layout.EAD_REVIEW_FLOW_COLUMNS.get(field)
            if not column:
                continue
            ok = data_service.save_ead_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point, column, new_value,
            )
            if ok:
                saved_fields.append(field)

        saved_compensating = layout.ead_compensating_controls(selected_model, selected_segment, monitoring_point)
        if (compensating_controls or "") != (saved_compensating or ""):
            ok = data_service.save_ead_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point,
                layout.COMPENSATING_CONTROLS_COLUMN, compensating_controls or "",
            )
            if ok:
                saved_fields.append("compensating_controls")

        saved_commentary = layout.ead_reviewer_commentary(selected_model, selected_segment, monitoring_point)
        if (conclusions_notes or "") != (saved_commentary or ""):
            ok = data_service.save_ead_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point,
                layout.REVIEWER_COMMENTARY_COLUMN, conclusions_notes or "",
            )
            if ok:
                saved_fields.append("reviewer_commentary")

        if not saved_fields:
            return no_update, (
                "Could not save -- no matching rows were found in the portfolio file for the current scope."
            )

        # Also persist the Scenario filter value in effect for this save --
        # see the matching comment in save_pd_review_flow_rag_changes. Not
        # counted in saved_fields/the status message.
        from ....shared.repositories.filters_config import default_scenario as cfg_default_scenario
        default_scenario = cfg_default_scenario()
        # The in-section pick wins: Scenario now lives in MEV Range and changes
        # without Apply, so the applied scope can be stale by the time of a save.
        scenario = scenario_store or (applied or {}).get("scenario") or default_scenario
        data_service.save_ead_review_flow_rag(data, reporting_cycle, model, segment, monitoring_point, "scenario", scenario)

        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        count = len(saved_fields)
        return {}, f"Saved {count} change{'s' if count != 1 else ''} to portfolio.xlsx at {timestamp}."

    # -----------------------------------------------------------------
    # Keep the "Unsaved changes" bar in sync with commentary keystrokes without
    # rebuilding the whole tab (which would drop the textarea's cursor/focus).
    # RAG picks already rebuild the whole tab (layout.EAD_REVIEW_FLOW_PENDING_STORE_ID
    # is an Input there), so this callback only needs to add live text typing to the mix.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.EAD_REVIEW_FLOW_SAVE_BAR_ID, "children"),
        Input(layout.CONCLUSIONS_NOTES_ID, "value"),
        Input(layout.COMPENSATING_CONTROLS_ID, "value"),
        Input(layout.EAD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.EAD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def sync_ead_review_flow_save_bar(conclusions_notes, compensating_controls, pending, applied, save_status):
        selected_model, selected_segment, monitoring_point, _reporting_cycle = _resolve_ead_scope(data, applied)
        review_flow_rags = layout.ead_review_flow_rags(selected_model, selected_segment, monitoring_point)
        saved_commentary = layout.ead_reviewer_commentary(selected_model, selected_segment, monitoring_point)
        saved_compensating = layout.ead_compensating_controls(selected_model, selected_segment, monitoring_point)
        commentary_changed = (conclusions_notes or "") != (saved_commentary or "")
        compensating_changed = (compensating_controls or "") != (saved_compensating or "")
        save_bar = layout.build_ead_review_flow_save_bar(
            pending or {}, review_flow_rags, save_status, commentary_changed, compensating_changed,
        )
        return [save_bar] if save_bar is not None else []
