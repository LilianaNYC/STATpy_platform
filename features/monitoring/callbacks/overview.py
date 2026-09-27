"""Callbacks for the Overview page."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, no_update

from ..ui import common as filter_shell
from ..ui.views import overview as layout
from ....shared.ui import controls
from ....shared.registration import already_registered
from ....shared.theme import APP_THEME_ID, URL_ID, normalize_theme_value
from ..data_access import PD_PERFORMANCE_DATA
from ..domain.overview import (
    overview_cycle_options,
    overview_model_cycle_quarters,
    overview_model_cycles,
    overview_model_options,
    overview_portfolio_options,
    overview_use_case_options,
)

_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}
_OVERVIEW_PATH = "/overview"


def _overview_filter_snapshot(
    reporting_cycle: str | None,
    monitoring_point: str | None,
    segment_model_group: str | None,
    selected_models: list[str] | None = None,
    region: str | None = None,
    portfolio: str | None = None,
) -> dict[str, str]:
    """Build an applied snapshot that matches the values visible in the top bar.

    ``region``/``portfolio`` scope the content indirectly -- they narrow the Model
    selection, which is what the charts are built from -- but they are recorded
    here so the rendered scope chip can state the full applied scope rather than
    leaving the reader to infer it from the model list.
    """
    cycle = str(reporting_cycle or "").strip()
    valid_points = controls.ALL_REPORTING_CYCLE_QUARTERS.get(cycle, [])
    resolved_point = filter_shell.resolve_monitoring_point_value(valid_points, monitoring_point)
    return {
        "reporting_cycle": cycle,
        "monitoring_point": resolved_point,
        "segment_model_group": str(segment_model_group or "All"),
        "models": list(selected_models or []),
        "region": str(region or "All"),
        "portfolio": str(portfolio or "All"),
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
    model_cycles = overview_model_cycles(data)
    model_cycle_quarters = overview_model_cycle_quarters(data)


    for value_id, toggle_id, menu_id, filter_key in (
        (layout.REGION_ID, layout.REGION_TOGGLE_ID, layout.REGION_MENU_ID, layout.REGION_FILTER_KEY),
        (layout.PORTFOLIO_ID, layout.PORTFOLIO_TOGGLE_ID, layout.PORTFOLIO_MENU_ID, layout.PORTFOLIO_FILTER_KEY),
        (layout.MODEL_USE_CASE_ID, layout.MODEL_USE_CASE_TOGGLE_ID, layout.MODEL_USE_CASE_MENU_ID, layout.MODEL_USE_CASE_FILTER_KEY),
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

    # -----------------------------------------------------------------
    # The top filter bar narrows strictly left to right:
    #
    #   Region -> Portfolio -> Model Use Case -> Reporting Cycle
    #          -> Model Group -> Model -> Monitoring Point
    #
    # So Cycle is narrowed by Model Use Case alone, and Cycle in turn narrows
    # Model (in sync_overview_model_options below). This REVERSES the previous
    # model-to-cycle direction, which was correct while Model sat to the left of
    # Cycle. Keeping both directions would close a dependency loop
    # (Model -> Cycle -> Model), which is exactly what callback rule 2 forbids,
    # so the model axis is deliberately gone from this callback.
    #
    # ``current_cycle`` stays a State purely to preserve a still-valid pick.
    # -----------------------------------------------------------------
    def _rescope(options, current, filter_key):
        """Re-narrowed options, led by their "Select …" placeholder, plus the
        value to write.

        Keeps a still-valid selection and otherwise leaves the filter
        **unanswered** -- it must never answer one for the user, which is what
        taking ``options[0]`` used to do. That mattered more once the page
        started empty: the cascade runs on first render, so a first-option
        fallback would have filled the whole bar in before the user touched it.
        """
        options = controls.with_placeholder(options, filter_key)
        return options, controls.keep_or_unselected(options, current)

    @app.callback(
        Output(layout.PORTFOLIO_ID, "options"),
        Output(layout.PORTFOLIO_ID, "value"),
        Input(layout.REGION_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
    )
    def sync_overview_portfolio_options(region, current_portfolio):
        return _rescope(overview_portfolio_options(data, region), current_portfolio, "portfolio")

    @app.callback(
        Output(layout.MODEL_USE_CASE_ID, "options"),
        Output(layout.MODEL_USE_CASE_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        State(layout.MODEL_USE_CASE_ID, "value"),
    )
    def sync_overview_use_case_options(region, portfolio, current_use_case):
        return _rescope(
            overview_use_case_options(data, region, portfolio), current_use_case, "model-use-case"
        )

    @app.callback(
        Output(layout.REPORTING_CYCLE_ID, "options"),
        Output(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.MODEL_USE_CASE_ID, "value"),
        State(layout.REPORTING_CYCLE_ID, "value"),
    )
    def sync_overview_cycle_options(region, portfolio, model_use_case, current_cycle):
        return _rescope(
            overview_cycle_options(data, region, portfolio, model_use_case),
            current_cycle,
            "reporting-cycle",
        )

    @app.callback(
        Output(layout.MONITORING_POINT_ID, "options"),
        Output(layout.MONITORING_POINT_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.OVERVIEW_MODEL_ID, "value"),
        State(layout.MONITORING_POINT_ID, "value"),
    )
    def sync_overview_monitoring_point_dropdown(reporting_cycle, selected_models, selected_monitoring_point):
        quarters: set[str] = set()
        for model in selected_models or []:
            quarters.update(model_cycle_quarters.get((model, reporting_cycle), set()))
        ascending = sorted(quarters) if quarters else controls.ALL_REPORTING_CYCLE_QUARTERS.get(reporting_cycle, [])
        # Display most-recent-first, matching Reporting Cycle above it. No
        # resolve_monitoring_point_value here any more: it picks the latest
        # quarter when the current value does not fit, which would answer the
        # filter for the user on the very first render.
        options = controls.with_placeholder(
            [{"label": option, "value": option} for option in reversed(ascending)], "monitoring-point")
        return options, controls.keep_or_unselected(options, selected_monitoring_point)

    # -----------------------------------------------------------------
    # Model checkbox dropdown: open/close, options narrowed by Model Group
    # (live, like sync_overview_monitoring_point_dropdown above), and the
    # toggle button's summary label.
    # -----------------------------------------------------------------
    @app.callback(
        Output(layout.OVERVIEW_MODEL_MENU_ID, "className"),
        Input(layout.OVERVIEW_MODEL_TOGGLE_ID, "n_clicks"),
        State(layout.OVERVIEW_MODEL_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_overview_model_menu(_n_clicks, current_class):
        if "open" in (current_class or "").split():
            return "checkbox-dropdown-menu"
        return "checkbox-dropdown-menu open"

    @app.callback(
        Output(layout.OVERVIEW_MODEL_ID, "options"),
        Output(layout.OVERVIEW_MODEL_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.SEGMENT_MODEL_GROUP_ID, "value"),
        State(layout.OVERVIEW_MODEL_ID, "value"),
    )
    def sync_overview_model_options(region, portfolio, reporting_cycle, segment_model_group, current_value):
        options = overview_model_options(
            data,
            segment_model_group,
            region=region,
            portfolio=portfolio,
            reporting_cycle=reporting_cycle,
        )
        # Keep whatever survives the narrowing, and nothing more. This used to
        # select *every* model when the survivors were empty, which on the
        # now-empty first render meant the Model filter answered itself.
        option_values = {option["value"] for option in options}
        return options, [v for v in (current_value or []) if v in option_values]

    @app.callback(
        Output(layout.OVERVIEW_MODEL_TOGGLE_ID, "children"),
        Input(layout.OVERVIEW_MODEL_ID, "value"),
        Input(layout.OVERVIEW_MODEL_ID, "options"),
    )
    def sync_overview_model_toggle_label(value, options):
        return layout.model_toggle_label(value, options)

    @app.callback(
        Output(layout.OVERVIEW_MODEL_ID, "value", allow_duplicate=True),
        Output(layout.OVERVIEW_MODEL_SELECT_ALL_ID, "value"),
        Input(layout.OVERVIEW_MODEL_SELECT_ALL_ID, "value"),
        Input(layout.OVERVIEW_MODEL_ID, "value"),
        State(layout.OVERVIEW_MODEL_ID, "options"),
        prevent_initial_call=True,
    )
    def sync_overview_model_select_all(select_all_value, models_value, options):
        option_values = [option["value"] for option in (options or [])]
        current_values = list(models_value or [])
        if ctx.triggered_id == layout.OVERVIEW_MODEL_SELECT_ALL_ID:
            if "all" in (select_all_value or []):
                return list(option_values), no_update
            return [], no_update
        select_all = ["all"] if option_values and set(option_values).issubset(current_values) else []
        return no_update, select_all

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
        State(layout.REGION_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
        State(layout.REPORTING_CYCLE_ID, "value"),
        State(layout.MONITORING_POINT_ID, "value"),
        State(layout.SEGMENT_MODEL_GROUP_ID, "value"),
        State(layout.OVERVIEW_MODEL_ID, "value"),
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
        region,
        portfolio,
        reporting_cycle,
        monitoring_point,
        segment_model_group,
        selected_models,
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
            selected_models,
            region=region,
            portfolio=portfolio,
        )

    # -----------------------------------------------------------------
    # Apply button dirty state: the page is Apply-gated, so the button says
    # whether the top bar still matches what is rendered below. Purely
    # presentational -- it only ever writes the button's own className, and
    # nothing reads that back, so it adds no edge to the filter cascade.
    # -----------------------------------------------------------------
    # The same callback also owns the Apply **gate**. The page opens with every
    # filter unanswered, so Apply stays disabled until all seven have a real
    # value -- nothing can be applied against a half-specified scope. Folded in
    # here rather than split out because it reads exactly the same Inputs, and
    # both outputs are the button's own props.
    @app.callback(
        Output(layout.APPLY_FILTERS_ID, "className"),
        Output(layout.APPLY_FILTERS_ID, "disabled"),
        Input(layout.REGION_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.MODEL_USE_CASE_ID, "value"),
        Input(layout.REPORTING_CYCLE_ID, "value"),
        Input(layout.SEGMENT_MODEL_GROUP_ID, "value"),
        Input(layout.OVERVIEW_MODEL_ID, "value"),
        Input(layout.MONITORING_POINT_ID, "value"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
    )
    def sync_overview_apply_state(
        region, portfolio, use_case, reporting_cycle, segment_model_group,
        selected_models, monitoring_point, applied,
    ):
        class_name = layout.apply_button_class(
            _overview_filter_snapshot(
                reporting_cycle, monitoring_point, segment_model_group,
                selected_models, region=region, portfolio=portfolio,
            ),
            applied,
        )
        # ``selected_models`` is a list -- a non-empty one counts as answered.
        complete = controls.all_selected(
            region, portfolio, use_case, reporting_cycle,
            segment_model_group, monitoring_point,
        ) and bool(selected_models)
        return class_name, not complete

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
        default_cycle = cfg["reporting_cycles"][0]["value"]

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
            selected_models=applied.get("models"),
            region=applied.get("region") or "All",
            portfolio=applied.get("portfolio") or "All",
        )
        return children, scoped_rows, segment_scoped_rows

    # -----------------------------------------------------------------
    # Interactive RAG journey: aggregate counts -> RAG bucket -> entity.
    # Both responsive graph variants share one selection store so a resize
    # never loses the user's current focus.
    # -----------------------------------------------------------------
    # Applying filters clears the current RAG-journey focus: the selected
    # model/segment belongs to the old scope. This is deliberately its own
    # callback rather than another branch of update_rag_flow_selection below.
    # That one's Inputs are the flow graphs and buttons, which live inside the
    # callback-rendered ``overview-content``; driving it from the applied-filters
    # store -- which lives outside that container -- meant it fired at the moment
    # the graphs did not exist yet, so the renderer failed to gather its Inputs
    # and the reset silently never ran.
    @app.callback(
        Output(layout.RAG_FLOW_SELECTION_STORE_ID, "data", allow_duplicate=True),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def reset_rag_flow_selection_on_apply(_applied):
        return {"model": None, "segment": None}

    @app.callback(
        Output(layout.RAG_FLOW_SELECTION_STORE_ID, "data"),
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
