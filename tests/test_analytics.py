"""Selector/analytics unit tests.

Pure functions over plain data are the highest-value place to test business
logic. These cover the shared range-selection helpers used by both dashboards.
"""

from __future__ import annotations

from STATpy_platform.shared.domain.calculations import (
    filter_pd_periods_by_range,
    get_pd_range_periods,
    get_pd_range_selection,
)
from STATpy_platform.shared.text import normalize_model_name, ordered_unique_strings

PERIODS = ["2022Q1", "2022Q2", "2022Q3", "2022Q4"]


def test_get_pd_range_periods_filters_and_sorts():
    assert get_pd_range_periods(["2022Q3", "2022Q1", "2022Q2"], "2022Q2") == ["2022Q1", "2022Q2"]


def test_get_pd_range_selection_drops_out_of_range_bounds():
    selection = get_pd_range_selection({"from": "2022Q2", "to": "9999Q9"}, PERIODS)
    assert selection == {"from": "2022Q2", "to": ""}


def test_filter_pd_periods_by_range_inclusive():
    assert filter_pd_periods_by_range({"from": "2022Q2", "to": "2022Q3"}, PERIODS) == ["2022Q2", "2022Q3"]


def test_filter_pd_periods_by_range_empty_returns_all():
    assert filter_pd_periods_by_range({}, PERIODS) == PERIODS


def test_normalize_model_name_trims_and_handles_missing():
    assert normalize_model_name("  Model A ") == "Model A"
    assert normalize_model_name(None) == ""


def test_ordered_unique_strings_preserves_first_seen_order():
    assert ordered_unique_strings(["b", "a", "b", "", None, "a", "c"]) == ["b", "a", "c"]
