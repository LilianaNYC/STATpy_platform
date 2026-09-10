"""Stable data interface for the backtesting dashboard.

Loads the backtesting workbook once at import time and exposes it as
:data:`BACKTESTING_PAGE_DATA` so filter options and chart data stay stable
across page navigation.

Consequence of loading at import time (shared by every dashboard here): editing
``backtesting_results.xlsx`` requires a process restart to take effect.
"""

from __future__ import annotations

from .repositories.loader import load_backtesting_workbook_data

# Backtesting page data. Loaded once at import time.
BACKTESTING_PAGE_DATA = load_backtesting_workbook_data()
