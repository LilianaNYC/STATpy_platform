"""Layout for the DQ Time Series page."""
from __future__ import annotations

from ... import data_access
from ..._views import timeseries as _view


def page_layout() -> list:
    return list(_view.layout(data_access.DATA))
