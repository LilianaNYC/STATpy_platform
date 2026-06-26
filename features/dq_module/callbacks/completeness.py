"""Callbacks for the DQ Completeness page."""
from __future__ import annotations

from ....shared.registration import already_registered
from .. import data_access
from ..ui.views import completeness as _view


def register_callbacks(app) -> None:
    if already_registered(app, "page:dq.completeness"):
        return
    _view.register_callbacks(app, data_access.DATA)
