"""Monitoring dashboard metadata and callback-registration entrypoint.

This is the single object the app-level registry (:mod:`features_registry`)
points at. :func:`register_callbacks` loops over the dashboard's pages and
registers each page's callbacks; it is safe to call more than once.
"""

from __future__ import annotations

from ...shared.registration import already_registered
from ...shared.types import DashboardDefinition
from . import data_access, page_registry, stores


def register_callbacks(app) -> None:
    """Register every monitoring page's callbacks (idempotent)."""
    if already_registered(app, "dashboard:monitoring"):
        return
    for page in page_registry.PAGES:
        page.register_callbacks(app)


DASHBOARD = DashboardDefinition(
    key="monitoring",
    label="Monitoring",
    icon="📊",
    base_path="/",
    register_callbacks=register_callbacks,
    pages=page_registry.PAGES,
    build_stores=stores.build_stores,
    get_app_meta=data_access.get_app_meta,
)
