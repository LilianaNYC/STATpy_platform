"""Vintage / horizon / target-quarter mapping for the backtesting engine.

A backtesting row is identified by two time coordinates that must not be
confused:

* **Vintage** -- the ``Month End Snapshot``: *when the forecast was made*.
* **Horizon** -- the ``Quarter``: *how far ahead it looks*, in quarters.

The **target quarter** is what the row is a statement about, and it is what
lets forecasts from different vintages be compared::

    target = vintage_quarter + horizon

``Quarter == 0`` is the realised anchor (the observed value at the snapshot
date), so its target quarter is the vintage's own quarter. That is the pivot the
whole backtest turns on: for any target quarter *T*, the actual is the anchor row
of the vintage whose quarter *is* *T*, and every earlier vintage's row with
``vintage + horizon == T`` is a forecast of it.

Quarter *labels* are always produced through
:mod:`shared.domain.quarter_labels` (``YYYY-Qn``), never parsed by hand here, so
they sort and render identically to every other dashboard's labels and can be
passed straight to ``shared.ui.charts.build_pd_time_series_xaxis``. This module
adds only the *arithmetic* the shared module does not provide -- and it does that
on dates, before conversion, rather than by picking labels apart.
"""

from __future__ import annotations

from datetime import date, datetime

from ....shared.domain import constants as config
from ....shared.domain.quarter_labels import (
    compare_pd_quarter_labels,
    format_pd_compact_quarter_label,
    iso_date_to_pd_quarter,
    # Private, imported deliberately: these are the shared module's own
    # definitions of "what a quarter label is" and "how quarter labels order".
    # Re-deriving either here would create a second, drifting definition of the
    # label format. ``shared/ui/charts.py`` imports ``_pd_quarter_sort_key`` the
    # same way.
    _QUARTER_LABEL_RE,
    _pd_quarter_sort_key,
)

__all__ = [
    "quarter_label_for_date",
    "add_quarters_to_date",
    "target_quarter_label",
    "horizon_from_labels",
    "is_anchor_quarter",
    "sort_quarter_labels",
    "quarter_sort_key",
    "compact_quarter_label",
    "build_vintage_index",
]


def _as_date(value) -> date | None:
    """Coerce a snapshot value to a plain ``date``.

    Accepts ``date``, ``datetime`` and ``pandas.Timestamp`` (a ``datetime``
    subclass), plus ISO-ish strings. Returns ``None`` for anything unusable so
    callers can skip the row rather than raise mid-aggregation.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # pandas NaT and floats-as-NaN both fail the isoformat path below.
    text = str(value).strip()
    if not text or text.lower() in {"nat", "nan", "none"}:
        return None
    try:
        return datetime.fromisoformat(text[:19]).date()
    except ValueError:
        return None


def quarter_label_for_date(value) -> str:
    """``YYYY-Qn`` label for a snapshot date, via the shared helper.

    The shared :func:`iso_date_to_pd_quarter` takes an ISO ``YYYY-MM-DD``
    string, so the only work here is coercing whatever the loader produced into
    that form.
    """
    coerced = _as_date(value)
    if coerced is None:
        return ""
    return iso_date_to_pd_quarter(coerced.isoformat())


def add_quarters_to_date(value, quarters: int) -> date | None:
    """The month-end date ``quarters`` quarters after ``value``.

    Arithmetic happens on the date, not on the label, so no quarter-label
    parsing is duplicated. Returns a month-end so the result converts to the
    intended quarter regardless of the input day-of-month.
    """
    start = _as_date(value)
    if start is None:
        return None

    month_index = start.year * 12 + (start.month - 1) + 3 * int(quarters)
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    if month == 12:
        return date(year, 12, 31)
    first_of_next = date(year + (month // 12), (month % 12) + 1, 1)
    return date.fromordinal(first_of_next.toordinal() - 1)


def target_quarter_label(snapshot, quarter: int | None) -> str:
    """The ``YYYY-Qn`` quarter a row is a statement *about*.

    ``quarter`` is the horizon, so the anchor (``0``) maps to the vintage's own
    quarter and horizon *n* maps *n* quarters later.
    """
    if quarter is None:
        return ""
    shifted = add_quarters_to_date(snapshot, int(quarter))
    if shifted is None:
        return ""
    return iso_date_to_pd_quarter(shifted.isoformat())


def horizon_from_labels(vintage_label: str, target_label: str) -> int | None:
    """Horizon in quarters between two ``YYYY-Qn`` labels.

    The inverse of :func:`target_quarter_label`, used when a caller holds labels
    rather than dates. Returns ``None`` if either label is not a quarter label.
    """
    vintage = _label_to_index(vintage_label)
    target = _label_to_index(target_label)
    if vintage is None or target is None:
        return None
    return target - vintage


def _label_to_index(label: str) -> int | None:
    """Absolute quarter index for a ``YYYY-Qn`` label, or ``None`` if invalid.

    Validity is the shared module's own regex, so this function accepts exactly
    the labels the rest of the platform considers quarter labels.
    """
    match = _QUARTER_LABEL_RE.match((label or "").strip())
    if not match:
        return None
    return int(match.group(1)) * 4 + (int(match.group(2)) - 1)


def is_anchor_quarter(quarter: int | None) -> bool:
    """Whether ``quarter`` is the realised anchor rather than a projection."""
    return quarter is not None and int(quarter) == config.BACKTESTING_ANCHOR_QUARTER


def sort_quarter_labels(labels) -> list[str]:
    """Chronologically sorted, de-duplicated ``YYYY-Qn`` labels.

    Ordering uses the shared comparator so it matches every other dashboard's
    quarter ordering exactly.
    """
    unique = [label for label in dict.fromkeys(labels) if label]
    return sorted(unique, key=_pd_quarter_sort_key)


def compact_quarter_label(label: str) -> str:
    """``YYYY-Qn`` -> ``YYYYQn``, via the shared formatter."""
    return format_pd_compact_quarter_label(label)


def build_vintage_index(snapshots) -> dict[str, int]:
    """Map each vintage's ``YYYY-Qn`` label to its position in time.

    Useful for "the Nth vintage" style grouping and for identifying the latest
    vintage without re-sorting dates at every call site.
    """
    labels = sort_quarter_labels(quarter_label_for_date(value) for value in snapshots)
    return {label: position for position, label in enumerate(labels)}


# Public aliases for the shared comparator and its sort key, so callers sort
# quarters through this module rather than reaching into a private name. Both are
# the shared implementations, not new ones.
compare_quarter_labels = compare_pd_quarter_labels
quarter_sort_key = _pd_quarter_sort_key
