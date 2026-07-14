"""SAAS workspace report figure orchestration helpers."""

from __future__ import annotations

import re

from ..data_access import SAAS_PAGE_DATA
from ..ui.views import workspace as layout
from ..domain import metrics, records, selectors


def build_model_report_figures(
    model_name: str,
    records_: list[dict],
    reference_records: list[dict],
    selected_mev_mode,
    selected_scenarios,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    reference_lines: str | None,
    selected_mevs,
    *,
    figure_builder,
    primary_run_for: str | None = None,
    include_model_in_title: bool = True,
) -> list[tuple[str, object, str, dict | None]]:
    """Build (title, figure, mev_type, monitoring_summary) tuples for a model using the default chart selections."""
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

    if not effective_mev_values or not effective_scenarios:
        return []
    if reference_lines == "monitoring" and len(effective_scenarios) != 1:
        return []

    development_date = selectors.model_development_date(model_name, primary_run_for)
    current_date = selectors.current_date_for_run_for(primary_run_for)

    figures: list[tuple[str, object, str, dict | None]] = []
    for mev_name in effective_mev_values:
        mev_records = [
            row for row in records_
            if str(row.get("MEV Name") or "").strip() == mev_name
        ]
        mev_reference_records = [
            row for row in reference_records
            if str(row.get("MEV Name") or "").strip() == mev_name
        ]
        mev_label = selectors.resolve_mev_label(mev_name, mev_label_mode)
        mev_type = selectors.mev_type_label(mev_name)
        monitoring_summary = None
        if reference_lines == "monitoring":
            monitoring_summary = metrics.compute_monitoring_summary_data(
                mev_reference_records,
                effective_scenarios,
                [mev_name],
                primary_run_for,
                development_date,
                current_date,
            )
        fig = figure_builder(
            model_name,
            mev_records,
            mev_reference_records,
            normalized_mev_mode,
            effective_scenarios,
            snapshot_period,
            mev_label_mode,
            None,
            reference_lines,
            primary_run_for,
            development_date,
            current_date,
            [mev_name],
        )
        title = f"{model_name} — {mev_label}" if include_model_in_title else mev_label
        figures.append((title, fig, mev_type, monitoring_summary))
    return figures


def build_model_report_sections(
    model_name: str,
    records_: list[dict],
    run_for,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    reference_lines: str | None,
    *,
    figure_builder,
    include_model_in_title: bool = True,
) -> list[tuple[str, object, str, dict | None]]:
    """Build (title, figure, mev_type, monitoring_summary) tuples for a model panel's default view."""
    snapshot_period_value = selectors.normalize_snapshot_period(snapshot_period)
    visible_records = records.filter_records_by_snapshot_period(records_, snapshot_period_value)
    scenario_options = records.build_scenario_options(visible_records)
    default_model_mev_mode = layout.DEFAULT_MEV_TYPE
    default_model_scenarios = (
        [scenario_options[0]["value"]] if scenario_options else []
    ) if reference_lines == "monitoring" else [
        option["value"] for option in scenario_options if option.get("value")
    ]
    family_mev_options = records.build_model_mev_options(
        records.filter_records_by_model_mevs(visible_records, model_name, "family"),
        mev_label_mode,
    )
    transformed_mev_options = records.build_model_mev_options(
        records.filter_records_by_model_mevs(visible_records, model_name, "transformed_only"),
        mev_label_mode,
    )
    default_family_mev = family_mev_options[0]["value"] if family_mev_options else ""
    default_model_mevs = [option["value"] for option in transformed_mev_options]
    default_display_mevs = records.active_selected_mevs(
        model_name,
        default_model_mev_mode,
        default_family_mev,
        default_model_mevs,
        visible_records,
    )
    selected_run_fors = selectors.normalize_selected_run_fors(run_for)
    primary_run_for = selected_run_fors[0] if selected_run_fors else None

    return build_model_report_figures(
        model_name,
        visible_records,
        records_,
        default_model_mev_mode,
        default_model_scenarios,
        snapshot_period_value,
        mev_label_mode,
        reference_lines,
        default_display_mevs,
        figure_builder=figure_builder,
        primary_run_for=primary_run_for,
        include_model_in_title=include_model_in_title,
    )


# Attribute rows mirrored from the dashboard cards: Segment identifies each
# child (it renders in the child heading, like the panel summary), while the
# others roll up to the parent header when every member shares them.
_ROLLUP_ATTRIBUTES = (
    ("Region", "model_region_map"),
    ("Model Group", "model_group_map"),
    ("Portfolio", "model_portfolio_map"),
)


def _model_segment_label(model_name: str) -> str:
    segments = SAAS_PAGE_DATA.get("model_segments_map", {}).get(model_name)
    if not segments:
        fallback = SAAS_PAGE_DATA.get("model_segments", {}).get(model_name)
        segments = [fallback] if fallback else []
    labels = [layout.format_segment_label(value) for value in segments if value]
    return ", ".join(labels)


def _model_rollup_attributes(model_name: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for label, map_key in _ROLLUP_ATTRIBUTES:
        values = [value for value in (SAAS_PAGE_DATA.get(map_key, {}).get(model_name) or []) if value]
        if values:
            suffix = "" if len(values) == 1 else "s"
            attributes[label] = f"{label}{suffix}: {', '.join(values)}"
    return attributes


def build_grouped_report_sections(
    run_for,
    compare_against,
    segment,
    selected_models,
    snapshot_period,
    reference_lines,
    mev_label_mode,
    *,
    region=None,
    model_group=None,
    portfolio=None,
    figure_builder,
) -> list[dict]:
    """Report sections mirroring the workspace hierarchy: one group per parent
    Descriptive Name, each holding its child models (identified by segment and
    GMIS model name) and their (mev_label, figure) pairs. Attributes shared by
    every child roll up to the group, exactly like the dashboard cards."""
    selected_run_fors = selectors.normalize_selected_run_fors(run_for)
    scoped_run_fors = selectors.scoped_run_for_values(run_for, compare_against)
    grouped = selectors.group_effective_models(
        segment, selected_models, region=region, model_group=model_group, portfolio=portfolio
    )

    if not selected_run_fors or not grouped:
        return []

    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    if time_series_df is None or time_series_df.empty:
        return []

    all_models = [name for _parent, members in grouped for name in members]
    filtered_df = time_series_df[time_series_df["Model Name"].isin(all_models)]
    filtered_df = filtered_df[filtered_df["Run For"].isin(scoped_run_fors)]
    records_ = filtered_df.to_dict(orient="records")

    groups: list[dict] = []
    for parent_label, member_models in grouped:
        per_member = {name: _model_rollup_attributes(name) for name in member_models}
        shared_keys = {
            label
            for label, _map_key in _ROLLUP_ATTRIBUTES
            if per_member[member_models[0]].get(label)
            and all(
                per_member[name].get(label) == per_member[member_models[0]].get(label)
                for name in member_models
            )
        }
        shared_attributes = [
            per_member[member_models[0]][label]
            for label, _map_key in _ROLLUP_ATTRIBUTES
            if label in shared_keys
        ]

        models: list[dict] = []
        for model_name in member_models:
            model_records = [row for row in records_ if row.get("Model Name") == model_name]
            figures = build_model_report_sections(
                model_name,
                model_records,
                run_for,
                snapshot_period,
                mev_label_mode,
                reference_lines,
                figure_builder=figure_builder,
                include_model_in_title=False,
            )
            models.append({
                "model_name": model_name,
                "segment_label": _model_segment_label(model_name),
                "attributes": [
                    text for label, text in per_member[model_name].items()
                    if label not in shared_keys
                ],
                "figures": figures,
            })

        groups.append({
            "parent_label": parent_label,
            "shared_attributes": shared_attributes,
            "models": models,
        })
    return groups


def run_for_filename_prefix(run_for) -> str:
    """Filesystem-safe prefix derived from the selected Reporting Cycle."""
    primary_run_for = selectors.primary_run_for_value(run_for)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(primary_run_for or "").strip()).strip("-")
    return slug or "SAAS"
