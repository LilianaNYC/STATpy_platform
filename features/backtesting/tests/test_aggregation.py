"""Unit tests for facility-row aggregation, including a hand-computed case."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from STATpy_platform.features.backtesting.domain import aggregation
from STATpy_platform.shared.domain import constants as config

SEGMENT = config.BACKTESTING_SEGMENT_COLUMN
MODEL = config.BACKTESTING_MODEL_NAME_COLUMN
SNAPSHOT = config.BACKTESTING_SNAPSHOT_COLUMN
RUN_FOR = config.BACKTESTING_RUN_FOR_COLUMN
SCENARIO = config.BACKTESTING_SCENARIO_COLUMN
JN = config.BACKTESTING_JN_FLAG_COLUMN
FACILITY = config.BACKTESTING_FACILITY_ID_COLUMN
INSTRUMENT = config.BACKTESTING_CREDIT_INSTRUMENT_ID_COLUMN
QUARTER = config.BACKTESTING_QUARTER_COLUMN
PD_VALUE = config.BACKTESTING_PD_VALUE_COLUMN
EAD_VALUE = config.BACKTESTING_EAD_VALUE_COLUMN


def _pd_rows(rows, *, model="PD_model_a", scenario="Base", jn="N", snapshot=date(2024, 3, 31)):
    """Facility-grain PD rows sharing one run key."""
    return pd.DataFrame([
        {
            SEGMENT: "Cyclical",
            MODEL: model,
            SNAPSHOT: pd.Timestamp(snapshot),
            RUN_FOR: "CCAR 2025",
            SCENARIO: scenario,
            JN: jn,
            FACILITY: facility,
            INSTRUMENT: f"{facility}-1",
            QUARTER: quarter,
            PD_VALUE: value,
        }
        for facility, quarter, value in rows
    ])


def _ead_rows(rows, *, scenario="Base", jn="N", snapshot=date(2024, 3, 31)):
    """Matching EAD rows. Note the EAD model differs from the PD model -- that is
    exactly why the exposure join must exclude Model Name."""
    return pd.DataFrame([
        {
            SEGMENT: "Cyclical",
            MODEL: "EAD_model_b",
            SNAPSHOT: pd.Timestamp(snapshot),
            RUN_FOR: "CCAR 2025",
            SCENARIO: scenario,
            JN: jn,
            FACILITY: facility,
            INSTRUMENT: f"{facility}-1",
            QUARTER: quarter,
            EAD_VALUE: value,
        }
        for facility, quarter, value in rows
    ])


# ---------------------------------------------------------------------------
# The hand-computed exposure-weighted case
# ---------------------------------------------------------------------------


def test_exposure_weighted_pd_matches_hand_computed_value():
    """Three facilities, deliberately skewed exposure.

        facility   PD      EAD          EAD x PD
        F-1        0.01     100,000        1,000
        F-2        0.02     400,000        8,000
        F-3        0.50      10,000        5,000
                            -------       ------
                            510,000       14,000

        weighted PD = 14,000 / 510,000 = 0.027450980392156862
        simple mean = (0.01 + 0.02 + 0.50) / 3 = 0.17666...

    The simple mean is ~6.4x the weighted figure because the riskiest facility is
    also the smallest. That gap is the whole reason for weighting.
    """
    pd_frame = _pd_rows([("F-1", 1, 0.01), ("F-2", 1, 0.02), ("F-3", 1, 0.50)])
    ead_frame = _ead_rows([("F-1", 1, 100_000.0), ("F-2", 1, 400_000.0), ("F-3", 1, 10_000.0)])

    aggregated, coverage = aggregation.aggregate_metric(
        pd_frame, config.BACKTESTING_METRIC_PD, ead_frame=ead_frame
    )

    assert len(aggregated) == 1
    row = aggregated.iloc[0]
    assert row["value"] == pytest.approx(14_000.0 / 510_000.0)
    assert row["value"] == pytest.approx(0.027450980392156862)
    assert row["value"] != pytest.approx(0.17666666666666667)   # not the simple mean
    assert row["exposure"] == pytest.approx(510_000.0)
    assert row["facility_count"] == 3
    assert coverage["matched_rows"] == 3
    assert coverage["unmatched_rows"] == 0
    assert coverage["row_coverage"] == pytest.approx(1.0)
    assert coverage["matched_exposure"] == pytest.approx(510_000.0)
    assert coverage["total_available_exposure"] == pytest.approx(510_000.0)
    assert coverage["exposure_coverage"] == pytest.approx(1.0)


def test_weighted_mean_reproduces_total_expected_defaulted_exposure():
    """The property that motivates exposure weighting: weighted PD x total EAD
    must equal the sum of facility-level EAD x PD. A simple mean does not."""
    pd_frame = _pd_rows([("F-1", 1, 0.01), ("F-2", 1, 0.02), ("F-3", 1, 0.50)])
    ead_frame = _ead_rows([("F-1", 1, 100_000.0), ("F-2", 1, 400_000.0), ("F-3", 1, 10_000.0)])

    aggregated, _ = aggregation.aggregate_metric(
        pd_frame, config.BACKTESTING_METRIC_PD, ead_frame=ead_frame
    )
    row = aggregated.iloc[0]
    assert row["value"] * row["exposure"] == pytest.approx(14_000.0)


def test_lgd_is_exposure_weighted_too():
    lgd_column = config.BACKTESTING_LGD_VALUE_COLUMN
    lgd_frame = _pd_rows([("F-1", 1, 0.0), ("F-2", 1, 0.0)]).rename(columns={PD_VALUE: lgd_column})
    lgd_frame[lgd_column] = [0.20, 0.60]
    lgd_frame[MODEL] = "LGD_model_a"
    ead_frame = _ead_rows([("F-1", 1, 300_000.0), ("F-2", 1, 100_000.0)])

    aggregated, _ = aggregation.aggregate_metric(
        lgd_frame, config.BACKTESTING_METRIC_LGD, ead_frame=ead_frame
    )
    # (0.20*300k + 0.60*100k) / 400k = 120k / 400k = 0.30
    assert aggregated.iloc[0]["value"] == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# Additive metrics
# ---------------------------------------------------------------------------


def test_amount_metrics_are_summed_not_weighted():
    ead_frame = _ead_rows([("F-1", 1, 100_000.0), ("F-2", 1, 400_000.0), ("F-3", 1, 10_000.0)])
    aggregated, coverage = aggregation.aggregate_metric(ead_frame, config.BACKTESTING_METRIC_EAD)
    row = aggregated.iloc[0]
    assert row["value"] == pytest.approx(510_000.0)
    assert row["exposure"] == pytest.approx(510_000.0)
    # No join happens for an additive metric, so coverage is trivially complete.
    assert coverage["row_coverage"] == pytest.approx(1.0)


def test_additive_metric_needs_no_ead_frame():
    ead_frame = _ead_rows([("F-1", 1, 5_000.0)])
    aggregated, _ = aggregation.aggregate_metric(ead_frame, config.BACKTESTING_METRIC_EAD)
    assert aggregated.iloc[0]["value"] == pytest.approx(5_000.0)


def test_weighted_metric_without_ead_frame_raises():
    pd_frame = _pd_rows([("F-1", 1, 0.01)])
    with pytest.raises(ValueError, match="exposure-weighted"):
        aggregation.aggregate_metric(pd_frame, config.BACKTESTING_METRIC_PD)


def test_is_exposure_weighted_classification():
    assert aggregation.is_exposure_weighted(config.BACKTESTING_METRIC_PD)
    assert aggregation.is_exposure_weighted(config.BACKTESTING_METRIC_PD_CRR)
    assert aggregation.is_exposure_weighted(config.BACKTESTING_METRIC_LGD)
    assert not aggregation.is_exposure_weighted(config.BACKTESTING_METRIC_EAD)
    assert not aggregation.is_exposure_weighted(config.BACKTESTING_METRIC_NCO)


# ---------------------------------------------------------------------------
# The exposure join
# ---------------------------------------------------------------------------


def test_exposure_join_ignores_model_name():
    """The PD model and EAD model differ, so a join including Model Name would
    match nothing. This is the single most load-bearing property of the join."""
    pd_frame = _pd_rows([("F-1", 1, 0.05)])
    ead_frame = _ead_rows([("F-1", 1, 200_000.0)])
    assert pd_frame.iloc[0][MODEL] != ead_frame.iloc[0][MODEL]

    weighted, coverage = aggregation.attach_exposure_weights(pd_frame, ead_frame)
    assert coverage["matched_rows"] == 1
    assert weighted.iloc[0][aggregation.EXPOSURE_WEIGHT_COLUMN] == pytest.approx(200_000.0)


def test_unmatched_rows_are_dropped_and_reported_not_equal_weighted():
    pd_frame = _pd_rows([("F-1", 1, 0.01), ("F-2", 1, 0.99)])
    ead_frame = _ead_rows([("F-1", 1, 100_000.0)])          # F-2 has no exposure row

    aggregated, coverage = aggregation.aggregate_metric(
        pd_frame, config.BACKTESTING_METRIC_PD, ead_frame=ead_frame
    )
    assert coverage["total_rows"] == 2
    assert coverage["matched_rows"] == 1
    assert coverage["unmatched_rows"] == 1
    assert coverage["row_coverage"] == pytest.approx(0.5)
    # F-2 is dropped rather than given an implicit weight, so the aggregate is
    # F-1's PD exactly -- not a blend of a weighted and an unweighted row.
    assert aggregated.iloc[0]["value"] == pytest.approx(0.01)
    assert aggregated.iloc[0]["facility_count"] == 1


def test_non_positive_weights_are_excluded():
    pd_frame = _pd_rows([("F-1", 1, 0.01), ("F-2", 1, 0.90), ("F-3", 1, 0.90)])
    ead_frame = _ead_rows([("F-1", 1, 50_000.0), ("F-2", 1, 0.0), ("F-3", 1, -10.0)])

    aggregated, coverage = aggregation.aggregate_metric(
        pd_frame, config.BACKTESTING_METRIC_PD, ead_frame=ead_frame
    )
    assert coverage["matched_rows"] == 1
    assert coverage["unmatched_rows"] == 2
    assert aggregated.iloc[0]["value"] == pytest.approx(0.01)


def test_duplicated_exposure_rows_raise_before_the_join_can_fan_out():
    """A duplicated EAD row silently multiplies a weighted aggregate, so the
    domain rejects it instead of returning multiplied rows."""
    pd_frame = _pd_rows([("F-1", 1, 0.01)])
    ead_frame = pd.concat([_ead_rows([("F-1", 1, 100_000.0)])] * 2, ignore_index=True)

    with pytest.raises(aggregation.ExposureFanOutError, match="would fan out"):
        aggregation.aggregate_metric(
            pd_frame,
            config.BACKTESTING_METRIC_PD,
            ead_frame=ead_frame,
        )


def test_row_and_exposure_coverage_are_distinct_measures():
    """One of two forecast rows matches, but it represents only one quarter of
    the EAD available in the same applied scope."""
    pd_frame = _pd_rows([("F-1", 1, 0.01), ("F-2", 1, 0.99)])
    ead_frame = _ead_rows([
        ("F-1", 1, 100_000.0),
        ("F-3", 1, 300_000.0),
    ])

    _, coverage = aggregation.attach_exposure_weights(pd_frame, ead_frame)

    assert coverage["row_coverage"] == pytest.approx(0.5)
    assert coverage["matched_exposure"] == pytest.approx(100_000.0)
    assert coverage["total_available_exposure"] == pytest.approx(400_000.0)
    assert coverage["exposure_coverage"] == pytest.approx(0.25)


def test_empty_inputs_yield_empty_aggregate_not_an_error():
    empty = _pd_rows([]).iloc[0:0]
    aggregated, coverage = aggregation.aggregate_metric(
        empty, config.BACKTESTING_METRIC_PD, ead_frame=_ead_rows([])
    )
    assert aggregated.empty
    assert coverage["matched_rows"] == 0


# ---------------------------------------------------------------------------
# Grouping and the chart-ready quarter columns
# ---------------------------------------------------------------------------


def test_rows_are_grouped_per_run_key_and_quarter():
    pd_frame = pd.concat([
        _pd_rows([("F-1", 1, 0.01), ("F-2", 1, 0.03)], jn="N"),
        _pd_rows([("F-1", 2, 0.02), ("F-2", 2, 0.04)], jn="N"),
        _pd_rows([("F-1", 1, 0.05), ("F-2", 1, 0.05)], jn="J"),
    ], ignore_index=True)
    ead_frame = pd.concat([
        _ead_rows([("F-1", 1, 100_000.0), ("F-2", 1, 100_000.0)], jn="N"),
        _ead_rows([("F-1", 2, 100_000.0), ("F-2", 2, 100_000.0)], jn="N"),
        _ead_rows([("F-1", 1, 100_000.0), ("F-2", 1, 100_000.0)], jn="J"),
    ], ignore_index=True)

    aggregated, _ = aggregation.aggregate_metric(
        pd_frame, config.BACKTESTING_METRIC_PD, ead_frame=ead_frame
    )
    # Two J/N flags x the quarters each covers = 3 groups.
    assert len(aggregated) == 3
    assert set(aggregated[JN]) == {"J", "N"}


def test_custom_group_columns_collapse_across_models():
    """Dropping Model Name from the grouping is how a segment-level number is
    taken across both (disjoint) PD populations."""
    frame = pd.concat([
        _pd_rows([("F-1", 1, 0.02)], model="PD_model_a"),
        _pd_rows([("F-9", 1, 0.06)], model="PD_model_b"),
    ], ignore_index=True)
    ead_frame = _ead_rows([("F-1", 1, 100_000.0), ("F-9", 1, 100_000.0)])

    aggregated, _ = aggregation.aggregate_metric(
        frame,
        config.BACKTESTING_METRIC_PD,
        ead_frame=ead_frame,
        group_columns=[SEGMENT, SNAPSHOT, RUN_FOR, SCENARIO, JN],
    )
    assert len(aggregated) == 1
    assert aggregated.iloc[0]["value"] == pytest.approx(0.04)
    assert aggregated.iloc[0]["facility_count"] == 2


def test_aggregate_attaches_chart_ready_quarter_columns():
    pd_frame = _pd_rows([("F-1", 0, 0.02), ("F-1", 1, 0.03)], snapshot=date(2024, 3, 31))
    ead_frame = _ead_rows([("F-1", 0, 100_000.0), ("F-1", 1, 100_000.0)], snapshot=date(2024, 3, 31))

    aggregated, _ = aggregation.aggregate_metric(
        pd_frame, config.BACKTESTING_METRIC_PD, ead_frame=ead_frame
    )
    by_quarter = {int(row[QUARTER]): row for _, row in aggregated.iterrows()}

    assert by_quarter[0][aggregation.VINTAGE_QUARTER_COLUMN] == "2024-Q1"
    assert by_quarter[0][aggregation.TARGET_QUARTER_COLUMN] == "2024-Q1"   # anchor
    assert by_quarter[0][aggregation.HORIZON_COLUMN] == 0
    assert by_quarter[1][aggregation.TARGET_QUARTER_COLUMN] == "2024-Q2"
    assert by_quarter[1][aggregation.HORIZON_COLUMN] == 1
