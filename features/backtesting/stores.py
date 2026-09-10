"""Dashboard-level ``dcc.Store`` components for the backtesting dashboard.

The page keeps its stores inline in its own layout (they are only needed while
the page is mounted), so this dashboard contributes no shell-level stores. The
hook is kept for parity with the onboarding contract: if backtesting later needs
state that must survive navigation, return those stores from
:func:`build_stores`.
"""

from __future__ import annotations


def build_stores() -> list:
    return []
