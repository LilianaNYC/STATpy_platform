"""Module-level data singletons shared across pages.

Each page's source workbook is loaded once, at import time, so that both a
page's ``layout`` function (called on every page load) and its callbacks
module can read the same in-memory data without re-reading the workbook or
threading ``data`` through ``app.py``.
"""

from __future__ import annotations

from datetime import datetime

from .data.data_loader import load_pd_performance_data, load_saas_mev_workbook_data


def _with_app_meta(data: dict) -> dict:
    refreshed_at = datetime.now().replace(microsecond=0)
    data["app_meta"] = {
        "run_id": f"DASH_{refreshed_at:%Y%m%d_%H%M%S}",
        "last_refresh": refreshed_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return data


# PD Performance tab data (Chapter 1 & 2). LGD/EAD Performance pages don't
# have a data source yet - see pages/monitoring_lgd_performance_layout.py and
# pages/monitoring_ead_performance_layout.py.
PD_PERFORMANCE_DATA = _with_app_meta(load_pd_performance_data())

# SAAS page data. Loaded once at import time so workbook-backed filters and
# chart data remain stable across page navigation.
SAAS_PAGE_DATA = load_saas_mev_workbook_data()
SAAS_FILTER_DATA = {
    "model_names": SAAS_PAGE_DATA.get("model_names", []),
}
