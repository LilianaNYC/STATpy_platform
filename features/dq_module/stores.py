"""App-level dcc.Store components for the DQ dashboard.

The DQ pages create their own stores inside each page layout (page-level
state), so there are no dashboard-level shell stores to contribute.
"""
from __future__ import annotations


def build_stores() -> list:
    return []
