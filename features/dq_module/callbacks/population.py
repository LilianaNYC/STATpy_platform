"""Callbacks for the DQ Population page."""
from __future__ import annotations

from ....shared.registration import already_registered
from .. import data_access
from ..ui.views import population as _view


def register_callbacks(app) -> None:
    if already_registered(app, "page:dq.population"):
        return
    _view.register_callbacks(app, data_access.DATA)
