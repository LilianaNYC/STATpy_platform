"""Unit tests for the backtest engine, including hand-computed error cases."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from STATpy_platform.features.backtesting.domain import aggregation, errors
from STATpy_platform.shared.domain import constants as config

SEGMENT = config.BACKTESTING_SEGMENT_COLUMN
MODEL = config.BACKTESTING_MODEL_NAME_COLUMN
SNAPSHOT = config.BACKTESTING_SNAPSHOT_COLUMN
RUN_FOR = config.BACKTESTING_RUN_FOR_COLUMN
SCENARIO = config.BACKTESTING_SCENARIO_COLUMN
JN = config.BACKTESTING_JN_FLAG_COLUMN
QUARTER = config.BACKTESTING_QUARTER_COLUMN


def _aggregated(
    rows,
    *,
    segment="Cyclical",
    model="PD_model_a",
    run_for="CCAR 2025",
    scenario="Base",
    jn="N",
):
    """Build an aggregated frame directly.

    ``rows`` is ``(snapshot, quarter, value)``. Going straight to the aggregated
    shape keeps these tests about the error engine rather than about aggregation,
    which has its own suite -- but the quarter columns are attached by the real
    :mod:`aggregation` helper so the two stay in step.
    """
    frame = pd.DataFrame([
        {
            SEGMENT: segment,
            MODEL: model,
            SNAPSHOT: pd.Timestamp(snapshot),
            RUN_FOR: run_for,
            SCENARIO: scenario,
            JN: jn,
            QUARTER: quarter,
            "value": value,
            "exposure": 1_000_000.0,
            "facility_count": 10,
        }
        for snapshot, quarter, value in rows
    ])
    return aggregation._attach_quarter_columns(frame, [SEGMENT, MODEL])


# ---------------------------------------------------------------------------
# The hand-computed error case
# ---------------------------------------------------------------------------


def test_error_measures_match_hand_computed_values():
    """One forecast, one actual, computed by hand.

        2024-Q1 vintage, horizon 1  -> targets 2024-Q2, forecast 0.0250
        2024-Q2 vintage, anchor      -> actual for 2024-Q2   = 0.0200

        error            = 0.0250 - 0.0200 =  0.0050
        absolute_error   = 0.0050
        percentage_error = 0.0050 / 0.0200 =  0.25   (25% over-forecast)
    """
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),      # the forecast
        (date(2024, 6, 30), 0, 0.0200),      # the actual (anchor of the next vintage)
    ])

    records = errors.build_error_records(aggregated)
    assert len(records) == 1

    record = records[0]
    assert record["vintage_quarter"] == "2024-Q1"
    assert record["target_quarter"] == "2024-Q2"
    assert record["horizon"] == 1
    assert record["forecast"] == pytest.approx(0.0250)
    assert record["actual"] == pytest.approx(0.0200)
    assert record["error"] == pytest.approx(0.0050)
    assert record["absolute_error"] == pytest.approx(0.0050)
    assert record["percentage_error"] == pytest.approx(0.25)


def test_under_forecast_produces_a_negative_signed_error():
    # The sign carries the meaning: negative = losses under-forecast.
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0150),
        (date(2024, 6, 30), 0, 0.0200),
    ])
    record = errors.build_error_records(aggregated)[0]
    assert record["error"] == pytest.approx(-0.0050)
    assert record["absolute_error"] == pytest.approx(0.0050)
    assert record["percentage_error"] == pytest.approx(-0.25)


def test_summary_statistics_match_hand_computed_values():
    """Three scored forecasts of three different targets.

        forecast  actual   error    abs     pct
        0.0250    0.0200   +0.0050  0.0050  +0.25
        0.0150    0.0200   -0.0050  0.0050  -0.25
        0.0400    0.0200   +0.0200  0.0200  +1.00

        bias = (0.005 - 0.005 + 0.020) / 3 = 0.02 / 3   = 0.006666...
        mae  = (0.005 + 0.005 + 0.020) / 3 = 0.03 / 3   = 0.01
        rmse = sqrt((25e-6 + 25e-6 + 400e-6) / 3)       = sqrt(150e-6)
        mape = (0.25 + 0.25 + 1.00) / 3                 = 0.5
        hit_rate at 10% tolerance = 0 of 3              = 0.0
        hit_rate at 30% tolerance = 2 of 3              = 0.666...
    """
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),      # -> 2024-Q2
        (date(2024, 3, 31), 2, 0.0150),      # -> 2024-Q3
        (date(2024, 3, 31), 3, 0.0400),      # -> 2024-Q4
        (date(2024, 6, 30), 0, 0.0200),      # actual 2024-Q2
        (date(2024, 9, 30), 0, 0.0200),      # actual 2024-Q3
        (date(2024, 12, 31), 0, 0.0200),     # actual 2024-Q4
    ])
    records = errors.build_error_records(aggregated)
    assert len(records) == 3

    summary = errors.summarize_errors(records)
    assert summary["count"] == 3
    assert summary["bias"] == pytest.approx(0.02 / 3)
    assert summary["mae"] == pytest.approx(0.01)
    assert summary["rmse"] == pytest.approx(math.sqrt(450e-6 / 3))
    assert summary["mape"] == pytest.approx(0.5)
    assert summary["mape_count"] == 3
    assert summary["hit_rate"] == pytest.approx(0.0)

    lenient = errors.summarize_errors(records, tolerance=0.30)
    assert lenient["hit_rate"] == pytest.approx(2 / 3)


def test_rmse_exceeds_mae_when_one_miss_dominates():
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),
        (date(2024, 3, 31), 2, 0.0150),
        (date(2024, 3, 31), 3, 0.0400),
        (date(2024, 6, 30), 0, 0.0200),
        (date(2024, 9, 30), 0, 0.0200),
        (date(2024, 12, 31), 0, 0.0200),
    ])
    summary = errors.summarize_errors(errors.build_error_records(aggregated))
    assert summary["rmse"] > summary["mae"]


# ---------------------------------------------------------------------------
# How actuals are found
# ---------------------------------------------------------------------------


def test_actual_comes_from_the_anchor_of_the_matching_vintage():
    aggregated = _aggregated([
        (date(2024, 3, 31), 0, 0.0100),
        (date(2024, 6, 30), 0, 0.0200),
        (date(2024, 9, 30), 0, 0.0300),
    ])
    lookup = errors.build_actual_lookup(aggregated)
    prefix = ("Cyclical", "PD_model_a", "CCAR 2025", "Base", "N")
    assert lookup[prefix + ("2024-Q1",)] == pytest.approx(0.0100)
    assert lookup[prefix + ("2024-Q2",)] == pytest.approx(0.0200)
    assert lookup[prefix + ("2024-Q3",)] == pytest.approx(0.0300)


def test_anchor_rows_are_never_scored_against_themselves():
    # An anchor compared to itself would be a guaranteed zero error, flattering
    # every summary statistic.
    aggregated = _aggregated([(date(2024, 3, 31), 0, 0.0200)])
    assert errors.build_error_records(aggregated) == []


def test_forecasts_without_an_actual_are_omitted_and_counted():
    """The most recent horizons genuinely have no actual yet -- they must not be
    scored as zero error, and the count must be visible to the caller."""
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),      # -> 2024-Q2, has an actual
        (date(2024, 3, 31), 4, 0.0300),      # -> 2025-Q1, no anchor exists
        (date(2024, 6, 30), 0, 0.0200),
    ])
    records = errors.build_error_records(aggregated)
    assert [record["target_quarter"] for record in records] == ["2024-Q2"]
    assert errors.unmatched_forecast_count(aggregated) == 1


def test_actuals_are_keyed_by_the_comparable_model_partition():
    """Distinct model partitions must not overwrite one another's anchors."""
    model_a = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),
        (date(2024, 6, 30), 0, 0.0200),
    ], model="PD_model_a")
    model_b = _aggregated([
        (date(2024, 3, 31), 1, 0.4500),
        (date(2024, 6, 30), 0, 0.4000),
    ], model="PD_model_b")
    combined = pd.concat([model_a, model_b], ignore_index=True)

    records = errors.build_error_records(combined)
    assert len(records) == 2
    actual_by_model = {record[MODEL]: record["actual"] for record in records}
    assert actual_by_model == pytest.approx({"PD_model_a": 0.0200, "PD_model_b": 0.4000})


@pytest.mark.parametrize(
    ("metric", "partition_column"),
    [
        (config.BACKTESTING_METRIC_LGD, MODEL),
        (config.BACKTESTING_METRIC_EAD, MODEL),
        (config.BACKTESTING_METRIC_NCO, config.BACKTESTING_PD_MODEL_NAME_COLUMN),
    ],
)
def test_comparable_population_actuals_resolve_for_partitioned_metrics(
    metric, partition_column
):
    """LGD, EAD and NCO retain model partitions with different actuals."""
    rows = []
    for suffix, forecast, actual in (("a", 12.0, 10.0), ("b", 110.0, 100.0)):
        identity = {
            SEGMENT: "Cyclical",
            SNAPSHOT: pd.Timestamp(date(2024, 3, 31)),
            RUN_FOR: "CCAR 2025",
            SCENARIO: "Base",
            JN: "N",
        }
        if metric == config.BACKTESTING_METRIC_NCO:
            identity.update({
                config.BACKTESTING_PD_MODEL_NAME_COLUMN: f"PD_model_{suffix}",
                config.BACKTESTING_LGD_MODEL_NAME_COLUMN: f"LGD_model_{suffix}",
                config.BACKTESTING_EAD_MODEL_NAME_COLUMN: f"EAD_model_{suffix}",
                config.BACKTESTING_LOSS_METHOD_COLUMN: "Expected Loss",
            })
        else:
            identity[MODEL] = f"{metric.upper()}_model_{suffix}"
        rows.append({**identity, QUARTER: 1, "value": forecast, "exposure": 1.0})
        rows.append({
            **identity,
            SNAPSHOT: pd.Timestamp(date(2024, 6, 30)),
            QUARTER: 0,
            "value": actual,
            "exposure": 1.0,
        })

    frame = aggregation._attach_quarter_columns(
        pd.DataFrame(rows), list(config.backtesting_run_key_columns(metric))
    )
    records = errors.build_error_records(frame)

    assert len(records) == 2
    actual_by_partition = {record[partition_column]: record["actual"] for record in records}
    if metric == config.BACKTESTING_METRIC_NCO:
        expected = {"PD_model_a": 10.0, "PD_model_b": 100.0}
    else:
        expected = {
            f"{metric.upper()}_model_a": 10.0,
            f"{metric.upper()}_model_b": 100.0,
        }
    assert actual_by_partition == pytest.approx(expected)


def test_conflicting_actuals_for_an_incomplete_key_fail_loudly():
    model_a = _aggregated([(date(2024, 6, 30), 0, 0.0200)], model="PD_model_a")
    model_b = _aggregated([(date(2024, 6, 30), 0, 0.4000)], model="PD_model_b")

    with pytest.raises(ValueError, match="conflicting realised anchors"):
        errors.build_actual_lookup(
            pd.concat([model_a, model_b], ignore_index=True), key_columns=[SEGMENT]
        )


def test_scoring_is_invariant_to_input_row_order():
    combined = pd.concat([
        _aggregated([
            (date(2024, 3, 31), 1, 0.0250),
            (date(2024, 6, 30), 0, 0.0200),
        ], model="PD_model_a", jn="N"),
        _aggregated([
            (date(2024, 3, 31), 1, 0.4500),
            (date(2024, 6, 30), 0, 0.4000),
        ], model="PD_model_b", jn="J"),
    ], ignore_index=True)

    expected = errors.build_error_records(combined)
    shuffled = combined.sample(frac=1.0, random_state=8675309).reset_index(drop=True)
    assert errors.build_error_records(shuffled) == expected


def test_segments_do_not_borrow_each_others_actuals():
    aggregated = pd.concat([
        _aggregated([(date(2024, 3, 31), 1, 0.0250)], segment="Cyclical"),
        _aggregated([(date(2024, 6, 30), 0, 0.0200)], segment="Defensive"),
    ], ignore_index=True)
    # The only anchor belongs to a different segment, so nothing is scorable.
    assert errors.build_error_records(aggregated) == []


def test_zero_actual_yields_no_percentage_error_but_keeps_signed_error():
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),
        (date(2024, 6, 30), 0, 0.0),
    ])
    record = errors.build_error_records(aggregated)[0]
    assert record["error"] == pytest.approx(0.0250)
    assert record["percentage_error"] is None

    summary = errors.summarize_errors([record])
    # bias/mae still measurable; mape has no denominator.
    assert summary["bias"] == pytest.approx(0.0250)
    assert summary["mape"] is None
    assert summary["mape_count"] == 0
    assert summary["hit_rate"] is None


# ---------------------------------------------------------------------------
# Scenario scoping
# ---------------------------------------------------------------------------


def test_only_the_base_scenario_is_scored_by_default():
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),
        (date(2024, 6, 30), 0, 0.0200),
    ])
    severe = aggregated.copy()
    severe[SCENARIO] = "Severe"
    severe.loc[severe[QUARTER] == 1, "value"] = 0.0900
    combined = pd.concat([aggregated, severe], ignore_index=True)

    records = errors.build_error_records(combined)
    assert len(records) == 1
    assert records[0]["forecast"] == pytest.approx(0.0250)

    assert errors.build_error_records(severe) == []


# ---------------------------------------------------------------------------
# Summary statistics at arbitrary grouping levels
# ---------------------------------------------------------------------------


def test_summarize_by_horizon_produces_an_error_curve():
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0210),      # -> 2024-Q2, small miss
        (date(2024, 3, 31), 2, 0.0400),      # -> 2024-Q3, large miss
        (date(2024, 6, 30), 0, 0.0200),
        (date(2024, 9, 30), 0, 0.0200),
    ])
    curve = errors.summarize_by(errors.build_error_records(aggregated), ["horizon"])
    assert [row["horizon"] for row in curve] == [1, 2]
    assert curve[0]["mae"] < curve[1]["mae"]


def test_summarize_by_accepts_multiple_keys():
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),
        (date(2024, 6, 30), 0, 0.0200),
    ])
    judgemental = aggregated.copy()
    judgemental[JN] = "J"
    judgemental.loc[judgemental[QUARTER] == 1, "value"] = 0.0205
    combined = pd.concat([aggregated, judgemental], ignore_index=True)

    summaries = errors.summarize_by(errors.build_error_records(combined), [JN, "horizon"])
    assert [(row[JN], row["horizon"]) for row in summaries] == [("J", 1), ("N", 1)]
    by_flag = {row[JN]: row["mae"] for row in summaries}
    assert by_flag["J"] < by_flag["N"]


def test_summarize_by_segment_ranks_populations():
    aggregated = pd.concat([
        _aggregated([(date(2024, 3, 31), 1, 0.0205), (date(2024, 6, 30), 0, 0.0200)], segment="Cyclical"),
        _aggregated([(date(2024, 3, 31), 1, 0.0500), (date(2024, 6, 30), 0, 0.0200)], segment="O&M"),
    ], ignore_index=True)
    summaries = errors.summarize_by(errors.build_error_records(aggregated), [SEGMENT])
    ranked = {row[SEGMENT]: row["mae"] for row in summaries}
    assert ranked["O&M"] > ranked["Cyclical"]


def test_summarize_empty_returns_none_not_zero():
    """None and 0.0 mean different things: "nothing measured" versus "measured,
    and it was perfect"."""
    summary = errors.summarize_errors([])
    assert summary["count"] == 0
    for key in ("bias", "mae", "rmse", "mape", "hit_rate"):
        assert summary[key] is None


# ---------------------------------------------------------------------------
# Chart-facing shape
# ---------------------------------------------------------------------------


def test_chart_rows_carry_a_quarter_key_the_shared_builders_read():
    """shared/ui/charts.py trend builders read row["quarter"] holding a YYYY-Qn
    label, so no adapter is needed at the chart milestone."""
    aggregated = _aggregated([
        (date(2024, 3, 31), 2, 0.0300),
        (date(2024, 3, 31), 1, 0.0250),
        (date(2024, 6, 30), 0, 0.0200),
        (date(2024, 9, 30), 0, 0.0200),
    ])
    rows = errors.error_records_to_chart_rows(errors.build_error_records(aggregated))

    assert [row["quarter"] for row in rows] == ["2024-Q2", "2024-Q3"]
    from STATpy_platform.shared.domain.quarter_labels import format_pd_compact_quarter_label
    assert format_pd_compact_quarter_label(rows[0]["quarter"]) == "2024Q2"


def test_chart_rows_can_plot_any_measure():
    aggregated = _aggregated([
        (date(2024, 3, 31), 1, 0.0250),
        (date(2024, 6, 30), 0, 0.0200),
    ])
    records = errors.build_error_records(aggregated)
    assert errors.error_records_to_chart_rows(records)[0]["value"] == pytest.approx(0.0050)
    percentage = errors.error_records_to_chart_rows(records, value_key="percentage_error")
    assert percentage[0]["value"] == pytest.approx(0.25)


def test_chart_rows_are_sorted_chronologically():
    aggregated = _aggregated([
        (date(2024, 3, 31), 3, 0.03),
        (date(2024, 3, 31), 1, 0.03),
        (date(2024, 3, 31), 2, 0.03),
        (date(2024, 6, 30), 0, 0.02),
        (date(2024, 9, 30), 0, 0.02),
        (date(2024, 12, 31), 0, 0.02),
    ])
    rows = errors.error_records_to_chart_rows(errors.build_error_records(aggregated))
    assert [row["quarter"] for row in rows] == ["2024-Q2", "2024-Q3", "2024-Q4"]
