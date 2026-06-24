"""Layout for the DQ Business Rules page."""
from __future__ import annotations

from dash import html

from ... import data_access
from .. import common
from ..views import rules as _view


def page_layout() -> list:
    # Wrap in the platform's .content scroll container (flex:1; overflow-y:auto),
    # exactly like the monitoring/saas pages. Without it the page can't scroll
    # and .page-shell's flex column squashes the charts.
    return [html.Div(
        [common.export_bar("rules", "Business Rules", data_access.DATA),
         *_view.layout(data_access.DATA)],
        className="content")]
