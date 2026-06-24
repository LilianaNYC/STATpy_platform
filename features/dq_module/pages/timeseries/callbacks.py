"""Callbacks for the DQ Time Series page."""
from __future__ import annotations

from .....shared.registration import already_registered
from ... import data_access
from ..._views import timeseries as _view


def register_callbacks(app) -> None:
    if already_registered(app, "page:dq.timeseries"):
        return
    _view.register_callbacks(app, data_access.DATA)
