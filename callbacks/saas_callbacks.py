"""Callbacks for the SAAS workspace."""

from __future__ import annotations

from datetime import datetime
import re
import statistics

from dash import ALL, MATCH, Input, Output, State, ctx, dcc, html, no_update

from ..components import filters as shared_filters
from ..components.charts import (
    SAAS_SCENARIO_COLOR_MAP,
    SAAS_SCENARIO_LABEL_MAP,
    build_saas_mev_time_series_figure,
    compute_saas_monitoring_band_spec,
)
from ..data.mev import format_pd_mev_value
from ..data.transformations import _finite
from ..data_store import SAAS_PAGE_DATA
from ..pages import saas_layout as layout

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}
_RAW_MEV_NAMES = set(SAAS_PAGE_DATA.get("raw_mev_names") or set())
_TRANSFORMED_MEV_NAMES = set(SAAS_PAGE_DATA.get("transformed_mev_names") or set())
_MONITORING_SCENARIO_NONE_VALUE = "__none__"


def _is_segment_active(segment: str | None) -> bool:
    return bool(segment) and segment != layout.SEGMENT_ALL_VALUE


def _normalize_selected_run_fors(value) -> list[str]:
    selected_values = _normalize_multi_values(value)
    valid_values = [option["value"] for option in layout.RUN_FOR_OPTIONS]
    return [value for value in valid_values if value in selected_values]


def _normalize_compare_against_values(value, selected_run_for: str | None = None) -> list[str]:
    selected_values = _normalize_multi_values(value)
    valid_values = [
        option["value"]
        for option in layout.RUN_FOR_OPTIONS
        if option["value"] and option["value"] != selected_run_for
    ]
    compare_values = [item for item in selected_values if item in valid_values]
    if not compare_values:
        return [layout.COMPARE_AGAINST_NONE_VALUE]
    return compare_values


def _scoped_run_for_values(run_for, compare_against) -> list[str]:
    primary_values = _normalize_selected_run_fors(run_for)
    primary_value = primary_values[0] if primary_values else None
    compare_values = _normalize_compare_against_values(compare_against, primary_value)
    scoped_values = list(primary_values)
    for compare_value in compare_values:
        if compare_value == layout.COMPARE_AGAINST_NONE_VALUE or compare_value in scoped_values:
            continue
        scoped_values.append(compare_value)
    return scoped_values


def _model_names_for_filters(segment: str | None) -> list[str]:
    base_models = list(SAAS_PAGE_DATA.get("model_names", []))
    model_segments = SAAS_PAGE_DATA.get("model_segments", {})
    if _is_segment_active(segment):
        base_models = [model_name for model_name in base_models if model_segments.get(model_name) == segment]
    return base_models


def _model_options_for_filters(segment: str | None, *, disabled: bool = False) -> list[dict]:
    values = _model_names_for_filters(segment)
    seen: set[str] = set()
    options: list[dict] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        option = {"label": value, "value": value}
        if disabled:
            option["disabled"] = True
        options.append(option)
    return options


def _normalize_selected_models(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_multi_values(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_selected_mevs(value) -> list[str]:
    return _normalize_multi_values(value)


def _normalize_selected_mev_mode(value: str | None, options: list[dict] | None = None) -> str:
    raw_value = str(value or "").strip().lower()
    valid_values = {
        str(option.get("value") or "").strip().lower()
        for option in (options or layout.MEV_TYPE_OPTIONS)
        if str(option.get("value") or "").strip()
    }
    if raw_value in valid_values:
        return raw_value
    return layout.DEFAULT_MEV_TYPE


def _normalize_selected_scenarios(value, options: list[dict] | None = None) -> list[str]:
    if isinstance(value, str):
        selected_values = [value] if value else []
    elif isinstance(value, list):
        selected_values = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        selected_values = []
    if options is None:
        return selected_values
    valid_values = {
        str(option.get("value") or "").strip().lower()
        for option in options
        if str(option.get("value") or "").strip()
    }
    return [selected_value for selected_value in selected_values if selected_value in valid_values]


def _coerce_quarter(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_snapshot_period(value: str | None) -> str:
    valid_values = {option["value"] for option in layout.SUBNAV_VIEW_OPTIONS}
    if value in valid_values:
        return value
    return layout.DEFAULT_SUBNAV_VIEW


def _normalize_mev_label_mode(value: str | None) -> str:
    valid_values = {option["value"] for option in layout.MEV_LABEL_MODE_OPTIONS}
    if value in valid_values:
        return value
    return layout.DEFAULT_MEV_LABEL_MODE


def _date_period_key(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except TypeError:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    return str(value)


def _available_date_periods(records: list[dict]) -> list[str]:
    return sorted({
        _date_period_key(row.get("Date"))
        for row in records
        if _date_period_key(row.get("Date"))
    })


def _normalize_date_range(range_value, periods: list[str]) -> dict[str, str]:
    range_value = range_value or {}
    range_from = range_value.get("from", "")
    range_to = range_value.get("to", "")
    return {
        "from": range_from if range_from in periods else "",
        "to": range_to if range_to in periods else "",
    }


def _filter_records_by_snapshot_period(records: list[dict], snapshot_period: str | None) -> list[dict]:
    snapshot_period_value = _normalize_snapshot_period(snapshot_period)
    if snapshot_period_value == layout.DEFAULT_SUBNAV_VIEW:
        return list(records)

    filtered_records: list[dict] = []
    for row in records:
        quarter_value = _coerce_quarter(row.get("Quarter"))
        if quarter_value is None:
            continue
        if snapshot_period_value == "history" and quarter_value <= 0:
            filtered_records.append(row)
        elif snapshot_period_value == "projection" and quarter_value >= 0:
            filtered_records.append(row)
    return filtered_records


def _filter_records_by_date_range(records: list[dict], range_value) -> list[dict]:
    periods = _available_date_periods(records)
    selection = _normalize_date_range(range_value, periods)
    if not selection["from"] and not selection["to"]:
        return list(records)

    filtered_records: list[dict] = []
    for row in records:
        period = _date_period_key(row.get("Date"))
        if not period:
            continue
        if selection["from"] and period < selection["from"]:
            continue
        if selection["to"] and period > selection["to"]:
            continue
        filtered_records.append(row)
    return filtered_records


def _resolve_date_range_selection(periods: list[str], window_value: str | None, from_value: str | None, to_value: str | None, triggered_id) -> dict[str, str]:
    current = _normalize_date_range({"from": from_value or "", "to": to_value or ""}, periods)

    if isinstance(triggered_id, dict) and triggered_id.get("type") == layout.MODEL_DATE_RANGE_WINDOW_TYPE:
        if window_value == "all":
            return {"from": "", "to": ""}
        count = _RANGE_PRESET_COUNTS.get(window_value or "")
        if not count or not periods:
            return current
        return {"from": periods[max(0, len(periods) - count)], "to": periods[-1]}

    if current["from"] and current["to"] and current["from"] > current["to"]:
        if isinstance(triggered_id, dict) and triggered_id.get("type") == layout.MODEL_DATE_RANGE_FROM_TYPE:
            current["to"] = current["from"]
        elif isinstance(triggered_id, dict) and triggered_id.get("type") == layout.MODEL_DATE_RANGE_TO_TYPE:
            current["from"] = current["to"]
    return current


def _effective_model_names(segment: str | None, selected_models) -> list[str]:
    selected_model_values = _normalize_selected_models(selected_models)
    all_model_values = [option["value"] for option in _model_options_for_filters(None)]
    all_models_selected = bool(all_model_values) and set(selected_model_values) == set(all_model_values)

    if _is_segment_active(segment):
        return _model_names_for_filters(segment)
    if selected_model_values and not all_models_selected:
        selected_value_set = set(selected_model_values)
        return [value for value in all_model_values if value in selected_value_set]
    if all_models_selected:
        return all_model_values
    return []


def _multi_toggle_label(selected_values: list[str], all_values: list[str], *, empty_label: str, all_label: str, unit_label: str) -> str:
    if not selected_values:
        return empty_label
    if all_values and set(selected_values) == set(all_values):
        return all_label
    if len(selected_values) == 1:
        return selected_values[0]
    return f"{len(selected_values)} {unit_label}"


def _run_for_meta_label(selected_run_fors) -> str:
    normalized_values = _normalize_selected_run_fors(selected_run_fors)
    if not normalized_values:
        return "No Reporting Cycle selected"
    all_values = [option["value"] for option in layout.RUN_FOR_OPTIONS]
    if all_values and set(normalized_values) == set(all_values):
        return "All Reporting Cycle values"
    if len(normalized_values) == 1:
        return normalized_values[0]
    return ", ".join(normalized_values)


def _run_for_toggle_label(selected_run_fors, all_run_for_values: list[str]) -> str:
    normalized_values = _normalize_selected_run_fors(selected_run_fors)
    if not normalized_values:
        return "Select Reporting Cycle"
    return normalized_values[0]


def _build_compare_against_options(selected_run_for: str | None) -> list[dict]:
    options = [{"label": "None", "value": layout.COMPARE_AGAINST_NONE_VALUE}]
    for option in layout.RUN_FOR_OPTIONS:
        value = option.get("value")
        if not value or value == selected_run_for:
            continue
        options.append({"label": option.get("label", value), "value": value})
    return options


def _compare_against_toggle_label(selected_values, selected_run_for: str | None) -> str:
    normalized_values = _normalize_compare_against_values(selected_values, selected_run_for)
    compare_values = [value for value in normalized_values if value != layout.COMPARE_AGAINST_NONE_VALUE]
    if not compare_values:
        return "None"
    if len(compare_values) == 1:
        return compare_values[0]
    return f"{len(compare_values)} Reporting Cycle values selected"


def _primary_run_for_value(run_for) -> str | None:
    selected_values = _normalize_selected_run_fors(run_for)
    return selected_values[0] if selected_values else None


def _model_development_date(model_name: str, run_for) -> datetime | None:
    primary_run_for = _primary_run_for_value(run_for)
    if not primary_run_for:
        return None
    return SAAS_PAGE_DATA.get("model_development_dates", {}).get(primary_run_for, {}).get(model_name)


def _current_date_for_run_for(run_for) -> datetime | None:
    primary_run_for = _primary_run_for_value(run_for)
    if not primary_run_for:
        return None
    match = re.search(r"(\d{4})$", primary_run_for)
    if not match:
        return None
    return datetime(int(match.group(1)) - 1, 12, 31)


def _format_monitoring_date(date_value) -> str:
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


def _build_monitoring_threshold_chips(band_spec: dict | None) -> list[html.Span]:
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


def _monitoring_marker_legend_item(
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


def _monitoring_scenario_legend_item(selected_scenarios) -> html.Div | None:
    normalized_scenarios = _normalize_selected_scenarios(selected_scenarios)
    if not normalized_scenarios:
        return None
    scenario_value = normalized_scenarios[0]
    scenario_label = SAAS_SCENARIO_LABEL_MAP.get(scenario_value, scenario_value.replace("_", " ").title())
    scenario_color = SAAS_SCENARIO_COLOR_MAP.get(scenario_value, "#475569")
    return _monitoring_marker_legend_item(
        "Scenario",
        scenario_label,
        "series",
        line_color=scenario_color,
        line_dash="solid" if scenario_value == "baseline" else "dashed",
    )


def _build_monitoring_summary(
    records: list[dict],
    selected_mev_mode,
    selected_scenarios,
    selected_mevs,
    primary_run_for: str | None,
    development_date,
    current_date,
):
    monitoring_records = _filter_records_by_mevs(
        _filter_records_by_scenarios(
            records,
            selected_scenarios,
        ),
        selected_mevs,
    )
    band_spec = compute_saas_monitoring_band_spec(
        monitoring_records,
        primary_run_for=primary_run_for,
        development_date=development_date,
    )

    threshold_items = _build_monitoring_threshold_chips(band_spec)
    marker_items = []
    scenario_item = _monitoring_scenario_legend_item(selected_scenarios)
    if scenario_item is not None:
        marker_items.append(scenario_item)
    if development_date is not None:
        marker_items.append(
            _monitoring_marker_legend_item(
                "Development",
                _format_monitoring_date(development_date),
                "development",
            )
        )
    if current_date is not None:
        marker_items.append(
            _monitoring_marker_legend_item(
                "Current date",
                _format_monitoring_date(current_date),
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


def _model_toggle_label(selected_models: list[str], all_options: list[dict], segment_active: bool) -> str:
    if segment_active:
        return "Disabled while Segment is selected"
    if not selected_models:
        return "Select models"
    all_values = [option["value"] for option in all_options]
    if all_values and set(selected_models) == set(all_values):
        return "All"
    if len(selected_models) == 1:
        return selected_models[0]
    return f"{len(selected_models)} models selected"


def _single_select_option_classes(value: str | None, option_ids: list[dict]) -> list[str]:
    return [
        "single-select-option is-selected" if option_id["value"] == value else "single-select-option"
        for option_id in option_ids
    ]


def _single_select_label(value: str | None, options: list[dict], default_label: str = "Select") -> str:
    labels = {option["value"]: option["label"] for option in options}
    return labels.get(value, value or default_label)


def _toggle_menu_class(current_class: str | None, *, base_class: str) -> str:
    if "open" in (current_class or "").split():
        return base_class
    return f"{base_class} open"


def _pluralize(count: int, label: str) -> str:
    return f"{count} {label}" if count == 1 else f"{count} {label}s"


def _format_month_year(value) -> str | None:
    if value is None or not hasattr(value, "strftime"):
        return None
    return value.strftime("%b %Y")




def _build_empty_state(title: str, copy: str):
    return html.Div(
        className="section-card pd-mev-empty-state",
        children=[
            html.Div(title, className="pd-mev-chart-title"),
            html.P(copy, className="pd-section-subtitle"),
        ],
    )


def _model_panel_id(model_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model_name.strip().lower()).strip("-")
    return f"saas-model-panel-{slug}"


def _build_subnav_models(segment: str | None, selected_models, segment_labels: dict[str, str]):
    effective_models = _effective_model_names(segment, selected_models)
    segment_active = _is_segment_active(segment)
    all_model_values = [option["value"] for option in _model_options_for_filters(None)]

    if not effective_models:
        return [
            html.Div(
                "No models are currently in scope. Adjust Segment or Specific Models above.",
                className="saas-subnav-model-summary",
            )
        ]

    if segment_active:
        segment_label = segment_labels.get(segment, segment or "Selected segment")
        summary = f"{len(effective_models)} models are in scope for {segment_label}."
    elif set(effective_models) == set(all_model_values):
        summary = f"All {len(effective_models)} models are currently in scope."
    elif len(effective_models) == 1:
        summary = "1 specific model is currently in scope."
    else:
        summary = f"{len(effective_models)} specific models are currently in scope."

    return [
        html.Div(summary, className="saas-subnav-model-summary"),
        html.Div(
            [
                html.Button(
                    model_name,
                    type="button",
                    className="saas-subnav-model-chip",
                    **{"data-saas-scroll-target": _model_panel_id(model_name)},
                )
                for model_name in effective_models
            ],
            className="saas-subnav-model-list",
        ),
    ]


def _filter_records_by_scenarios(records: list[dict], selected_scenarios) -> list[dict]:
    normalized_scenarios = _normalize_selected_scenarios(selected_scenarios)
    if not normalized_scenarios:
        return []
    if layout.DEFAULT_SCENARIO_FILTER in normalized_scenarios:
        return records
    selected_scenario_set = set(normalized_scenarios)
    return [row for row in records if str(row.get("Scenario") or "").strip().lower() in selected_scenario_set]


def _mev_types_for_name(mev_name: str) -> set[str]:
    normalized_name = str(mev_name or "").strip()
    mev_types: set[str] = set()
    if normalized_name in _TRANSFORMED_MEV_NAMES:
        mev_types.add("transformed")
    if normalized_name in _RAW_MEV_NAMES:
        mev_types.add("raw")
    return mev_types


def _mev_picker_label(selected_mev_mode: str | None) -> str:
    normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        return "MEV Family"
    if normalized_mode == "transformed_only":
        return "Transformed MEVs"
    return "Raw MEVs"


def _mev_picker_empty_label(selected_mev_mode: str | None) -> str:
    normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        return "Select transformed MEV"
    if normalized_mode == "transformed_only":
        return "Select transformed MEVs"
    return "Select raw MEVs"


def _mev_picker_section_class(*, visible: bool) -> str:
    return "saas-mev-picker-section" if visible else "saas-mev-picker-section is-hidden"


def _family_map_for_model(model_name: str) -> dict[str, list[str]]:
    return SAAS_PAGE_DATA.get("model_mev_family_map", {}).get(model_name, {})


def _allowed_mev_names_for_model(model_name: str, selected_mev_mode: str | None = None) -> set[str]:
    model_mev_map = SAAS_PAGE_DATA.get("model_mev_map", {})
    model_entry = model_mev_map.get(model_name, {})
    normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode in {"family", "transformed_only"}:
        return set(model_entry.get("transformed", []))
    return set(model_entry.get("raw", []))


def _filter_records_by_model_mevs(records: list[dict], model_name: str, selected_mev_mode: str | None = None) -> list[dict]:
    allowed_mev_names = _allowed_mev_names_for_model(model_name, selected_mev_mode)
    if not allowed_mev_names:
        return []
    return [
        row for row in records
        if str(row.get("MEV Name") or "").strip() in allowed_mev_names
    ]


def _format_scenario_label(value: str) -> str:
    if value == layout.DEFAULT_SCENARIO_FILTER:
        return "All"
    return value.replace("_", " ").title()


def _build_scenario_options(records: list[dict]) -> list[dict]:
    scenario_values: list[str] = []
    seen: set[str] = set()
    for row in records:
        scenario_value = str(row.get("Scenario") or "").strip().lower()
        if not scenario_value or scenario_value in seen:
            continue
        seen.add(scenario_value)
        scenario_values.append(scenario_value)
    return [
        {"label": _format_scenario_label(value), "value": value}
        for value in scenario_values
    ]


def _active_mev_label_map(label_mode: str | None) -> dict[str, str]:
    normalized_mode = _normalize_mev_label_mode(label_mode)
    if normalized_mode == "long_name":
        return SAAS_PAGE_DATA.get("mev_label_map", {})
    if normalized_mode == "group_mnemonic":
        return SAAS_PAGE_DATA.get("mev_group_label_map", {})
    return {}


def _resolve_mev_label(mev_name: str, label_mode: str | None) -> str:
    return _active_mev_label_map(label_mode).get(mev_name) or mev_name


def _resolve_mev_description(mev_name: str) -> str | None:
    description = SAAS_PAGE_DATA.get("mev_description_map", {}).get(mev_name)
    return description or None


def _mev_description_label(mev_name: str) -> str:
    mev_types = _mev_types_for_name(mev_name)
    if mev_types == {"raw"}:
        return "Raw MEV description"
    if mev_types == {"transformed"}:
        return "Transformed MEV description"
    if mev_types:
        return "Raw / Transformed MEV description"
    return "MEV description"


def _show_historical_statistics(selected_value) -> bool:
    return str(selected_value or "").strip().lower() == "on"


def _compute_historical_dispersion_stats(records: list[dict], selected_scenarios) -> dict | None:
    scoped_records = _filter_records_by_scenarios(records, selected_scenarios)
    values_by_date: dict[object, dict[tuple[str, str], float]] = {}
    visible_lines: set[tuple[str, str]] = set()

    for row in scoped_records:
        date_value = row.get("Date")
        scenario_value = str(row.get("Scenario") or "").strip().lower()
        run_for_value = str(row.get("Run For") or "").strip()
        numeric_value = row.get("MEV Value")
        if date_value is None or not run_for_value or not _finite(numeric_value):
            continue
        line_key = (run_for_value, scenario_value)
        visible_lines.add(line_key)
        values_by_date.setdefault(date_value, {})[line_key] = float(numeric_value)

    if len(visible_lines) < 2:
        return {
            "visible_lines": len(visible_lines),
            "matched_quarters": 0,
            "has_dispersion": False,
        }

    per_date_ranges: list[float] = []
    per_date_stddevs: list[float] = []
    max_range_date = None
    max_range_value = None

    for date_value in sorted(values_by_date):
        line_values = list(values_by_date[date_value].values())
        if len(line_values) < 2:
            continue
        range_value = max(line_values) - min(line_values)
        stddev_value = statistics.pstdev(line_values) if len(line_values) > 1 else 0.0
        per_date_ranges.append(range_value)
        per_date_stddevs.append(stddev_value)
        if max_range_value is None or range_value > max_range_value:
            max_range_value = range_value
            max_range_date = date_value

    if not per_date_ranges:
        return {
            "visible_lines": len(visible_lines),
            "matched_quarters": 0,
            "has_dispersion": False,
        }

    return {
        "visible_lines": len(visible_lines),
        "matched_quarters": len(per_date_ranges),
        "avg_range": sum(per_date_ranges) / len(per_date_ranges),
        "max_range": max(per_date_ranges),
        "avg_stddev": sum(per_date_stddevs) / len(per_date_stddevs),
        "max_stddev": max(per_date_stddevs),
        "max_range_date": max_range_date,
        "has_dispersion": True,
    }


def _format_historical_dispersion_date(date_value) -> str:
    if date_value is None:
        return "—"
    if hasattr(date_value, "strftime"):
        return date_value.strftime("%b %d, %Y").replace(" 0", " ")
    return str(date_value)


def _build_historical_dispersion_summary(records: list[dict], selected_scenarios):
    stats = _compute_historical_dispersion_stats(records, selected_scenarios)
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

    max_range_caption = _format_historical_dispersion_date(stats.get("max_range_date"))
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


def _build_model_mev_options(records: list[dict], label_mode: str | None) -> list[dict]:
    mev_names = sorted(
        {str(row.get("MEV Name") or "").strip() for row in records if str(row.get("MEV Name") or "").strip()},
        key=lambda value: _resolve_mev_label(value, label_mode).lower(),
    )
    options: list[dict] = []
    for mev_name in mev_names:
        options.append({"label": _resolve_mev_label(mev_name, label_mode), "value": mev_name})
    return options


def _records_for_model_scope(model_name: str, run_for, snapshot_period: str | None, compare_against=None) -> list[dict]:
    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    if time_series_df is None or time_series_df.empty:
        return []

    selected_run_fors = _scoped_run_for_values(run_for, compare_against)
    filtered_df = time_series_df[time_series_df["Model Name"] == model_name]
    if selected_run_fors:
        filtered_df = filtered_df[filtered_df["Run For"].isin(selected_run_fors)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    return _filter_records_by_snapshot_period(
        filtered_df.to_dict(orient="records"),
        _normalize_snapshot_period(snapshot_period),
    )


def _build_model_mev_options_for_mode(
    model_name: str,
    run_for,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    selected_mev_mode: str | None,
    compare_against=None,
) -> list[dict]:
    base_records = _records_for_model_scope(model_name, run_for, snapshot_period, compare_against)
    return _build_model_mev_options(
        _filter_records_by_model_mevs(base_records, model_name, selected_mev_mode),
        mev_label_mode,
    )


def _scenario_toggle_label(selected_scenarios, scenario_options: list[dict]) -> str:
    normalized_scenarios = _normalize_selected_scenarios(selected_scenarios, scenario_options)
    if not normalized_scenarios:
        return "Select scenarios"

    all_values = [option["value"] for option in scenario_options if option.get("value")]
    if all_values and set(normalized_scenarios) == set(all_values):
        return "All"

    label_by_value = {option["value"]: option["label"] for option in scenario_options if option.get("value")}
    if len(normalized_scenarios) == 1:
        return label_by_value.get(normalized_scenarios[0], normalized_scenarios[0])
    return f"{len(normalized_scenarios)} scenarios selected"


def _scenario_meta_label(selected_scenarios, scenario_options: list[dict]) -> str:
    normalized_scenarios = _normalize_selected_scenarios(selected_scenarios, scenario_options)
    if not normalized_scenarios:
        return "No scenarios selected"

    all_values = [option["value"] for option in scenario_options if option.get("value")]
    if all_values and set(normalized_scenarios) == set(all_values):
        return "All"

    selected_labels = [
        option["label"]
        for option in scenario_options
        if option.get("value") in normalized_scenarios
    ]
    return ", ".join(selected_labels)


def _single_selected_scenario(selected_scenarios, scenario_options: list[dict]) -> str:
    normalized_scenarios = _normalize_selected_scenarios(selected_scenarios, scenario_options)
    if normalized_scenarios:
        return normalized_scenarios[0]
    all_values = [option["value"] for option in scenario_options if option.get("value")]
    return all_values[0] if all_values else ""


def _build_model_scenario_dropdown(
    model_name: str,
    selected_scenarios,
    scenario_options: list[dict],
    *,
    single_select: bool = False,
) -> html.Div:
    effective_scenarios = _normalize_selected_scenarios(selected_scenarios, scenario_options)
    all_values = [option["value"] for option in scenario_options if option.get("value")]
    if single_select:
        single_select_options = [
            {"label": "None", "value": _MONITORING_SCENARIO_NONE_VALUE},
            *scenario_options,
        ]
        selected_value = _single_selected_scenario(selected_scenarios, single_select_options)
        return html.Div(
            className="checkbox-dropdown single-select-dropdown",
            children=[
                dcc.Dropdown(
                    id={"type": layout.MODEL_SCENARIO_FILTER_TYPE, "model": model_name},
                    options=single_select_options,
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
                    _scenario_toggle_label(selected_value, single_select_options),
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
                                html.Span("✓", className="single-select-option-check"),
                            ],
                            id={"type": layout.MODEL_SCENARIO_OPTION_TYPE, "model": model_name, "value": option["value"]},
                            type="button",
                            n_clicks=0,
                            className="single-select-option is-selected" if option["value"] == selected_value else "single-select-option",
                        )
                        for option in single_select_options
                    ],
                ),
            ],
        )
    return html.Div(
        className="checkbox-dropdown",
        children=[
            html.Button(
                _scenario_toggle_label(effective_scenarios, scenario_options),
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


def _mev_type_toggle_label(selected_mev_mode: str | None, mev_type_options: list[dict]) -> str:
    normalized_mode = _normalize_selected_mev_mode(selected_mev_mode, mev_type_options)
    label_by_value = {option["value"]: option["label"] for option in mev_type_options if option.get("value")}
    return label_by_value.get(normalized_mode, normalized_mode or "Select MEV View")


def _build_model_mev_type_dropdown(model_name: str, selected_mev_mode: str | None, mev_type_options: list[dict]) -> html.Div:
    effective_mev_mode = _normalize_selected_mev_mode(selected_mev_mode, mev_type_options)
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
                _mev_type_toggle_label(effective_mev_mode, mev_type_options),
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
                            html.Span("✓", className="single-select-option-check", **{"aria-hidden": "true"}),
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


def _filter_records_by_mevs(records: list[dict], selected_mevs) -> list[dict]:
    selected_mev_values = _normalize_selected_mevs(selected_mevs)
    if not selected_mev_values:
        return []
    selected_mev_set = set(selected_mev_values)
    return [row for row in records if str(row.get("MEV Name") or "").strip() in selected_mev_set]


def _build_single_mev_option_buttons(options: list[dict], selected_value: str | None, model_name: str):
    return [
        html.Button(
            [
                html.Span(option["label"], className="single-select-option-label"),
                html.Span("✓", className="single-select-option-check", **{"aria-hidden": "true"}),
            ],
            id={"type": layout.MODEL_MEV_SINGLE_OPTION_TYPE, "model": model_name, "value": option["value"]},
            type="button",
            n_clicks=0,
            className="single-select-option is-selected" if option["value"] == selected_value else "single-select-option",
        )
        for option in options
    ]


def _family_display_mevs(model_name: str, selected_mev: str | None, records: list[dict] | None = None) -> list[str]:
    available_names = {
        str(row.get("MEV Name") or "").strip()
        for row in (records or [])
        if str(row.get("MEV Name") or "").strip()
    }
    family_map = _family_map_for_model(model_name)
    normalized_selected = str(selected_mev or "").strip()
    if not normalized_selected:
        return []

    family_values = [normalized_selected]
    family_values.extend(family_map.get(normalized_selected, []))
    ordered_values = list(dict.fromkeys(value for value in family_values if value))
    if not available_names:
        return ordered_values
    return [value for value in ordered_values if value in available_names]


def _active_selected_mevs(
    model_name: str,
    selected_mev_mode: str | None,
    selected_mev_single,
    selected_mevs_multi,
    records: list[dict] | None = None,
) -> list[str]:
    normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        selected_value = _normalize_selected_mevs(selected_mev_single)
        selected_mev = selected_value[0] if selected_value else None
        return _family_display_mevs(model_name, selected_mev, records)
    return _normalize_selected_mevs(selected_mevs_multi)


def _mev_toggle_label(
    selected_mev_mode: str | None,
    selected_mev_single,
    selected_mevs_multi,
    single_mev_options: list[dict],
    multi_mev_options: list[dict],
) -> str:
    normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        selected_mev_values = _normalize_selected_mevs(selected_mev_single)
        if not selected_mev_values:
            return _mev_picker_empty_label(normalized_mode)
        label_by_value = {option["value"]: option["label"] for option in single_mev_options if option.get("value")}
        return label_by_value.get(selected_mev_values[0], selected_mev_values[0])

    selected_mev_values = _normalize_selected_mevs(selected_mevs_multi)
    if not selected_mev_values:
        return _mev_picker_empty_label(normalized_mode)

    all_values = [option["value"] for option in multi_mev_options if option.get("value")]
    if all_values and set(selected_mev_values) == set(all_values):
        if normalized_mode == "transformed_only":
            return "All"
        return "All raw MEVs"

    label_by_value = {option["value"]: option["label"] for option in multi_mev_options if option.get("value")}
    if len(selected_mev_values) == 1:
        return label_by_value.get(selected_mev_values[0], selected_mev_values[0])
    return f"{len(selected_mev_values)} MEVs selected"


def _build_model_mev_dropdown(
    model_name: str,
    selected_mev_mode: str | None,
    single_mev_options: list[dict],
    selected_mev_single: str | None,
    multi_mev_options: list[dict],
    selected_mevs_multi: list[str],
) -> html.Div:
    normalized_mode = _normalize_selected_mev_mode(selected_mev_mode)
    show_single_picker = normalized_mode == "family"
    return html.Div(
        className="checkbox-dropdown pd-mev-filter-dropdown",
        children=[
            html.Button(
                _mev_toggle_label(
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
                        className=_mev_picker_section_class(visible=show_single_picker),
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
                                children=_build_single_mev_option_buttons(single_mev_options, selected_mev_single, model_name),
                            ),
                        ],
                    ),
                    html.Div(
                        id={"type": layout.MODEL_MEV_MULTI_SECTION_TYPE, "model": model_name},
                        className=_mev_picker_section_class(visible=not show_single_picker),
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


def _build_model_figure(
    model_name: str,
    records: list[dict],
    reference_records: list[dict],
    selected_mev_mode,
    selected_scenarios,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    range_value,
    reference_lines: str | None,
    primary_run_for: str | None = None,
    development_date=None,
    current_date=None,
    selected_mevs=None,
):
    monitoring_reference_records = _filter_records_by_mevs(
        _filter_records_by_scenarios(
            reference_records,
            selected_scenarios,
        ),
        selected_mevs,
    )
    scoped_reference_records = _filter_records_by_date_range(
        monitoring_reference_records,
        range_value,
    )
    y_axis_title = None
    if selected_mevs:
        selected_mev_name = _normalize_selected_mevs(selected_mevs)
        if selected_mev_name:
            y_axis_title = _resolve_mev_label(selected_mev_name[0], mev_label_mode)
    return build_saas_mev_time_series_figure(
        _filter_records_by_date_range(
            _filter_records_by_mevs(
                _filter_records_by_scenarios(
                    records,
                    selected_scenarios,
                ),
                selected_mevs,
            ),
            range_value,
        ),
        mev_label_map=_active_mev_label_map(mev_label_mode),
        model_label_map={model_name: model_name},
        y_axis_title=y_axis_title,
        snapshot_period=_normalize_snapshot_period(snapshot_period),
        historical_reference_records=scoped_reference_records,
        monitoring_reference_records=monitoring_reference_records,
        reference_lines=reference_lines or layout.DEFAULT_REFERENCE_LINES,
        empty_message=f"No MEV time-series data matches the active filters for {model_name}.",
        primary_run_for=primary_run_for,
        development_date=development_date,
        current_date=current_date,
    )


def _build_model_chart_cards(
    model_name: str,
    records: list[dict],
    reference_records: list[dict],
    selected_mev_mode,
    selected_scenarios,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    range_value,
    reference_lines: str | None,
    selected_mevs,
    shared_meta_parts: list[str],
    primary_run_for: str | None = None,
    show_historical_statistics=False,
):
    normalized_mev_mode = _normalize_selected_mev_mode(selected_mev_mode)
    scenario_options = _build_scenario_options(records)
    visible_mev_names = {
        str(row.get("MEV Name") or "").strip()
        for row in records
        if str(row.get("MEV Name") or "").strip()
    }
    effective_mev_values = [
        value for value in _normalize_selected_mevs(selected_mevs)
        if value in visible_mev_names
    ]
    effective_scenarios = _normalize_selected_scenarios(selected_scenarios, scenario_options)

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
    development_date = _model_development_date(model_name, primary_run_for)
    current_date = _current_date_for_run_for(primary_run_for)

    for mev_name in effective_mev_values:
        mev_records = [row for row in records if str(row.get("MEV Name") or "").strip() == mev_name]
        mev_reference_records = [row for row in reference_records if str(row.get("MEV Name") or "").strip() == mev_name]
        mev_label = _resolve_mev_label(mev_name, mev_label_mode)
        mev_description = _resolve_mev_description(mev_name)
        meta_text = f"{_mev_description_label(mev_name)}: {mev_description}" if mev_description else ""
        monitoring_summary = None
        historical_dispersion_summary = None
        if reference_lines == "monitoring":
            monitoring_summary = _build_monitoring_summary(
                mev_reference_records,
                normalized_mev_mode,
                effective_scenarios,
                [mev_name],
                primary_run_for,
                development_date,
                current_date,
            )
        if _normalize_snapshot_period(snapshot_period) == "history" and show_historical_statistics:
            historical_dispersion_summary = _build_historical_dispersion_summary(
                mev_records,
                effective_scenarios,
            )
        fig = _build_model_figure(
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
                                    html.Div(mev_label, className="pd-mev-chart-title"),
                                    html.Div(meta_text, className="pd-mev-chart-meta"),
                                ]
                            ),
                        ],
                    ),
                    monitoring_summary,
                    historical_dispersion_summary,
                    dcc.Graph(
                        figure=fig,
                        config=_GRAPH_CONFIG,
                        className="pd-mev-chart",
                    ),
                ],
            )
        )

    return cards


def _build_model_panel(
    panel_index: int,
    model_name: str,
    records: list[dict],
    run_for,
    compare_against,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    reference_lines: str | None,
    show_historical_statistics=False,
):
    snapshot_period_value = _normalize_snapshot_period(snapshot_period)
    visible_records = _filter_records_by_snapshot_period(records, snapshot_period_value)
    scenario_options = _build_scenario_options(visible_records)
    mev_type_options = list(layout.MEV_TYPE_OPTIONS)
    default_model_mev_mode = layout.DEFAULT_MEV_TYPE
    default_model_scenarios = (
        _MONITORING_SCENARIO_NONE_VALUE
        if reference_lines == "monitoring"
        else [option["value"] for option in scenario_options if option.get("value")]
    )
    family_mev_options = _build_model_mev_options(
        _filter_records_by_model_mevs(visible_records, model_name, "family"),
        mev_label_mode,
    )
    transformed_mev_options = _build_model_mev_options(
        _filter_records_by_model_mevs(visible_records, model_name, "transformed_only"),
        mev_label_mode,
    )
    default_family_mev = family_mev_options[0]["value"] if family_mev_options else ""
    default_model_mevs = [option["value"] for option in transformed_mev_options]
    default_display_mevs = _active_selected_mevs(
        model_name,
        default_model_mev_mode,
        default_family_mev,
        default_model_mevs,
        visible_records,
    )
    date_periods = _available_date_periods(visible_records)
    mev_names = sorted({str(row.get("MEV Name") or "").strip() for row in visible_records if str(row.get("MEV Name") or "").strip()})
    scenario_names = sorted({str(row.get("Scenario") or "").strip().lower() for row in visible_records if str(row.get("Scenario") or "").strip()})
    date_values = sorted({row.get("Date") for row in visible_records if row.get("Date") is not None})

    model_segments = SAAS_PAGE_DATA.get("model_segments", {})
    segment_name = layout.format_segment_label(model_segments.get(model_name))
    range_start = _format_month_year(date_values[0]) if date_values else None
    range_end = _format_month_year(date_values[-1]) if date_values else None

    meta_parts = [f"Reporting Cycle: {_run_for_meta_label(run_for)}"]
    snapshot_label = next(
        (option["label"] for option in layout.SUBNAV_VIEW_OPTIONS if option["value"] == snapshot_period_value),
        None,
    )
    if snapshot_label:
        meta_parts.append(snapshot_label)
    if mev_names:
        meta_parts.append(_pluralize(len(mev_names), "MEV"))
    if scenario_names:
        meta_parts.append(_pluralize(len(scenario_names), "scenario"))
    if range_start and range_end:
        meta_parts.append(f"{range_start} to {range_end}")

    chart_cards = _build_model_chart_cards(
        model_name,
        visible_records,
        records,
        default_model_mev_mode,
        default_model_scenarios,
        snapshot_period_value,
        mev_label_mode,
        None,
        reference_lines,
        default_display_mevs,
        meta_parts,
        _normalize_selected_run_fors(run_for)[0] if _normalize_selected_run_fors(run_for) else None,
        show_historical_statistics,
    )

    return html.Div(
        id=_model_panel_id(model_name),
        className="section-card pd-mev-model-panel",
        children=[
            html.Div(
                className="pd-mev-model-heading",
                children=[
                    html.Div(
                        className="pd-mev-model-copy",
                        children=[
                            html.Div(f"{panel_index}. Model Profile", className="pd-content-kicker"),
                            html.H4(model_name),
                            html.P(f"Segment: {segment_name}"),
                        ],
                    ),
                    html.Div(
                        className="pd-mev-model-heading-actions",
                        children=[
                            html.Div(
                                className="pd-mev-filter-group saas-model-mev-type-filter",
                                children=[
                                    html.Label("MEV View"),
                                    _build_model_mev_type_dropdown(
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
                                    _build_model_scenario_dropdown(
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
                                        _mev_picker_label(default_model_mev_mode),
                                        id={"type": layout.MODEL_MEV_LABEL_TYPE, "model": model_name},
                                    ),
                                    _build_model_mev_dropdown(
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
                ],
            ),
            html.Div(
                id={"type": layout.MODEL_MEV_GRID_TYPE, "model": model_name},
                className="pd-mev-chart-grid",
                children=chart_cards,
            ),
        ],
    )


def register_callbacks(app) -> None:
    """Register SAAS top-bar and chart callbacks."""

    segment_labels = {option["value"]: option["label"] for option in layout.SEGMENT_NAME_OPTIONS}
    subnav_view_labels = {option["value"]: option["label"] for option in layout.SUBNAV_VIEW_OPTIONS}
    reference_line_labels = {option["value"]: option["label"] for option in layout.REFERENCE_LINES_OPTIONS}
    mev_label_mode_labels = {option["value"]: option["label"] for option in layout.MEV_LABEL_MODE_OPTIONS}
    run_for_labels = {option["value"]: option["label"] for option in layout.RUN_FOR_OPTIONS}
    run_for_values = [option["value"] for option in layout.RUN_FOR_OPTIONS]

    @app.callback(
        Output(layout.MODEL_NAME_ID, "value", allow_duplicate=True),
        Output(layout.MODEL_NAME_SELECT_ALL_ID, "value"),
        Input(layout.MODEL_NAME_SELECT_ALL_ID, "value"),
        Input(layout.MODEL_NAME_ID, "value"),
        State(layout.MODEL_NAME_ID, "options"),
        prevent_initial_call=True,
    )
    def sync_saas_model_selection(select_all_value, models_value, models_options):
        all_names = [option["value"] for option in models_options if option.get("value")]
        if ctx.triggered_id == layout.MODEL_NAME_SELECT_ALL_ID:
            if "all" in (select_all_value or []):
                return all_names, no_update
            return [], no_update
        select_all = ["all"] if all_names and set(models_value or []) == set(all_names) else []
        return no_update, select_all

    @app.callback(
        Output(layout.SEGMENT_NAME_ID, "disabled"),
        Output(layout.SEGMENT_TOGGLE_ID, "disabled"),
        Output(layout.MODEL_NAME_SELECT_ALL_ID, "options"),
        Output(layout.MODEL_NAME_ID, "options"),
        Output(layout.MODEL_NAME_ID, "value"),
        Output(layout.MODEL_NAME_TOGGLE_ID, "children"),
        Output(layout.MODEL_NAME_TOGGLE_ID, "disabled"),
        Output(layout.FILTER_HELP_ID, "children"),
        Input(layout.SEGMENT_NAME_ID, "value"),
        Input(layout.MODEL_NAME_ID, "value"),
        Input(layout.RESET_FILTERS_ID, "n_clicks"),
    )
    def sync_saas_filter_controls(segment, selected_models, _reset_clicks):
        segment_active = _is_segment_active(segment)
        all_options = _model_options_for_filters(None)
        all_option_values = [option["value"] for option in all_options]
        current_values = _normalize_selected_models(selected_models)

        if ctx.triggered_id == layout.RESET_FILTERS_ID:
            segment_active = False
            current_values = list(all_option_values)

        option_values = set(all_option_values)
        current_values = [value for value in current_values if value in option_values]
        has_specific_model_selection = 0 < len(current_values) < len(all_option_values)
        select_all_options = [{"label": "All", "value": "all", "disabled": segment_active}]

        if segment_active:
            model_options = _model_options_for_filters(None, disabled=True)
            toggle_label = "Disabled while Segment is selected"
            help_text = "Segment filtering is active. Reset Segment to All to select specific models."
        else:
            model_options = _model_options_for_filters(None, disabled=False)
            toggle_label = _model_toggle_label(current_values, all_options, False)
            if has_specific_model_selection:
                help_text = "Specific Models filtering is active. Clear the model selection to use the Segment filter."
            else:
                help_text = "Choose a segment or specific models. These filters cannot be combined."

        return (
            has_specific_model_selection,
            has_specific_model_selection,
            select_all_options,
            model_options,
            current_values,
            toggle_label,
            segment_active,
            help_text,
        )

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
            return "checkbox-dropdown-menu single-select-menu"
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
        Output(layout.COMPARE_AGAINST_ID, "options"),
        Output(layout.COMPARE_AGAINST_ID, "value", allow_duplicate=True),
        Input(layout.RUN_FOR_ID, "value"),
        Input(layout.COMPARE_AGAINST_ID, "value"),
        prevent_initial_call=True,
    )
    def sync_compare_against_selection(run_for_value, compare_against_values):
        selected_run_fors = _normalize_selected_run_fors(run_for_value)
        selected_run_for = selected_run_fors[0] if selected_run_fors else None
        options = _build_compare_against_options(selected_run_for)
        normalized_values = _normalize_compare_against_values(compare_against_values, selected_run_for)
        return options, normalized_values

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
        Output(layout.SEGMENT_TOGGLE_ID, "children"),
        Output({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.SEGMENT_FILTER_KEY, "value": ALL}, "className"),
        Input(layout.SEGMENT_NAME_ID, "value"),
        State({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.SEGMENT_FILTER_KEY, "value": ALL}, "id"),
    )
    def sync_segment_shell(value, option_ids):
        label = segment_labels.get(value, value or "Select")
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
        single_mev_options = _build_model_mev_options_for_mode(
            model_name,
            run_for,
            snapshot_period,
            mev_label_mode,
            "family",
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
        next_single_value = next(
            (value for value in _normalize_selected_mevs(selected_mev_single) if value in single_option_values),
            single_option_values[0] if single_option_values else "",
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
        Output(layout.SEGMENT_NAME_ID, "value", allow_duplicate=True),
        Output(layout.SEGMENT_MENU_ID, "className", allow_duplicate=True),
        Input({"type": shared_filters.SINGLE_SELECT_OPTION_ID, "filter": layout.SEGMENT_FILTER_KEY, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_segment(_clicks):
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

    @app.callback(
        Output(layout.HISTORICAL_STATS_FILTER_ID, "className"),
        Input(layout.SUBNAV_VIEW_ID, "value"),
    )
    def sync_historical_stats_filter_visibility(snapshot_period):
        base_class = "monitoring-filter saas-historical-stats-filter"
        if _normalize_snapshot_period(snapshot_period) != "history":
            return f"{base_class} is-hidden"
        return base_class

    @app.callback(
        Output(layout.RUN_FOR_ID, "value"),
        Output(layout.COMPARE_AGAINST_ID, "value"),
        Output(layout.SEGMENT_NAME_ID, "value"),
        Output(layout.SUBNAV_VIEW_ID, "value"),
        Output(layout.REFERENCE_LINES_ID, "value"),
        Output(layout.MEV_LABEL_MODE_ID, "value"),
        Output(layout.HISTORICAL_STATS_ID, "value"),
        Input(layout.RESET_FILTERS_ID, "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_saas_filters(_reset_clicks):
        return (
            layout.DEFAULT_RUN_FOR_VALUE,
            list(layout.DEFAULT_COMPARE_AGAINST_VALUES),
            layout.DEFAULT_SEGMENT,
            layout.DEFAULT_SUBNAV_VIEW,
            layout.DEFAULT_REFERENCE_LINES,
            layout.DEFAULT_MEV_LABEL_MODE,
            layout.DEFAULT_HISTORICAL_STATS_VALUE,
        )

    @app.callback(
        Output(layout.SUBNAV_MODELS_ID, "children"),
        Input(layout.SEGMENT_NAME_ID, "value"),
        Input(layout.MODEL_NAME_ID, "value"),
    )
    def render_saas_subnav_models(segment, selected_models):
        return _build_subnav_models(segment, selected_models, segment_labels)

    @app.callback(
        Output(layout.MEV_MODEL_PANELS_ID, "children"),
        Input(layout.RUN_FOR_ID, "value"),
        Input(layout.COMPARE_AGAINST_ID, "value"),
        Input(layout.SEGMENT_NAME_ID, "value"),
        Input(layout.MODEL_NAME_ID, "value"),
        Input(layout.SUBNAV_VIEW_ID, "value"),
        Input(layout.REFERENCE_LINES_ID, "value"),
        Input(layout.MEV_LABEL_MODE_ID, "value"),
        Input(layout.HISTORICAL_STATS_ID, "value"),
    )
    def render_saas_mev_chart(run_for, compare_against, segment, selected_models, snapshot_period, reference_lines, mev_label_mode, show_historical_statistics_values):
        selected_run_fors = _normalize_selected_run_fors(run_for)
        scoped_run_fors = _scoped_run_for_values(run_for, compare_against)
        effective_models = _effective_model_names(segment, selected_models)
        show_historical_statistics = (
            _normalize_snapshot_period(snapshot_period) == "history"
            and _show_historical_statistics(show_historical_statistics_values)
        )

        if not selected_run_fors:
            return _build_empty_state(
                "Choose Reporting Cycle value",
                "Select one Reporting Cycle value to render the SAAS workbook charts.",
            )

        if not effective_models:
            return _build_empty_state(
                "No models match the current filters",
                "Adjust Segment or Specific Models to bring one or more SAAS models into scope.",
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
        for panel_index, model_name in enumerate(effective_models, start=1):
            model_records = [row for row in records if row.get("Model Name") == model_name]
            panels.append(
                _build_model_panel(
                    panel_index,
                    model_name,
                    model_records,
                    selected_run_fors,
                    compare_against,
                    snapshot_period,
                    mev_label_mode,
                    reference_lines,
                    show_historical_statistics,
                )
            )

        return panels or _build_empty_state(
            "No MEV charts match the current filters",
            "Adjust the Reporting Cycle, Segment, or Specific Models filters to broaden the SAAS workbook selection.",
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
        State(layout.RUN_FOR_ID, "value"),
        State(layout.COMPARE_AGAINST_ID, "value"),
        State(layout.SUBNAV_VIEW_ID, "value"),
        State(layout.REFERENCE_LINES_ID, "value"),
        State(layout.MEV_LABEL_MODE_ID, "value"),
        State(layout.HISTORICAL_STATS_ID, "value"),
        prevent_initial_call=True,
    )
    def update_model_mev_chart_controls(selected_mev_mode, selected_scenario, selected_mevs_multi, selected_mev_single, window_value, from_value, to_value, run_for, compare_against, snapshot_period, reference_lines, mev_label_mode, show_historical_statistics_values):
        model_name = ctx.triggered_id["model"]
        time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
        if time_series_df is None or time_series_df.empty:
            return no_update, no_update

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
        range_value = _resolve_date_range_selection(periods, window_value, from_value, to_value, ctx.triggered_id)
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
        )
        mev_names = sorted({str(row.get("MEV Name") or "").strip() for row in records if str(row.get("MEV Name") or "").strip()})
        scenario_names = sorted({str(row.get("Scenario") or "").strip().lower() for row in records if str(row.get("Scenario") or "").strip()})
        date_values = sorted({row.get("Date") for row in records if row.get("Date") is not None})

        meta_parts = [f"Reporting Cycle: {_run_for_meta_label(selected_run_fors)}"]
        snapshot_label = next(
            (option["label"] for option in layout.SUBNAV_VIEW_OPTIONS if option["value"] == snapshot_period_value),
            None,
        )
        if snapshot_label:
            meta_parts.append(snapshot_label)
        if mev_names:
            meta_parts.append(_pluralize(len(mev_names), "MEV"))
        if scenario_names:
            meta_parts.append(_pluralize(len(scenario_names), "scenario"))
        if date_values:
            meta_parts.append(f"{_format_month_year(date_values[0])} to {_format_month_year(date_values[-1])}")

        return (
            _build_model_chart_cards(
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
                meta_parts,
                selected_run_fors[0] if selected_run_fors else None,
                show_historical_statistics,
            ),
            range_controls,
        )
