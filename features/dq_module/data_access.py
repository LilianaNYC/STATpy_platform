"""Stable data interface for the DQ Wholesale dashboard (thin facade).

Public surface consumed by the platform and this feature's callbacks:
``DATA`` (loaded once), ``get_metrics``, ``recompute_into`` / ``refresh`` (the
in-app "Update data" button), ``get_app_meta`` (sidebar/footer), and
``export_html`` / ``export_excel`` (the per-page Export menu). All real work is
delegated to ``services`` + ``repositories`` so the rest of the feature never
imports the compute/IO layers directly:

  - the seed payload is loaded/saved by ``repositories.results_store``;
  - recompute + report generation run through ``services.report_service``
    (which lazily pulls the heavy compute engine only when actually recomputing).
"""
from __future__ import annotations

import threading

from ...config.settings import settings
from .repositories import results_store
from .services import report_service

_BUILD_LOCK = threading.Lock()

# Loaded once at import time; refreshed IN PLACE by recompute_into() so every
# page/callback holding ``DATA`` sees new data without re-importing.
DATA: dict = results_store.load_metrics()


def get_metrics() -> dict:
    return DATA


def recompute_into(metrics: dict) -> str:
    """Rebuild from the Excel in ``settings.source_data_dir`` and swap into
    ``metrics`` in place, persisting the result as the new seed."""
    with _BUILD_LOCK:
        fresh, run_id = report_service.compute_fresh(settings.source_data_dir)
    metrics.clear()
    metrics.update(fresh)
    results_store.save_metrics(fresh)
    return run_id


def refresh() -> str:
    """Convenience: recompute the module-level DATA singleton."""
    return recompute_into(DATA)


def get_app_meta() -> dict:
    """Sidebar/footer metadata the shell surfaces for this dashboard."""
    return {
        "latest_snapshot": DATA.get("data_as_of") or DATA.get("latest_quarter") or "—",
        "last_refresh": DATA.get("last_refresh") or "—",
        "source_file": DATA.get("source") or "—",
        "run_id": DATA.get("run_id") or "DQ",
    }


def export_html() -> str:
    """Full self-contained HTML report (every tab) — see report_service."""
    return report_service.export_html(DATA)


def export_excel() -> bytes:
    """Metrics workbook (.xlsx) — see report_service."""
    return report_service.export_excel(DATA)
