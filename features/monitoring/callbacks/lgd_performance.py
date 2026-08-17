"""Callbacks for the LGD Performance page."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import lgd_performance as layout
from ....shared.ui import controls
from ....shared.domain.mev_range import model_field_values, models_matching
from ..domain.lgd import (
    get_lgd_model_options,
    get_lgd_segments_for_model,
    lgd_store_key,
    resolve_lgd_models,
    resolve_lgd_monitoring_point,
    resolve_lgd_segment,
)
from ....shared.registration import already_registered
from ....shared.repositories.filters_config import cycle_family
from ....shared.theme import APP_THEME_ID
from ..data_access import PD_PERFORMANCE_DATA
from ..services import data_service

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def _dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _merge_same_family_lgd_cycle_data(observations_by_cycle: dict, reporting_cycle: str) -> dict:
    """Pool ``lgd_observations_by_cycle`` across every cycle in the same
    family as ``reporting_cycle`` (e.g. "CCAR 2024" + "CCAR 2025" +
    "CCAR 2026", never "BAU 2025Q1") so trend charts can show history from
    prior same-family cycles, not just the selected one. The merged rows
    still need capping to "<= monitoring point" downstream (see
    ``build_lgd_period_summary``), since -- unlike a single cycle's own
    rows -- the pool can now include a later same-family cycle's future
    quarters relative to whatever monitoring point is selected.
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


def _resolve_lgd_scope(data: dict, applied: dict | None) -> tuple[str | None, str | None, str, str]:
    """Resolve (selected_model, selected_segment, monitoring_point, reporting_cycle) from the applied store.

    Shared by the review-flow Save callback and the save-bar sync callback so both always agree on which
    portfolio-file row a read/write targets. Assumes ``_LGD_STORE`` (installed by the master render
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
    # Mirrors the same fallback in layout.render_lgd_performance_content: with no explicit model and no
    # segment, the tab defaults to the first available LGD model rather than showing nothing. Without
    # this, a Save/sync here would resolve a different (empty) scope key than what's on screen.
    if (not selected_model or selected_model == "all") and (selected_segment in (None, "", "All", "all")):
        model_options = get_lgd_model_options(data)
        selected_model = model_options[0] if model_options else selected_model
    monitoring_point = resolve_lgd_monitoring_point(data, selected_model, selected_segment, applied.get("monitoring_point"))
    return selected_model, selected_segment, monitoring_point, reporting_cycle


def register_callbacks(app) -> None:
    """Register LGD Performance callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.lgd_performance"):
        return

    data = PD_PERFORMANCE_DATA

    for value_id, toggle_id, menu_id, filter_key in (
        (layout.REPORTING_CYCLE_ID, layout.REPORTING_CYCLE_TOGGLE_ID, layout.REPORTING_CYCLE_MENU_ID, layout.REPORTING_CYCLE_FILTER_KEY),
        (layout.SCENARIO_ID, layout.SCENARIO_TOGGLE_ID, layout.SCENARIO_MENU_ID, layout.SCENARIO_FILTER_KEY),
        (layout.MONITORING_POINT_DROPDOWN_ID, layout.MONITORING_POINT_TOGGLE_ID, layout.MONITORING_POINT_MENU_ID, layout.MONITORING_POINT_FILTER_KEY),
        (layout.SEGMENT_DROPDOWN_ID, layout.SEGMENT_TOGGLE_ID, layout.SEGMENT_MENU_ID, layout.SEGMENT_FILTER_KEY),
        (layout.MODEL_DROPDOWN_ID, layout.MODEL_TOGGLE_ID, layout.MODEL_MENU_ID, layout.MODEL_FILTER_KEY),
        (layout.REGION_ID, layout.REGION_TOGGLE_ID, layout.REGION_MENU_ID, layout.REGION_FILTER_KEY),
        (layout.PORTFOLIO_ID, layout.PORTFOLIO_TOGGLE_ID, layout.PORTFOLIO_MENU_ID, layout.PORTFOLIO_FILTER_KEY),
        (layout.MODEL_GROUP_ID, layout.MODEL_GROUP_TOGGLE_ID, layout.MODEL_GROUP_MENU_ID, layout.MODEL_GROUP_FILTER_KEY),
    ):
        filter_shell.register_single_select_callbacks(
            app,
            value_id=value_id,
            toggle_id=toggle_id,
            menu_id=menu_id,
            filter_key=filter_key,
        )

    mev_catalog = data.get("mev_catalog") or {}
    lgd_model_options = get_lgd_model_options(data)
    lgd_model_segment_cycles = data.get("lgd_model_segment_cycles") or {}
    lgd_segment_models = data.get("lgd_segment_models") or {}
    mev_scenarios_by_cycle = data.get("mev_scenarios_by_cycle") or {}
    # A model's own quarters for a cycle, pooled across its segments -- see
    # the equivalent pd_model_cycle_quarters note in pd_performance.py.
    lgd_model_cycle_quarters: dict[tuple[str, str], set[str]] = {}
    # The same, further scoped to (model, segment, cycle) -- once a real
    # segment is picked, its own quarters take precedence over the
    # model-wide pool above (segments can have different footprints).
    lgd_model_segment_cycle_quarters: dict[tuple[str, str, str], set[str]] = {}
    for cycle, cycle_data in (data.get("lgd_observations_by_cycle") or {}).items():
        for (model, segment), rows in (cycle_data.get("metrics_store") or {}).items():
            quarters = {row["Monitoring Period"] for row in rows if row.get("Monitoring Period")}
            lgd_model_cycle_quarters.setdefault((model, cycle), set()).update(quarters)
            lgd_model_segment_cycle_quarters.setdefault((model, segment, cycle), set()).update(quarters)

    from ....shared.repositories.filters_config import load_filter_config as _load_filter_config
    _cfg = _load_filter_config()
    _cfg_cycle_options = [{"label": c["label"], "value": c["value"]} for c in _cfg["reporting_cycles"]]
    _cfg_scenario_options = [{"label": s["label"], "value": s["value"]} for s in _cfg["scenarios"]]

    def _narrow_lgd_cycle_options(cycles: list[str] | None) -> list[dict[str, str]]:
        if cycles is None:
            return _cfg_cycle_options
        allowed = set(cycles)
        narrowed = [option for option in _cfg_cycle_options if option["value"] in allowed]
        return narrowed or _cfg_cycle_options

    @app.callback(
        Output(layout.PORTFOLIO_ID, "options"),
        Output(layout.PORTFOLIO_ID, "value"),
        Input(layout.REGION_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
    )
    def sync_lgd_region_to_portfolio_options(region, current_portfolio):
        matches = models_matching(mev_catalog, "LGD", region, None, lgd_model_options)
        portfolios = model_field_values(mev_catalog, "portfolio", matches)
        options = [{"label": "All", "value": "All"}] + [{"label": p, "value": p} for p in portfolios]
        value = current_portfolio if current_portfolio in portfolios or current_portfolio == "All" else "All"
        return options, value

    @app.callback(
        Output(layout.MODEL_DROPDOWN_ID, "options"),
        Output(layout.MODEL_DROPDOWN_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MODEL_DROPDOWN_ID, "value"),
    )
    def sync_lgd_region_portfolio_to_model_options(region, portfolio, segment, current_model):
        matches = models_matching(mev_catalog, "LGD", region, portfolio, lgd_model_options)
        if segment and segment not in ("All", ""):
            segment_models = set(lgd_segment_models.get(segment, []))
            matches = [m for m in matches if m in segment_models]
        options = [{"label": "Select model", "value": ""}] + [{"label": m, "value": m} for m in matches]
        value = current_model if current_model in matches else ""
        return options, value

    def _install_lgd_store(reporting_cycle):
        from ..domain.lgd import set_lgd_metrics
        observations_by_cycle = data.get("lgd_observations_by_cycle") or {}
        cycle_data = observations_by_cycle.get(reporting_cycle)
        if cycle_data:
            merged = _merge_same_family_lgd_cycle_data(observations_by_cycle, reporting_cycle)
            set_lgd_metrics(merged["metrics_store"], merged["quarters"], merged["quarter_cycle_map"])
        else:
            set_lgd_metrics(None, [])
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
    def update_lgd_range_store(
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

    # Segment is never disabled/blocked by Model. With no model chosen, its
    # options still show every real segment plus a "Select segment"
    # placeholder (mirroring Model's own "Select model" placeholder); with a
    # model chosen, options/value resolve via get_lgd_segments_for_model /
    # resolve_lgd_segment as before.
    @app.callback(
        Output(layout.SEGMENT_DROPDOWN_ID, "options"),
        Output(layout.SEGMENT_DROPDOWN_ID, "value"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
        State(layout.SEGMENT_DROPDOWN_ID, "value"),
    )
    def sync_lgd_segment_dropdown(selected_model, selected_segment):
        has_model = bool(resolve_lgd_models(data, selected_model))
        segments = get_lgd_segments_for_model(data, selected_model)
        options = _dropdown_options(segments)
        if has_model:
            value = resolve_lgd_segment(data, selected_model, selected_segment)
        else:
            options = [{"label": "Select segment", "value": ""}] + options
            value = selected_segment if selected_segment in segments else ""
        return options, value

    # -----------------------------------------------------------------
    # Model Use Case / Cycle narrows to whichever reporting cycles actually
    # have data for the selected Model/Segment population -- see
    # sync_pd_population_to_cycle_options for the rationale.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.REPORTING_CYCLE_ID, "options"),
        Output(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
        Input(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.REPORTING_CYCLE_ID, "value"),
    )
    def sync_lgd_population_to_cycle_options(selected_model, selected_segment, current_cycle):
        has_model = bool(resolve_lgd_models(data, selected_model))
        segment_key = selected_segment if selected_segment and selected_segment not in ("", "all", "All") else "All"
        if has_model:
            cycles = lgd_model_segment_cycles.get((selected_model, segment_key))
            if cycles is None:
                cycles = lgd_model_segment_cycles.get((selected_model, "All"), [])
        elif selected_segment and selected_segment not in ("", "all", "All"):
            cycles = sorted({
                cycle
                for (population_model, population_segment), population_cycles in lgd_model_segment_cycles.items()
                if population_segment == selected_segment
                for cycle in population_cycles
            })
        else:
            cycles = None
        options = _narrow_lgd_cycle_options(cycles)
        allowed_values = {option["value"] for option in options}
        value = current_cycle if current_cycle in allowed_values else (options[0]["value"] if options else "")
        return options, value

    # -----------------------------------------------------------------
    # Scenario options come from dummy_mev_data.xlsx's "scenario" sheet: the
    # distinct "Scenario" values available for the "Run For" cycle matching
    # the selected Model Use Case / Cycle -- see sync_pd_cycle_to_scenario_options.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.SCENARIO_ID, "options"),
        Output(layout.SCENARIO_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.SCENARIO_ID, "value"),
    )
    def sync_lgd_cycle_to_scenario_options(cycle, current_scenario):
        scenarios = mev_scenarios_by_cycle.get(cycle)
        if scenarios:
            options = [option for option in _cfg_scenario_options if option["value"] in set(scenarios)] or _cfg_scenario_options
        else:
            options = _cfg_scenario_options
        allowed_values = {option["value"] for option in options}
        value = current_scenario if current_scenario in allowed_values else (options[0]["value"] if options else "")
        return options, value

    @app.callback(
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "options"),
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
        Input(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
    )
    def sync_lgd_monitoring_point_dropdown(reporting_cycle, selected_model, selected_segment, selected_monitoring_point):
        if selected_model:
            model_quarters = None
            if selected_segment:
                model_quarters = lgd_model_segment_cycle_quarters.get((selected_model, selected_segment, reporting_cycle))
            if not model_quarters:
                model_quarters = lgd_model_cycle_quarters.get((selected_model, reporting_cycle))
            options = sorted(model_quarters)[-controls.MONITORING_POINT_WINDOW:] if model_quarters else []
        else:
            options = controls.LGD_REPORTING_CYCLE_QUARTERS.get(reporting_cycle, [])
        value = filter_shell.resolve_monitoring_point_value(options, selected_monitoring_point)
        return _dropdown_options(options), value

    # -----------------------------------------------------------------
    # Scenario Ranking selector -> lgd-scenario-ranking-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.SCENARIO_RANKING_STORE_ID, "data"),
        Input(layout.SCENARIO_RANKING_FILTER_ID, "value"),
        prevent_initial_call=True,
    )
    def update_lgd_scenario_ranking_store(selected_scenarios):
        return {"scenarios": selected_scenarios or []}

    # -----------------------------------------------------------------
    # Apply is gated on a Model being selected: Segment can be browsed/picked
    # freely with no model chosen, but the dashboard itself always needs one
    # explicit model to resolve data against -- see apply_pd_filters.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLY_FILTERS_ID, "disabled"),
        Input(layout.MODEL_DROPDOWN_ID, "value"),
    )
    def sync_lgd_apply_button_availability(selected_model):
        return not bool(selected_model)

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data", allow_duplicate=True),
        Output(layout.COMPENSATING_CONTROLS_STORE_ID, "data", allow_duplicate=True),
        Output(layout.LGD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.LGD_REVIEW_FLOW_STATUS_STORE_ID, "data", allow_duplicate=True),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.SCENARIO_ID, "value"),
        State(layout.MODEL_DROPDOWN_ID, "value"),
        State(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_lgd_filters(_n_clicks, reporting_cycle, scenario, selected_model, selected_segment, selected_monitoring_point):
        """Snapshot the current top filters so the content renders only on Apply.

        Also discards the scope-specific review-flow state (unsaved reviewer sign-off draft, unsaved
        compensating-controls draft, staged RAG picks, last save-status message) -- see ``apply_pd_filters``.
        """
        if not _n_clicks or not selected_model:
            return no_update, no_update, no_update, no_update, no_update
        return {
            "reporting_cycle": reporting_cycle,
            "scenario": scenario,
            "model": selected_model,
            "segment": selected_segment,
            "monitoring_point": selected_monitoring_point,
        }, "", "", {}, ""

    # -----------------------------------------------------------------
    # Master re-render: applied store + range store -> lgd-dashboard-content
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.RANGE_STORE_ID, "data"),
        Input(layout.SCENARIO_RANKING_STORE_ID, "data"),
        Input(layout.LGD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        Input(APP_THEME_ID, "value"),
        State(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        State(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        State(layout.LGD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        # Not prevent_initial_call: a deep link from an Overview escalation
        # card (see shared.deep_link) bakes a populated APPLIED_FILTERS_STORE_ID
        # directly into this page's initial layout (page_layout, since this
        # page's stores -- unlike PD's -- are rebuilt fresh on every
        # navigation), and a full page load's very first callback batch is
        # exactly the "initial call" this flag would otherwise suppress. With
        # no deep link, ``applied`` is falsy and this just re-renders the same
        # getting-started prompt page_layout already server-rendered.
    )
    def render_lgd_content(
        applied, range_store, scenario_ranking_store, review_flow_pending_edits, theme_value,
        conclusions_notes, compensating_controls, review_flow_save_status,
    ):
        if not applied:
            return layout.build_lgd_apply_prompt()

        from ....shared.repositories.filters_config import load_filter_config
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"]
        default_scenario = cfg["scenarios"][0]["value"]

        reporting_cycle = applied.get("reporting_cycle") or default_cycle
        scenario = applied.get("scenario") or default_scenario

        _install_lgd_store(reporting_cycle)

        return layout.render_lgd_performance_content(
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
    # Reviewer conclusions textarea -> lgd-conclusions-notes-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        Input(layout.CONCLUSIONS_NOTES_ID, "value"),
        prevent_initial_call=True,
    )
    def save_lgd_conclusions_notes(value):
        return value or ""

    # -----------------------------------------------------------------
    # Compensating-controls textarea -> lgd-compensating-controls-store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        Input(layout.COMPENSATING_CONTROLS_ID, "value"),
        prevent_initial_call=True,
    )
    def save_lgd_compensating_controls(value):
        return value or ""

    # -----------------------------------------------------------------
    # Review-flow RAG pickers (Post Subjective Review / Pre-/Post-Mitigation)
    # -> lgd-review-flow-pending-store (staged only, not yet written to disk)
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.LGD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        Input({"type": layout.LGD_REVIEW_FLOW_OPTION_ID, "field": ALL}, "value"),
        State(layout.LGD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def stage_lgd_review_flow_rag(_values, pending):
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
        Output(layout.LGD_REVIEW_FLOW_PENDING_STORE_ID, "data", allow_duplicate=True),
        Output(layout.LGD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        Input(layout.LGD_REVIEW_FLOW_SAVE_ID, "n_clicks"),
        State(layout.LGD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.CONCLUSIONS_NOTES_STORE_ID, "data"),
        State(layout.COMPENSATING_CONTROLS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def save_lgd_review_flow_rag_changes(n_clicks, pending, applied, conclusions_notes, compensating_controls):
        # Same dynamic-mount quirk as the picker above: the Save button only exists once there's a
        # pending edit or commentary change, so it "just appeared" at least once and could fire
        # without a real click.
        if not n_clicks:
            return no_update, no_update

        selected_model, selected_segment, monitoring_point, reporting_cycle = _resolve_lgd_scope(data, applied)
        model, segment = lgd_store_key(selected_model, selected_segment)

        saved_fields = []
        for field, new_value in (pending or {}).items():
            if new_value not in ("Green", "Amber", "Red"):
                continue
            column = layout.LGD_REVIEW_FLOW_COLUMNS.get(field)
            if not column:
                continue
            ok = data_service.save_lgd_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point, column, new_value,
            )
            if ok:
                saved_fields.append(field)

        saved_compensating = layout.lgd_compensating_controls(selected_model, selected_segment, monitoring_point)
        if (compensating_controls or "") != (saved_compensating or ""):
            ok = data_service.save_lgd_review_flow_rag(
                data, reporting_cycle, model, segment, monitoring_point,
                layout.COMPENSATING_CONTROLS_COLUMN, compensating_controls or "",
            )
            if ok:
                saved_fields.append("compensating_controls")

        saved_commentary = layout.lgd_reviewer_commentary(selected_model, selected_segment, monitoring_point)
        if (conclusions_notes or "") != (saved_commentary or ""):
            ok = data_service.save_lgd_review_flow_rag(
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
        from ....shared.repositories.filters_config import load_filter_config
        default_scenario = load_filter_config()["scenarios"][0]["value"]
        scenario = (applied or {}).get("scenario") or default_scenario
        data_service.save_lgd_review_flow_rag(data, reporting_cycle, model, segment, monitoring_point, "scenario", scenario)

        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        count = len(saved_fields)
        return {}, f"Saved {count} change{'s' if count != 1 else ''} to portfolio.xlsx at {timestamp}."

    # -----------------------------------------------------------------
    # Keep the "Unsaved changes" bar in sync with commentary keystrokes without
    # rebuilding the whole tab (which would drop the textarea's cursor/focus).
    # RAG picks already rebuild the whole tab (layout.LGD_REVIEW_FLOW_PENDING_STORE_ID
    # is an Input there), so this callback only needs to add live text typing to the mix.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.LGD_REVIEW_FLOW_SAVE_BAR_ID, "children"),
        Input(layout.CONCLUSIONS_NOTES_ID, "value"),
        Input(layout.COMPENSATING_CONTROLS_ID, "value"),
        Input(layout.LGD_REVIEW_FLOW_PENDING_STORE_ID, "data"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.LGD_REVIEW_FLOW_STATUS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def sync_lgd_review_flow_save_bar(conclusions_notes, compensating_controls, pending, applied, save_status):
        selected_model, selected_segment, monitoring_point, _reporting_cycle = _resolve_lgd_scope(data, applied)
        review_flow_rags = layout.lgd_review_flow_rags(selected_model, selected_segment, monitoring_point)
        saved_commentary = layout.lgd_reviewer_commentary(selected_model, selected_segment, monitoring_point)
        saved_compensating = layout.lgd_compensating_controls(selected_model, selected_segment, monitoring_point)
        commentary_changed = (conclusions_notes or "") != (saved_commentary or "")
        compensating_changed = (compensating_controls or "") != (saved_compensating or "")
        save_bar = layout.build_lgd_review_flow_save_bar(
            pending or {}, review_flow_rags, save_status, commentary_changed, compensating_changed,
        )
        return [save_bar] if save_bar is not None else []
