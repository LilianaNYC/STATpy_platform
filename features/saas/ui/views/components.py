"""Small Dash view helpers for the SAAS workspace."""

from __future__ import annotations

from datetime import datetime
import re

from dash import dcc, html

from .....shared.ui.charts import (
    SAAS_SCENARIO_LABEL_MAP,
    compute_saas_monitoring_band_spec,
)
from .....shared.domain.mev_range import format_pd_mev_value
from ...data_access import SAAS_PAGE_DATA
from . import workspace as layout
from ...domain import metrics, records, selectors

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def single_select_option_classes(value: str | None, option_ids: list[dict]) -> list[str]:
    return [
        "single-select-option is-selected" if option_id["value"] == value else "single-select-option"
        for option_id in option_ids
    ]


def toggle_menu_class(current_class: str | None, *, base_class: str) -> str:
    if "open" in (current_class or "").split():
        return base_class
    return f"{base_class} open"


def format_monitoring_date(date_value) -> str:
    if date_value is None:
        return "—"
    if hasattr(date_value, "year") and hasattr(date_value, "month"):
        year = int(date_value.year)
        month = int(date_value.month)
    else:
        text = str(date_value).strip()
        parsed_date = None
        for candidate in (text[:10], text):
            try:
                parsed_date = datetime.fromisoformat(candidate)
                break
            except ValueError:
                continue
        if parsed_date is None:
            return text
        year = parsed_date.year
        month = parsed_date.month
    quarter = ((month - 1) // 3) + 1
    return f"{year}Q{quarter}"


def build_monitoring_threshold_chips(band_spec: dict | None) -> list[html.Span]:
    if not band_spec:
        return []

    def chip(label, value, tone):
        return html.Span(
            [html.Strong(label), value],
            className=f"pd-mev-threshold-chip pd-mev-threshold-chip-{tone}",
        )

    return [
        chip(
            "Green",
            f"{format_pd_mev_value(band_spec['green_low'])} to {format_pd_mev_value(band_spec['green_high'])}",
            "green",
        ),
        chip(
            "Amber low",
            f"{format_pd_mev_value(band_spec['amber_low_low'])} to {format_pd_mev_value(band_spec['amber_low_high'])}",
            "amber",
        ),
        chip(
            "Amber high",
            f"{format_pd_mev_value(band_spec['amber_high_low'])} to {format_pd_mev_value(band_spec['amber_high_high'])}",
            "amber",
        ),
        chip(
            "Red",
            f"< {format_pd_mev_value(band_spec['red_low_cutoff'])} or > {format_pd_mev_value(band_spec['red_high_cutoff'])}",
            "red",
        ),
    ]


def monitoring_marker_legend_item(
    label: str,
    value_text: str,
    tone: str,
    *,
    line_color: str | None = None,
    line_dash: str | None = None,
) -> html.Div:
    line_style = {}
    if line_color:
        line_style["borderTopColor"] = line_color
    if line_dash:
        line_style["borderTopStyle"] = line_dash
    return html.Div(
        className=f"pd-mev-marker-legend-item pd-mev-marker-legend-item-{tone}",
        children=[
            html.Span(
                className=f"pd-mev-marker-legend-line pd-mev-marker-legend-line-{tone}",
                style=line_style or None,
                **{"aria-hidden": "true"},
            ),
            html.Span(
                className="pd-mev-marker-legend-copy",
                children=[
                    html.Span(label, className="pd-mev-marker-legend-label"),
                    html.Span(value_text, className="pd-mev-marker-legend-date"),
                ],
            ),
        ],
    )


_MONITORING_SCENARIO_COLORS = {
    "light": {"baseline": "#16a34a", "intsevere": "#dc2626", "_default": "#1e3a8a"},
    "dark": {"baseline": "#86efac", "intsevere": "#fb7185", "_default": "#93c5fd"},
}


def monitoring_scenario_legend_item(selected_scenarios, theme_value: str | None = None) -> html.Div | None:
    normalized_scenarios = selectors.normalize_selected_scenarios(selected_scenarios)
    if not normalized_scenarios:
        return None
    scenario_value = normalized_scenarios[0]
    scenario_label = SAAS_SCENARIO_LABEL_MAP.get(scenario_value, scenario_value.replace("_", " ").title())
    palette = _MONITORING_SCENARIO_COLORS.get(selectors.normalize_theme_value(theme_value), _MONITORING_SCENARIO_COLORS["light"])
    scenario_color = palette.get(scenario_value, palette["_default"])
    return monitoring_marker_legend_item(
        "Scenario",
        scenario_label,
        "series",
        line_color=scenario_color,
        line_dash="solid",
    )


def build_monitoring_summary(
    records_: list[dict],
    selected_mev_mode,
    selected_scenarios,
    selected_mevs,
    primary_run_for: str | None,
    development_date,
    current_date,
    theme_value: str | None = None,
):
    monitoring_records = records.filter_records_by_mevs(
        records.filter_records_by_scenarios(
            records_,
            selected_scenarios,
        ),
        selected_mevs,
    )
    band_spec = compute_saas_monitoring_band_spec(
        monitoring_records,
        primary_run_for=primary_run_for,
        development_date=development_date,
    )

    threshold_items = build_monitoring_threshold_chips(band_spec)
    marker_items = []
    scenario_item = monitoring_scenario_legend_item(selected_scenarios, theme_value)
    if scenario_item is not None:
        marker_items.append(scenario_item)
    if development_date is not None:
        marker_items.append(
            monitoring_marker_legend_item(
                "Development Date",
                format_monitoring_date(development_date),
                "development",
            )
        )
    if current_date is not None:
        marker_items.append(
            monitoring_marker_legend_item(
                "Scenario Date",
                format_monitoring_date(current_date),
                "current",
            )
        )

    summary_rows = []
    if threshold_items:
        summary_rows.append(html.Div(threshold_items, className="pd-mev-monitoring-summary-row pd-mev-monitoring-summary-row-thresholds"))
    if marker_items:
        summary_rows.append(html.Div(marker_items, className="pd-mev-monitoring-summary-row pd-mev-monitoring-summary-row-markers"))

    if not summary_rows:
        return None
    return html.Div(summary_rows, className="pd-mev-monitoring-summary", **{"aria-label": "Monitoring summary"})


def format_historical_dispersion_date(date_value) -> str:
    if date_value is None:
        return "—"
    if hasattr(date_value, "strftime"):
        return date_value.strftime("%b %d, %Y").replace(" 0", " ")
    return str(date_value)


def build_historical_dispersion_summary(records_: list[dict], selected_scenarios):
    stats = metrics.compute_historical_dispersion_stats(records_, selected_scenarios)
    if not stats:
        return None

    if not stats.get("has_dispersion"):
        return html.Div(
            className="saas-historical-dispersion saas-historical-dispersion-empty",
            children=[
                html.Div("Historical Dispersion", className="saas-historical-dispersion-title"),
                html.Div(
                    "Add another visible line through Scenario or Compare To to compute historical dispersion statistics.",
                    className="saas-historical-dispersion-note",
                ),
            ],
        )

    def stat_card(label: str, value: str, tooltip: str, tone: str = "default"):
        return html.Div(
            className=f"saas-historical-dispersion-card is-{tone}",
            children=[
                html.Div(
                    className="saas-historical-dispersion-card-label-row",
                    children=[
                        html.Div(label, className="saas-historical-dispersion-card-label"),
                        html.Span(
                            "i",
                            className="pd-info-chip saas-historical-dispersion-info",
                            title=tooltip,
                            **{"aria-label": f"{label}. {tooltip}"},
                        ),
                    ],
                ),
                html.Div(value, className="saas-historical-dispersion-card-value"),
            ],
        )

    max_range_caption = format_historical_dispersion_date(stats.get("max_range_date"))
    return html.Div(
        className="saas-historical-dispersion",
        children=[
            html.Div(
                className="saas-historical-dispersion-header",
                children=[
                    html.Div("Historical Dispersion", className="saas-historical-dispersion-title"),
                    html.Div("Computed from the exact lines visible in this chart.", className="saas-historical-dispersion-note"),
                ],
            ),
            html.Div(
                className="saas-historical-dispersion-grid",
                children=[
                    stat_card(
                        "Visible lines",
                        str(stats["visible_lines"]),
                        "Number of distinct chart lines included in this historical dispersion calculation.",
                        "neutral",
                    ),
                    stat_card(
                        "Common quarters",
                        str(stats["matched_quarters"]),
                        "Number of historical dates with at least two visible line values, so dispersion can be computed.",
                        "neutral",
                    ),
                    stat_card(
                        "Avg range",
                        format_pd_mev_value(stats["avg_range"]),
                        "Average across common historical quarters of max(value) minus min(value) across the visible lines.",
                        "blue",
                    ),
                    stat_card(
                        "Max range",
                        format_pd_mev_value(stats["max_range"]),
                        "Largest single-quarter spread between the highest and lowest visible line values.",
                        "amber",
                    ),
                    stat_card(
                        "Avg stdev",
                        format_pd_mev_value(stats["avg_stddev"]),
                        "Average across common historical quarters of the population standard deviation across the visible lines.",
                        "blue",
                    ),
                    stat_card(
                        "Max stdev",
                        format_pd_mev_value(stats["max_stddev"]),
                        "Largest single-quarter population standard deviation across the visible line values.",
                        "amber",
                    ),
                ],
            ),
            html.Div(f"Worst quarter by range: {max_range_caption}", className="saas-historical-dispersion-footer"),
        ],
    )


def build_empty_state(title: str, copy: str):
    return html.Div(
        className="section-card pd-mev-empty-state",
        children=[
            html.Div(title, className="pd-mev-chart-title"),
            html.P(copy, className="pd-section-subtitle"),
        ],
    )


def mev_picker_label(selected_mev_mode: str | None) -> str:
    normalized_mode = selectors.normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        return "MEV Family"
    if normalized_mode == "transformed_only":
        return "Transformed MEVs"
    return "Raw MEVs"


def mev_picker_empty_label(selected_mev_mode: str | None) -> str:
    normalized_mode = selectors.normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        return "Select transformed MEV"
    if normalized_mode == "transformed_only":
        return "Select transformed MEVs"
    return "Select raw MEVs"


def mev_picker_section_class(*, visible: bool) -> str:
    return "saas-mev-picker-section" if visible else "saas-mev-picker-section is-hidden"


def build_single_mev_option_buttons(options: list[dict], selected_value: str | None, model_name: str):
    return [
        html.Button(
            [
                html.Span(option["label"], className="single-select-option-label"),
                html.Span("\u2713", className="single-select-option-check", **{"aria-hidden": "true"}),
            ],
            id={"type": layout.MODEL_MEV_SINGLE_OPTION_TYPE, "model": model_name, "value": option["value"]},
            type="button",
            n_clicks=0,
            className="single-select-option is-selected" if option["value"] == selected_value else "single-select-option",
        )
        for option in options
    ]


def scenario_toggle_label(selected_scenarios, scenario_options: list[dict]) -> str:
    normalized_scenarios = selectors.normalize_selected_scenarios(selected_scenarios, scenario_options)
    if not normalized_scenarios:
        return "Select scenarios"

    all_values = [option["value"] for option in scenario_options if option.get("value")]
    if all_values and set(normalized_scenarios) == set(all_values):
        return "All"

    label_by_value = {option["value"]: option["label"] for option in scenario_options if option.get("value")}
    if len(normalized_scenarios) == 1:
        return label_by_value.get(normalized_scenarios[0], normalized_scenarios[0])
    return f"{len(normalized_scenarios)} scenarios selected"


def single_selected_scenario(selected_scenarios, scenario_options: list[dict]) -> str:
    normalized_scenarios = selectors.normalize_selected_scenarios(selected_scenarios, scenario_options)
    if normalized_scenarios:
        return normalized_scenarios[0]
    all_values = [option["value"] for option in scenario_options if option.get("value")]
    return all_values[0] if all_values else ""


def build_model_scenario_dropdown(
    model_name: str,
    selected_scenarios,
    scenario_options: list[dict],
    *,
    single_select: bool = False,
) -> html.Div:
    effective_scenarios = selectors.normalize_selected_scenarios(selected_scenarios, scenario_options)
    all_values = [option["value"] for option in scenario_options if option.get("value")]
    if single_select:
        selected_value = single_selected_scenario(selected_scenarios, scenario_options)
        return html.Div(
            className="checkbox-dropdown single-select-dropdown",
            children=[
                dcc.Dropdown(
                    id={"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": model_name},
                    options=scenario_options,
                    value=selected_value,
                    clearable=False,
                    searchable=False,
                    style={"display": "none"},
                ),
                dcc.Checklist(
                    id={"type": layout.MODEL_SCENARIO_SELECT_ALL_TYPE, "model": model_name},
                    options=[],
                    value=[],
                    style={"display": "none"},
                ),
                html.Button(
                    scenario_toggle_label(selected_value, scenario_options),
                    id={"type": layout.MODEL_SCENARIO_TOGGLE_TYPE, "model": model_name},
                    type="button",
                    n_clicks=0,
                    className="checkbox-dropdown-toggle",
                ),
                html.Div(
                    id={"type": layout.MODEL_SCENARIO_MENU_TYPE, "model": model_name},
                    className="checkbox-dropdown-menu",
                    children=[
                        html.Button(
                            [
                                html.Span(option["label"], className="single-select-option-label"),
                                html.Span("\u2713", className="single-select-option-check"),
                            ],
                            id={"type": layout.MODEL_SCENARIO_OPTION_TYPE, "model": model_name, "value": option["value"]},
                            type="button",
                            n_clicks=0,
                            className="single-select-option is-selected" if option["value"] == selected_value else "single-select-option",
                        )
                        for option in scenario_options
                    ],
                ),
            ],
        )
    return html.Div(
        className="checkbox-dropdown",
        children=[
            html.Button(
                scenario_toggle_label(effective_scenarios, scenario_options),
                id={"type": layout.MODEL_SCENARIO_TOGGLE_TYPE, "model": model_name},
                type="button",
                n_clicks=0,
                className="checkbox-dropdown-toggle",
            ),
            html.Div(
                id={"type": layout.MODEL_SCENARIO_MENU_TYPE, "model": model_name},
                className="checkbox-dropdown-menu",
                children=[
                    dcc.Checklist(
                        id={"type": layout.MODEL_SCENARIO_SELECT_ALL_TYPE, "model": model_name},
                        options=[{"label": "All", "value": "all"}],
                        value=["all"] if all_values and set(effective_scenarios) == set(all_values) else [],
                        className="pd-models-select-all",
                    ),
                    dcc.Checklist(
                        id={"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": model_name},
                        options=scenario_options,
                        value=effective_scenarios,
                        className="pd-models-checklist",
                    ),
                ],
            ),
        ],
    )


def mev_type_toggle_label(selected_mev_mode: str | None, mev_type_options: list[dict]) -> str:
    normalized_mode = selectors.normalize_selected_mev_mode(selected_mev_mode, mev_type_options)
    label_by_value = {option["value"]: option["label"] for option in mev_type_options if option.get("value")}
    return label_by_value.get(normalized_mode, normalized_mode or "Select MEV View")


def build_model_mev_type_dropdown(model_name: str, selected_mev_mode: str | None, mev_type_options: list[dict]) -> html.Div:
    effective_mev_mode = selectors.normalize_selected_mev_mode(selected_mev_mode, mev_type_options)
    return html.Div(
        className="checkbox-dropdown single-select-dropdown",
        children=[
            dcc.Dropdown(
                id={"type": layout.MODEL_MEV_TYPE_FILTER_TYPE, "model": model_name},
                options=mev_type_options,
                value=effective_mev_mode,
                clearable=False,
                searchable=False,
                style={"display": "none"},
            ),
            html.Button(
                mev_type_toggle_label(effective_mev_mode, mev_type_options),
                id={"type": layout.MODEL_MEV_TYPE_TOGGLE_TYPE, "model": model_name},
                type="button",
                n_clicks=0,
                className="checkbox-dropdown-toggle",
            ),
            html.Div(
                id={"type": layout.MODEL_MEV_TYPE_MENU_TYPE, "model": model_name},
                className="checkbox-dropdown-menu single-select-menu",
                children=[
                    html.Button(
                        [
                            html.Span(option["label"], className="single-select-option-label"),
                            html.Span("\u2713", className="single-select-option-check", **{"aria-hidden": "true"}),
                        ],
                        id={"type": layout.MODEL_MEV_TYPE_OPTION_TYPE, "model": model_name, "value": option["value"]},
                        type="button",
                        n_clicks=0,
                        className="single-select-option is-selected" if option["value"] == effective_mev_mode else "single-select-option",
                    )
                    for option in mev_type_options
                ],
            ),
        ],
    )


def mev_toggle_label(
    selected_mev_mode: str | None,
    selected_mev_single,
    selected_mevs_multi,
    single_mev_options: list[dict],
    multi_mev_options: list[dict],
) -> str:
    normalized_mode = selectors.normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        selected_mev_values = selectors.normalize_selected_mevs(selected_mev_single)
        if not selected_mev_values:
            return mev_picker_empty_label(normalized_mode)
        label_by_value = {option["value"]: option["label"] for option in single_mev_options if option.get("value")}
        return label_by_value.get(selected_mev_values[0], selected_mev_values[0])

    selected_mev_values = selectors.normalize_selected_mevs(selected_mevs_multi)
    if not selected_mev_values:
        return mev_picker_empty_label(normalized_mode)

    all_values = [option["value"] for option in multi_mev_options if option.get("value")]
    if all_values and set(selected_mev_values) == set(all_values):
        return "All"

    label_by_value = {option["value"]: option["label"] for option in multi_mev_options if option.get("value")}
    if len(selected_mev_values) == 1:
        return label_by_value.get(selected_mev_values[0], selected_mev_values[0])
    return f"{len(selected_mev_values)} MEVs selected"


def build_model_mev_dropdown(
    model_name: str,
    selected_mev_mode: str | None,
    single_mev_options: list[dict],
    selected_mev_single: str | None,
    multi_mev_options: list[dict],
    selected_mevs_multi: list[str],
) -> html.Div:
    normalized_mode = selectors.normalize_selected_mev_mode(selected_mev_mode)
    show_single_picker = normalized_mode == "family"
    return html.Div(
        className="checkbox-dropdown pd-mev-filter-dropdown",
        children=[
            html.Button(
                mev_toggle_label(
                    normalized_mode,
                    selected_mev_single,
                    selected_mevs_multi,
                    single_mev_options,
                    multi_mev_options,
                ),
                id={"type": layout.MODEL_MEV_TOGGLE_TYPE, "model": model_name},
                type="button",
                n_clicks=0,
                className="checkbox-dropdown-toggle",
            ),
            html.Div(
                id={"type": layout.MODEL_MEV_MENU_TYPE, "model": model_name},
                className="checkbox-dropdown-menu",
                children=[
                    html.Div(
                        id={"type": layout.MODEL_MEV_SINGLE_SECTION_TYPE, "model": model_name},
                        className=mev_picker_section_class(visible=show_single_picker),
                        children=[
                            dcc.Dropdown(
                                id={"type": layout.MODEL_MEV_SINGLE_VALUE_TYPE, "model": model_name},
                                options=single_mev_options,
                                value=selected_mev_single,
                                clearable=False,
                                searchable=False,
                                style={"display": "none"},
                            ),
                            html.Div(
                                id={"type": layout.MODEL_MEV_SINGLE_OPTIONS_TYPE, "model": model_name},
                                className="saas-mev-picker-single-options",
                                children=build_single_mev_option_buttons(single_mev_options, selected_mev_single, model_name),
                            ),
                        ],
                    ),
                    html.Div(
                        id={"type": layout.MODEL_MEV_MULTI_SECTION_TYPE, "model": model_name},
                        className=mev_picker_section_class(visible=not show_single_picker),
                        children=[
                            dcc.Checklist(
                                id={"type": layout.MODEL_MEV_SELECT_ALL_TYPE, "model": model_name},
                                options=[{"label": "All", "value": "all"}],
                                value=["all"] if multi_mev_options and set(selected_mevs_multi) == {option["value"] for option in multi_mev_options if option.get("value")} else [],
                                className="pd-models-select-all",
                            ),
                            dcc.Checklist(
                                id={"type": layout.MODEL_MEV_FILTER_TYPE, "model": model_name},
                                options=multi_mev_options,
                                value=selected_mevs_multi,
                                className="pd-models-checklist",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def model_panel_id(model_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model_name.strip().lower()).strip("-")
    return f"saas-model-panel-{slug}"


def build_subnav_models(segment: str | None, selected_models, *, region: str | None = None, model_group: str | None = None, portfolio: str | None = None):
    """Subnav chip list: always the models in scope. When a Segment filter is
    active the in-scope models are the ones in that segment (group_effective_models
    already applies the filter), so a segment selection narrows the chips rather
    than switching the section to a segment list. Returns (label, children)."""
    groups = selectors.group_effective_models(
        segment, selected_models, region=region, model_group=model_group, portfolio=portfolio
    )

    if not groups:
        return "Models in Scope", []

    # One chip per parent Descriptive Name (not per child Model Name), scrolling
    # to the parent card. Two Model Names sharing a descriptive name would
    # otherwise surface as two identical-looking chips.
    return "Models in Scope", [
        html.Div(
            [
                html.Button(
                    parent_label,
                    type="button",
                    className="saas-subnav-model-chip",
                    **{"data-saas-scroll-target": model_group_id(parent_label)},
                )
                for parent_label, _member_models in groups
            ],
            className="saas-subnav-model-list",
        ),
    ]


def build_model_chart_cards(
    model_name: str,
    records_: list[dict],
    reference_records: list[dict],
    selected_mev_mode,
    selected_scenarios,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    range_value,
    reference_lines: str | None,
    selected_mevs,
    *,
    figure_builder,
    primary_run_for: str | None = None,
    show_historical_statistics=False,
    theme_value: str | None = None,
):
    normalized_mev_mode = selectors.normalize_selected_mev_mode(selected_mev_mode)
    scenario_options = records.build_scenario_options(records_)
    visible_mev_names = {
        str(row.get("MEV Name") or "").strip()
        for row in records_
        if str(row.get("MEV Name") or "").strip()
    }
    effective_mev_values = [
        value for value in selectors.normalize_selected_mevs(selected_mevs)
        if value in visible_mev_names
    ]
    effective_scenarios = selectors.normalize_selected_scenarios(selected_scenarios, scenario_options)

    if not effective_mev_values:
        empty_mev_message = "Choose one transformed MEV in the model header to render the charts."
        if normalized_mev_mode != "family":
            empty_mev_message = "Choose one or more MEVs in the model header to render the charts."
        return [
            html.Article(
                className="pd-mev-chart-card",
                children=[
                    html.Div(
                        className="pd-mev-chart-header",
                        children=[
                            html.Div(
                                [
                                    html.Div("No MEVs selected", className="pd-mev-chart-title"),
                                    html.Div(
                                        empty_mev_message,
                                        className="pd-mev-chart-meta",
                                    ),
                                ]
                            ),
                        ],
                    ),
                ],
            ),
        ]

    if not effective_scenarios:
        return [
            html.Article(
                className="pd-mev-chart-card",
                children=[
                    html.Div(
                        className="pd-mev-chart-header",
                        children=[
                            html.Div(
                                [
                                    html.Div("No scenarios selected", className="pd-mev-chart-title"),
                                    html.Div(
                                        "Choose one or more scenarios in the model header to render the charts.",
                                        className="pd-mev-chart-meta",
                                    ),
                                ]
                            ),
                        ],
                    ),
                ],
            ),
        ]

    if reference_lines == "monitoring" and len(effective_scenarios) != 1:
        return [
            html.Article(
                className="pd-mev-chart-card",
                children=[
                    html.Div(
                        className="pd-mev-chart-header",
                        children=[
                            html.Div(
                                [
                                    html.Div("Choose one scenario", className="pd-mev-chart-title"),
                                    html.Div(
                                        "Monitoring view requires exactly one scenario to be selected.",
                                        className="pd-mev-chart-meta",
                                    ),
                                ]
                            ),
                        ],
                    ),
                ],
            ),
        ]

    cards = []
    development_date = selectors.model_development_date(model_name, primary_run_for)
    current_date = selectors.current_date_for_run_for(primary_run_for)

    for mev_name in effective_mev_values:
        mev_records = [row for row in records_ if str(row.get("MEV Name") or "").strip() == mev_name]
        mev_reference_records = [
            row for row in reference_records
            if str(row.get("MEV Name") or "").strip() == mev_name
        ]
        mev_label = selectors.resolve_mev_label(mev_name, mev_label_mode)
        mev_type = selectors.mev_type_label(mev_name)
        mev_description = selectors.resolve_mev_description(mev_name)
        normalized_label_mode = selectors.normalize_mev_label_mode(mev_label_mode)
        if normalized_label_mode == "long_name" or normalized_label_mode == "group_mnemonic":
            meta_lines = [html.Div(f"US Mnemonic: {mev_name}", className="pd-mev-chart-meta")]
            if mev_description:
                meta_lines.append(html.Div(f"Description: {mev_description}", className="pd-mev-chart-meta"))
        else:
            descriptive_name = selectors.active_mev_label_map("long_name").get(mev_name)
            meta_lines = []
            if descriptive_name:
                meta_lines.append(html.Div(f"Descriptive Name: {descriptive_name}", className="pd-mev-chart-meta"))
            if mev_description:
                meta_lines.append(html.Div(f"Description: {mev_description}", className="pd-mev-chart-meta"))
        monitoring_summary = None
        historical_dispersion_summary = None
        if reference_lines == "monitoring":
            monitoring_summary = build_monitoring_summary(
                mev_reference_records,
                normalized_mev_mode,
                effective_scenarios,
                [mev_name],
                primary_run_for,
                development_date,
                current_date,
                theme_value=theme_value,
            )
        if selectors.normalize_snapshot_period(snapshot_period) == "history" and show_historical_statistics:
            historical_dispersion_summary = build_historical_dispersion_summary(
                mev_records,
                effective_scenarios,
            )
        fig = figure_builder(
            model_name,
            mev_records,
            mev_reference_records,
            normalized_mev_mode,
            effective_scenarios,
            snapshot_period,
            mev_label_mode,
            range_value,
            reference_lines,
            primary_run_for,
            development_date,
            current_date,
            [mev_name],
            theme_value,
        )

        cards.append(
            html.Article(
                className="pd-mev-chart-card",
                children=[
                    html.Div(
                        className="pd-mev-chart-header",
                        children=[
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            mev_label,
                                            html.Span(mev_type, className="pd-mev-chart-type-tag")
                                            if mev_type and mev_type != "—"
                                            else None,
                                        ],
                                        className="pd-mev-chart-title",
                                    ),
                                    *meta_lines,
                                ]
                            ),
                        ],
                    ),
                    monitoring_summary,
                    historical_dispersion_summary,
                    dcc.Graph(
                        figure=fig,
                        config=GRAPH_CONFIG,
                        className="pd-mev-chart",
                    ),
                ],
            )
        )

    if normalized_mev_mode != "family":
        return cards
    return group_cards_into_family_rows(model_name, effective_mev_values, cards)


def group_cards_into_family_rows(
    model_name: str, mev_names: list[str], cards: list, *, max_per_row: int = 2
) -> list:
    """Group cards so each transformed MEV's row also holds its raw MEVs, family by family,
    wrapping a family onto additional rows (never sharing a row with another family) once
    it exceeds ``max_per_row`` cards."""
    family_map = records.family_map_for_model(model_name)
    rows: list = []
    current_row: list = []
    current_family_raws: set[str] = set()
    for mev_name, card in zip(mev_names, cards):
        is_family_head = mev_name in family_map
        continues_family = not is_family_head and mev_name in current_family_raws
        starts_new_row = not continues_family or len(current_row) >= max_per_row
        if starts_new_row and current_row:
            rows.append(html.Div(className="pd-mev-chart-family-row", children=current_row))
            current_row = []
        current_row.append(card)
        if is_family_head:
            current_family_raws = set(family_map.get(mev_name, []))
        elif not continues_family:
            current_family_raws = set()
    if current_row:
        rows.append(html.Div(className="pd-mev-chart-family-row", children=current_row))
    return rows


# Per-model attribute rows, in the order they render (and are considered for
# roll-up to the parent header). A model can carry several distinct values for
# one attribute (e.g. multi-region models), so labels pluralize. "Segment" is
# deliberately absent: it is shown in the child summary heading instead, so it
# is neither rendered as an attribute row nor rolled up to the header.
_ATTRIBUTE_ORDER = ("Region", "Portfolio", "Model Group")


def model_attributes(model_name: str) -> dict[str, list[str]]:
    """``attribute -> display values`` for a model. Attributes with no value are
    omitted. Includes a "Segment" key (used by the child summary heading);
    :data:`_ATTRIBUTE_ORDER` governs which keys render as rows / roll up, and it
    excludes Segment. Segment values are run through
    :func:`layout.format_segment_label`."""
    attributes: dict[str, list[str]] = {}

    segments = SAAS_PAGE_DATA.get("model_segments_map", {}).get(model_name)
    if not segments:
        fallback = SAAS_PAGE_DATA.get("model_segments", {}).get(model_name)
        segments = [fallback] if fallback else []
    segment_values = [layout.format_segment_label(value) for value in segments if value]
    if segment_values:
        attributes["Segment"] = segment_values

    for key, map_key in (
        ("Region", "model_region_map"),
        ("Portfolio", "model_portfolio_map"),
        ("Model Group", "model_group_map"),
    ):
        values = [value for value in (SAAS_PAGE_DATA.get(map_key, {}).get(model_name) or []) if value]
        if values:
            attributes[key] = values

    return attributes


def _attribute_line(singular: str, values: list[str]):
    label = singular if len(values) == 1 else f"{singular}s"
    return html.P(f"{label}: {', '.join(values)}", className="pd-mev-model-attr")


def render_attribute_lines(attributes: dict[str, list[str]], *, skip=()) -> list:
    """Render an ordered attribute map to ``html.P`` rows, dropping the keys in
    ``skip`` (used to suppress attributes already shown once on the parent card)."""
    return [
        _attribute_line(key, attributes[key])
        for key in _ATTRIBUTE_ORDER
        if key in attributes and key not in skip
    ]


def model_attribute_lines(model_name: str, *, skip=()) -> list:
    """Full per-model attribute rows shown inside a parent card's child block."""
    return render_attribute_lines(model_attributes(model_name), skip=skip)


def partition_group_attributes(member_names: list[str]):
    """Split a parent's attributes into the ones shared by every child and the
    ones that differ. Returns ``(shared_lines, shared_keys)``: an attribute is
    shared iff every member carries the identical value list for it, in which
    case it renders once on the parent card and is suppressed on each child.

    A singleton parent trivially shares every attribute, so they all roll up
    into the header (the lone child then shows only its charts) -- giving a
    singleton card the same header layout as a multi-child parent.
    """
    if not member_names:
        return [], frozenset()

    per_member = {name: model_attributes(name) for name in member_names}
    shared_lines: list = []
    shared_keys: set[str] = set()
    for key in _ATTRIBUTE_ORDER:
        values_seen = {tuple(per_member[name].get(key, ())) for name in member_names}
        common = next(iter(values_seen))
        if len(values_seen) == 1 and common:
            shared_lines.append(_attribute_line(key, list(common)))
            shared_keys.add(key)
    return shared_lines, frozenset(shared_keys)


def model_group_id(parent_label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", parent_label.strip().lower()).strip("-")
    return f"saas-model-group-{slug}"


def build_model_group_card(
    group_index: int,
    parent_label: str,
    member_panels: list,
    *,
    shared_attribute_lines: list | None = None,
):
    """One collapsible card per parent Descriptive Name, with every in-scope
    child model panel nested inside. Two Model Names sharing a descriptive name
    (see selectors.group_effective_models) render as sibling children of one card
    instead of two visually-identical top-level panels. Attributes common to
    every child are rolled up into the header; the card is a native
    ``<details>`` so it can be collapsed, and the subnav opens it on navigation."""
    summary_children = [
        html.Div(f"{group_index}. Model", className="pd-content-kicker"),
        html.H4(parent_label),
    ]
    if len(member_panels) > 1:
        summary_children.append(
            html.P(f"{len(member_panels)} models", className="pd-mev-model-group-count")
        )
    if shared_attribute_lines:
        summary_children.append(
            html.Div(shared_attribute_lines, className="pd-mev-model-group-shared")
        )
    return html.Details(
        id=model_group_id(parent_label),
        className="section-card pd-mev-model-group",
        # Parent opens by default so the page loads showing the waterfall of
        # child Model Names under each parent; each child stays collapsed until
        # clicked so the charts start below the fold.
        open=True,
        children=[
            html.Summary(summary_children, className="pd-mev-model-group-heading"),
            html.Div(className="pd-mev-model-group-members", children=member_panels),
        ],
    )


def build_model_panel(
    panel_index: int | str,
    model_name: str,
    records_: list[dict],
    run_for,
    compare_against,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    reference_lines: str | None,
    *,
    figure_builder,
    show_historical_statistics=False,
    theme_value: str | None = None,
    suppress_attributes=(),
):
    snapshot_period_value = selectors.normalize_snapshot_period(snapshot_period)
    visible_records = records.filter_records_by_snapshot_period(records_, snapshot_period_value)
    scenario_options = records.build_scenario_options(visible_records)
    mev_type_options = list(layout.MEV_TYPE_OPTIONS)
    default_model_mev_mode = layout.DEFAULT_MEV_TYPE
    default_model_scenarios = (
        [scenario_options[0]["value"]] if scenario_options else []
    ) if reference_lines == "monitoring" else [option["value"] for option in scenario_options if option.get("value")]
    family_mev_options = records.build_family_mev_options(
        records.filter_records_by_model_mevs(visible_records, model_name, "family"),
        mev_label_mode,
    )
    transformed_mev_options = records.build_model_mev_options(
        records.filter_records_by_model_mevs(visible_records, model_name, "transformed_only"),
        mev_label_mode,
    )
    default_family_mev = (
        records.FAMILY_ALL_VALUE
        if records.FAMILY_ALL_VALUE in {option["value"] for option in family_mev_options}
        else next(
            (option["value"] for option in family_mev_options if option["value"] != records.FAMILY_ALL_VALUE),
            "",
        )
    )
    default_model_mevs = [option["value"] for option in transformed_mev_options]
    date_periods = records.available_date_periods(visible_records)
    attribute_lines = model_attribute_lines(model_name, skip=suppress_attributes)
    # The child summary shows the model's segment(s); the underlying Model Name
    # (its GMIS name) moves into the info-chip tooltip.
    segment_labels = model_attributes(model_name).get("Segment", [])
    summary_heading = ", ".join(segment_labels) if segment_labels else model_name
    gmis_tooltip = f"GMIS Name: {model_name}"
    # Charts are built lazily the first time this (collapsed-by-default) panel is
    # opened -- see the MODEL_CHART_TRIGGER_TYPE callback. Rendering every model's
    # charts up front draws dozens of hidden Plotly figures at once and freezes
    # the page, so the grid starts as a placeholder and a hidden trigger button
    # (clicked by the client on first open) asks the server to build them.
    chart_cards = [
        html.Div("Loading charts…", className="pd-mev-chart-meta saas-chart-placeholder"),
    ]

    # Collapsible child panel: the summary is the model's identity (so a
    # collapsed parent card shows a waterfall of just its child Model Names),
    # and the body -- filter controls plus charts -- lives below the fold.
    # Charts stay in the DOM while collapsed, so their MATCH callbacks keep
    # working; a global 'toggle' handler resizes Plotly when a panel opens.
    return html.Details(
        id=model_panel_id(model_name),
        className="pd-mev-model-panel",
        open=False,
        children=[
            html.Summary(
                className="pd-mev-model-heading-summary",
                children=[
                    html.Div(
                        className="pd-mev-model-copy",
                        children=[
                            html.Div(
                                [
                                    f"{panel_index}. {summary_heading}",
                                    html.Span(
                                        "i",
                                        className="pd-info-chip",
                                        title=gmis_tooltip,
                                        style={"marginLeft": "6px", "textTransform": "none", "verticalAlign": "middle"},
                                        **{"aria-label": gmis_tooltip},
                                    ),
                                ],
                                className="pd-content-kicker",
                            ),
                            *attribute_lines,
                        ],
                    ),
                ],
            ),
            html.Div(
                className="pd-mev-model-body",
                children=[
                    html.Div(
                        className="pd-mev-model-heading-actions",
                        children=[
                            html.Div(
                                className="pd-mev-filter-group saas-model-mev-type-filter",
                                children=[
                                    html.Label("MEV View"),
                                    build_model_mev_type_dropdown(
                                        model_name,
                                        default_model_mev_mode,
                                        mev_type_options,
                                    ),
                                ],
                            ),
                            html.Div(
                                className="pd-mev-filter-group saas-model-scenario-filter",
                                children=[
                                    html.Label("Scenario"),
                                    build_model_scenario_dropdown(
                                        model_name,
                                        default_model_scenarios,
                                        scenario_options,
                                        single_select=reference_lines == "monitoring",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="pd-mev-filter-group saas-model-mev-filter",
                                children=[
                                    html.Label(
                                        mev_picker_label(default_model_mev_mode),
                                        id={"type": layout.MODEL_MEV_LABEL_TYPE, "model": model_name},
                                    ),
                                    build_model_mev_dropdown(
                                        model_name,
                                        default_model_mev_mode,
                                        family_mev_options,
                                        default_family_mev,
                                        transformed_mev_options,
                                        default_model_mevs,
                                    ),
                                ],
                            ),
                            html.Div(
                                id={"type": layout.MODEL_DATE_RANGE_CONTROLS_TYPE, "model": model_name},
                                className="saas-date-range-controls",
                                children=[
                                    layout.build_model_date_range_controls(
                                        model_name,
                                        date_periods,
                                        None,
                                        disabled=snapshot_period_value == "projection",
                                    )
                                ],
                            ),
                        ],
                    ),
                    html.Button(
                        id={"type": layout.MODEL_CHART_TRIGGER_TYPE, "model": model_name},
                        className="saas-chart-trigger",
                        style={"display": "none"},
                        n_clicks=0,
                        **{"aria-hidden": "true", "tabIndex": -1},
                    ),
                    html.Div(
                        id={"type": layout.MODEL_MEV_GRID_TYPE, "model": model_name},
                        className="pd-mev-chart-grid",
                        children=chart_cards,
                    ),
                ],
            ),
        ],
    )
