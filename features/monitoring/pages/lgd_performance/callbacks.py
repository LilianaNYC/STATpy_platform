"""Callbacks for the LGD Performance page (placeholder).

No interactive state yet - this page is static. See
:mod:`features.monitoring.pages.pd_performance.callbacks` for the fully
ported page.
"""

from __future__ import annotations

from .....shared.registration import already_registered


def register_callbacks(app) -> None:
    """No callbacks to register yet (idempotent placeholder)."""
    if already_registered(app, "page:monitoring.lgd_performance"):
        return
