"""Dashboard-level ``dcc.Store`` components for the monitoring dashboard.

All monitoring stores are currently owned by the PD Performance page (the only
interactive page), so the store ids and builder are defined there and surfaced
here as the dashboard's store interface. When a second monitoring page needs
shared state, its stores should be added here too.
"""

from __future__ import annotations

from .ui.views.pd_performance import (
    MEV_FILTER_STORE_ID,
    RANGE_STORE_ID,
    TREND_HORIZON_STORE_ID,
    build_stores,
)

__all__ = [
    "MEV_FILTER_STORE_ID",
    "RANGE_STORE_ID",
    "TREND_HORIZON_STORE_ID",
    "build_stores",
]
