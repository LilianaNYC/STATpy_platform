"""Layout for the DQ Balance & Composition page."""
from __future__ import annotations

from ... import data_access
from ..._views import summary_details as _view


def page_layout() -> list:
    return list(_view.layout(data_access.DATA))
