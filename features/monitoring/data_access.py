"""Stable in-memory data interface for the monitoring dashboard.

Loads the monitoring snapshot once at import time (via
:mod:`features.monitoring.services.data_service`) and exposes it as
:data:`PD_PERFORMANCE_DATA`, so the page layout (called on every page load) and
the callbacks read the same in-memory data without re-reading the workbook or
threading ``data`` through ``app.py``. The load/enrich orchestration lives in
the services layer; this module is just the cached bridge.
"""

from __future__ import annotations

from .services import data_service

# Monitoring data, loaded once at import time.
PD_PERFORMANCE_DATA = data_service.load_monitoring_data()


def get_app_meta() -> dict:
    """Sidebar/footer metadata the shell surfaces for this dashboard."""
    return data_service.get_app_meta(PD_PERFORMANCE_DATA)
