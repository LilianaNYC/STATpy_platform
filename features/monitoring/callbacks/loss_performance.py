"""Callbacks for the Loss Performance page."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import loss_performance as layout
from ....shared.ui import controls
from ..domain.loss import (
    get_loss_segments_for_model,
)
from ....shared.registration import already_registered
from ....shared.repositories.filters_config import cycle_family
from ....shared.repositories.filters_config import cycle_options_for_cycles
from ....shared.theme import APP_THEME_ID
from ..data_access import PD_PERFORMANCE_DATA

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}


def _dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _merge_same_family_loss_cycle_data(observations_by_cycle: dict, reporting_cycle: str) -> dict:
    """Pool ``loss_observations_by_cycle`` across every cycle in the same
    family as ``reporting_cycle`` -- see the equivalent
    ``_merge_same_family_lgd_cycle_data`` in ``lgd_performance.py``.
    """
    family = cycle_family(reporting_cycle)
    quarters: set[str] = set()
    metrics_store: dict[tuple[str, str], list[dict]] = {}
    for cycle, cycle_data in (observations_by_cycle or {}).items():
        if cycle_family(cycle) != family:
            continue
        quarters.update(cycle_data.get("quarters") or [])
        for key, rows in (cycle_data.get("metrics_store") or {}).items():
            metrics_store.setdefault(key, []).extend(dict(row, reporting_cycle=cycle) for row in rows)
    for rows in metrics_store.values():
        rows.sort(key=lambda row: row.get("Monitoring Period") or "")
    return {"quarters": sorted(quarters), "metrics_store": metrics_store}


def register_callbacks(app) -> None:
    """Register Loss Performance callbacks against ``app`` (idempotent)."""
    if already_registered(app, "page:monitoring.loss_performance"):
        return

    data = PD_PERFORMANCE_DATA
    mev_scenarios_by_cycle = data.get("mev_scenarios_by_cycle") or {}

    from ....shared.repositories.filters_config import load_filter_config as _load_filter_config
    # with_placeholder: every option list a callback writes has to carry the
    # "Select …" entry, or the value "" matches no option and the shell's toggle
    # falls back to a bare "Select" (see _option_label).
    _cfg_scenario_options = controls.with_placeholder(
        [{"label": s["label"], "value": s["value"]} for s in _load_filter_config()["scenarios"]],
        "scenario",
    )

    for value_id, toggle_id, menu_id, filter_key in (
        (layout.MODEL_USE_CASE_ID, layout.MODEL_USE_CASE_TOGGLE_ID, layout.MODEL_USE_CASE_MENU_ID, layout.MODEL_USE_CASE_FILTER_KEY),
        (layout.REPORTING_CYCLE_ID, layout.REPORTING_CYCLE_TOGGLE_ID, layout.REPORTING_CYCLE_MENU_ID, layout.REPORTING_CYCLE_FILTER_KEY),
        (layout.MONITORING_POINT_DROPDOWN_ID, layout.MONITORING_POINT_TOGGLE_ID, layout.MONITORING_POINT_MENU_ID, layout.MONITORING_POINT_FILTER_KEY),
        (layout.SEGMENT_DROPDOWN_ID, layout.SEGMENT_TOGGLE_ID, layout.SEGMENT_MENU_ID, layout.SEGMENT_FILTER_KEY),
        (layout.MODEL_DROPDOWN_ID, layout.MODEL_TOGGLE_ID, layout.MODEL_MENU_ID, layout.MODEL_FILTER_KEY),
        # Region/Portfolio/Model Group: Loss has no entries in dummy_mev_data.xlsx
        # (no per-model Region/Portfolio, and only one implicit "model"), so these
        # are fixed, single-option placeholders for positional consistency with
        # the other three tabs -- not wired to narrow anything.
        (layout.REGION_ID, layout.REGION_TOGGLE_ID, layout.REGION_MENU_ID, layout.REGION_FILTER_KEY),
        (layout.PORTFOLIO_ID, layout.PORTFOLIO_TOGGLE_ID, layout.PORTFOLIO_MENU_ID, layout.PORTFOLIO_FILTER_KEY),
        # Scenario: net new here (Loss has no Loss_Sensitivity_Projections sheet,
        # so nothing downstream reads it) -- present for bar consistency only.
        (layout.SCENARIO_ID, layout.SCENARIO_TOGGLE_ID, layout.SCENARIO_MENU_ID, layout.SCENARIO_FILTER_KEY),
    ):
        filter_shell.register_single_select_callbacks(
            app,
            value_id=value_id,
            toggle_id=toggle_id,
            menu_id=menu_id,
            filter_key=filter_key,
        )

    # -----------------------------------------------------------------
    # Scenario options come from dummy_mev_data.xlsx's "scenario" sheet: the
    # distinct "Scenario" values available for the "Run For" cycle matching
    # the selected Model Use Case / Cycle -- see sync_pd_cycle_to_scenario_options.
    # Still unwired to anything downstream (see the Scenario registration note
    # above), but its own options/value now stay consistent with the other tabs.
    # -----------------------------------------------------------------
    # -----------------------------------------------------------------
    # Model Use Case -> Reporting Cycle. Loss has a single portfolio-wide
    # entity, so unlike the other tabs there is no Model/Segment population to
    # narrow by -- the use case is the only scope the cycle list depends on.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.REPORTING_CYCLE_ID, "options"),
        Output(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.MODEL_USE_CASE_ID, "value"),
        State(layout.REPORTING_CYCLE_ID, "value"),
    )
    def sync_loss_use_case_to_cycle_options(model_use_case, current_cycle):
        # with_placeholder on every rewrite: the value "" must match an option,
        # or the shell's toggle falls back to a bare "Select" (see _option_label).
        options = controls.with_placeholder(
            cycle_options_for_cycles(None, model_use_case), "reporting-cycle")
        value = controls.keep_or_unselected(options, current_cycle)
        return options, value

    @app.callback(
        Output(layout.SCENARIO_ID, "options"),
        Output(layout.SCENARIO_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.SCENARIO_ID, "value"),
    )
    def sync_loss_cycle_to_scenario_options(cycle, current_scenario):
        scenarios = mev_scenarios_by_cycle.get(cycle)
        if scenarios:
            options = [option for option in _cfg_scenario_options if option["value"] in set(scenarios)] or _cfg_scenario_options
        else:
            options = _cfg_scenario_options
        allowed_values = {option["value"] for option in options}
        value = controls.keep_or_unselected(options, current_scenario)
        return options, value

    def _install_loss_store(reporting_cycle):
        from ..domain.loss import set_loss_metrics
        observations_by_cycle = data.get("loss_observations_by_cycle") or {}
        cycle_data = observations_by_cycle.get(reporting_cycle)
        if cycle_data:
            merged = _merge_same_family_loss_cycle_data(observations_by_cycle, reporting_cycle)
            set_loss_metrics(merged["metrics_store"], merged["quarters"])
        else:
            set_loss_metrics(None, [])
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
    def update_loss_range_store(
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
    def sync_loss_segment_dropdown(selected_model, selected_segment):
        segments = get_loss_segments_for_model(data, selected_model)
        options = controls.with_placeholder(_dropdown_options(segments), "portfolio-segment")
        # Segment stays unanswered until the user answers it, exactly like every
        # other filter -- matching PD. Picking a Model used to run
        # resolve_loss_segment here, which never returns empty: it falls back to
        # "All", or to ``segments[0]`` when the model has no "All" aggregate row.
        # For a single-segment model that was harmless, but a model with five
        # segments had the choice made for it (LGD Model A silently became
        # "Cyclical"), which is the auto-selection the empty start removes.
        #
        # resolve_loss_segment is still the right call elsewhere -- the page
        # layout uses it for deep links, which name a scope deliberately.
        value = controls.keep_or_unselected(options, selected_segment)
        return options, value

    @app.callback(
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "options"),
        Output(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
    )
    def sync_loss_monitoring_point_dropdown(reporting_cycle, selected_monitoring_point):
        quarters = controls.LOSS_REPORTING_CYCLE_QUARTERS.get(reporting_cycle, [])
        # Display most-recent-first, matching Reporting Cycle. No
        # resolve_monitoring_point_value: it answers the filter with the latest
        # quarter, which on the empty first render fills it in unasked.
        options = controls.with_placeholder(
            _dropdown_options(list(reversed(quarters))), "monitoring-point")
        return options, controls.keep_or_unselected(options, selected_monitoring_point)

    # -----------------------------------------------------------------
    # Apply is gated on a Model being selected: Segment can be browsed/picked
    # freely with no model chosen, but the dashboard itself always needs one
    # explicit model to resolve data against -- see apply_pd_filters, and
    # matches LGD/EAD's sync_lgd_apply_button_availability /
    # sync_ead_apply_button_availability.
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
        Input(layout.SCENARIO_ID, "value"),
    )
    def sync_loss_apply_button_availability(*filter_values):
        return not controls.all_selected(*filter_values)

    # -----------------------------------------------------------------
    # Apply filters: snapshot current filter values into the applied store
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.MODEL_DROPDOWN_ID, "value"),
        State(layout.SEGMENT_DROPDOWN_ID, "value"),
        State(layout.MONITORING_POINT_DROPDOWN_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_loss_filters(_n_clicks, reporting_cycle, selected_model, selected_segment, selected_monitoring_point):
        # The button is disabled without a model, but a stale click event is
        # still guarded here -- see apply_lgd_filters / apply_ead_filters.
        if not _n_clicks or not selected_model:
            return no_update
        return {
            "reporting_cycle": reporting_cycle,
            "model": selected_model,
            "segment": selected_segment,
            "monitoring_point": selected_monitoring_point,
        }

    # -----------------------------------------------------------------
    # Master re-render: applied store + range store -> loss-dashboard-content
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.CONTENT_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.RANGE_STORE_ID, "data"),
        Input(APP_THEME_ID, "value"),
        # Not prevent_initial_call: see the matching comment in
        # callbacks/lgd_performance.py's render_lgd_content -- a deep-linked
        # APPLIED_FILTERS_STORE_ID is baked into this page's initial layout,
        # and needs this callback's first ("initial call") batch to fire.
    )
    def render_loss_content(applied, range_store, theme_value):
        if not applied:
            return layout.build_loss_apply_prompt()

        from ....shared.repositories.filters_config import load_filter_config
        cfg = load_filter_config()
        default_cycle = cfg["reporting_cycles"][0]["value"]

        reporting_cycle = applied.get("reporting_cycle") or default_cycle
        _install_loss_store(reporting_cycle)

        return layout.render_loss_performance_content(
            data,
            applied.get("model"),
            applied.get("segment"),
            applied.get("monitoring_point"),
            range_store or {},
            theme_value=theme_value,
        )
