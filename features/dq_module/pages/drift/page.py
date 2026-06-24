"""Layout for the DQ Distribution Drift page."""
from __future__ import annotations

from ... import data_access
from ..._views import drift as _view


def page_layout() -> list:
    return list(_view.layout(data_access.DATA))
