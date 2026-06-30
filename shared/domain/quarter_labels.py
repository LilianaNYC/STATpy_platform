"""Quarter-label parsing/formatting/sorting helpers.

Ports the small ``YYYY-Qn`` quarter-label utilities from
``pages/monitoring_pd_models_page.py`` that are shared by the MEV range
section (:mod:`mev_range`), the monitoring PD/LGD/EAD performance views, and
the shared chart helpers (:mod:`shared.ui.charts`).

Note: these labels use the ``YYYY-Qn`` format (produced by
:func:`iso_date_to_pd_quarter` from ISO dates and used directly as keys in
``dummy_mev_data.xlsx``). This is a *different* format from the portfolio
quarter labels (``YYYYQn``) used elsewhere in :mod:`calculations`.
"""

from __future__ import annotations

import re
from functools import cmp_to_key

_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_QUARTER_LABEL_RE = re.compile(r"^(\d{4})-Q([1-4])$")


# ---------------------------------------------------------------------------
# Date / quarter-label helpers
# ---------------------------------------------------------------------------


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


def format_pd_compact_quarter_label(period: str | None) -> str:
    """Port of ``formatPdCompactQuarterLabel``: ``YYYY-Qn`` -> ``YYYYQn``."""
    match = _QUARTER_LABEL_RE.match(period or "")
    return f"{match.group(1)}Q{match.group(2)}" if match else (period or "")
