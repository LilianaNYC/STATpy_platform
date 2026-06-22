"""Stable data interface for the monitoring dashboard.

Loads the PD Performance source workbook once at import time and exposes it as
:data:`PD_PERFORMANCE_DATA`, so the page layout (called on every page load) and
the callbacks read the same in-memory data without re-reading the workbook or
threading ``data`` through ``app.py``. This hides loader/store details from the
page modules (the blueprint's ``data_access.py`` responsibility).
"""

from __future__ import annotations

from datetime import datetime

from ...config.settings import settings
from ...data.monitoring.loader import load_pd_performance_data


def _with_app_meta(data: dict) -> dict:
    refreshed_at = datetime.now().replace(microsecond=0)
    data["app_meta"] = {
        "run_id": f"DASH_{refreshed_at:%Y%m%d_%H%M%S}",
        "last_refresh": refreshed_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return data


# PD Performance tab data (Chapter 1 & 2), loaded once at import time.
PD_PERFORMANCE_DATA = _with_app_meta(load_pd_performance_data())


def get_app_meta() -> dict:
    """Sidebar/footer metadata the shell surfaces for this dashboard."""
    app_meta = PD_PERFORMANCE_DATA.get("app_meta") or {}
    return {
        "latest_snapshot": PD_PERFORMANCE_DATA.get("latest_snapshot_date") or "—",
        "last_refresh": app_meta.get("last_refresh") or "—",
        "source_file": PD_PERFORMANCE_DATA.get("source_file") or settings.portfolio_file.name,
        "run_id": app_meta.get("run_id") or "DASH",
    }
