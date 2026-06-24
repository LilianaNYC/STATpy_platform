"""Layout for the DQ Business Rules page."""
from __future__ import annotations

from ... import data_access
from ..._views import rules as _view


def page_layout() -> list:
    return list(_view.layout(data_access.DATA))
