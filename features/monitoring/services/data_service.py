"""Monitoring data orchestration (load + enrich the source snapshot).

Pulls the aggregated PD/LGD/EAD/Loss metrics from this feature's own
repository layer, attaches run metadata, and normalizes the portfolio frame.
``data_access`` calls :func:`load_monitoring_data` once at import time and caches
the result; everything else reads that cached snapshot.
"""

from __future__ import annotations

from datetime import datetime

import polars as pl

from ....config.settings import settings
from ..repositories.loader import (
    load_pd_performance_data_from_aggregated as _load_source_snapshot,
    update_ead_review_flow_rag as _update_ead_review_flow_rag,
    update_lgd_review_flow_rag as _update_lgd_review_flow_rag,
    update_pd_review_flow_rag as _update_pd_review_flow_rag,
)

_PD_REVIEW_FLOW_HORIZONS = ("1y", "2y", "nco_1y")


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


def save_pd_review_flow_rag(
    data: dict,
    reporting_cycle: str,
    level: str,
    model_or_segment: str,
    quarter: str,
    field: str,
    new_value: str,
) -> bool:
    """Persist an edited Post Subjective Review / Pre-/Post-Mitigation RAG to the portfolio file.

    Writes the change to ``portfolio.xlsx`` first (the source of truth), then -- only if that
    succeeded -- mutates the matching entries in ``data``'s already-loaded ``metrics_store`` in place,
    so the running app reflects the edit immediately without a process restart.
    """
    updated_rows = _update_pd_review_flow_rag(reporting_cycle, level, model_or_segment, quarter, field, new_value)
    if not updated_rows:
        return False

    cycle_data = (data.get("observations_by_cycle") or {}).get(reporting_cycle) or {}
    metrics_store = cycle_data.get("metrics_store")
    if metrics_store is not None:
        for horizon in _PD_REVIEW_FLOW_HORIZONS:
            row = metrics_store.get((level, model_or_segment, quarter, horizon))
            if row is not None:
                row[field] = new_value
    return True


def save_lgd_review_flow_rag(
    data: dict,
    reporting_cycle: str,
    level: str,
    model_or_segment: str,
    quarter: str,
    field: str,
    new_value: str,
) -> bool:
    """Persist an edited Post Subjective Review / Pre-/Post-Mitigation RAG to the portfolio file.

    Same write-then-mutate-in-place pattern as :func:`save_pd_review_flow_rag`, but for
    ``LGD_Performance_Metrics``, which has no horizon dimension: one row per
    ``(level, model_or_segment)`` list holds one entry per monitoring period.
    """
    updated_rows = _update_lgd_review_flow_rag(reporting_cycle, level, model_or_segment, quarter, field, new_value)
    if not updated_rows:
        return False

    cycle_data = (data.get("lgd_observations_by_cycle") or {}).get(reporting_cycle) or {}
    metrics_store = cycle_data.get("metrics_store")
    if metrics_store is not None:
        for row in metrics_store.get((level, model_or_segment), []):
            if str(row.get("Monitoring Period", "")) == str(quarter):
                row[field] = new_value
    return True


def save_ead_review_flow_rag(
    data: dict,
    reporting_cycle: str,
    level: str,
    model_or_segment: str,
    quarter: str,
    field: str,
    new_value: str,
) -> bool:
    """Persist an edited Post Subjective Review / Pre-/Post-Mitigation RAG to the portfolio file.

    Same write-then-mutate-in-place pattern as :func:`save_lgd_review_flow_rag`, for
    ``EAD_Performance_Metrics``.
    """
    updated_rows = _update_ead_review_flow_rag(reporting_cycle, level, model_or_segment, quarter, field, new_value)
    if not updated_rows:
        return False

    cycle_data = (data.get("ead_observations_by_cycle") or {}).get(reporting_cycle) or {}
    metrics_store = cycle_data.get("metrics_store")
    if metrics_store is not None:
        for row in metrics_store.get((level, model_or_segment), []):
            if str(row.get("Monitoring Period", "")) == str(quarter):
                row[field] = new_value
    return True


def get_app_meta(data: dict) -> dict:
    """Sidebar/footer metadata the shell surfaces for this dashboard."""
    app_meta = data.get("app_meta") or {}
    return {
        "latest_snapshot": data.get("latest_snapshot_date") or "—",
        "last_refresh": app_meta.get("last_refresh") or "—",
        "source_file": data.get("source_file") or settings.portfolio_file.name,
        "run_id": app_meta.get("run_id") or "DASH",
    }
