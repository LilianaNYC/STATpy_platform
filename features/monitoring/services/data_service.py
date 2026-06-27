"""Monitoring data orchestration (load + enrich the source snapshot).

Pulls the aggregated PD/LGD/EAD/Loss metrics from the shared ``data`` layer
(the repository), attaches run metadata, and normalizes the portfolio frame.
``data_access`` calls :func:`load_monitoring_data` once at import time and caches
the result; everything else reads that cached snapshot.
"""

from __future__ import annotations

from datetime import datetime

import polars as pl

from ....config.settings import settings
from ....data.monitoring.loader import (
    load_pd_performance_data_from_aggregated as _load_source_snapshot,
)


def _with_app_meta(data: dict) -> dict:
    refreshed_at = datetime.now().replace(microsecond=0)
    data["app_meta"] = {
        "run_id": f"DASH_{refreshed_at:%Y%m%d_%H%M%S}",
        "last_refresh": refreshed_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return data


def _with_polars_portfolio(data: dict) -> dict:
    portfolio = data.get("portfolio")
    if portfolio is not None and not isinstance(portfolio, pl.DataFrame):
        data["portfolio"] = pl.from_pandas(portfolio)
    return data


def load_monitoring_data() -> dict:
    """Load and enrich the monitoring snapshot used by every page."""
    return _with_polars_portfolio(_with_app_meta(_load_source_snapshot()))


def get_app_meta(data: dict) -> dict:
    """Sidebar/footer metadata the shell surfaces for this dashboard."""
    app_meta = data.get("app_meta") or {}
    return {
        "latest_snapshot": data.get("latest_snapshot_date") or "—",
        "last_refresh": app_meta.get("last_refresh") or "—",
        "source_file": data.get("source_file") or settings.portfolio_file.name,
        "run_id": app_meta.get("run_id") or "DASH",
    }
