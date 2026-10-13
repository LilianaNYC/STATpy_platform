"""One ordering rule for every filter's option list.

Text values sort alphabetically, case-insensitively. Values that are dates,
quarters or numbers sort **descending** -- newest or largest first -- because in
those filters the most recent value is the one reached for nearly every time,
so it belongs at the top of the menu rather than the bottom.

Two things this module deliberately does *not* order:

* **Aggregate sentinels** -- "All", "Select model", "Select segment". They are
  not values, they are the absence of a choice, so callers keep them pinned at
  the head of the list instead of letting them sort into position.
* **Domain sequences that lay out figures and tables**, above all
  ``features.monitoring.domain.overview.MODEL_GROUPS`` (PD -> LGD -> EAD ->
  Loss, the loss-decomposition order). Those are not filter values, and
  alphabetizing them would scramble the reading order of every chart and table
  keyed on them.

Pure: no I/O, no Dash, no pandas.
"""

from __future__ import annotations

import re

# A year or plain number, with an optional quarter suffix: "2026", "2025Q1", "9".
_PERIOD = re.compile(r"^(\d+)(?:\s*Q(\d+))?$", re.IGNORECASE)

# What quarter a bare year counts as when sorting. A bare year stands for the
# whole year, so it sorts *after* that year's individual quarters: "CCAR 2025"
# reads as more recent than "CECL 2025Q1", which is how the hand-maintained
# cycle order this module replaced had it.
_WHOLE_YEAR = 5


def _text_key(value) -> tuple[str, str]:
    # Casefold first so "IVB" and "ivb" land together; the raw text is a stable
    # tie-break for values that differ only in case.
    text = str(value)
    return (text.casefold(), text)


def period_key(value) -> tuple[int, int] | None:
    """``(year, quarter)`` for a year/quarter/number, or ``None`` if it is text.

    Parsed rather than compared as text, so "10" sorts above "9" instead of
    below it.
    """
    match = _PERIOD.match(str(value).strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2) or _WHOLE_YEAR))


def alphabetical(values, *, key=None) -> list:
    """A-Z, case-insensitive. ``key`` picks the text out of a richer value."""
    pick = key or (lambda value: value)
    return sorted(values, key=lambda value: _text_key(pick(value)))


def newest_first(values, *, key=None) -> list:
    """Dates, quarters and numbers, largest first.

    Anything that does not parse as a period keeps its place *after* everything
    that does, ordered alphabetically -- a stray label never silently jumps to
    the head of the menu. Stable, so pre-sorting the input supplies the
    tie-break between values sharing a period.
    """
    pick = key or (lambda value: value)
    periods, others = [], []
    for value in values:
        (periods if period_key(pick(value)) is not None else others).append(value)
    periods.sort(key=lambda value: period_key(pick(value)), reverse=True)
    return periods + alphabetical(others, key=pick)


def composite_cycles_newest_first(cycles) -> list:
    """Composite cycle values ("CCAR 2026", "CECL 2025Q1"), most recent first.

    Ordered on the **cycle part** after the family name, never on the composite
    as a whole: compared as text, "CECL 2025Q1" would outrank "CCAR 2026". The
    plain sort first is the tie-break, so two families sharing a cycle land in
    family order.
    """
    return newest_first(sorted(cycles), key=lambda cycle: str(cycle).split(" ", 1)[-1])


__all__ = ["alphabetical", "composite_cycles_newest_first", "newest_first", "period_key"]
