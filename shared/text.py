"""Text-normalisation helpers shared across dashboard data loaders.

These were previously private helpers in ``data/data_loader.py``; they are
promoted here because both the monitoring and SAAS loaders rely on them
(the "rule of two" for shared code).
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def normalize_model_name(value: Any) -> str:
    """Return a trimmed string for a model name, or ``""`` for missing values."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def ordered_unique_strings(values) -> list[str]:
    """Return trimmed, de-duplicated, non-empty strings in first-seen order."""
    ordered_values: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value).strip() if raw_value is not None and not pd.isna(raw_value) else ""
        if not value or value in seen:
            continue
        seen.add(value)
        ordered_values.append(value)
    return ordered_values
