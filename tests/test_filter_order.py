"""The one ordering rule every filter's option list follows.

Text A-Z; dates, quarters and numbers newest/largest first. These are the pure
unit tests for the rule itself -- ``test_filter_bar_ordering.py`` checks that
the rendered bars actually obey it.
"""

from __future__ import annotations

from STATpy_platform.shared.domain.filter_order import alphabetical, newest_first, period_key


def test_alphabetical_ignores_case():
    assert alphabetical(["beta", "Alpha", "gamma"]) == ["Alpha", "beta", "gamma"]


def test_alphabetical_is_stable_across_case_only_differences():
    """Two spellings of one name must not swap places run to run."""
    assert alphabetical(["IVB", "ivb", "IVB"]) == ["IVB", "IVB", "ivb"]


def test_alphabetical_can_read_through_a_key():
    options = [{"value": "b"}, {"value": "A"}]
    assert alphabetical(options, key=lambda o: o["value"]) == [{"value": "A"}, {"value": "b"}]


def test_numbers_sort_by_value_not_as_text():
    """The reason periods are parsed: as text "9" would outrank "10"."""
    assert newest_first(["9", "10", "2"]) == ["10", "9", "2"]


def test_quarters_and_years_read_most_recent_first():
    assert newest_first(["2024", "2026", "2025Q1", "2025"]) == ["2026", "2025", "2025Q1", "2024"]


def test_a_bare_year_stands_for_the_whole_year():
    """So "2025" outranks every quarter of 2025 -- an annual cycle is the
    year's final state, which is how the hand-maintained cycle order had it."""
    assert newest_first(["2025Q4", "2025"]) == ["2025", "2025Q4"]
    assert period_key("2025") > period_key("2025Q4")


def test_non_periods_fall_below_periods_rather_than_jumping_the_queue():
    assert newest_first(["TBC", "2026", "amber", "2024"]) == ["2026", "2024", "amber", "TBC"]


def test_period_key_rejects_text():
    assert period_key("C&I") is None
    assert period_key("") is None
    assert period_key("2026") == (2026, 5)
    assert period_key("2025Q1") == (2025, 1)


def test_newest_first_is_stable_so_callers_supply_their_own_tie_break():
    """``_sort_cycles`` relies on this: it pre-sorts by cycle family so two
    cycles sharing a period keep a deterministic order."""
    values = [("CECL", "2025"), ("CCAR", "2025")]
    pre_sorted = sorted(values)
    assert newest_first(pre_sorted, key=lambda v: v[1]) == [("CCAR", "2025"), ("CECL", "2025")]
