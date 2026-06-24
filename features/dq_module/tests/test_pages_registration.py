"""UI + callbacks — each page builds a .content layout and registers callbacks."""

import dash
import pytest
from dash import html

from STATpy_platform.features.dq_module import page_registry
from STATpy_platform.features.dq_module.dashboard import DASHBOARD

_PAGE_IDS = [p.key for p in page_registry.PAGES]


@pytest.mark.parametrize("page", page_registry.PAGES, ids=_PAGE_IDS)
def test_page_layout_wraps_in_content(page):
    out = page.build_layout()
    assert isinstance(out, list) and out
    assert any(getattr(n, "className", None) == "content" for n in out), \
        f"{page.key}: layout not wrapped in the platform .content scroll container"


def test_dashboard_callbacks_idempotent_with_exports():
    app = dash.Dash("dq-test", suppress_callback_exceptions=True)
    app.layout = html.Div([p.build_layout() for p in DASHBOARD.pages])
    DASHBOARD.register_callbacks(app)
    n1 = len(app.callback_map)
    DASHBOARD.register_callbacks(app)          # second call must add nothing
    assert len(app.callback_map) == n1 and n1 > 0
    # every page wires its two server-side export downloads
    for key in _PAGE_IDS:
        assert f"dqd-{key}-export-dl-html.data" in app.callback_map
        assert f"dqd-{key}-export-dl-xlsx.data" in app.callback_map
