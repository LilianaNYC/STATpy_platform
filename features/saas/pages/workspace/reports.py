"""SAAS workspace report figure orchestration helpers."""

from __future__ import annotations

import re

from ...data_access import SAAS_PAGE_DATA
from . import page as layout, records, selectors


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
) -> list[tuple[str, object]]:
    """Build (title, figure) pairs for a model using the default chart selections."""
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

    figures: list[tuple[str, object]] = []
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
        figures.append((f"{model_name} — {mev_label}", fig))
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
) -> list[tuple[str, object]]:
    """Build (title, figure) pairs for a model panel's default view."""
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
    )


def build_report_figures(
    run_for,
    compare_against,
    segment,
    selected_models,
    snapshot_period,
    reference_lines,
    mev_label_mode,
    *,
    figure_builder,
) -> list[tuple[str, object]]:
    selected_run_fors = selectors.normalize_selected_run_fors(run_for)
    scoped_run_fors = selectors.scoped_run_for_values(run_for, compare_against)
    effective_models = selectors.effective_model_names(segment, selected_models)

    if not selected_run_fors or not effective_models:
        return []

    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    if time_series_df is None or time_series_df.empty:
        return []

    filtered_df = time_series_df[time_series_df["Model Name"].isin(effective_models)]
    filtered_df = filtered_df[filtered_df["Run For"].isin(scoped_run_fors)]
    records_ = filtered_df.to_dict(orient="records")

    sections: list[tuple[str, object]] = []
    for model_name in effective_models:
        model_records = [row for row in records_ if row.get("Model Name") == model_name]
        sections.extend(
            build_model_report_sections(
                model_name,
                model_records,
                run_for,
                snapshot_period,
                mev_label_mode,
                reference_lines,
                figure_builder=figure_builder,
            )
        )
    return sections


def run_for_filename_prefix(run_for) -> str:
    """Filesystem-safe prefix derived from the selected Reporting Cycle."""
    primary_run_for = selectors.primary_run_for_value(run_for)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(primary_run_for or "").strip()).strip("-")
    return slug or "SAAS"
