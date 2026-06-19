"""Cached dashboard data shared across pages.

The PD source workbook is loaded lazily the first time the Dash app is
created, then cached so layouts and callbacks use the same in-memory data.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from .data.data_loader import load_pd_performance_data


def _with_app_meta(data: dict) -> dict:
    refreshed_at = datetime.now().replace(microsecond=0)
    data["app_meta"] = {
        "run_id": f"DASH_{refreshed_at:%Y%m%d_%H%M%S}",
        "last_refresh": refreshed_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return data


@lru_cache(maxsize=1)
def get_pd_performance_data() -> dict:
    """Return cached PD Performance data for layouts and callbacks."""
    return _with_app_meta(load_pd_performance_data())
