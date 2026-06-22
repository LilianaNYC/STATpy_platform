"""SAAS dashboard metadata and callback-registration entrypoint."""

from __future__ import annotations

from ...shared.registration import already_registered
from ...shared.types import DashboardDefinition
from . import page_registry, stores


def register_callbacks(app) -> None:
    """Register every SAAS page's callbacks (idempotent)."""
    if already_registered(app, "dashboard:saas"):
        return
    for page in page_registry.PAGES:
        page.register_callbacks(app)


DASHBOARD = DashboardDefinition(
    key="saas",
    label="SAAS",
    icon="🗂️",
    base_path="/saas",
    register_callbacks=register_callbacks,
    pages=page_registry.PAGES,
    build_stores=stores.build_stores,
)
