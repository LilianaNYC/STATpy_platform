"""SAAS workspace Plotly figure builders."""

from __future__ import annotations

from .....components.charts import build_saas_mev_time_series_figure
from . import page as layout, records, selectors


def build_model_figure(
    model_name: str,
    records_: list[dict],
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
    theme_value: str | None = None,
):
    monitoring_reference_records = records.filter_records_by_mevs(
        records.filter_records_by_scenarios(
            reference_records,
            selected_scenarios,
        ),
        selected_mevs,
    )
    scoped_reference_records = records.filter_records_by_date_range(
        monitoring_reference_records,
        range_value,
    )
    y_axis_title = None
    if selected_mevs:
        selected_mev_name = selectors.normalize_selected_mevs(selected_mevs)
        if selected_mev_name:
            y_axis_title = selectors.resolve_mev_label(selected_mev_name[0], mev_label_mode)
    return build_saas_mev_time_series_figure(
        records.filter_records_by_date_range(
            records.filter_records_by_mevs(
                records.filter_records_by_scenarios(
                    records_,
                    selected_scenarios,
                ),
                selected_mevs,
            ),
            range_value,
        ),
        mev_label_map=selectors.active_mev_label_map(mev_label_mode),
        model_label_map={model_name: model_name},
        y_axis_title=y_axis_title,
        snapshot_period=selectors.normalize_snapshot_period(snapshot_period),
        historical_reference_records=scoped_reference_records,
        monitoring_reference_records=monitoring_reference_records,
        reference_lines=reference_lines or layout.DEFAULT_REFERENCE_LINES,
        empty_message=f"No MEV time-series data matches the active filters for {model_name}.",
        primary_run_for=primary_run_for,
        development_date=development_date,
        current_date=current_date,
        projection_start_date=selectors.projection_start_date_for_run_for(primary_run_for),
        theme=selectors.normalize_theme_value(theme_value),
    )
