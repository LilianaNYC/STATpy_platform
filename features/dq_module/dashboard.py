"""DQ Wholesale dashboard metadata + callback-registration entrypoint."""
from __future__ import annotations

from ...shared.registration import already_registered
from ...shared.types import DashboardDefinition
from . import data_access, page_registry, stores


def register_callbacks(app) -> None:
    """Register every DQ page's callbacks (idempotent)."""
    if already_registered(app, "dashboard:dq"):
        return
    for page in page_registry.PAGES:
        page.register_callbacks(app)


DASHBOARD = DashboardDefinition(
    key="dq",
    label="DQ Wholesale",
    icon="\U0001f9ea",
    base_path="/dq-overview",
    register_callbacks=register_callbacks,
    pages=page_registry.PAGES,
    build_stores=stores.build_stores,
    get_app_meta=data_access.get_app_meta,
)
