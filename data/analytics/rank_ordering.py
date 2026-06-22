"""Scenario Rank Ordering helpers for the PD Performance dashboard.

Ports the facility-level PD path aggregation helpers from
``pages/monitoring_pd_models_page.py`` (``buildPdRankOrderingAggregate``,
``buildPdRankOrderingPeriodLabelMap``, ``getPdRankOrderingSelectedFacilities``,
and the small ``YYYY-Qn`` quarter-label utilities used by both the rank
ordering and MEV range sections).

Note: rank-ordering / MEV periods use the ``YYYY-Qn`` label format (produced
by :func:`iso_date_to_pd_quarter` from ISO dates and used directly as keys in
``facilities_dummy_data.json`` / ``dummy_mev_data.xlsx``). This is a
*different* format from the portfolio quarter labels (``YYYYQn``) used
elsewhere in :mod:`calculations`.
"""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Any

from .calculations import PdFilterContext, _to_number

_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_QUARTER_LABEL_RE = re.compile(r"^(\d{4})-Q([1-4])$")
_FORECAST_STEP_RE = re.compile(r"^Q(\d+)$", re.IGNORECASE)

_MONTH_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


# ---------------------------------------------------------------------------
# Date / quarter-label helpers
# ---------------------------------------------------------------------------


def format_pd_short_date(value: str | None) -> str:
    """Port of ``formatPdShortDate``: ``YYYY-MM-DD`` -> ``Mon D, YYYY``."""
    if not value:
        return "—"
    match = _ISO_DATE_RE.match(value)
    if not match:
        return value
    year, month, day = match.groups()
    month_index = int(month) - 1
    if not (0 <= month_index <= 11):
        return value
    return f"{_MONTH_ABBR[month_index]} {int(day)}, {year}"


def format_pd_date_summary(dates: list[str | None]) -> str:
    """Port of ``formatPdDateSummary``."""
    unique_dates = list(dict.fromkeys(date for date in (dates or []) if date))
    if not unique_dates:
        return "—"
    if len(unique_dates) <= 2:
        return " / ".join(format_pd_short_date(date) for date in unique_dates)
    return f"{len(unique_dates)} dates"


def iso_date_to_pd_quarter(value: str | None) -> str:
    """Port of ``isoDateToPdQuarter``: ``YYYY-MM-DD`` -> ``YYYY-Qn``."""
    match = _ISO_DATE_RE.match(value or "")
    if not match:
        return ""
    year, month, _day = match.groups()
    quarter = (int(month) - 1) // 3 + 1
    return f"{year}-Q{quarter}"


def compare_pd_quarter_labels(left: str | None, right: str | None) -> int:
    """Port of ``comparePdQuarterLabels``."""
    left_match = _QUARTER_LABEL_RE.match(left or "")
    right_match = _QUARTER_LABEL_RE.match(right or "")
    if not left_match or not right_match:
        left_str = left or ""
        right_str = right or ""
        return -1 if left_str < right_str else (1 if left_str > right_str else 0)
    left_sort = int(left_match.group(1)) * 10 + int(left_match.group(2))
    right_sort = int(right_match.group(1)) * 10 + int(right_match.group(2))
    return left_sort - right_sort


_pd_quarter_sort_key = cmp_to_key(compare_pd_quarter_labels)


def add_pd_quarter_offset(quarter: str | None, offset: float | None) -> str:
    """Port of ``addPdQuarterOffset``."""
    match = _QUARTER_LABEL_RE.match(quarter or "")
    offset_number = _to_number(offset)
    if not match or offset_number is None:
        return ""
    quarter_index = int(match.group(1)) * 4 + (int(match.group(2)) - 1) + int(offset_number)
    next_year = quarter_index // 4
    next_quarter = (quarter_index % 4) + 1
    return f"{next_year}-Q{next_quarter}"


def format_pd_compact_quarter_label(period: str | None) -> str:
    """Port of ``formatPdCompactQuarterLabel``: ``YYYY-Qn`` -> ``YYYYQn``."""
    match = _QUARTER_LABEL_RE.match(period or "")
    return f"{match.group(1)}Q{match.group(2)}" if match else (period or "")


def get_pd_quarter_distance(start_quarter: str | None, end_quarter: str | None) -> int | None:
    """Port of ``getPdQuarterDistance``."""
    start_match = _QUARTER_LABEL_RE.match(start_quarter or "")
    end_match = _QUARTER_LABEL_RE.match(end_quarter or "")
    if not start_match or not end_match:
        return None
    start_index = int(start_match.group(1)) * 4 + (int(start_match.group(2)) - 1)
    end_index = int(end_match.group(1)) * 4 + (int(end_match.group(2)) - 1)
    return end_index - start_index


# ---------------------------------------------------------------------------
# Facility selection / aggregation
# ---------------------------------------------------------------------------


def get_pd_rank_ordering_selected_facilities(
    rank_ordering_facilities: dict[str, Any], ctx: PdFilterContext
) -> list[dict[str, Any]]:
    """Port of ``getPdRankOrderingSelectedFacilities``."""
    selected_models = set(ctx.models) if ctx.models else None
    facilities = []
    for facility_id, facility in (rank_ordering_facilities or {}).items():
        if selected_models is not None and facility.get("pd_model") not in selected_models:
            continue
        if ctx.segment != "all" and facility.get("segment") != ctx.segment:
            continue
        facilities.append({"facility_id": facility_id, **facility})
    return facilities


def get_pd_rank_ordering_forecast_offset(step_label: str | None) -> int | None:
    """Port of ``getPdRankOrderingForecastOffset``."""
    match = _FORECAST_STEP_RE.match(str(step_label or "").strip())
    return int(match.group(1)) if match else None


def accumulate_pd_rank_ordering_value(accumulator: dict[str, dict[str, float]], period: str | None, raw_value: Any) -> None:
    """Port of ``accumulatePdRankOrderingValue``."""
    value = _to_number(raw_value)
    if not period or value is None:
        return
    bucket = accumulator.setdefault(period, {"sum": 0.0, "count": 0})
    bucket["sum"] += value
    bucket["count"] += 1


def finalize_pd_rank_ordering_aggregate(accumulator: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """Port of ``finalizePdRankOrderingAggregate``."""
    points = [
        {"period": period, "value": bucket["sum"] / bucket["count"]}
        for period, bucket in accumulator.items()
        if bucket["count"] > 0
    ]
    points.sort(key=lambda point: _pd_quarter_sort_key(point["period"]))
    return points


def build_pd_rank_ordering_aggregate(
    facilities: list[dict[str, Any]], historical_key: str, forecast_key: str
) -> dict[str, Any]:
    """Port of ``buildPdRankOrderingAggregate``."""
    historical_accumulator: dict[str, dict[str, float]] = {}
    base_accumulator: dict[str, dict[str, float]] = {}
    severe_accumulator: dict[str, dict[str, float]] = {}
    severe_dates: list[str] = []

    for facility in facilities:
        severe_scenario_date = facility.get("severe_scenario_date")
        if severe_scenario_date:
            severe_dates.append(severe_scenario_date)

        for period, value in (facility.get(historical_key) or {}).items():
            accumulate_pd_rank_ordering_value(historical_accumulator, period, value)

        severe_quarter = iso_date_to_pd_quarter(severe_scenario_date)
        forecast_payload = facility.get(forecast_key) or {}
        for scenario_name, accumulator in (("base", base_accumulator), ("severe", severe_accumulator)):
            for step_label, value in (forecast_payload.get(scenario_name) or {}).items():
                offset = get_pd_rank_ordering_forecast_offset(step_label)
                period = add_pd_quarter_offset(severe_quarter, offset) if (severe_quarter and offset is not None) else ""
                accumulate_pd_rank_ordering_value(accumulator, period, value)

    historical = finalize_pd_rank_ordering_aggregate(historical_accumulator)
    base = finalize_pd_rank_ordering_aggregate(base_accumulator)
    severe = finalize_pd_rank_ordering_aggregate(severe_accumulator)
    periods = sorted(
        {point["period"] for point in (*historical, *base, *severe)},
        key=_pd_quarter_sort_key,
    )
    return {
        "historical": historical,
        "base": base,
        "severe": severe,
        "periods": periods,
        "severe_dates": sorted({date for date in severe_dates if date}),
    }


def get_pd_rank_ordering_scenario_quarter(severe_dates: list[str]) -> str:
    """Port of ``getPdRankOrderingScenarioQuarter``."""
    quarters = sorted(
        {iso_date_to_pd_quarter(date) for date in (severe_dates or []) if iso_date_to_pd_quarter(date)},
        key=_pd_quarter_sort_key,
    )
    return quarters[0] if len(quarters) == 1 else ""


def build_pd_rank_ordering_period_label_map(
    periods: list[str], severe_dates: list[str], hide_scenario_quarter: bool = False
) -> dict[str, str]:
    """Port of ``buildPdRankOrderingPeriodLabelMap``."""
    scenario_quarter = get_pd_rank_ordering_scenario_quarter(severe_dates)
    label_map: dict[str, str] = {}
    for period in periods:
        offset = get_pd_quarter_distance(scenario_quarter, period)
        if offset is not None and 1 <= offset <= 9:
            label_map[period] = f"Q{offset}"
        elif offset == 0 and hide_scenario_quarter:
            label_map[period] = ""
        else:
            label_map[period] = format_pd_compact_quarter_label(period)
    return label_map
