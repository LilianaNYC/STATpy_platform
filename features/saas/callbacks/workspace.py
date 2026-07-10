"""Callbacks for the SAAS workspace."""

from __future__ import annotations

from datetime import datetime

from dash import ALL, MATCH, Input, Output, State, ctx, dcc, no_update
from dash.exceptions import PreventUpdate

from ....shared.ui import controls as shared_filters
from ....shared.ui.charts import SAAS_SCENARIO_LABEL_MAP
from ....shared import theme
from ....shared.registration import already_registered
from ..data_access import SAAS_PAGE_DATA
from ..services import exports, reports
from ..ui.views import figures, workspace as layout, components as views
from ..domain import metrics, records, selectors

_is_segment_active = selectors.is_segment_active
_active_segment_values = selectors.active_segment_values
_segment_toggle_label = selectors.segment_toggle_label
_normalize_selected_run_fors = selectors.normalize_selected_run_fors
_normalize_compare_against_values = selectors.normalize_compare_against_values
_scoped_run_for_values = selectors.scoped_run_for_values
_run_for_meta_label = selectors.run_for_meta_label
_build_compare_against_options = selectors.build_compare_against_options
_compare_against_toggle_label = selectors.compare_against_toggle_label
_model_options_for_filters = selectors.model_options_for_filters
_model_group_options_for_filters = selectors.model_group_options_for_filters
_portfolio_options_for_filters = selectors.portfolio_options_for_filters
_segment_options_for_filters = selectors.segment_options_for_filters
_is_region_active = selectors.is_region_active
_is_model_group_active = selectors.is_model_group_active
_is_portfolio_active = selectors.is_portfolio_active
_model_toggle_label = selectors.model_toggle_label
_normalize_selected_models = selectors.normalize_selected_models
_normalize_multi_values = selectors.normalize_multi_values
_normalize_selected_mevs = selectors.normalize_selected_mevs
_normalize_selected_mev_mode = selectors.normalize_selected_mev_mode
_normalize_snapshot_period = selectors.normalize_snapshot_period
_normalize_mev_label_mode = selectors.normalize_mev_label_mode
_normalize_theme_value = selectors.normalize_theme_value
_effective_model_names = selectors.effective_model_names
_group_effective_models = selectors.group_effective_models
_primary_run_for_value = selectors.primary_run_for_value
_show_historical_statistics = selectors.show_historical_statistics
_compute_saas_metrics = metrics.compute_saas_metrics
_compute_saas_reconciliation = metrics.compute_saas_reconciliation
_compute_saas_projection_comparison = metrics.compute_saas_projection_comparison
_available_date_periods = records.available_date_periods
_filter_records_by_snapshot_period = records.filter_records_by_snapshot_period
_filter_records_by_date_range = records.filter_records_by_date_range
_build_model_mev_options_for_mode = records.build_model_mev_options_for_mode
_build_family_mev_options_for_mode = records.build_family_mev_options_for_mode
_active_selected_mevs = records.active_selected_mevs
_single_select_option_classes = views.single_select_option_classes
_toggle_menu_class = views.toggle_menu_class
_build_empty_state = views.build_empty_state
_mev_picker_label = views.mev_picker_label
_mev_picker_section_class = views.mev_picker_section_class
_build_single_mev_option_buttons = views.build_single_mev_option_buttons
_scenario_toggle_label = views.scenario_toggle_label
_single_selected_scenario = views.single_selected_scenario
_mev_type_toggle_label = views.mev_type_toggle_label
_mev_toggle_label = views.mev_toggle_label


def _register_menu_callbacks(app) -> None:
    @app.callback(
        Output(layout.RUN_FOR_MENU_ID, "className"),
        Input(layout.RUN_FOR_TOGGLE_ID, "n_clicks"),
        State(layout.RUN_FOR_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_run_for_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output(layout.COMPARE_AGAINST_MENU_ID, "className"),
        Input(layout.COMPARE_AGAINST_TOGGLE_ID, "n_clicks"),
        State(layout.COMPARE_AGAINST_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_compare_against_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu")

    @app.callback(
        Output(layout.SEGMENT_MENU_ID, "className"),
        Input(layout.SEGMENT_TOGGLE_ID, "n_clicks"),
        State(layout.SEGMENT_MENU_ID, "className"),
        State(layout.SEGMENT_TOGGLE_ID, "disabled"),
        prevent_initial_call=True,
    )
    def toggle_segment_menu(_n_clicks, current_class, is_disabled):
        if is_disabled:
            return "checkbox-dropdown-menu"
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu")

    @app.callback(
        Output(layout.REGION_MENU_ID, "className"),
        Input(layout.REGION_TOGGLE_ID, "n_clicks"),
        State(layout.REGION_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_region_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output(layout.MODEL_GROUP_MENU_ID, "className"),
        Input(layout.MODEL_GROUP_TOGGLE_ID, "n_clicks"),
        State(layout.MODEL_GROUP_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_model_group_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output(layout.PORTFOLIO_MENU_ID, "className"),
        Input(layout.PORTFOLIO_TOGGLE_ID, "n_clicks"),
        State(layout.PORTFOLIO_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_portfolio_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output(layout.SUBNAV_VIEW_MENU_ID, "className"),
        Input(layout.SUBNAV_VIEW_TOGGLE_ID, "n_clicks"),
        State(layout.SUBNAV_VIEW_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_subnav_view_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output(layout.REFERENCE_LINES_MENU_ID, "className"),
        Input(layout.REFERENCE_LINES_TOGGLE_ID, "n_clicks"),
        State(layout.REFERENCE_LINES_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_reference_lines_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output(layout.MEV_LABEL_MODE_MENU_ID, "className"),
        Input(layout.MEV_LABEL_MODE_TOGGLE_ID, "n_clicks"),
        State(layout.MEV_LABEL_MODE_MENU_ID, "className"),
        prevent_initial_call=True,
    )
    def toggle_mev_label_mode_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output({"type": layout.MODEL_SCENARIO_MENU_TYPE, "model": MATCH}, "className"),
        Input({"type": layout.MODEL_SCENARIO_TOGGLE_TYPE, "model": MATCH}, "n_clicks"),
        State({"type": layout.MODEL_SCENARIO_MENU_TYPE, "model": MATCH}, "className"),
        prevent_initial_call=True,
    )
    def toggle_model_scenario_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu")

    @app.callback(
        Output({"type": layout.MODEL_MEV_TYPE_MENU_TYPE, "model": MATCH}, "className"),
        Input({"type": layout.MODEL_MEV_TYPE_TOGGLE_TYPE, "model": MATCH}, "n_clicks"),
        State({"type": layout.MODEL_MEV_TYPE_MENU_TYPE, "model": MATCH}, "className"),
        prevent_initial_call=True,
    )
    def toggle_model_mev_type_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu single-select-menu")

    @app.callback(
        Output(layout.MODEL_NAME_MENU_ID, "className"),
        Input(layout.MODEL_NAME_TOGGLE_ID, "n_clicks"),
        State(layout.MODEL_NAME_MENU_ID, "className"),
        State(layout.MODEL_NAME_TOGGLE_ID, "disabled"),
        prevent_initial_call=True,
    )
    def toggle_model_menu(_n_clicks, current_class, is_disabled):
        if is_disabled:
            return "checkbox-dropdown-menu"
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu")

    @app.callback(
        Output({"type": layout.MODEL_MEV_MENU_TYPE, "model": MATCH}, "className"),
        Input({"type": layout.MODEL_MEV_TOGGLE_TYPE, "model": MATCH}, "n_clicks"),
        State({"type": layout.MODEL_MEV_MENU_TYPE, "model": MATCH}, "className"),
        prevent_initial_call=True,
    )
    def toggle_model_mev_menu(_n_clicks, current_class):
        return _toggle_menu_class(current_class, base_class="checkbox-dropdown-menu")


def _register_single_select_callbacks(app) -> None:
    @app.callback(
        Output(layout.RUN_FOR_ID, "value", allow_duplicate=True),
        Output(layout.RUN_FOR_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.RUN_FOR_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_run_for(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(layout.REGION_ID, "value", allow_duplicate=True),
        Output(layout.REGION_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.REGION_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_region(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(layout.MODEL_GROUP_ID, "value", allow_duplicate=True),
        Output(layout.MODEL_GROUP_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.MODEL_GROUP_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_model_group(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(layout.PORTFOLIO_ID, "value", allow_duplicate=True),
        Output(layout.PORTFOLIO_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.PORTFOLIO_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_portfolio(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(layout.SUBNAV_VIEW_ID, "value", allow_duplicate=True),
        Output(layout.SUBNAV_VIEW_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.SUBNAV_VIEW_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_subnav_view(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(layout.REFERENCE_LINES_ID, "value", allow_duplicate=True),
        Output(layout.REFERENCE_LINES_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.REFERENCE_LINES_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_reference_lines(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(layout.MEV_LABEL_MODE_ID, "value", allow_duplicate=True),
        Output(layout.MEV_LABEL_MODE_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.MEV_LABEL_MODE_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_mev_label_mode(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output(layout.HISTORICAL_STATS_ID, "value", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.HISTORICAL_STATS_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_historical_stats_toggle(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update
        return triggered["value"]


def _register_shell_callbacks(
    app,
    run_for_labels,
    region_labels,
    model_group_labels,
    portfolio_labels,
    subnav_view_labels,
    reference_line_labels,
    mev_label_mode_labels,
) -> None:
    @app.callback(
        Output(layout.RUN_FOR_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.RUN_FOR_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.RUN_FOR_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.RUN_FOR_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_run_for_shell(value, option_ids):
        label = run_for_labels.get(value, value or "Select")
        return label, _single_select_option_classes(value, option_ids)

    @app.callback(
        Output(layout.DOWNLOAD_REPORT_ID, "disabled"),
        Output(layout.EXCEL_OPEN_ID, "disabled"),
        Output(layout.EXPORT_ACTIONS_ID, "className"),
        Output(layout.EXPORT_ACTIONS_ID, "open"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
    )
    def sync_export_shell(applied_filters):
        has_applied_filters = bool(applied_filters)
        class_name = "saas-download-actions" if has_applied_filters else "saas-download-actions is-disabled"
        return (not has_applied_filters, not has_applied_filters, class_name, False)

    @app.callback(
        Output(layout.SEGMENT_TOGGLE_ID, "children"),
        Input(layout.SEGMENT_NAME_ID, "value"),
    )
    def sync_segment_toggle(segment_values):
        return _segment_toggle_label(segment_values)

    @app.callback(
        Output(layout.REGION_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.REGION_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.REGION_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.REGION_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_region_shell(value, option_ids):
        label = region_labels.get(value, value or "Select")
        return label, _single_select_option_classes(value, option_ids)

    @app.callback(
        Output(layout.MODEL_GROUP_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.MODEL_GROUP_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.MODEL_GROUP_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.MODEL_GROUP_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_model_group_shell(value, option_ids):
        label = model_group_labels.get(value, value or "Select")
        return label, _single_select_option_classes(value, option_ids)

    @app.callback(
        Output(layout.PORTFOLIO_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.PORTFOLIO_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.PORTFOLIO_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.PORTFOLIO_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_portfolio_shell(value, option_ids):
        label = portfolio_labels.get(value, value or "Select")
        return label, _single_select_option_classes(value, option_ids)

    @app.callback(
        Output(layout.SUBNAV_VIEW_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.SUBNAV_VIEW_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.SUBNAV_VIEW_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.SUBNAV_VIEW_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_subnav_view_shell(value, option_ids):
        label = subnav_view_labels.get(value, value or "Select")
        return label, _single_select_option_classes(value, option_ids)

    @app.callback(
        Output(layout.REFERENCE_LINES_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.REFERENCE_LINES_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.REFERENCE_LINES_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.REFERENCE_LINES_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_reference_lines_shell(value, option_ids):
        label = reference_line_labels.get(value, value or "Select")
        return label, _single_select_option_classes(value, option_ids)

    @app.callback(
        Output(layout.MEV_LABEL_MODE_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.MEV_LABEL_MODE_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.MEV_LABEL_MODE_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.MEV_LABEL_MODE_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_mev_label_mode_shell(value, option_ids):
        label_mode_value = _normalize_mev_label_mode(value)
        label = mev_label_mode_labels.get(label_mode_value, label_mode_value or "Select")
        return label, _single_select_option_classes(label_mode_value, option_ids)

    @app.callback(
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.HISTORICAL_STATS_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.HISTORICAL_STATS_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.HISTORICAL_STATS_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_historical_stats_toggle(value, option_ids):
        return _single_select_option_classes(value, option_ids)


def _register_model_picker_callbacks(app) -> None:
    @app.callback(
        Output({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "value", allow_duplicate=True),
        Output({"type": layout.MODEL_SCENARIO_SELECT_ALL_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_SCENARIO_SELECT_ALL_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "value"),
        State({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "options"),
        State(layout.REFERENCE_LINES_ID, "value"),
        prevent_initial_call=True,
    )
    def sync_model_scenario_selection(select_all_value, selected_scenarios, scenario_options, reference_lines):
        all_scenario_values = [option["value"] for option in scenario_options if option.get("value")]
        if (reference_lines or layout.DEFAULT_REFERENCE_LINES) == "monitoring":
            selected_value = _single_selected_scenario(selected_scenarios, scenario_options or [])
            return selected_value, []
        if ctx.triggered_id and ctx.triggered_id.get("type") == layout.MODEL_SCENARIO_SELECT_ALL_TYPE:
            if "all" in (select_all_value or []):
                return all_scenario_values, no_update
            return [], no_update
        select_all = ["all"] if all_scenario_values and set(selected_scenarios or []) == set(all_scenario_values) else []
        return no_update, select_all

    @app.callback(
        Output({"type": layout.MODEL_SCENARIO_TOGGLE_TYPE, "model": MATCH}, "children"),
        Input({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "value"),
        State({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "options"),
    )
    def sync_model_scenario_toggle(selected_scenarios, scenario_options):
        return _scenario_toggle_label(selected_scenarios, scenario_options or [])

    @app.callback(
        Output({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "value", allow_duplicate=True),
        Output({"type": layout.MODEL_SCENARIO_MENU_TYPE, "model": MATCH}, "className", allow_duplicate=True),
        Input({"type": layout.MODEL_SCENARIO_OPTION_TYPE, "model": MATCH, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_model_scenario_option(_clicks):
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict):
            return no_update, no_update
        return triggered.get("value"), "checkbox-dropdown-menu"

    @app.callback(
        Output({"type": layout.MODEL_SCENARIO_OPTION_TYPE, "model": MATCH, "value": ALL}, "className"),
        Input({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "value"),
        State({"type": layout.MODEL_SCENARIO_OPTION_TYPE, "model": MATCH, "value": ALL}, "id"),
    )
    def sync_model_scenario_option_classes(selected_scenarios, option_ids):
        selected_value = _single_selected_scenario(selected_scenarios, [
            {"value": option_id.get("value")}
            for option_id in (option_ids or [])
        ])
        return _single_select_option_classes(selected_value, option_ids or [])

    @app.callback(
        Output({"type": layout.MODEL_MEV_TYPE_TOGGLE_TYPE, "model": MATCH}, "children"),
        Output({"type": layout.MODEL_MEV_TYPE_OPTION_TYPE, "model": MATCH, "value": ALL}, "className"),
        Input({"type": layout.MODEL_MEV_TYPE_FILTER_TYPE, "model": MATCH}, "value"),
        State({"type": layout.MODEL_MEV_TYPE_OPTION_TYPE, "model": MATCH, "value": ALL}, "id"),
    )
    def sync_model_mev_type_toggle(selected_mev_mode, option_ids):
        normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
        return _mev_type_toggle_label(normalized_mode, layout.MEV_TYPE_OPTIONS), _single_select_option_classes(normalized_mode, option_ids)

    @app.callback(
        Output({"type": layout.MODEL_MEV_TYPE_FILTER_TYPE, "model": MATCH}, "value", allow_duplicate=True),
        Output({"type": layout.MODEL_MEV_TYPE_MENU_TYPE, "model": MATCH}, "className", allow_duplicate=True),
        Input({"type": layout.MODEL_MEV_TYPE_OPTION_TYPE, "model": MATCH, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_model_mev_type(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu single-select-menu"

    @app.callback(
        Output({"type": layout.MODEL_MEV_LABEL_TYPE, "model": MATCH}, "children"),
        Output({"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": MATCH}, "options"),
        Output({"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": MATCH}, "value", allow_duplicate=True),
        Output({"type": layout.MODEL_MEV_SINGLE_OPTIONS_TYPE, "model": MATCH}, "children"),
        Output({"type": layout.MODEL_MEV_FILTER_TYPE, "model": MATCH}, "options"),
        Output({"type": layout.MODEL_MEV_FILTER_TYPE, "model": MATCH}, "value", allow_duplicate=True),
        Output({"type": layout.MODEL_MEV_SELECT_ALL_TYPE, "model": MATCH}, "value"),
        Output({"type": layout.MODEL_MEV_SINGLE_SECTION_TYPE, "model": MATCH}, "className"),
        Output({"type": layout.MODEL_MEV_MULTI_SECTION_TYPE, "model": MATCH}, "className"),
        Input({"type": layout.MODEL_MEV_SELECT_ALL_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_MEV_FILTER_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_MEV_TYPE_FILTER_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": MATCH}, "value"),
        State(layout.RUN_FOR_ID, "value"),
        State(layout.COMPARE_AGAINST_ID, "value"),
        State(layout.SUBNAV_VIEW_ID, "value"),
        State(layout.MEV_LABEL_MODE_ID, "value"),
        prevent_initial_call=True,
    )
    def sync_model_mev_selection(
        select_all_value,
        selected_mevs_multi,
        selected_mev_mode,
        selected_mev_single,
        run_for,
        compare_against,
        snapshot_period,
        mev_label_mode,
    ):
        model_name = (ctx.triggered_id or {}).get("model")
        normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
        single_mev_options = _build_family_mev_options_for_mode(
            model_name,
            run_for,
            snapshot_period,
            mev_label_mode,
            compare_against,
        )
        multi_mev_options = _build_model_mev_options_for_mode(
            model_name,
            run_for,
            snapshot_period,
            mev_label_mode,
            normalized_mode,
            compare_against,
        )

        single_option_values = [option["value"] for option in single_mev_options if option.get("value")]
        default_single_value = (
            records.FAMILY_ALL_VALUE
            if records.FAMILY_ALL_VALUE in single_option_values
            else next(
                (value for value in single_option_values if value != records.FAMILY_ALL_VALUE),
                single_option_values[0] if single_option_values else "",
            )
        )
        next_single_value = next(
            (value for value in _normalize_selected_mevs(selected_mev_single) if value in single_option_values),
            default_single_value,
        )
        multi_option_values = [option["value"] for option in multi_mev_options if option.get("value")]
        valid_selected_multi = [value for value in _normalize_selected_mevs(selected_mevs_multi) if value in multi_option_values]

        triggered_type = (ctx.triggered_id or {}).get("type")
        if normalized_mode == "family":
            next_multi_value = valid_selected_multi
            next_select_all = []
        elif triggered_type == layout.MODEL_MEV_SELECT_ALL_TYPE:
            if "all" in (select_all_value or []):
                next_multi_value = multi_option_values
            else:
                next_multi_value = []
            next_select_all = no_update
        elif triggered_type == layout.MODEL_MEV_FILTER_TYPE:
            next_multi_value = valid_selected_multi
            next_select_all = ["all"] if multi_option_values and set(next_multi_value) == set(multi_option_values) else []
        else:
            next_multi_value = valid_selected_multi or multi_option_values
            next_select_all = ["all"] if multi_option_values and set(next_multi_value) == set(multi_option_values) else []

        return (
            _mev_picker_label(normalized_mode),
            single_mev_options,
            next_single_value,
            _build_single_mev_option_buttons(single_mev_options, next_single_value, model_name),
            multi_mev_options,
            next_multi_value,
            next_select_all,
            _mev_picker_section_class(visible=normalized_mode == "family"),
            _mev_picker_section_class(visible=normalized_mode != "family"),
        )

    @app.callback(
        Output({"type": layout.MODEL_MEV_TOGGLE_TYPE, "model": MATCH}, "children"),
        Input({"type": layout.MODEL_MEV_TYPE_FILTER_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_MEV_FILTER_TYPE, "model": MATCH}, "value"),
        State({"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": MATCH}, "options"),
        State({"type": layout.MODEL_MEV_FILTER_TYPE, "model": MATCH}, "options"),
    )
    def sync_model_mev_toggle(selected_mev_mode, selected_mev_single, selected_mevs_multi, single_mev_options, multi_mev_options):
        return _mev_toggle_label(
            selected_mev_mode,
            selected_mev_single,
            selected_mevs_multi,
            single_mev_options or [],
            multi_mev_options or [],
        )

    @app.callback(
        Output({"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": MATCH}, "value", allow_duplicate=True),
        Output({"type": layout.MODEL_MEV_MENU_TYPE, "model": MATCH}, "className", allow_duplicate=True),
        Input({"type": layout.MODEL_MEV_SINGLE_OPTION_TYPE, "model": MATCH, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_model_mev_single_value(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], "checkbox-dropdown-menu"


def _register_export_callbacks(
    app,
    subnav_view_labels,
    reference_line_labels,
    mev_label_mode_labels,
    region_labels,
    model_group_labels,
    portfolio_labels,
) -> None:
    @app.callback(
        Output(layout.DOWNLOAD_DATA_ID, "data"),
        Input(layout.DOWNLOAD_REPORT_ID, "n_clicks"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def download_saas_report(_n_clicks, applied):
        applied = applied or {}
        if not applied:
            raise PreventUpdate
        run_for = applied.get("run_for")
        compare_against = applied.get("compare_against")
        segment = applied.get("segment")
        region = applied.get("region")
        model_group = applied.get("model_group")
        portfolio = applied.get("portfolio")
        selected_models = applied.get("selected_models")
        snapshot_period = applied.get("snapshot_period")
        reference_lines = applied.get("reference_lines")
        mev_label_mode = applied.get("mev_label_mode")
        sections = reports.build_report_figures(
            run_for, compare_against, segment, selected_models,
            snapshot_period, reference_lines, mev_label_mode,
            region=region, model_group=model_group, portfolio=portfolio,
            figure_builder=figures.build_model_figure,
        )

        effective_models = _effective_model_names(segment, selected_models, region=region, model_group=model_group, portfolio=portfolio)
        if _is_segment_active(segment):
            scope_label = f"Segment: {', '.join(layout.format_segment_label(v) for v in _active_segment_values(segment))}"
        elif effective_models:
            scope_label = f"Models: {', '.join(effective_models)}"
        else:
            scope_label = "Models: None selected"

        meta_lines = [
            f"Model Use Case / Cycle: {_run_for_meta_label(run_for)}",
            f"Compare To: {_compare_against_toggle_label(compare_against, _primary_run_for_value(run_for))}",
            f"Region: {region_labels.get(region or layout.DEFAULT_REGION, region)}",
            f"Model Group: {model_group_labels.get(model_group or layout.DEFAULT_MODEL_GROUP, model_group)}",
            f"Portfolio: {portfolio_labels.get(portfolio or layout.DEFAULT_PORTFOLIO, portfolio)}",
            scope_label,
            f"Snapshot Period: {subnav_view_labels.get(_normalize_snapshot_period(snapshot_period), snapshot_period)}",
            f"Reference Lines: {reference_line_labels.get(reference_lines or layout.DEFAULT_REFERENCE_LINES, reference_lines)}",
            f"MEV Label: {mev_label_mode_labels.get(_normalize_mev_label_mode(mev_label_mode), mev_label_mode)}",
        ]

        html_doc = exports.build_saas_report_html(sections, meta_lines)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = reports.run_for_filename_prefix(run_for)
        return dcc.send_string(html_doc, filename=f"{prefix}-saas-charts-{timestamp}.html")

    @app.callback(
        Output(layout.EXCEL_MODAL_ID, "className"),
        Input(layout.EXCEL_OPEN_ID, "n_clicks"),
        Input(layout.EXCEL_CANCEL_ID, "n_clicks"),
        Input(layout.EXCEL_GENERATE_ID, "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_excel_modal(_open_clicks, _cancel_clicks, _generate_clicks):
        if ctx.triggered_id == layout.EXCEL_OPEN_ID:
            return "saas-modal-overlay is-open"
        return "saas-modal-overlay"

    @app.callback(
        Output(layout.EXCEL_DOWNLOAD_DATA_ID, "data"),
        Input(layout.EXCEL_GENERATE_ID, "n_clicks"),
        State(layout.EXCEL_SCENARIO_ID, "value"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def download_saas_excel(_n_clicks, scenario, applied):
        applied = applied or {}
        if not applied:
            raise PreventUpdate
        run_for = applied.get("run_for")
        segment = applied.get("segment")
        region = applied.get("region")
        model_group = applied.get("model_group")
        portfolio = applied.get("portfolio")
        selected_models = applied.get("selected_models")
        mev_label_mode = applied.get("mev_label_mode")
        metric_rows, chart_specs, primary_run_for, baseline_available = _compute_saas_metrics(
            run_for, segment, selected_models, mev_label_mode, scenario,
            region=region, model_group=model_group, portfolio=portfolio,
        )
        scenario_value = str(scenario or "").strip().lower()
        scenario_label = SAAS_SCENARIO_LABEL_MAP.get(scenario_value, scenario_value.replace("_", " ").title() or "—")
        columns = exports.active_metric_columns(baseline_available, scenario_label, scenario_value)
        effective_models = _effective_model_names(segment, selected_models, region=region, model_group=model_group, portfolio=portfolio)
        if _is_segment_active(segment):
            scope_label = f"Segment: {', '.join(layout.format_segment_label(v) for v in _active_segment_values(segment))}"
        elif effective_models:
            scope_label = f"Models: {', '.join(effective_models)}"
        else:
            scope_label = "Models: None selected"

        meta_lines = [
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Model Use Case / Cycle: {primary_run_for or '—'}",
            f"Scenario: {scenario_label}",
            f"Region: {region_labels.get(region or layout.DEFAULT_REGION, region)}",
            f"Model Group: {model_group_labels.get(model_group or layout.DEFAULT_MODEL_GROUP, model_group)}",
            f"Portfolio: {portfolio_labels.get(portfolio or layout.DEFAULT_PORTFOLIO, portfolio)}",
            scope_label,
            f"MEV Label: {mev_label_mode_labels.get(_normalize_mev_label_mode(mev_label_mode), mev_label_mode)}",
            f"All Metrics and Charts in this workbook are computed from the selected scenario ({scenario_label}): "
            "the History lines/columns use that scenario's history (Quarter <= 0) and the projection "
            "lines/columns use that scenario's projection (Quarter > 0).",
            "Scope: primary Model Use Case / Cycle only, using the full history + projection regardless of the on-screen "
            "Snapshot Period. Standard deviation is population (ddof=0).",
            "Exception: the 'Is Baseline Min/Max ...' columns always use the Baseline scenario's projection "
            "(shown only when Baseline is available and is not the selected scenario).",
        ]

        workbook = exports.build_saas_excel_workbook(metric_rows, chart_specs, meta_lines, scenario_label, columns)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = reports.run_for_filename_prefix(run_for)
        return dcc.send_bytes(lambda buffer: workbook.save(buffer), filename=f"{prefix}-saas-historical-range-analysis-{timestamp}.xlsx")

    @app.callback(
        Output(layout.RECON_MODAL_ID, "className"),
        Input(layout.RECON_OPEN_ID, "n_clicks"),
        Input(layout.RECON_CANCEL_ID, "n_clicks"),
        Input(layout.RECON_GENERATE_ID, "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_recon_modal(_open_clicks, _cancel_clicks, _generate_clicks):
        if ctx.triggered_id == layout.RECON_OPEN_ID:
            return "saas-modal-overlay is-open"
        return "saas-modal-overlay"

    @app.callback(
        Output(layout.RECON_DOWNLOAD_DATA_ID, "data"),
        Input(layout.RECON_GENERATE_ID, "n_clicks"),
        State(layout.RECON_SCENARIO_ID, "value"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def download_saas_reconciliation(_n_clicks, scenario, applied):
        applied = applied or {}
        if not applied:
            raise PreventUpdate
        run_for = applied.get("run_for")
        compare_against = applied.get("compare_against")
        segment = applied.get("segment")
        region = applied.get("region")
        model_group = applied.get("model_group")
        portfolio = applied.get("portfolio")
        selected_models = applied.get("selected_models")
        mev_label_mode = applied.get("mev_label_mode")
        recon = _compute_saas_reconciliation(
            run_for, compare_against, segment, selected_models, mev_label_mode, scenario,
            region=region, model_group=model_group, portfolio=portfolio,
        )
        scenario_value = str(scenario or "").strip().lower()
        scenario_label = SAAS_SCENARIO_LABEL_MAP.get(scenario_value, scenario_value.replace("_", " ").title() or "—")
        threshold_fraction = 0.03  # default 3.0%; the user can change cell B1 in the Summary tab
        primary = recon.get("primary")
        compare_cycles = recon.get("compare_cycles", [])
        effective_models = _effective_model_names(segment, selected_models, region=region, model_group=model_group, portfolio=portfolio)
        if _is_segment_active(segment):
            scope_label = f"Segment: {', '.join(layout.format_segment_label(v) for v in _active_segment_values(segment))}"
        elif effective_models:
            scope_label = f"Models: {', '.join(effective_models)}"
        else:
            scope_label = "Models: None selected"

        meta_lines = [
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Primary Model Use Case / Cycle: {primary or '—'}",
            f"Compare To: {', '.join(compare_cycles) if compare_cycles else 'None selected'}",
            f"Scenario: {scenario_label}",
            f"Region: {region_labels.get(region or layout.DEFAULT_REGION, region)}",
            f"Model Group: {model_group_labels.get(model_group or layout.DEFAULT_MODEL_GROUP, model_group)}",
            f"Portfolio: {portfolio_labels.get(portfolio or layout.DEFAULT_PORTFOLIO, portfolio)}",
            scope_label,
            f"MEV Label: {mev_label_mode_labels.get(_normalize_mev_label_mode(mev_label_mode), mev_label_mode)}",
            f"Relative threshold: {threshold_fraction * 100:g}% by default - editable in the Summary tab (cell B1).",
            "Each MEV is reconciled over the historical dates (Quarter <= 0) that overlap across all selected "
            "model use case / cycles. Diff = compare cycle minus primary cycle; % is relative to the primary cycle value.",
        ]
        if not compare_cycles:
            meta_lines.append(
                "WARNING: No 'Compare To' cycle is selected. Select at least one Compare To model use case / cycle, "
                "then export again to produce the reconciliation."
            )

        workbook = exports.build_saas_reconciliation_workbook(recon, meta_lines, scenario_label, threshold_fraction)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = reports.run_for_filename_prefix(run_for)
        return dcc.send_bytes(lambda buffer: workbook.save(buffer), filename=f"{prefix}-saas-historical-reconciliation-{timestamp}.xlsx")

    @app.callback(
        Output(layout.PROJECTION_MODAL_ID, "className"),
        Input(layout.PROJECTION_OPEN_ID, "n_clicks"),
        Input(layout.PROJECTION_CANCEL_ID, "n_clicks"),
        Input(layout.PROJECTION_GENERATE_ID, "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_projection_modal(_open_clicks, _cancel_clicks, _generate_clicks):
        if ctx.triggered_id == layout.PROJECTION_OPEN_ID:
            return "saas-modal-overlay is-open"
        return "saas-modal-overlay"

    @app.callback(
        Output(layout.PROJECTION_DOWNLOAD_DATA_ID, "data"),
        Input(layout.PROJECTION_GENERATE_ID, "n_clicks"),
        State(layout.PROJECTION_SCENARIO_ID, "value"),
        State(layout.PROJECTION_HORIZON_ID, "value"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def download_saas_projection(_n_clicks, scenario, horizon, applied):
        applied = applied or {}
        if not applied:
            raise PreventUpdate
        run_for = applied.get("run_for")
        compare_against = applied.get("compare_against")
        segment = applied.get("segment")
        region = applied.get("region")
        model_group = applied.get("model_group")
        portfolio = applied.get("portfolio")
        selected_models = applied.get("selected_models")
        mev_label_mode = applied.get("mev_label_mode")
        try:
            max_quarter = int(horizon)
        except (TypeError, ValueError):
            max_quarter = 20
        comparison = _compute_saas_projection_comparison(
            run_for, compare_against, segment, selected_models, mev_label_mode, scenario, max_quarter,
            region=region, model_group=model_group, portfolio=portfolio,
        )
        scenario_value = str(scenario or "").strip().lower()
        scenario_label = SAAS_SCENARIO_LABEL_MAP.get(scenario_value, scenario_value.replace("_", " ").title() or "—")
        primary = comparison.get("primary")
        compare_cycles = comparison.get("compare_cycles", [])
        effective_models = _effective_model_names(segment, selected_models, region=region, model_group=model_group, portfolio=portfolio)
        if _is_segment_active(segment):
            scope_label = f"Segment: {', '.join(layout.format_segment_label(v) for v in _active_segment_values(segment))}"
        elif effective_models:
            scope_label = f"Models: {', '.join(effective_models)}"
        else:
            scope_label = "Models: None selected"

        meta_lines = [
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Primary Model Use Case / Cycle: {primary or '—'}",
            f"Compare To: {', '.join(compare_cycles) if compare_cycles else 'None selected'}",
            f"Scenario: {scenario_label}",
            f"Region: {region_labels.get(region or layout.DEFAULT_REGION, region)}",
            f"Model Group: {model_group_labels.get(model_group or layout.DEFAULT_MODEL_GROUP, model_group)}",
            f"Portfolio: {portfolio_labels.get(portfolio or layout.DEFAULT_PORTFOLIO, portfolio)}",
            scope_label,
            f"MEV Label: {mev_label_mode_labels.get(_normalize_mev_label_mode(mev_label_mode), mev_label_mode)}",
            f"Projection horizon: up to Q{max_quarter}.",
            "Each MEV's projection is compared across the selected model use case / cycles, aligned by quarter offset "
            "(Q0 = the as-of/jump-off point, Q1.. = projected quarters), over the common horizon. "
            "Diff = compare cycle minus primary cycle; % is relative to the primary cycle value.",
        ]
        if not compare_cycles:
            meta_lines.append(
                "WARNING: No 'Compare To' cycle is selected. Select at least one Compare To model use case / cycle, "
                "then export again to produce the projection comparison."
            )

        workbook = exports.build_saas_projection_workbook(comparison, meta_lines, scenario_label)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = reports.run_for_filename_prefix(run_for)
        return dcc.send_bytes(lambda buffer: workbook.save(buffer), filename=f"{prefix}-saas-projection-comparison-{timestamp}.xlsx")


def _register_filter_callbacks(app) -> None:
    @app.callback(
        Output(layout.SEGMENT_NAME_ID, "value", allow_duplicate=True),
        Output(layout.SEGMENT_PREV_STORE_ID, "data"),
        Input(layout.SEGMENT_NAME_ID, "value"),
        State(layout.SEGMENT_PREV_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def sync_segment_selection(segment_values, prev_values):
        option_values = {option["value"] for option in layout.SEGMENT_NAME_OPTIONS}
        raw_values = [value for value in _normalize_multi_values(segment_values) if value in option_values]
        prev_values = [value for value in _normalize_multi_values(prev_values) if value in option_values]

        # "All" is mutually exclusive with specific segments: checking it
        # clears the segments, and checking a segment drops "All".
        added = [value for value in raw_values if value not in prev_values]
        if layout.SEGMENT_ALL_VALUE in added:
            result = [layout.SEGMENT_ALL_VALUE]
        else:
            specific_values = [value for value in raw_values if value != layout.SEGMENT_ALL_VALUE]
            result = specific_values if specific_values else [layout.SEGMENT_ALL_VALUE]

        return result, result

    @app.callback(
        Output(layout.MODEL_NAME_ID, "value", allow_duplicate=True),
        Output(layout.MODEL_NAME_SELECT_ALL_ID, "value"),
        Input(layout.MODEL_NAME_SELECT_ALL_ID, "value"),
        Input(layout.MODEL_NAME_ID, "value"),
        State(layout.MODEL_NAME_ID, "options"),
        prevent_initial_call=True,
    )
    def sync_saas_model_selection(select_all_value, models_value, models_options):
        # Options may be narrowed by the search box, so "All" only adds or
        # removes the visible models and leaves hidden selections untouched.
        visible_names = [option["value"] for option in models_options if option.get("value")]
        current_values = list(models_value or [])
        if ctx.triggered_id == layout.MODEL_NAME_SELECT_ALL_ID:
            if "all" in (select_all_value or []):
                return current_values + [name for name in visible_names if name not in current_values], no_update
            return [value for value in current_values if value not in set(visible_names)], no_update
        select_all = ["all"] if visible_names and set(visible_names).issubset(current_values) else []
        return no_update, select_all

    @app.callback(
        Output(layout.SEGMENT_NAME_ID, "options"),
        Output(layout.SEGMENT_TOGGLE_ID, "disabled"),
        Output(layout.MODEL_NAME_SELECT_ALL_ID, "options"),
        Output(layout.MODEL_NAME_ID, "options"),
        Output(layout.MODEL_NAME_ID, "value"),
        Output(layout.MODEL_NAME_TOGGLE_ID, "children"),
        Output(layout.MODEL_NAME_TOGGLE_ID, "disabled"),
        Output(layout.FILTER_HELP_ID, "children"),
        Input(layout.SEGMENT_NAME_ID, "value"),
        Input(layout.REGION_ID, "value"),
        Input(layout.MODEL_GROUP_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.MODEL_NAME_ID, "value"),
        Input(layout.MODEL_NAME_SEARCH_ID, "value"),
    )
    def sync_saas_filter_controls(segment, region, model_group, portfolio, selected_models, model_search):
        segment_active = _is_segment_active(segment)
        all_options = _model_options_for_filters(None, region=region, model_group=model_group, portfolio=portfolio)
        all_option_values = [option["value"] for option in all_options]
        current_values = _normalize_selected_models(selected_models)

        option_values = set(all_option_values)
        current_values = [value for value in current_values if value in option_values]
        has_specific_model_selection = 0 < len(current_values) < len(all_option_values)
        # Segment and Specific Models are both always interactive in SAAS
        # (unlike the PD Performance dashboard, where they're mutually
        # exclusive). If both end up set, Segment still takes priority in
        # effective_model_names. Segment's own options are additionally
        # narrowed to whatever the current Specific Models selection actually
        # covers (segment=None here so Segment doesn't gate its own options).
        selected_raw_models = _effective_model_names(None, current_values, region=region, model_group=model_group, portfolio=portfolio)
        select_all_options = [{"label": "All", "value": "all"}]
        segment_options = [
            {"label": option["label"], "value": option["value"]}
            for option in _segment_options_for_filters(
                region=region, model_group=model_group, portfolio=portfolio, model_names=selected_raw_models,
            )
        ]
        model_options = _model_options_for_filters(None, region=region, model_group=model_group, portfolio=portfolio, disabled=False)
        toggle_label = _model_toggle_label(current_values, all_options, False)

        if segment_active and has_specific_model_selection:
            help_text = "Both Segment and Specific Models are set. Segment takes priority while it's active."
        else:
            help_text = ""

        # The search box narrows only the visible options; models checked before
        # searching stay selected even while hidden.
        search_text = str(model_search or "").strip().lower()
        if search_text:
            model_options = [
                option for option in model_options
                if search_text in str(option.get("label", "")).lower()
                or search_text in str(option.get("value", "")).lower()
            ]

        return (
            segment_options,
            False,  # Segment's toggle is never disabled by a Specific Models selection
            select_all_options,
            model_options,
            current_values,
            toggle_label,
            False,  # Specific Models' toggle is never disabled by a Segment selection
            help_text,
        )

    # Cascade: Region -> Model Group -> Portfolio -> Specific Models, with
    # Segment narrowing off the same three upstream filters as a separate
    # (mutually exclusive with Specific Models) alternative. Each step below
    # narrows the next filter's options to only values still reachable, and
    # resets that filter back to "All" if its current selection is no longer
    # part of the narrowed set.
    @app.callback(
        Output(layout.MODEL_GROUP_ID, "options"),
        Output(layout.MODEL_GROUP_MENU_ID, "children"),
        Output(layout.MODEL_GROUP_ID, "value", allow_duplicate=True),
        Input(layout.REGION_ID, "value"),
        State(layout.MODEL_GROUP_ID, "value"),
        prevent_initial_call=True,
    )
    def narrow_model_group_options(region, current_model_group):
        options = _model_group_options_for_filters(region=region)
        valid_values = {option["value"] for option in options}
        selected_value = current_model_group if current_model_group in valid_values else layout.MODEL_GROUP_ALL_VALUE
        children = shared_filters.build_single_select_option_buttons(options, selected_value, layout.MODEL_GROUP_FILTER_KEY)
        value_output = selected_value if selected_value != current_model_group else no_update
        return options, children, value_output

    @app.callback(
        Output(layout.PORTFOLIO_ID, "options"),
        Output(layout.PORTFOLIO_MENU_ID, "children"),
        Output(layout.PORTFOLIO_ID, "value", allow_duplicate=True),
        Input(layout.REGION_ID, "value"),
        Input(layout.MODEL_GROUP_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
        prevent_initial_call=True,
    )
    def narrow_portfolio_options(region, model_group, current_portfolio):
        options = _portfolio_options_for_filters(region=region, model_group=model_group)
        valid_values = {option["value"] for option in options}
        selected_value = current_portfolio if current_portfolio in valid_values else layout.PORTFOLIO_ALL_VALUE
        children = shared_filters.build_single_select_option_buttons(options, selected_value, layout.PORTFOLIO_FILTER_KEY)
        value_output = selected_value if selected_value != current_portfolio else no_update
        return options, children, value_output

    @app.callback(
        Output(layout.SEGMENT_NAME_ID, "value", allow_duplicate=True),
        Input(layout.REGION_ID, "value"),
        Input(layout.MODEL_GROUP_ID, "value"),
        Input(layout.PORTFOLIO_ID, "value"),
        Input(layout.MODEL_NAME_ID, "value"),
        State(layout.SEGMENT_NAME_ID, "value"),
        prevent_initial_call=True,
    )
    def reset_invalid_segment_selection(region, model_group, portfolio, selected_models, current_segment):
        selected_raw_models = _effective_model_names(
            None, _normalize_selected_models(selected_models), region=region, model_group=model_group, portfolio=portfolio,
        )
        valid_values = {
            option["value"]
            for option in _segment_options_for_filters(
                region=region, model_group=model_group, portfolio=portfolio, model_names=selected_raw_models,
            )
        }
        active_values = _active_segment_values(current_segment)
        if active_values and not set(active_values).issubset(valid_values):
            return [layout.SEGMENT_ALL_VALUE]
        return no_update

    @app.callback(
        Output(layout.COMPARE_AGAINST_ID, "options"),
        Output(layout.COMPARE_AGAINST_ID, "value", allow_duplicate=True),
        Output(layout.COMPARE_AGAINST_PREV_STORE_ID, "data"),
        Input(layout.RUN_FOR_ID, "value"),
        Input(layout.COMPARE_AGAINST_ID, "value"),
        Input(layout.REFERENCE_LINES_ID, "value"),
        State(layout.COMPARE_AGAINST_PREV_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def sync_compare_against_selection(run_for_value, compare_against_values, reference_lines, prev_values):
        selected_run_fors = _normalize_selected_run_fors(run_for_value)
        selected_run_for = selected_run_fors[0] if selected_run_fors else None
        options = _build_compare_against_options(selected_run_for)
        option_values = {option["value"] for option in options}
        triggered_ids = {triggered["prop_id"].split(".")[0] for triggered in ctx.triggered}

        if layout.REFERENCE_LINES_ID in triggered_ids and reference_lines == "monitoring":
            result = [layout.COMPARE_AGAINST_NONE_VALUE]
            return options, result, result

        raw_values = [value for value in _normalize_multi_values(compare_against_values) if value in option_values]
        prev_values = [value for value in _normalize_multi_values(prev_values) if value in option_values]

        if layout.COMPARE_AGAINST_ID in triggered_ids:
            # Multiple reporting cycles may be selected, but "None" is mutually
            # exclusive with them: checking it clears the cycles, and checking a
            # cycle drops "None".
            added = [value for value in raw_values if value not in prev_values]
            if layout.COMPARE_AGAINST_NONE_VALUE in added:
                result = [layout.COMPARE_AGAINST_NONE_VALUE]
            else:
                cycle_values = [value for value in raw_values if value != layout.COMPARE_AGAINST_NONE_VALUE]
                result = cycle_values if cycle_values else [layout.COMPARE_AGAINST_NONE_VALUE]
        else:
            result = prev_values if prev_values else [layout.COMPARE_AGAINST_NONE_VALUE]

        return options, result, result

    @app.callback(
        Output(layout.COMPARE_AGAINST_TOGGLE_ID, "children"),
        Input(layout.COMPARE_AGAINST_ID, "value"),
        State(layout.RUN_FOR_ID, "value"),
    )
    def sync_compare_against_toggle(compare_against_values, run_for_value):
        selected_run_fors = _normalize_selected_run_fors(run_for_value)
        selected_run_for = selected_run_fors[0] if selected_run_fors else None
        return _compare_against_toggle_label(compare_against_values, selected_run_for)

    @app.callback(
        Output(layout.RECON_OPEN_ID, "disabled"),
        Output(layout.PROJECTION_OPEN_ID, "disabled"),
        Output(layout.DOWNLOAD_COMPARE_HELP_ID, "className"),
        Input(layout.COMPARE_AGAINST_ID, "value"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        State(layout.RUN_FOR_ID, "value"),
    )
    def sync_comparison_download_availability(compare_against_values, applied_filters, run_for_value):
        if not applied_filters:
            return True, True, "saas-download-compare-note is-hidden"
        selected_run_fors = _normalize_selected_run_fors(run_for_value)
        selected_run_for = selected_run_fors[0] if selected_run_fors else None
        normalized_values = _normalize_compare_against_values(compare_against_values, selected_run_for)
        has_compare_cycle = any(value != layout.COMPARE_AGAINST_NONE_VALUE for value in normalized_values)
        note_class = "saas-download-compare-note is-hidden" if has_compare_cycle else "saas-download-compare-note"
        return not has_compare_cycle, not has_compare_cycle, note_class

    @app.callback(
        Output(layout.HISTORICAL_STATS_FILTER_ID, "className"),
        Input(layout.SUBNAV_VIEW_ID, "value"),
    )
    def sync_historical_stats_filter_visibility(snapshot_period):
        base_class = "monitoring-filter saas-historical-stats-filter"
        if _normalize_snapshot_period(snapshot_period) != "history":
            return f"{base_class} is-hidden"
        return base_class


def _register_render_callbacks(app) -> None:
    @app.callback(
        Output(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(layout.APPLY_FILTERS_ID, "n_clicks"),
        State(layout.RUN_FOR_ID, "value"),
        State(layout.COMPARE_AGAINST_ID, "value"),
        State(layout.SEGMENT_NAME_ID, "value"),
        State(layout.REGION_ID, "value"),
        State(layout.MODEL_GROUP_ID, "value"),
        State(layout.PORTFOLIO_ID, "value"),
        State(layout.MODEL_NAME_ID, "value"),
        State(layout.SUBNAV_VIEW_ID, "value"),
        State(layout.REFERENCE_LINES_ID, "value"),
        State(layout.MEV_LABEL_MODE_ID, "value"),
        State(layout.HISTORICAL_STATS_ID, "value"),
        prevent_initial_call=True,
    )
    def apply_saas_filters(
        _n_clicks,
        run_for,
        compare_against,
        segment,
        region,
        model_group,
        portfolio,
        selected_models,
        snapshot_period,
        reference_lines,
        mev_label_mode,
        show_historical_statistics_values,
    ):
        """Snapshot the current top filters so the content renders only on Apply."""
        return {
            "run_for": run_for,
            "compare_against": compare_against,
            "segment": segment,
            "region": region,
            "model_group": model_group,
            "portfolio": portfolio,
            "selected_models": selected_models,
            "snapshot_period": snapshot_period,
            "reference_lines": reference_lines,
            "mev_label_mode": mev_label_mode,
            "historical_stats": show_historical_statistics_values,
        }

    @app.callback(
        Output(layout.SUBNAV_MODELS_LABEL_ID, "children"),
        Output(layout.SUBNAV_MODELS_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def render_saas_subnav_models(applied):
        applied = applied or {}
        return views.build_subnav_models(
            applied.get("segment"),
            applied.get("selected_models"),
            region=applied.get("region"),
            model_group=applied.get("model_group"),
            portfolio=applied.get("portfolio"),
        )

    @app.callback(
        Output(layout.MEV_MODEL_PANELS_ID, "children"),
        Input(layout.APPLIED_FILTERS_STORE_ID, "data"),
        Input(theme.APP_THEME_ID, "value"),
        prevent_initial_call=True,
    )
    def render_saas_mev_chart(applied, theme_value):
        if not applied:
            return no_update
        run_for = applied.get("run_for")
        compare_against = applied.get("compare_against")
        segment = applied.get("segment")
        region = applied.get("region")
        model_group = applied.get("model_group")
        portfolio = applied.get("portfolio")
        selected_models = applied.get("selected_models")
        snapshot_period = applied.get("snapshot_period")
        reference_lines = applied.get("reference_lines")
        mev_label_mode = applied.get("mev_label_mode")
        show_historical_statistics_values = applied.get("historical_stats")
        theme_value = _normalize_theme_value(theme_value)
        selected_run_fors = _normalize_selected_run_fors(run_for)
        scoped_run_fors = _scoped_run_for_values(run_for, compare_against)
        effective_models = _effective_model_names(segment, selected_models, region=region, model_group=model_group, portfolio=portfolio)
        show_historical_statistics = (
            _normalize_snapshot_period(snapshot_period) == "history"
            and _show_historical_statistics(show_historical_statistics_values)
        )

        if not selected_run_fors:
            return _build_empty_state(
                "Choose Model Use Case / Cycle value",
                "Select one Model Use Case / Cycle value to render the SAAS workbook charts.",
            )

        if not effective_models:
            return _build_empty_state(
                "No models match the current filters",
                "Adjust Region, Model Group, Portfolio, Segment, or Specific Models to bring one or more SAAS models into scope.",
            )

        time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
        if time_series_df is None or time_series_df.empty:
            return _build_empty_state(
                "No SAAS MEV data is available",
                "The workbook did not return any MEV time-series records for this page.",
            )

        filtered_df = time_series_df[time_series_df["Model Name"].isin(effective_models)]
        filtered_df = filtered_df[filtered_df["Run For"].isin(scoped_run_fors)]

        records = filtered_df.to_dict(orient="records")
        panels = []
        panel_index = 0
        for group_index, (parent_label, member_models) in enumerate(
            _group_effective_models(segment, selected_models, region=region, model_group=model_group, portfolio=portfolio),
            start=1,
        ):
            shared_attribute_lines, shared_attribute_keys = views.partition_group_attributes(
                member_models, selected_run_fors
            )
            member_panels = []
            for model_name in member_models:
                panel_index += 1
                model_records = [row for row in records if row.get("Model Name") == model_name]
                member_panels.append(
                    views.build_model_panel(
                        panel_index,
                        model_name,
                        model_records,
                        selected_run_fors,
                        compare_against,
                        snapshot_period,
                        mev_label_mode,
                        reference_lines,
                        figure_builder=figures.build_model_figure,
                        show_historical_statistics=show_historical_statistics,
                        theme_value=theme_value,
                        suppress_attributes=shared_attribute_keys,
                    )
                )
            panels.append(
                views.build_model_group_card(
                    group_index,
                    parent_label,
                    member_panels,
                    shared_attribute_lines=shared_attribute_lines,
                )
            )

        return panels or _build_empty_state(
            "No MEV charts match the current filters",
            "Adjust the Model Use Case / Cycle, Segment, or Specific Models filters to broaden the SAAS workbook selection.",
        )

    @app.callback(
        Output({"type": layout.MODEL_MEV_GRID_TYPE, "model": MATCH}, "children"),
        Output({"type": layout.MODEL_DATE_RANGE_CONTROLS_TYPE, "model": MATCH}, "children"),
        Input({"type": layout.MODEL_MEV_TYPE_FILTER_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_MEV_FILTER_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_DATE_RANGE_WINDOW_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_DATE_RANGE_FROM_TYPE, "model": MATCH}, "value"),
        Input({"type": layout.MODEL_DATE_RANGE_TO_TYPE, "model": MATCH}, "value"),
        Input(theme.APP_THEME_ID, "value"),
        State({"type": layout.MODEL_MEV_GRID_TYPE, "model": MATCH}, "id"),
        State(layout.APPLIED_FILTERS_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_model_mev_chart_controls(selected_mev_mode, selected_scenario, selected_mevs_multi, selected_mev_single, window_value, from_value, to_value, theme_value, model_grid_id, applied):
        model_name = (
            ctx.triggered_id.get("model")
            if isinstance(ctx.triggered_id, dict)
            else (model_grid_id or {}).get("model")
        )
        if not model_name:
            return no_update, no_update
        time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
        if time_series_df is None or time_series_df.empty:
            return no_update, no_update

        # Family mode draws the raw lines by expanding the selected transformed
        # parent (records.family_display_mevs), so they only resolve once the
        # single-value picker is settled. On first paint this MATCH callback can
        # fire against the just-created picker before sync_model_mev_selection has
        # set its value; rendering then would blank build_model_panel's correct
        # initial charts (transformed + raw). Leave the initial render in place
        # until the family selection is settled. (Single-select can't be cleared
        # to empty from the UI, so this only guards the transient creation race.)
        if _normalize_selected_mev_mode(selected_mev_mode) == "family" and not _normalize_selected_mevs(selected_mev_single):
            return no_update, no_update

        applied = applied or {}
        run_for = applied.get("run_for")
        compare_against = applied.get("compare_against")
        snapshot_period = applied.get("snapshot_period")
        reference_lines = applied.get("reference_lines")
        mev_label_mode = applied.get("mev_label_mode")
        show_historical_statistics_values = applied.get("historical_stats")

        selected_run_fors = _normalize_selected_run_fors(run_for)
        scoped_run_fors = _scoped_run_for_values(run_for, compare_against)
        snapshot_period_value = _normalize_snapshot_period(snapshot_period)
        show_historical_statistics = (
            snapshot_period_value == "history"
            and _show_historical_statistics(show_historical_statistics_values)
        )
        filtered_df = time_series_df[time_series_df["Model Name"] == model_name]
        if scoped_run_fors:
            filtered_df = filtered_df[filtered_df["Run For"].isin(scoped_run_fors)]
        else:
            filtered_df = filtered_df.iloc[0:0]

        base_records = _filter_records_by_snapshot_period(
            filtered_df.to_dict(orient="records"),
            snapshot_period_value,
        )
        periods = _available_date_periods(base_records)
        range_value = selectors.resolve_date_range_selection(
            periods,
            window_value,
            from_value,
            to_value,
            ctx.triggered_id,
            window_trigger_type=layout.MODEL_DATE_RANGE_WINDOW_TYPE,
            from_trigger_type=layout.MODEL_DATE_RANGE_FROM_TYPE,
            to_trigger_type=layout.MODEL_DATE_RANGE_TO_TYPE,
        )
        range_controls = [
            layout.build_model_date_range_controls(
                model_name,
                periods,
                range_value,
                disabled=snapshot_period_value == "projection",
            )
        ]
        records = _filter_records_by_date_range(base_records, range_value)
        active_selected_mevs = _active_selected_mevs(
            model_name,
            selected_mev_mode,
            selected_mev_single,
            selected_mevs_multi,
            base_records,
            mev_label_mode=mev_label_mode,
        )
        return (
            views.build_model_chart_cards(
                model_name,
                records,
                filtered_df.to_dict(orient="records"),
                selected_mev_mode,
                selected_scenario,
                snapshot_period_value,
                mev_label_mode,
                range_value,
                reference_lines,
                active_selected_mevs,
                figure_builder=figures.build_model_figure,
                primary_run_for=selected_run_fors[0] if selected_run_fors else None,
                show_historical_statistics=show_historical_statistics,
                theme_value=_normalize_theme_value(theme_value),
            ),
            range_controls,
        )


def _build_callback_label_maps():
    return {
        "run_for_labels": {option["value"]: option["label"] for option in layout.RUN_FOR_OPTIONS},
        "region_labels": {option["value"]: option["label"] for option in layout.REGION_OPTIONS},
        "model_group_labels": {option["value"]: option["label"] for option in layout.MODEL_GROUP_OPTIONS},
        "portfolio_labels": {option["value"]: option["label"] for option in layout.PORTFOLIO_OPTIONS},
        "subnav_view_labels": {option["value"]: option["label"] for option in layout.SUBNAV_VIEW_OPTIONS},
        "reference_line_labels": {option["value"]: option["label"] for option in layout.REFERENCE_LINES_OPTIONS},
        "mev_label_mode_labels": {option["value"]: option["label"] for option in layout.MEV_LABEL_MODE_OPTIONS},
    }


def register_callbacks(app) -> None:
    """Register SAAS top-bar and chart callbacks (idempotent)."""
    if already_registered(app, "page:saas.workspace"):
        return

    _register_menu_callbacks(app)
    _register_single_select_callbacks(app)

    label_maps = _build_callback_label_maps()
    region_labels = label_maps["region_labels"]
    model_group_labels = label_maps["model_group_labels"]
    portfolio_labels = label_maps["portfolio_labels"]
    subnav_view_labels = label_maps["subnav_view_labels"]
    reference_line_labels = label_maps["reference_line_labels"]
    mev_label_mode_labels = label_maps["mev_label_mode_labels"]
    run_for_labels = label_maps["run_for_labels"]

    _register_shell_callbacks(
        app,
        run_for_labels,
        region_labels,
        model_group_labels,
        portfolio_labels,
        subnav_view_labels,
        reference_line_labels,
        mev_label_mode_labels,
    )

    _register_filter_callbacks(app)
    _register_model_picker_callbacks(app)

    _register_export_callbacks(
        app,
        subnav_view_labels,
        reference_line_labels,
        mev_label_mode_labels,
        region_labels,
        model_group_labels,
        portfolio_labels,
    )
    _register_render_callbacks(app)
