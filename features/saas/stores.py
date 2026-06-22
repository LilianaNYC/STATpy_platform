"""Dashboard-level ``dcc.Store`` components for the SAAS dashboard.

The SAAS workspace keeps its stores inline in its page layout (they are only
needed while the page is mounted), so this dashboard contributes no
shell-level stores. The hook is kept for parity with the onboarding contract:
if SAAS later needs state that must survive navigation, return those stores
from :func:`build_stores`.
"""

from __future__ import annotations


def build_stores() -> list:
    return []
