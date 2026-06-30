"""Layout for the SAAS workspace."""

from __future__ import annotations

from datetime import date

from dash import dcc, html

from .....shared.ui import controls as shared_filters
from .....shared.ui.charts import SAAS_SCENARIO_LABEL_MAP
from .....shared.domain.calculations import get_pd_range_preset, get_pd_range_selection
from ...data_access import SAAS_PAGE_DATA

RUN_FOR_ID = "saas-run-for"
RUN_FOR_TOGGLE_ID = "saas-run-for-toggle"
RUN_FOR_MENU_ID = "saas-run-for-menu"
RUN_FOR_FILTER_KEY = "saas-run-for"
COMPARE_AGAINST_ID = "saas-compare-against"
COMPARE_AGAINST_TOGGLE_ID = "saas-compare-against-toggle"
COMPARE_AGAINST_MENU_ID = "saas-compare-against-menu"
COMPARE_AGAINST_PREV_STORE_ID = "saas-compare-against-prev-store"
COMPARE_AGAINST_NONE_VALUE = "none"

SEGMENT_NAME_ID = "saas-segment-name"
SEGMENT_TOGGLE_ID = "saas-segment-toggle"
SEGMENT_MENU_ID = "saas-segment-menu"
SEGMENT_FILTER_KEY = "saas-segment"

MODEL_NAME_ID = "saas-model-name"
MODEL_NAME_SELECT_ALL_ID = "saas-model-name-select-all"
MODEL_NAME_TOGGLE_ID = "saas-model-name-toggle"
MODEL_NAME_MENU_ID = "saas-model-name-menu"

MEV_MODEL_PANELS_ID = "saas-mev-model-panels"
FILTER_HELP_ID = "saas-filter-help"
APPLY_FILTERS_ID = "saas-apply-filters"
APPLIED_FILTERS_STORE_ID = "saas-applied-filters-store"
EXPORT_ACTIONS_ID = "saas-export-actions"
DOWNLOAD_REPORT_ID = "saas-download-report"
DOWNLOAD_DATA_ID = "saas-download-report-data"
DOWNLOAD_COMPARE_HELP_ID = "saas-download-compare-help"
EXCEL_OPEN_ID = "saas-excel-open"
EXCEL_MODAL_ID = "saas-excel-modal"
EXCEL_SCENARIO_ID = "saas-excel-scenario"
EXCEL_GENERATE_ID = "saas-excel-generate"
EXCEL_CANCEL_ID = "saas-excel-cancel"
EXCEL_DOWNLOAD_DATA_ID = "saas-excel-download-data"
RECON_OPEN_ID = "saas-recon-open"
RECON_MODAL_ID = "saas-recon-modal"
RECON_SCENARIO_ID = "saas-recon-scenario"
RECON_GENERATE_ID = "saas-recon-generate"
RECON_CANCEL_ID = "saas-recon-cancel"
RECON_DOWNLOAD_DATA_ID = "saas-recon-download-data"
PROJECTION_OPEN_ID = "saas-projection-open"
PROJECTION_MODAL_ID = "saas-projection-modal"
PROJECTION_SCENARIO_ID = "saas-projection-scenario"
PROJECTION_HORIZON_ID = "saas-projection-horizon"
PROJECTION_GENERATE_ID = "saas-projection-generate"
PROJECTION_CANCEL_ID = "saas-projection-cancel"
PROJECTION_DOWNLOAD_DATA_ID = "saas-projection-download-data"
SUBNAV_ID = "saas-subnav"
SUBNAV_MODELS_ID = "saas-subnav-models"
MEV_TIME_SERIES_SECTION_ID = "saas-mev-time-series-section"
SUBNAV_VIEW_ID = "saas-subnav-view"
SUBNAV_VIEW_TOGGLE_ID = "saas-subnav-view-toggle"
SUBNAV_VIEW_MENU_ID = "saas-subnav-view-menu"
SUBNAV_VIEW_FILTER_KEY = "saas-subnav-view"

REFERENCE_LINES_ID = "saas-reference-lines"
REFERENCE_LINES_TOGGLE_ID = "saas-reference-lines-toggle"
REFERENCE_LINES_MENU_ID = "saas-reference-lines-menu"
REFERENCE_LINES_FILTER_KEY = "saas-reference-lines"

MEV_LABEL_MODE_ID = "saas-mev-label-mode"
MEV_LABEL_MODE_TOGGLE_ID = "saas-mev-label-mode-toggle"
MEV_LABEL_MODE_MENU_ID = "saas-mev-label-mode-menu"
MEV_LABEL_MODE_FILTER_KEY = "saas-mev-label-mode"
HISTORICAL_STATS_FILTER_ID = "saas-historical-stats-filter"
HISTORICAL_STATS_FILTER_KEY = "saas-historical-stats"
HISTORICAL_STATS_ID = "saas-historical-stats"

SEGMENT_ALL_VALUE = "all"
DEFAULT_SEGMENT = SEGMENT_ALL_VALUE
SUBNAV_VIEW_OPTIONS = [
    {"label": "History", "value": "history"},
    {"label": "Projection", "value": "projection"},
    {"label": "History & Projection", "value": "history_projection"},
]
DEFAULT_SUBNAV_VIEW = "history_projection"
REFERENCE_LINES_OPTIONS = [
    {"label": "None", "value": "none"},
    {"label": "Min-Max lines", "value": "min_max"},
    {"label": "Monitoring", "value": "monitoring"},
]
DEFAULT_REFERENCE_LINES = "none"
MEV_LABEL_MODE_OPTIONS = [
    {"label": "Descriptive Name", "value": "long_name"},
    {"label": "US Mnemonic", "value": "us_mnemonic"},
    {"label": "Group Mnemonic", "value": "group_mnemonic"},
]
DEFAULT_MEV_LABEL_MODE = "us_mnemonic"
HISTORICAL_STATS_OPTIONS = [
    {"label": "Off", "value": "off"},
    {"label": "On", "value": "on"},
]
DEFAULT_HISTORICAL_STATS_VALUE = "off"

MODEL_SCENARIO_FILTER_TYPE = "saas-model-scenario-filter"
MODEL_SCENARIO_SELECT_ALL_TYPE = "saas-model-scenario-select-all"
MODEL_SCENARIO_TOGGLE_TYPE = "saas-model-scenario-toggle"
MODEL_SCENARIO_MENU_TYPE = "saas-model-scenario-menu"
MODEL_SCENARIO_OPTION_TYPE = "saas-model-scenario-option"
MODEL_MEV_TYPE_FILTER_TYPE = "saas-model-mev-type-filter"
MODEL_MEV_TYPE_TOGGLE_TYPE = "saas-model-mev-type-toggle"
MODEL_MEV_TYPE_MENU_TYPE = "saas-model-mev-type-menu"
MODEL_MEV_TYPE_OPTION_TYPE = "saas-model-mev-type-option"
MODEL_MEV_FILTER_TYPE = "saas-model-mev-filter"
MODEL_MEV_SELECT_ALL_TYPE = "saas-model-mev-select-all"
MODEL_MEV_TOGGLE_TYPE = "saas-model-mev-toggle"
MODEL_MEV_MENU_TYPE = "saas-model-mev-menu"
MODEL_MEV_LABEL_TYPE = "saas-model-mev-label"
MODEL_MEV_SINGLE_SECTION_TYPE = "saas-model-mev-single-section"
MODEL_MEV_SINGLE_VALUE_TYPE = "saas-model-mev-single-value"
MODEL_MEV_SINGLE_OPTIONS_TYPE = "saas-model-mev-single-options"
MODEL_MEV_SINGLE_OPTION_TYPE = "saas-model-mev-single-option"
MODEL_MEV_MULTI_SECTION_TYPE = "saas-model-mev-multi-section"
MODEL_MEV_GRID_TYPE = "saas-model-mev-grid"
MODEL_DATE_RANGE_CONTROLS_TYPE = "saas-model-date-range-controls"
MODEL_DATE_RANGE_WINDOW_TYPE = "saas-model-date-range-window"
MODEL_DATE_RANGE_FROM_TYPE = "saas-model-date-range-from"
MODEL_DATE_RANGE_TO_TYPE = "saas-model-date-range-to"
DEFAULT_SCENARIO_FILTER = "all"
MEV_TYPE_OPTIONS = [
    {"label": "Transformed + raw", "value": "family"},
    {"label": "Transformed only", "value": "transformed_only"},
    {"label": "Raw only", "value": "raw_only"},
]
DEFAULT_MEV_TYPE = "family"


def format_segment_label(segment_value: str | None) -> str:
    if not segment_value:
        return "Raw / No Specific Model"
    return segment_value


def _build_run_for_options() -> list[dict]:
    values = SAAS_PAGE_DATA.get("run_for_values") or []
    return [{"label": value, "value": value} for value in values if value]


def _build_segment_options() -> list[dict]:
    values = SAAS_PAGE_DATA.get("segment_values") or []
    return [{"label": "All", "value": SEGMENT_ALL_VALUE}] + [
        {"label": value, "value": value}
        for value in values
        if value
    ]


RUN_FOR_OPTIONS = _build_run_for_options()
DEFAULT_RUN_FOR_VALUE = RUN_FOR_OPTIONS[0]["value"] if RUN_FOR_OPTIONS else ""
COMPARE_AGAINST_OPTIONS = [{"label": "None", "value": COMPARE_AGAINST_NONE_VALUE}] + [
    {"label": option["label"], "value": option["value"]}
    for option in RUN_FOR_OPTIONS
    if option.get("value") and option["value"] != DEFAULT_RUN_FOR_VALUE
]
DEFAULT_COMPARE_AGAINST_VALUES = [COMPARE_AGAINST_NONE_VALUE]
SEGMENT_NAME_OPTIONS = _build_segment_options()


def _build_excel_scenario_options() -> list[dict]:
    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    scenario_values: list[str] = []
    if time_series_df is not None and not time_series_df.empty and "Scenario" in time_series_df.columns:
        scenario_values = [str(value).strip().lower() for value in time_series_df["Scenario"].dropna().unique()]
    order = {"baseline": 0, "intsevere": 1, "other": 2}
    ordered = sorted({value for value in scenario_values if value}, key=lambda value: order.get(value, 99))
    return [
        {"label": SAAS_SCENARIO_LABEL_MAP.get(value, value.replace("_", " ").title()), "value": value}
        for value in ordered
    ]


EXCEL_SCENARIO_OPTIONS = _build_excel_scenario_options()
DEFAULT_EXCEL_SCENARIO = next(
    (option["value"] for option in EXCEL_SCENARIO_OPTIONS if option["value"] == "intsevere"),
    EXCEL_SCENARIO_OPTIONS[0]["value"] if EXCEL_SCENARIO_OPTIONS else "",
)


def _format_range_period_label(period: str) -> str:
    try:
        date_value = date.fromisoformat(period)
        quarter = ((date_value.month - 1) // 3) + 1
        return f"{date_value.year}Q{quarter}"
    except (TypeError, ValueError):
        return period


def _build_date_range_options(periods: list[str], all_label: str) -> list[dict]:
    return [{"label": all_label, "value": ""}] + [
        {"label": _format_range_period_label(period), "value": period}
        for period in periods
    ]


def _build_single_select_filter(
    label: str,
    *,
    value_id: str,
    toggle_id: str,
    menu_id: str,
    filter_key: str,
    options: list[dict],
    value: str,
    min_width: str = "220px",
) -> html.Div:
    return html.Div(
        className="monitoring-filter",
        style={"minWidth": min_width, "maxWidth": "420px"},
        children=[
            html.Label(label, htmlFor=toggle_id),
            shared_filters.build_single_select_dropdown(
                value_id=value_id,
                toggle_id=toggle_id,
                menu_id=menu_id,
                filter_key=filter_key,
                options=options,
                value=value,
            ),
        ],
    )


def _build_checklist_filter(
    label: str,
    *,
    toggle_id: str,
    menu_id: str,
    checklist_id: str,
    options: list[dict],
    value: list[str],
    button_label: str,
    min_width: str = "220px",
    wrapper_class_name: str = "monitoring-filter",
) -> html.Div:
    select_all_id = None
    if checklist_id == MODEL_NAME_ID:
        select_all_id = MODEL_NAME_SELECT_ALL_ID
    return html.Div(
        className=wrapper_class_name,
        style={"minWidth": min_width, "maxWidth": "420px"},
        children=[
            html.Label(label, htmlFor=toggle_id),
            html.Div(
                className="checkbox-dropdown",
                children=[
                    html.Button(
                        button_label,
                        id=toggle_id,
                        type="button",
                        n_clicks=0,
                        className="checkbox-dropdown-toggle",
                    ),
                    html.Div(
                        id=menu_id,
                        className="checkbox-dropdown-menu",
                        children=[
                            dcc.Checklist(
                                id=select_all_id,
                                options=[{"label": "All", "value": "all"}] if select_all_id else [],
                                value=[],
                                className="pd-models-select-all" if select_all_id else None,
                            ) if select_all_id else None,
                            dcc.Checklist(
                                id=checklist_id,
                                options=options,
                                value=list(value),
                                className="pd-models-checklist",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_inline_segmented_filter(
    label: str,
    *,
    filter_id: str,
    value_id: str,
    filter_key: str,
    options: list[dict],
    value: str,
    min_width: str = "220px",
    wrapper_class_name: str = "monitoring-filter",
    dropdown_kwargs: dict | None = None,
) -> html.Div:
    selected_value = value or (options[0]["value"] if options else "")
    return html.Div(
        id=filter_id,
        className=wrapper_class_name,
        style={"minWidth": min_width, "maxWidth": "260px"},
        children=[
            html.Label(label, htmlFor=value_id),
            dcc.Dropdown(
                id=value_id,
                options=options,
                value=selected_value,
                clearable=False,
                searchable=False,
                style={"display": "none"},
                **(dropdown_kwargs or {}),
            ),
            html.Div(
                className="saas-inline-segmented",
                role="radiogroup",
                **{"aria-label": label},
                children=[
                    html.Button(
                        [
                            html.Span(option["label"], className="single-select-option-label"),
                            html.Span("✓", className="single-select-option-check", **{"aria-hidden": "true"}),
                        ],
                        id={
                            "type": shared_filters.SINGLE_SELECT_OPTION_ID,
                            "filter": filter_key,
                            "value": option["value"],
                        },
                        type="button",
                        n_clicks=0,
                        className="single-select-option is-selected" if option["value"] == selected_value else "single-select-option",
                    )
                    for option in options
                ],
            ),
        ],
    )


def model_descriptive_label(model_name: str) -> str:
    """Model's descriptive name (from the model_characteristic sheet), falling
    back to the raw Model Name when no descriptive name is available."""
    descriptive_map = SAAS_PAGE_DATA.get("model_descriptive_name_map", {})
    return descriptive_map.get(model_name) or model_name


def _build_model_name_options() -> list[dict]:
    values = SAAS_PAGE_DATA.get("model_names", [])
    seen: set[str] = set()
    options: list[dict] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        options.append({"label": model_descriptive_label(value), "value": value})
    return options


def _default_model_selection() -> list[str]:
    return [option["value"] for option in _build_model_name_options()]


def build_model_date_range_controls(
    model_name: str,
    periods: list[str],
    range_value: dict | None = None,
    *,
    disabled: bool = False,
) -> html.Div:
    selection = get_pd_range_selection(range_value, periods)
    preset = get_pd_range_preset(range_value, periods)

    return html.Div(
        className="pd-range-controls",
        **{"aria-label": "Visible date range"},
        children=[
            html.Label([
                html.Span("Window"),
                dcc.Dropdown(
                    id={"type": MODEL_DATE_RANGE_WINDOW_TYPE, "model": model_name},
                    options=[
                        {"label": "All periods", "value": "all"},
                        {"label": "Last 4 quarters", "value": "last-4"},
                        {"label": "Last 8 quarters", "value": "last-8"},
                        {"label": "Last 12 quarters", "value": "last-12"},
                        {"label": "Custom range", "value": "custom", "disabled": True},
                    ],
                    value=preset,
                    clearable=False,
                    disabled=disabled,
                ),
            ]),
            html.Label([
                html.Span("From"),
                dcc.Dropdown(
                    id={"type": MODEL_DATE_RANGE_FROM_TYPE, "model": model_name},
                    options=_build_date_range_options(periods, "Earliest"),
                    value=selection["from"],
                    clearable=False,
                    disabled=disabled or not periods,
                ),
            ]),
            html.Label([
                html.Span("To"),
                dcc.Dropdown(
                    id={"type": MODEL_DATE_RANGE_TO_TYPE, "model": model_name},
                    options=_build_date_range_options(periods, "Latest"),
                    value=selection["to"],
                    clearable=False,
                    disabled=disabled or not periods,
                ),
            ]),
        ],
    )


def _build_section_subnav() -> html.Div:
    return html.Div(
        id=SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group saas-subnav-group",
                children=[
                    html.Div("Models in Scope", className="monitoring-section-subnav-label"),
                    html.Div(id=SUBNAV_MODELS_ID, className="saas-subnav-models"),
                ],
            ),
        ],
    )


def _build_top_bar() -> html.Div:
    return html.Div(
        className="top-bar",
        children=[
            html.Div(
                style={"flex": "1"},
                children=[
                    html.Div("Scenario Analysis as a Service (SAAS)", className="monitoring-dashboard-title"),
                    html.Div(
                        className="monitoring-controls saas-top-filter-row saas-primary-filter-row",
                        children=[
                            _build_single_select_filter(
                                "Reporting Cycle",
                                value_id=RUN_FOR_ID,
                                toggle_id=RUN_FOR_TOGGLE_ID,
                                menu_id=RUN_FOR_MENU_ID,
                                filter_key=RUN_FOR_FILTER_KEY,
                                options=RUN_FOR_OPTIONS,
                                value=DEFAULT_RUN_FOR_VALUE,
                                min_width="260px",
                            ),
                            _build_checklist_filter(
                                "Compare To",
                                toggle_id=COMPARE_AGAINST_TOGGLE_ID,
                                menu_id=COMPARE_AGAINST_MENU_ID,
                                checklist_id=COMPARE_AGAINST_ID,
                                options=COMPARE_AGAINST_OPTIONS,
                                value=DEFAULT_COMPARE_AGAINST_VALUES,
                                button_label="None",
                                min_width="280px",
                            ),
                            _build_single_select_filter(
                                "Segment",
                                value_id=SEGMENT_NAME_ID,
                                toggle_id=SEGMENT_TOGGLE_ID,
                                menu_id=SEGMENT_MENU_ID,
                                filter_key=SEGMENT_FILTER_KEY,
                                options=SEGMENT_NAME_OPTIONS,
                                value=DEFAULT_SEGMENT,
                            ),
                            _build_checklist_filter(
                                "Specific Models",
                                toggle_id=MODEL_NAME_TOGGLE_ID,
                                menu_id=MODEL_NAME_MENU_ID,
                                checklist_id=MODEL_NAME_ID,
                                options=_build_model_name_options(),
                                value=_default_model_selection(),
                                button_label="Select models",
                                min_width="360px",
                                wrapper_class_name="monitoring-filter monitoring-model-filter",
                            ),
                            html.Div(
                                className="monitoring-filter saas-top-filter-action",
                                children=[
                                    html.Div(
                                        className="pd-mev-filter-actions",
                                        children=[
                                            html.Button(
                                                "Apply filters",
                                                id=APPLY_FILTERS_ID,
                                                className="btn pd-mev-filter-reset saas-top-filter-reset saas-top-filter-apply",
                                                n_clicks=0,
                                                type="button",
                                                title="Load the SAAS charts using the selected filters.",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        "",
                        id=FILTER_HELP_ID,
                        className="monitoring-filter-help",
                    ),
                    html.Div(
                        className="monitoring-controls saas-top-filter-row saas-secondary-filter-row",
                        children=[
                            _build_single_select_filter(
                                "Snapshot Period",
                                value_id=SUBNAV_VIEW_ID,
                                toggle_id=SUBNAV_VIEW_TOGGLE_ID,
                                menu_id=SUBNAV_VIEW_MENU_ID,
                                filter_key=SUBNAV_VIEW_FILTER_KEY,
                                options=SUBNAV_VIEW_OPTIONS,
                                value=DEFAULT_SUBNAV_VIEW,
                                min_width="240px",
                            ),
                            _build_single_select_filter(
                                "Reference Lines",
                                value_id=REFERENCE_LINES_ID,
                                toggle_id=REFERENCE_LINES_TOGGLE_ID,
                                menu_id=REFERENCE_LINES_MENU_ID,
                                filter_key=REFERENCE_LINES_FILTER_KEY,
                                options=REFERENCE_LINES_OPTIONS,
                                value=DEFAULT_REFERENCE_LINES,
                                min_width="220px",
                            ),
                            _build_single_select_filter(
                                "MEV Label",
                                value_id=MEV_LABEL_MODE_ID,
                                toggle_id=MEV_LABEL_MODE_TOGGLE_ID,
                                menu_id=MEV_LABEL_MODE_MENU_ID,
                                filter_key=MEV_LABEL_MODE_FILTER_KEY,
                                options=MEV_LABEL_MODE_OPTIONS,
                                value=DEFAULT_MEV_LABEL_MODE,
                                min_width="220px",
                            ),
                            _build_inline_segmented_filter(
                                "Historical Statistics",
                                filter_id=HISTORICAL_STATS_FILTER_ID,
                                value_id=HISTORICAL_STATS_ID,
                                filter_key=HISTORICAL_STATS_FILTER_KEY,
                                options=HISTORICAL_STATS_OPTIONS,
                                value=DEFAULT_HISTORICAL_STATS_VALUE,
                                min_width="220px",
                                wrapper_class_name="monitoring-filter saas-historical-stats-filter is-hidden",
                            ),
                        ],
                    ),
                    _build_section_subnav(),
                ],
            ),
            html.Details(
                id=EXPORT_ACTIONS_ID,
                className="saas-download-actions is-disabled",
                title="Apply filters to enable export.",
                children=[
                    html.Summary(
                        [
                            html.Span("⬇", className="saas-download-report-icon", **{"aria-hidden": "true"}),
                            html.Span("Export", className="saas-download-toggle-label"),
                            html.Span("▾", className="saas-download-caret", **{"aria-hidden": "true"}),
                        ],
                        className="btn pd-mev-filter-reset saas-download-toggle",
                    ),
                    html.Div(
                        className="saas-download-menu-panel",
                        children=[
                            html.Button(
                                [
                                    html.Span("Current charts", className="saas-download-item-title"),
                                    html.Span("HTML / PDF", className="saas-download-item-format"),
                                ],
                                id=DOWNLOAD_REPORT_ID,
                                className="saas-download-menu-item",
                                n_clicks=0,
                                type="button",
                            ),
                            html.Button(
                                [
                                    html.Span("Historical range analysis", className="saas-download-item-title"),
                                    html.Span("Excel", className="saas-download-item-format"),
                                ],
                                id=EXCEL_OPEN_ID,
                                className="saas-download-menu-item",
                                n_clicks=0,
                                type="button",
                            ),
                            html.Button(
                                [
                                    html.Span("Historical reconciliation", className="saas-download-item-title"),
                                    html.Span("Excel", className="saas-download-item-format"),
                                ],
                                id=RECON_OPEN_ID,
                                className="saas-download-menu-item",
                                n_clicks=0,
                                type="button",
                                disabled=True,
                            ),
                            html.Button(
                                [
                                    html.Span("Projection comparison", className="saas-download-item-title"),
                                    html.Span("Excel", className="saas-download-item-format"),
                                ],
                                id=PROJECTION_OPEN_ID,
                                className="saas-download-menu-item",
                                n_clicks=0,
                                type="button",
                                disabled=True,
                            ),
                            html.Div(
                                "Select a Compare To reporting cycle to enable the comparison exports.",
                                id=DOWNLOAD_COMPARE_HELP_ID,
                                className="saas-download-compare-note",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_excel_modal() -> html.Div:
    return html.Div(
        id=EXCEL_MODAL_ID,
        className="saas-modal-overlay",
        children=html.Div(
            className="saas-modal",
            children=[
                html.Div("Historical Range Analysis report", className="saas-modal-title"),
                html.P(
                    "Choose the scenario to use for the Severely Adverse projection metrics. "
                    "The workbook (README, Metrics and Charts) is built from your current filters.",
                    className="saas-modal-subtitle",
                ),
                html.Label("Scenario", htmlFor=EXCEL_SCENARIO_ID, className="saas-modal-label"),
                dcc.Dropdown(
                    id=EXCEL_SCENARIO_ID,
                    options=EXCEL_SCENARIO_OPTIONS,
                    value=DEFAULT_EXCEL_SCENARIO,
                    clearable=False,
                    searchable=False,
                    className="saas-modal-dropdown",
                ),
                html.Div(
                    className="saas-modal-actions",
                    children=[
                        html.Button(
                            "Cancel",
                            id=EXCEL_CANCEL_ID,
                            type="button",
                            n_clicks=0,
                            className="btn saas-modal-cancel",
                        ),
                        html.Button(
                            "Generate Excel",
                            id=EXCEL_GENERATE_ID,
                            type="button",
                            n_clicks=0,
                            className="btn btn-primary saas-modal-generate",
                        ),
                    ],
                ),
            ],
        ),
    )


def _build_recon_modal() -> html.Div:
    return html.Div(
        id=RECON_MODAL_ID,
        className="saas-modal-overlay",
        children=html.Div(
            className="saas-modal",
            children=[
                html.Div("Historical Reconciliation report", className="saas-modal-title"),
                html.P(
                    "Reconciles each MEV's historical values across the primary Reporting Cycle and the "
                    "Compare To cycle(s), over the overlapping historical dates. "
                    "Select at least one Compare To cycle before exporting. The relative threshold defaults "
                    "to 3.0% and can be changed in the Summary tab (cell B1).",
                    className="saas-modal-subtitle",
                ),
                html.Label("Scenario", htmlFor=RECON_SCENARIO_ID, className="saas-modal-label"),
                dcc.Dropdown(
                    id=RECON_SCENARIO_ID,
                    options=EXCEL_SCENARIO_OPTIONS,
                    value=DEFAULT_EXCEL_SCENARIO,
                    clearable=False,
                    searchable=False,
                    className="saas-modal-dropdown",
                ),
                html.Div(
                    className="saas-modal-actions",
                    children=[
                        html.Button(
                            "Cancel",
                            id=RECON_CANCEL_ID,
                            type="button",
                            n_clicks=0,
                            className="btn saas-modal-cancel",
                        ),
                        html.Button(
                            "Generate Excel",
                            id=RECON_GENERATE_ID,
                            type="button",
                            n_clicks=0,
                            className="btn btn-primary saas-modal-generate",
                        ),
                    ],
                ),
            ],
        ),
    )


def _build_projection_modal() -> html.Div:
    return html.Div(
        id=PROJECTION_MODAL_ID,
        className="saas-modal-overlay",
        children=html.Div(
            className="saas-modal",
            children=[
                html.Div("Projection Comparison report", className="saas-modal-title"),
                html.P(
                    "Compares each MEV's projection across the primary Reporting Cycle and the Compare To "
                    "cycle(s), aligned by quarter offset (Q0, Q1, ...). Projections are expected to differ - "
                    "the Summary characterises the divergence. Select at least one Compare To cycle before exporting.",
                    className="saas-modal-subtitle",
                ),
                html.Label("Scenario", htmlFor=PROJECTION_SCENARIO_ID, className="saas-modal-label"),
                dcc.Dropdown(
                    id=PROJECTION_SCENARIO_ID,
                    options=EXCEL_SCENARIO_OPTIONS,
                    value=DEFAULT_EXCEL_SCENARIO,
                    clearable=False,
                    searchable=False,
                    className="saas-modal-dropdown",
                ),
                html.Label("Projection horizon", htmlFor=PROJECTION_HORIZON_ID, className="saas-modal-label"),
                dcc.Dropdown(
                    id=PROJECTION_HORIZON_ID,
                    options=[
                        {"label": "Up to Q9", "value": 9},
                        {"label": "Up to Q20", "value": 20},
                    ],
                    value=20,
                    clearable=False,
                    searchable=False,
                    className="saas-modal-dropdown",
                ),
                html.Div(
                    className="saas-modal-actions",
                    children=[
                        html.Button(
                            "Cancel",
                            id=PROJECTION_CANCEL_ID,
                            type="button",
                            n_clicks=0,
                            className="btn saas-modal-cancel",
                        ),
                        html.Button(
                            "Generate Excel",
                            id=PROJECTION_GENERATE_ID,
                            type="button",
                            n_clicks=0,
                            className="btn btn-primary saas-modal-generate",
                        ),
                    ],
                ),
            ],
        ),
    )


def build_apply_prompt() -> html.Div:
    """Placeholder + how-to guide shown until the user applies the filters."""
    return html.Div(
        className="section-card pd-mev-empty-state saas-getting-started",
        children=[
            html.Div("Getting started with the SAAS dashboard", className="pd-mev-chart-title"),
            html.P(
                "Set your filters in the top bar, then click “Apply filters” to render the charts and enable Export. "
                "Use the quick guide below to move from setup to analysis smoothly.",
                className="pd-section-subtitle",
            ),
            html.Div(
                className="saas-getting-started-summary",
                children=[
                    html.Div("Quick start", className="saas-getting-started-summary-title"),
                    html.Div(
                        className="saas-getting-started-highlights",
                        children=[
                            html.Span("1. Choose Reporting Cycle, scope, and view options.", className="saas-getting-started-highlight"),
                            html.Span("2. Click Apply filters to load charts and unlock Export.", className="saas-getting-started-highlight"),
                            html.Span("3. Use Compare To only when you want cycle-to-cycle comparisons.", className="saas-getting-started-highlight"),
                        ],
                    ),
                    html.Div(
                        "Charts and exports always reflect the most recent applied filter snapshot, not any unapplied edits still sitting in the top bar.",
                        className="saas-getting-started-summary-note",
                    ),
                ],
            ),
            html.Ol(
                className="saas-getting-started-steps",
                children=[
                    html.Li([
                        html.Strong("Pick a Reporting Cycle. "),
                        "Choose the cycle to review (e.g. CCAR 2026). This sets the primary “Projection starts” point for every chart.",
                    ]),
                    html.Li([
                        html.Strong("(Optional) Compare To. "),
                        "Add one or more reporting cycles to overlay against the primary cycle for benchmarking. "
                        "Compare To also powers the Historical Reconciliation and Projection Comparison exports.",
                    ]),
                    html.Li([
                        html.Strong("Choose your model scope. "),
                        "Select a Segment or a set of Specific Models — these two filters cannot be combined.",
                    ]),
                    html.Li([
                        html.Strong("Set the view options. "),
                        "Adjust Snapshot Period (History, Projection, or History & Projection), Reference Lines "
                        "(None, Min-Max, or Monitoring), and the MEV Label convention.",
                        html.Span(
                            "Note: the Monitoring reference lines describe a single reporting cycle, so they "
                            "can't be combined with Compare To. To use Monitoring, set Compare To back to "
                            "“None”; to compare cycles, choose None or Min-Max reference lines instead.",
                            className="saas-getting-started-note",
                        ),
                    ]),
                    html.Li([
                        html.Strong("Click “Apply filters”. "),
                        "The charts load here, one card per model. Nothing renders until you apply, and the Export menu stays disabled until this step is complete.",
                    ]),
                    html.Li([
                        html.Strong("Fine-tune each model card. "),
                        "Within a card you can switch the scenario, MEV, and visible date range without re-applying the top filters. These card-level changes are for on-screen analysis only.",
                    ]),
                    html.Li([
                        html.Strong("Export what you need. "),
                        "Open the Export menu in the top-right for:",
                        html.Ul(
                            className="saas-getting-started-substeps",
                            children=[
                                html.Li([
                                    html.Strong("Export Charts (PDF/HTML) — "),
                                    "a shareable visual record of the on-screen charts (open in a browser and print to PDF).",
                                ]),
                                html.Li([
                                    html.Strong("Historical Range Analysis (Excel) — "),
                                    "for one chosen scenario: per-model metrics and charts (history statistics, severely-adverse "
                                    "projection min/max, and the ±2-STD breach tests).",
                                ]),
                                html.Li([
                                    html.Strong("Historical Reconciliation (Excel) — "),
                                    "checks that history agrees across reporting cycles over the overlapping dates "
                                    "(it should be the same or very close). Requires Compare To.",
                                ]),
                                html.Li([
                                    html.Strong("Projection Comparison (Excel) — "),
                                    "compares projection paths across cycles, aligned by quarter offset, up to Q9 or Q20. "
                                    "Projections are expected to differ, so it summarises the divergence. Requires Compare To.",
                                ]),
                            ],
                        ),
                        html.Span(
                            "Note: Export uses the last applied top-bar filters. If you change Reporting Cycle, Compare To, Segment, Specific Models, Snapshot Period, Reference Lines, or MEV Label, click Apply filters again before exporting. The two comparison exports also need at least one Compare To cycle, and each Excel starts with a README tab explaining its columns.",
                            className="saas-getting-started-note",
                        ),
                    ]),
                    html.Li([
                        html.Strong("Start over. "),
                        "Refresh the page at any time to clear the charts and return to this starting view.",
                    ]),
                ],
            ),
        ],
    )


def _build_chart_canvas() -> html.Section:
    return html.Section(
        id=MEV_TIME_SERIES_SECTION_ID,
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Executive summary: "),
                    "The Scenario Analysis as a Service (SAAS) dashboard is a self-service tool for reviewing the macro-economic variables (MEVs) that drive credit risk models under stress scenarios, across reporting cycles. By bringing each MEV's history and forward projections together, it helps users understand the drivers behind the models and sense-check the scenario projections.",
                ],
            ),
            html.Div(
                id=MEV_MODEL_PANELS_ID,
                className="saas-model-panel-stack",
                children=build_apply_prompt(),
            ),
        ],
    )


def page_layout() -> list:
    """Top bar + SAAS MEV chart canvas."""
    return [
        dcc.Store(id=COMPARE_AGAINST_PREV_STORE_ID, data=list(DEFAULT_COMPARE_AGAINST_VALUES)),
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
        dcc.Download(id=DOWNLOAD_DATA_ID),
        dcc.Download(id=EXCEL_DOWNLOAD_DATA_ID),
        dcc.Download(id=RECON_DOWNLOAD_DATA_ID),
        dcc.Download(id=PROJECTION_DOWNLOAD_DATA_ID),
        _build_excel_modal(),
        _build_recon_modal(),
        _build_projection_modal(),
        _build_top_bar(),
        html.Div(
            className="content",
            children=[
                html.Div(
                    id="tab-saas",
                    className="tab-panel active pd-performance-app saas-page",
                    children=[_build_chart_canvas()],
                ),
            ],
        ),
    ]
