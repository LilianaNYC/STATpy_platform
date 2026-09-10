"""Unit tests for the vintage / horizon / target-quarter mapping."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from STATpy_platform.features.backtesting.domain import vintages
from STATpy_platform.shared.domain.quarter_labels import iso_date_to_pd_quarter


def test_quarter_label_for_date_matches_shared_helper():
    # The label must be whatever the shared helper produces -- not a
    # reimplementation that happens to agree today.
    for value in (date(2023, 3, 31), date(2024, 12, 31), date(2025, 1, 1)):
        assert vintages.quarter_label_for_date(value) == iso_date_to_pd_quarter(value.isoformat())


def test_quarter_label_accepts_datetime_and_timestamp():
    assert vintages.quarter_label_for_date(date(2024, 6, 30)) == "2024-Q2"
    assert vintages.quarter_label_for_date(datetime(2024, 6, 30, 14, 30)) == "2024-Q2"
    assert vintages.quarter_label_for_date(pd.Timestamp("2024-06-30")) == "2024-Q2"


def test_quarter_label_for_unusable_values_is_empty():
    for value in (None, pd.NaT, "", "not-a-date", float("nan")):
        assert vintages.quarter_label_for_date(value) == ""


def test_anchor_quarter_maps_to_its_own_vintage_quarter():
    # Quarter 0 is the realised anchor: it describes the snapshot's own quarter.
    assert vintages.target_quarter_label(date(2024, 3, 31), 0) == "2024-Q1"


def test_horizon_shifts_target_quarter_forward():
    snapshot = date(2024, 3, 31)          # 2024-Q1
    expected = {
        1: "2024-Q2",
        2: "2024-Q3",
        3: "2024-Q4",
        4: "2025-Q1",                     # crosses the year boundary
        9: "2026-Q2",
    }
    for horizon, label in expected.items():
        assert vintages.target_quarter_label(snapshot, horizon) == label


def test_target_quarter_is_stable_across_snapshot_day_of_month():
    # Any day inside 2024-Q1 must land on the same target, so a workbook that
    # ever emits a non-month-end snapshot does not silently shift horizons.
    for day in (date(2024, 1, 1), date(2024, 2, 15), date(2024, 3, 31)):
        assert vintages.target_quarter_label(day, 2) == "2024-Q3"


def test_add_quarters_returns_month_end():
    assert vintages.add_quarters_to_date(date(2024, 3, 31), 1) == date(2024, 6, 30)
    assert vintages.add_quarters_to_date(date(2024, 3, 31), 3) == date(2024, 12, 31)
    assert vintages.add_quarters_to_date(date(2024, 12, 31), 1) == date(2025, 3, 31)


def test_add_quarters_handles_negative_offsets():
    assert vintages.add_quarters_to_date(date(2024, 3, 31), -1) == date(2023, 12, 31)
    assert vintages.add_quarters_to_date(date(2024, 3, 31), -5) == date(2022, 12, 31)


def test_horizon_from_labels_is_the_inverse_of_target_quarter_label():
    snapshot = date(2023, 9, 30)
    vintage_label = vintages.quarter_label_for_date(snapshot)
    for horizon in range(0, 10):
        target = vintages.target_quarter_label(snapshot, horizon)
        assert vintages.horizon_from_labels(vintage_label, target) == horizon


def test_horizon_from_labels_rejects_non_quarter_labels():
    assert vintages.horizon_from_labels("2024-Q1", "nonsense") is None
    assert vintages.horizon_from_labels("2024Q1", "2024-Q2") is None   # compact form
    assert vintages.horizon_from_labels("", "") is None


def test_is_anchor_quarter():
    assert vintages.is_anchor_quarter(0) is True
    assert vintages.is_anchor_quarter(1) is False
    assert vintages.is_anchor_quarter(None) is False


def test_sort_quarter_labels_orders_chronologically_and_dedupes():
    labels = ["2025-Q1", "2024-Q3", "2024-Q3", "2023-Q4", "2024-Q1"]
    assert vintages.sort_quarter_labels(labels) == [
        "2023-Q4", "2024-Q1", "2024-Q3", "2025-Q1",
    ]


def test_sort_quarter_labels_tolerates_a_malformed_label():
    # The shared comparator falls back to plain string comparison when a label is
    # not a quarter label, so a malformed entry is ordered somewhere rather than
    # raising. Its exact position is not a guarantee worth asserting -- only that
    # sorting survives it and the valid labels keep their relative order.
    ordered = vintages.sort_quarter_labels(["2025-Q1", "2024-Q13", "2023-Q4"])
    assert len(ordered) == 3
    assert ordered.index("2023-Q4") < ordered.index("2025-Q1")


def test_sort_quarter_labels_drops_blanks():
    assert vintages.sort_quarter_labels(["", "2024-Q1", None]) == ["2024-Q1"]


def test_compact_quarter_label_matches_chart_axis_expectation():
    # build_pd_time_series_xaxis renders YYYY-Qn ticks via this same formatter.
    assert vintages.compact_quarter_label("2024-Q2") == "2024Q2"


def test_build_vintage_index_orders_snapshots_in_time():
    snapshots = [date(2024, 6, 30), date(2023, 3, 31), date(2024, 12, 31)]
    assert vintages.build_vintage_index(snapshots) == {
        "2023-Q1": 0,
        "2024-Q2": 1,
        "2024-Q4": 2,
    }
