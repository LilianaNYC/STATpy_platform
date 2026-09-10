"""Tests for the backtesting figure builders and the service that feeds them."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from STATpy_platform.features.backtesting.domain import aggregation, errors
from STATpy_platform.features.backtesting.services import backtesting_service
from STATpy_platform.features.backtesting.ui.views import figures
from STATpy_platform.shared.domain import constants as config
from STATpy_platform.shared.ui import charts

SEGMENT = config.BACKTESTING_SEGMENT_COLUMN
MODEL = config.BACKTESTING_MODEL_NAME_COLUMN
SNAPSHOT = config.BACKTESTING_SNAPSHOT_COLUMN
RUN_FOR = config.BACKTESTING_RUN_FOR_COLUMN
SCENARIO = config.BACKTESTING_SCENARIO_COLUMN
JN = config.BACKTESTING_JN_FLAG_COLUMN
QUARTER = config.BACKTESTING_QUARTER_COLUMN
FACILITY = config.BACKTESTING_FACILITY_ID_COLUMN
INSTRUMENT = config.BACKTESTING_CREDIT_INSTRUMENT_ID_COLUMN


def _records():
    frame = pd.DataFrame([
        {
            SEGMENT: "Cyclical", MODEL: "PD_model_a", SNAPSHOT: pd.Timestamp(snapshot),
            RUN_FOR: "CCAR 2025", SCENARIO: "Base", JN: "N", QUARTER: quarter,
            "value": value, "exposure": 1_000_000.0, "facility_count": 10,
        }
        for snapshot, quarter, value in (
            (date(2024, 3, 31), 1, 0.0250),
            (date(2024, 3, 31), 2, 0.0400),
            (date(2024, 6, 30), 0, 0.0200),
            (date(2024, 9, 30), 0, 0.0200),
        )
    ])
    aggregated = aggregation._attach_quarter_columns(frame, [SEGMENT, MODEL])
    return errors.build_error_records(aggregated)


# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------


def test_forecast_actual_figure_plots_actual_and_per_vintage_forecasts():
    fig = charts.build_backtesting_forecast_actual_figure(_records())
    names = [trace.name for trace in fig.data]
    assert any("Actual" in name for name in names)
    assert any("Forecast" in name for name in names)
    # One legend entry for the forecast paths, however many vintages there are.
    assert sum(1 for trace in fig.data if trace.showlegend and "Forecast" in (trace.name or "")) == 1


def test_forecast_actual_figure_uses_quarter_labels_on_the_shared_axis():
    fig = charts.build_backtesting_forecast_actual_figure(_records())
    # build_pd_time_series_xaxis renders YYYY-Qn ticks compactly as YYYYQn.
    assert "2024Q2" in list(fig.layout.xaxis.ticktext)


def test_forecast_actual_figure_is_transparent_so_the_card_theme_shows_through():
    fig = charts.build_backtesting_forecast_actual_figure(_records())
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"


def test_figures_build_for_both_themes():
    records = _records()
    summaries = errors.summarize_by(records, ["horizon"])
    for theme in ("light", "dark"):
        assert charts.build_backtesting_forecast_actual_figure(records, theme=theme).data
        assert charts.build_backtesting_horizon_error_figure(summaries, theme=theme).data


def test_dark_theme_changes_the_rendered_colours():
    records = _records()
    light = charts.build_backtesting_forecast_actual_figure(records, theme="light")
    dark = charts.build_backtesting_forecast_actual_figure(records, theme="dark")
    assert light.layout.font.color != dark.layout.font.color


def test_empty_records_return_the_shared_empty_figure_not_a_blank_graph():
    fig = charts.build_backtesting_forecast_actual_figure([])
    assert not fig.data
    assert fig.layout.annotations           # carries the explanatory message
    assert charts.build_backtesting_horizon_error_figure([]).layout.annotations


def test_horizon_figure_plots_mape_and_bias():
    summaries = errors.summarize_by(_records(), ["horizon"])
    fig = charts.build_backtesting_horizon_error_figure(summaries)
    names = [trace.name for trace in fig.data]
    assert "MAPE" in names and "Bias" in names


def test_error_rag_bands():
    assert charts.backtest_error_rag(0.05) == "Green"
    assert charts.backtest_error_rag(-0.20) == "Amber"
    assert charts.backtest_error_rag(0.90) == "Red"
    assert charts.backtest_error_rag(None) == "N/A"


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------


def test_rates_format_as_percentages_and_amounts_as_currency():
    assert figures.metric_value_format(config.BACKTESTING_METRIC_PD)[0].endswith("%")
    assert figures.metric_value_format(config.BACKTESTING_METRIC_LGD)[0].endswith("%")
    # A percent format on a currency amount would render $12m as 1,200,000,000%.
    assert figures.metric_value_format(config.BACKTESTING_METRIC_EAD)[0] == "$,.0f"
    assert figures.metric_value_format(config.BACKTESTING_METRIC_NCO)[0] == "$,.0f"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def applied():
    return {
        "region": "all", "portfolio": "all", "model_group": "all",
        "segment": "all", "model": "all", "run_for": "all",
        "scenario": "Base", "jn_flag": "all", "snapshot": "all",
    }


def test_service_scores_every_metric(applied):
    views = backtesting_service.build_dashboard_view(applied)
    assert set(views) == set(config.BACKTESTING_METRIC_SHEETS)
    for metric, view in views.items():
        assert view["records"], metric
        assert view["by_horizon"], metric
        assert view["summary"]["count"] > 0, metric


def test_service_reports_unscored_recent_horizons(applied):
    view = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_PD, applied)
    # The most recent horizons have no realised anchor yet -- not an error.
    assert view["unscored"] > 0


def test_service_weights_rate_metrics_and_sums_amounts(applied):
    pd_view = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_PD, applied)
    ead_view = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_EAD, applied)
    # A rate stays in [0,1]; an amount is currency-scale.
    assert 0.0 < pd_view["records"][0]["actual"] < 1.0
    assert ead_view["records"][0]["actual"] > 1_000.0


def test_service_narrows_by_segment(applied):
    scoped = backtesting_service.build_metric_view(
        config.BACKTESTING_METRIC_PD, {**applied, "segment": "Defensive"}
    )
    # PD_model_a serves Cyclical only, so results.pd has nothing in Defensive.
    assert scoped["records"] == []

    crr = backtesting_service.build_metric_view(
        config.BACKTESTING_METRIC_PD_CRR, {**applied, "segment": "Defensive"}
    )
    assert crr["records"]


def test_service_scopes_lgd_by_facility_population_not_by_model_name(applied):
    """The Model filter is PD-side. Applied to results.lgd by Model Name it
    would match nothing, so it must scope by facility population instead."""
    view = backtesting_service.build_metric_view(
        config.BACKTESTING_METRIC_LGD, {**applied, "model": "PD_model_a"}
    )
    assert view["records"], "LGD must still score when a PD model is selected"

    everything = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_LGD, applied)
    assert view["row_count"] < everything["row_count"]


def test_service_treats_no_filters_as_no_narrowing(applied):
    """``None`` means "nothing selected", not "nothing in scope".

    It is the layout that withholds the call until Apply is clicked; the service
    itself has no reason to invent an empty result, and returning one here would
    hide a caller that forgot to pass its filters.
    """
    unfiltered = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_PD, None)
    # The fixture pins Scenario to Base, so compare against a truly open scope.
    everything = backtesting_service.build_metric_view(
        config.BACKTESTING_METRIC_PD, {**applied, "scenario": "all"}
    )
    assert unfiltered["row_count"] == everything["row_count"]
    assert len(unfiltered["records"]) == len(everything["records"])


def test_service_only_scores_the_base_scenario(applied):
    """Non-base scenarios are conservative by design; scoring them measures the
    buffer, not accuracy."""
    view = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_PD, applied)
    assert {record[SCENARIO] for record in view["records"]} == {"Base"}


def test_service_scores_a_single_selected_snapshot_against_full_history(applied):
    view = backtesting_service.build_metric_view(
        config.BACKTESTING_METRIC_PD,
        {**applied, "snapshot": "2023-03-31"},
    )
    assert view["summary"]["count"] > 0
    assert {record["vintage_quarter"] for record in view["records"]} == {"2023-Q1"}


def test_non_base_selections_are_unscored_context_for_every_metric(applied):
    views = backtesting_service.build_dashboard_view({**applied, "scenario": "Severe"})

    for metric, view in views.items():
        assert view["records"] == [], metric
        assert view["by_horizon"] == [], metric
        assert view["summary"]["count"] == 0, metric
        assert view["summary"]["mape_count"] == 0, metric
        for statistic in ("bias", "mae", "rmse", "mape", "hit_rate"):
            assert view["summary"][statistic] is None, (metric, statistic)
        assert view["scoring_status"] == "context_only", metric
        assert "not scored" in view["scoring_note"], metric
        assert view["vintage_series"], f"{metric} should remain available as context"


@pytest.mark.parametrize(
    "metric",
    [config.BACKTESTING_METRIC_EAD, config.BACKTESTING_METRIC_NCO],
)
def test_all_cycles_and_jn_compare_but_model_populations_combine(
    monkeypatch, applied, metric
):
    """Additive values combine disjoint models once and preserve four alternative
    cycle/J-N observations instead of summing all eight partitions together."""
    value_column = config.BACKTESTING_METRIC_VALUE_COLUMNS[metric]
    rows = []
    expected = {}
    for run_for, run_base in (("CCAR 2025", 1_000.0), ("CCAR 2026", 2_000.0)):
        for jn_flag, overlay in (("N", 0.0), ("J", 100.0)):
            actual = 0.0
            forecast = 0.0
            for suffix, partition_value in (("a", 10.0), ("b", 20.0)):
                identity = {
                    SEGMENT: "Cyclical",
                    RUN_FOR: run_for,
                    SCENARIO: "Base",
                    JN: jn_flag,
                    FACILITY: f"F-{suffix}",
                    INSTRUMENT: f"I-{suffix}",
                }
                if metric == config.BACKTESTING_METRIC_EAD:
                    identity[MODEL] = f"EAD_model_{suffix}"
                else:
                    identity.update({
                        config.BACKTESTING_PD_MODEL_NAME_COLUMN: f"PD_model_{suffix}",
                        config.BACKTESTING_LGD_MODEL_NAME_COLUMN: f"LGD_model_{suffix}",
                        config.BACKTESTING_EAD_MODEL_NAME_COLUMN: f"EAD_model_{suffix}",
                        config.BACKTESTING_LOSS_METHOD_COLUMN: "Expected Loss",
                    })
                partition_actual = run_base + overlay + partition_value
                partition_forecast = partition_actual * 1.10
                actual += partition_actual
                forecast += partition_forecast
                rows.extend([
                    {
                        **identity,
                        SNAPSHOT: pd.Timestamp(date(2024, 3, 31)),
                        QUARTER: 1,
                        value_column: partition_forecast,
                    },
                    {
                        **identity,
                        SNAPSHOT: pd.Timestamp(date(2024, 6, 30)),
                        QUARTER: 0,
                        value_column: partition_actual,
                    },
                ])
            expected[(run_for, jn_flag)] = (forecast, actual)

    frame = pd.DataFrame(rows)
    monkeypatch.setattr(backtesting_service, "_facility_scope", lambda _applied: None)
    monkeypatch.setattr(
        backtesting_service,
        "_frame",
        lambda requested: frame if requested == metric else pd.DataFrame(),
    )

    all_view = backtesting_service.build_metric_view(metric, applied)
    assert len(all_view["records"]) == 4
    all_records = {
        (record[RUN_FOR], record[JN]): record for record in all_view["records"]
    }
    assert set(all_records) == set(expected)

    for identity, (forecast, actual) in expected.items():
        record = all_records[identity]
        assert record["forecast"] == pytest.approx(forecast)
        assert record["actual"] == pytest.approx(actual)

        scoped = backtesting_service.build_metric_view(
            metric,
            {**applied, "run_for": identity[0], "jn_flag": identity[1]},
        )
        assert len(scoped["records"]) == 1
        assert scoped["records"][0]["forecast"] == pytest.approx(record["forecast"])
        assert scoped["records"][0]["actual"] == pytest.approx(record["actual"])


# ---------------------------------------------------------------------------
# Vintage curves (static-pool view)
# ---------------------------------------------------------------------------


def test_vintage_curve_draws_one_line_per_vintage_with_an_end_label(applied):
    view = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_PD, applied)
    fig = charts.build_backtesting_vintage_curve_figure(view["vintage_series"])
    assert len(fig.data) == len(view["vintage_series"])
    # Each curve is labelled at its right-hand end, not only in the legend.
    assert len(fig.layout.annotations) == len(fig.data)
    # Quarters render compactly (2024Q1) here as on every other chart.
    from STATpy_platform.shared.domain.quarter_labels import format_pd_compact_quarter_label
    assert {trace.name for trace in fig.data} == {
        format_pd_compact_quarter_label(entry["vintage"]) for entry in view["vintage_series"]
    }


def test_vintage_curve_is_plotted_against_age_not_calendar_quarter(applied):
    view = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_PD, applied)
    fig = charts.build_backtesting_vintage_curve_figure(view["vintage_series"])
    # x is the horizon, so every cohort starts at 0 regardless of its vintage,
    # and the axis is named and ticked the same way the error-by-horizon chart
    # names and ticks its own horizon axis.
    assert all(trace.x[0] == 0 for trace in fig.data)
    assert fig.layout.xaxis.title.text == "Projection horizon"
    assert list(fig.layout.xaxis.ticktext)[:2] == ["Q+0", "Q+1"]


def test_vintage_curve_labels_are_consistent_with_the_other_charts():
    """Quarters read compactly (2024Q1) and horizons read Q+n, matching the
    forecast-vs-actual axis and the error-by-horizon axis respectively."""
    series = [{"vintage": "2024-Q1", "points": [
        {"horizon": 0, "value": 0.01, "target_quarter": "2024-Q1"},
        {"horizon": 1, "value": 0.02, "target_quarter": "2024-Q2"},
    ]}]
    fig = charts.build_backtesting_vintage_curve_figure(series)

    assert fig.data[0].name == "2024Q1"
    assert fig.layout.annotations[0].text.strip() == "2024Q1"
    assert list(fig.layout.xaxis.ticktext) == ["Q+0", "Q+1"]
    # Hover target quarters are compact too.
    assert list(fig.data[0].customdata) == ["2024Q1", "2024Q2"]


def test_vintage_series_keeps_horizons_that_have_no_actual_yet(applied):
    """A vintage curve is about the projected path, so it must not be trimmed to
    the horizons that happen to be scoreable."""
    view = backtesting_service.build_metric_view(config.BACKTESTING_METRIC_PD, applied)
    horizons = {point["horizon"] for entry in view["vintage_series"] for point in entry["points"]}
    assert horizons == set(range(10))

    scored = {record["horizon"] for record in view["records"]}
    assert scored < horizons


def test_cumulative_loss_accumulates_and_is_share_of_opening_exposure(applied):
    curves = backtesting_service.build_cumulative_loss_series(applied)
    assert curves
    for entry in curves:
        values = [point["value"] for point in entry["points"]]
        # Cumulative, so non-decreasing, and a share so within a sane range.
        assert values == sorted(values)
        assert 0.0 <= values[0] <= values[-1] < 1.0


def test_cumulative_loss_is_empty_without_both_nco_and_ead(applied):
    impossible = {**applied, "segment": "not-a-segment"}
    assert backtesting_service.build_cumulative_loss_series(impossible) == []


def test_cumulative_loss_figure_builds_for_both_themes(applied):
    curves = backtesting_service.build_cumulative_loss_series(applied)
    for theme in ("light", "dark"):
        fig = figures.build_cumulative_loss_figure(curves, theme=theme)
        assert fig.data
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"


def test_end_labels_never_overlap_even_when_curves_converge():
    """Vintage curves converge, so several can finish within a hair of each
    other. The labels must still be readable."""
    series = [
        {"vintage": f"2024-Q{n}", "points": [{"horizon": 0, "value": 0.0},
                                             {"horizon": 1, "value": 0.10 + n * 1e-6}]}
        for n in range(1, 5)
    ]
    fig = charts.build_backtesting_vintage_curve_figure(series)
    ys = sorted(annotation.y for annotation in fig.layout.annotations)
    assert len(ys) == 4
    assert all(second > first for first, second in zip(ys, ys[1:]))


def test_de_colliding_labels_does_not_move_the_plotted_data():
    """Only the label moves; the curve stays where the data puts it."""
    series = [
        {"vintage": "2024-Q1", "points": [{"horizon": 0, "value": 0.10}]},
        {"vintage": "2024-Q2", "points": [{"horizon": 0, "value": 0.100001}]},
    ]
    fig = charts.build_backtesting_vintage_curve_figure(series)
    assert [trace.y[-1] for trace in fig.data] == [0.10, 0.100001]


def test_periodic_loss_sums_to_the_cumulative_curve(applied):
    """The two views are the same data differenced, so they must reconcile --
    otherwise the pair would tell contradictory stories."""
    cumulative = backtesting_service.build_loss_curve_series(applied, cumulative=True)
    periodic = backtesting_service.build_loss_curve_series(applied, cumulative=False)
    assert len(cumulative) == len(periodic) and cumulative

    by_series = {
        (entry["vintage"], entry["run_for"], entry["jn_flag"]): entry
        for entry in periodic
    }
    for entry in cumulative:
        key = (entry["vintage"], entry["run_for"], entry["jn_flag"])
        steps = [point["value"] for point in by_series[key]["points"]]
        assert sum(steps) == pytest.approx(entry["points"][-1]["value"])


def test_periodic_loss_is_not_forced_to_rise(applied):
    """A cumulative curve can only ever rise; the periodic one must be free to
    fall, which is the whole reason for showing it."""
    periodic = backtesting_service.build_loss_curve_series(applied, cumulative=False)
    values = [point["value"] for entry in periodic for point in entry["points"]]
    assert any(second < first for first, second in zip(values, values[1:]))


def test_both_loss_views_share_a_denominator(applied):
    """Same opening exposure on both, so the charts can be read against each
    other rather than only against themselves."""
    cumulative = backtesting_service.build_loss_curve_series(applied, cumulative=True)
    periodic = backtesting_service.build_loss_curve_series(applied, cumulative=False)
    # At horizon 0 nothing has accumulated yet, so the two coincide.
    for cum, per in zip(cumulative, periodic):
        assert cum["points"][0]["value"] == pytest.approx(per["points"][0]["value"])


def test_periodic_loss_figure_builds_for_both_themes(applied):
    series = backtesting_service.build_loss_curve_series(applied, cumulative=False)
    for theme in ("light", "dark"):
        assert figures.build_periodic_loss_figure(series, theme=theme).data
