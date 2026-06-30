"""Regression tests for shared PD chart helpers."""

from __future__ import annotations

from datetime import date

import pytest

from STATpy_platform.shared.ui.charts import (
    build_pd_confidence_interval_trend_figure,
    build_pd_default_rate_trend_figure,
    build_pd_discrimination_trend_figures,
    build_pd_notching_trend_figure,
    build_pd_go_live_accuracy_trend_figure,
    build_pd_mev_range_figure,
    build_pd_scenario_projection_figure,
    build_pd_scenario_rank_figure,
    build_pd_time_series_xaxis,
)


def test_pd_time_series_xaxis_uses_mev_range_quarter_label_format():
    axis = build_pd_time_series_xaxis(
        ["2023-Q1", "2023-Q2", "2023-Q3", "2023-Q4"],
        {"title": "Portfolio Quarter"},
    )

    assert axis["ticktext"] == ["2023Q1", "2023Q2", "2023Q3", "2023Q4"]


def test_pd_time_series_xaxis_keeps_labels_horizontal_when_compact():
    axis = build_pd_time_series_xaxis(
        [f"2023-Q{quarter}" for quarter in (1, 2, 3, 4)] + [f"2024-Q{quarter}" for quarter in (1, 2, 3, 4)],
        {"title": "Portfolio Quarter"},
        density="compact",
    )

    assert axis["tickangle"] == 0


def test_pd_mev_range_uses_selected_scenario_q0_as_scenario_marker():
    mev_data = {
        "dev_range": {
            "min": 1.0,
            "max": 3.0,
            "mean": 2.0,
            "2std_lower": 0.5,
            "2std_upper": 3.5,
            "development_date": "2025-Q3",
        },
        "time_series": {
            "2025-Q3": 1.2,
            "2025-Q4": 1.8,
            "2026-Q1": 2.4,
            "2026-Q2": 2.8,
            "2026-Q3": 3.2,
        },
        "scenario_series_by_cycle": {
            "CCAR 2026": {
                "intsevere": {
                    "2025-Q3": 1.2,
                    "2025-Q4": 1.8,
                    "2026-Q1": 2.4,
                    "2026-Q2": 2.8,
                    "2026-Q3": 3.2,
                },
            },
        },
        "scenario_quarter_zero_by_cycle": {
            "CCAR 2026": {"intsevere": "2025-Q4"},
        },
    }

    figure = build_pd_mev_range_figure(
        {},
        "Unemployment",
        mev_data,
        "#dc2626",
        current_quarter="2026-Q3",
        reporting_cycle="CCAR 2026",
        scenario="intsevere",
    )

    scenario_markers = [
        shape
        for shape in figure.layout.shapes
        if getattr(shape, "type", None) == "line"
        and getattr(getattr(shape, "line", None), "color", None) == "#dc2626"
    ]

    assert scenario_markers
    assert scenario_markers[0].x0 == date(2025, 12, 31)


def test_pd_mev_range_uses_reporting_cycle_q0_when_selected_scenario_missing():
    mev_data = {
        "dev_range": {
            "min": 1.0,
            "max": 3.0,
            "mean": 2.0,
            "2std_lower": 0.5,
            "2std_upper": 3.5,
            "development_date": "2025-Q3",
        },
        "time_series": {
            "2025-Q3": 1.2,
            "2025-Q4": 1.8,
            "2026-Q1": 2.4,
        },
        "scenario_series_by_cycle": {
            "CCAR 2026": {
                "baseline": {
                    "2025-Q3": 1.2,
                    "2025-Q4": 1.8,
                    "2026-Q1": 2.4,
                },
            },
        },
        "scenario_quarter_zero_by_cycle": {
            "CCAR 2026": {"baseline": "2025-Q4"},
        },
    }

    figure = build_pd_mev_range_figure(
        {},
        "Unemployment",
        mev_data,
        "#dc2626",
        reporting_cycle="CCAR 2026",
        scenario="intsevere",
    )
    scenario_markers = [
        shape
        for shape in figure.layout.shapes
        if getattr(shape, "type", None) == "line"
        and getattr(getattr(shape, "line", None), "color", None) == "#dc2626"
    ]

    assert scenario_markers
    assert scenario_markers[0].x0 == date(2025, 12, 31)


def test_pd_mev_range_xaxis_reduces_dense_end_label_overlap():
    quarters = [f"2024-Q{quarter}" for quarter in (1, 2, 3, 4)] + [
        f"2025-Q{quarter}" for quarter in (1, 2, 3, 4)
    ] + [f"2026-Q{quarter}" for quarter in (1, 2, 3, 4)]
    mev_data = {
        "dev_range": {
            "min": 1.0,
            "max": 3.0,
            "mean": 2.0,
            "2std_lower": 0.5,
            "2std_upper": 3.5,
            "development_date": "2025-Q3",
        },
        "time_series": {quarter: 1.0 + index * 0.1 for index, quarter in enumerate(quarters)},
        "scenario_quarter_zero_by_cycle": {
            "CCAR 2026": {"intsevere": "2025-Q4"},
        },
    }

    figure = build_pd_mev_range_figure(
        {},
        "Unemployment",
        mev_data,
        "#dc2626",
        reporting_cycle="CCAR 2026",
        scenario="intsevere",
    )

    assert len(figure.layout.xaxis.tickvals) <= 6
    assert figure.layout.xaxis.tickangle == 0
    assert figure.layout.margin.b == 72


def test_pd_scenario_projection_and_rank_figures_show_all_scenarios():
    rows = [
        {"projection_quarter": "2025-12-31", "quarter": 0, "scenario_variant": "baseline", "projected_pd": 0.020},
        {"projection_quarter": "2025-12-31", "quarter": 0, "scenario_variant": "intsevere", "projected_pd": 0.030},
        {"projection_quarter": "2025-12-31", "quarter": 0, "scenario_variant": "baseline_2std_shock", "projected_pd": 0.045},
        {"projection_quarter": "2026-03-31", "quarter": 1, "scenario_variant": "baseline", "projected_pd": 0.021},
        {"projection_quarter": "2026-03-31", "quarter": 1, "scenario_variant": "intsevere", "projected_pd": 0.033},
        {"projection_quarter": "2026-03-31", "quarter": 1, "scenario_variant": "baseline_2std_shock", "projected_pd": 0.050},
    ]

    projection = build_pd_scenario_projection_figure(rows)
    ranking = build_pd_scenario_rank_figure(rows)

    assert [trace.name for trace in projection.data] == ["baseline", "intsevere", "baseline_2std_shock"]
    assert list(projection.layout.xaxis.ticktext) == ["Q0", "Q1"]
    assert list(ranking.data[0].y) == ["baseline", "intsevere", "baseline_2std_shock"]
    # Rank order runs 1 (lowest PD) to N (highest PD): the most-severe path ranks highest.
    assert ranking.data[0].z[2][0] == 3


def test_confidence_interval_trend_hides_y_axis_zero_line():
    figure = build_pd_confidence_interval_trend_figure(
        [
            {"quarter": "2023-Q1", "confidence_interval": 0.00},
            {"quarter": "2023-Q2", "confidence_interval": 0.12},
        ],
        {
            "pd_thresholds": [
                {"metric": "Confidence Interval Test", "green_min": 0.0, "green_max": 0.25, "amber_lower": -0.1, "amber_upper": 0.35},
            ]
        },
        "2023-Q2",
    )

    assert figure.layout.yaxis.zeroline is False


def test_confidence_interval_trend_uses_theme_monochrome_line():
    figure = build_pd_confidence_interval_trend_figure(
        [
            {"quarter": "2023-Q1", "confidence_interval": 0.00},
            {"quarter": "2023-Q2", "confidence_interval": 0.12},
        ],
        {
            "pd_thresholds": [
                {"metric": "Confidence Interval Test", "green_min": 0.0, "green_max": 0.25, "amber_lower": -0.1, "amber_upper": 0.35},
            ]
        },
        "2023-Q2",
        theme="dark",
    )

    assert figure.data[0].line.color == "rgba(203,213,225,0.78)"


def test_notching_trend_starts_difference_axis_at_negative_point_five_and_uses_ci_axis_style():
    figure = build_pd_notching_trend_figure(
        [
            {"quarter": "2023-Q1", "actual_notch": 4, "predicted_notch": 5, "notching_difference": 1},
            {"quarter": "2023-Q2", "actual_notch": 3, "predicted_notch": 5, "notching_difference": 2},
        ],
        {
            "pd_thresholds": [
                {"metric": "Notching Test", "green_min": -1.0, "green_max": 1.0, "amber_lower": -2.0, "amber_upper": 2.0},
            ]
        },
    )

    assert figure.layout.yaxis2.range[0] == -0.5
    assert figure.layout.xaxis.showline is None
    assert figure.layout.xaxis2.showline is None
    assert figure.layout.yaxis.showline is None
    assert figure.layout.yaxis2.showline is None
    assert figure.layout.yaxis.zeroline is False
    assert figure.layout.yaxis2.zeroline is False
    assert figure.layout.xaxis.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.xaxis2.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.yaxis.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.yaxis2.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.xaxis.gridwidth == 0.8
    assert figure.layout.xaxis2.gridwidth == 0.8
    assert figure.layout.yaxis.gridwidth == 0.8
    assert figure.layout.yaxis2.gridwidth == 0.8


def test_notching_trend_makes_zero_green_band_visible_for_exact_zero_threshold():
    figure = build_pd_notching_trend_figure(
        [
            {"quarter": "2023-Q1", "actual_notch": 4, "predicted_notch": 4, "notching_difference": 0},
            {"quarter": "2023-Q2", "actual_notch": 4, "predicted_notch": 5, "notching_difference": 1},
        ],
        {
            "pd_thresholds": [
                {
                    "metric": "Notching Test",
                    "green_min": 0.0,
                    "green_max": 0.0,
                    "amber_min": 0.0,
                    "amber_max": 1.0,
                    "red_condition": "above amber_max",
                },
            ]
        },
    )

    green_shapes = [
        shape for shape in figure.layout.shapes
        if getattr(shape, "fillcolor", None) == "rgba(22,163,74,.10)"
    ]
    assert any(shape.y0 == -0.5 and shape.y1 == 0.05 for shape in green_shapes)
    amber_shapes = [
        shape for shape in figure.layout.shapes
        if getattr(shape, "fillcolor", None) == "rgba(217,119,6,.18)"
    ]
    assert any(shape.y0 == 0.05 and shape.y1 == 1.05 for shape in amber_shapes)


def test_ae_ratio_figure_uses_soft_ratio_grid_style():
    figure = build_pd_default_rate_trend_figure(
        [
            {
                "quarter": "2023-Q1",
                "observed_default_rate": 0.02,
                "predicted_default_rate": 0.01,
                "actual_expected_ratio": 2.0,
            },
            {
                "quarter": "2023-Q2",
                "observed_default_rate": 0.01,
                "predicted_default_rate": 0.01,
                "actual_expected_ratio": 1.0,
            },
        ],
        {
            "pd_thresholds": [
                {"metric": "Actual / Expected Ratio", "green_min": 0.8, "green_max": 1.2, "amber_min": 0.6, "amber_max": 1.5, "red_condition": "outside amber range"},
            ]
        },
        theme="dark",
    )

    assert figure.layout.xaxis.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.xaxis2.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.yaxis.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.yaxis2.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.xaxis.gridwidth == 0.8
    assert figure.layout.xaxis2.gridwidth == 0.8
    assert figure.layout.yaxis.gridwidth == 0.8
    assert figure.layout.yaxis2.gridwidth == 0.8
    assert figure.layout.yaxis.zeroline is False
    assert figure.layout.yaxis2.zeroline is False
    assert figure.data[2].line.color == "rgba(203,213,225,0.78)"
    assert not any(
        getattr(shape, "type", None) == "line" and getattr(shape, "y0", None) == 1 and getattr(shape, "y1", None) == 1
        for shape in figure.layout.shapes
    )


def test_delta_accuracy_figure_uses_soft_ratio_grid_style():
    figure = build_pd_go_live_accuracy_trend_figure(
        [
            {
                "quarter": "2023-Q1",
                "accuracy_ratio": 0.4,
                "go_live_accuracy_ratio": 0.35,
                "delta_accuracy_ratio": 0.05,
            },
            {
                "quarter": "2023-Q2",
                "accuracy_ratio": 0.45,
                "go_live_accuracy_ratio": 0.35,
                "delta_accuracy_ratio": 0.10,
            },
        ],
        {
            "pd_thresholds": [
                {"metric": "Delta Accuracy Ratio", "green_min": 0.0, "green_max": 0.1, "amber_min": 0.1, "amber_max": 0.2, "red_condition": "above amber_max"},
            ]
        },
        "2023-Q1",
        theme="light",
    )

    assert figure.layout.xaxis.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.xaxis2.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.yaxis.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.yaxis2.gridcolor == "rgba(148,163,184,0.18)"
    assert figure.layout.xaxis.gridwidth == 0.8
    assert figure.layout.xaxis2.gridwidth == 0.8
    assert figure.layout.yaxis.gridwidth == 0.8
    assert figure.layout.yaxis2.gridwidth == 0.8
    assert figure.layout.yaxis.zeroline is False
    assert figure.layout.yaxis2.zeroline is False
    assert figure.data[2].line.color == "rgba(71,85,105,0.75)"


def test_notching_trend_uses_theme_monochrome_line():
    figure = build_pd_notching_trend_figure(
        [
            {"quarter": "2023-Q1", "actual_notch": 4, "predicted_notch": 5, "notching_difference": 1},
            {"quarter": "2023-Q2", "actual_notch": 3, "predicted_notch": 5, "notching_difference": 2},
        ],
        {
            "pd_thresholds": [
                {"metric": "Notching Test", "green_min": -1.0, "green_max": 1.0, "amber_lower": -2.0, "amber_upper": 2.0},
            ]
        },
        theme="light",
    )

    assert figure.data[2].line.color == "rgba(71,85,105,0.75)"


def test_discriminatory_power_other_metrics_hide_zero_line():
    figures = build_pd_discrimination_trend_figures(
        [
            {"quarter": "2023-Q1", "gini_coefficient": 0.1, "ks_statistic": 0.2, "kendall_tau": -0.05},
            {"quarter": "2023-Q2", "gini_coefficient": 0.15, "ks_statistic": 0.25, "kendall_tau": 0.04},
        ],
        {
            "pd_thresholds": [
                {"metric": "Gini Coefficient", "green_min": 0.1, "green_max": 0.3, "amber_min": 0.05, "amber_max": 0.35, "red_condition": "outside amber range"},
                {"metric": "KS Statistic", "green_min": 0.1, "green_max": 0.3, "amber_min": 0.05, "amber_max": 0.35, "red_condition": "outside amber range"},
                {"metric": "Kendall's Tau", "green_min": -0.1, "green_max": 0.1, "amber_min": -0.2, "amber_max": 0.2, "red_condition": "outside amber range"},
            ]
        },
        "2023-Q2",
    )

    assert figures["gini_coefficient"].layout.yaxis.zeroline is False
    assert figures["ks_statistic"].layout.yaxis.zeroline is False
    assert figures["kendall_tau"].layout.yaxis.zeroline is False


def test_discriminatory_power_other_metrics_use_neutral_theme_line_color():
    figures = build_pd_discrimination_trend_figures(
        [
            {"quarter": "2023-Q1", "gini_coefficient": 0.1, "ks_statistic": 0.2, "kendall_tau": -0.05},
            {"quarter": "2023-Q2", "gini_coefficient": 0.15, "ks_statistic": 0.25, "kendall_tau": 0.04},
        ],
        {
            "pd_thresholds": [
                {"metric": "Gini Coefficient", "green_min": 0.1, "green_max": 0.3, "amber_min": 0.05, "amber_max": 0.35, "red_condition": "outside amber range"},
                {"metric": "KS Statistic", "green_min": 0.1, "green_max": 0.3, "amber_min": 0.05, "amber_max": 0.35, "red_condition": "outside amber range"},
                {"metric": "Kendall's Tau", "green_min": -0.1, "green_max": 0.1, "amber_min": -0.2, "amber_max": 0.2, "red_condition": "outside amber range"},
            ]
        },
        "2023-Q2",
        theme="dark",
    )

    assert figures["gini_coefficient"].data[0].line.color == "rgba(203,213,225,0.78)"
    assert figures["ks_statistic"].data[0].line.color == "rgba(203,213,225,0.78)"
    assert figures["kendall_tau"].data[0].line.color == "rgba(203,213,225,0.78)"
