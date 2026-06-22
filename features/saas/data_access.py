"""Stable data interface for the SAAS dashboard.

Loads the SAAS MEV workbook once at import time and exposes it as
:data:`SAAS_PAGE_DATA` so workbook-backed filters and chart data stay stable
across page navigation.
"""

from __future__ import annotations

from ...data.saas.loader import load_saas_mev_workbook_data

# SAAS page data. Loaded once at import time.
SAAS_PAGE_DATA = load_saas_mev_workbook_data()
