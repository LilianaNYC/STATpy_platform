"""Entry point for the multi-dashboard Wholesale Credit Dash app.

Run with::

    python -m STATpy_platform.app

Wiring is registry-driven: dashboards are declared in
:mod:`features_registry`, and this module simply builds the shell and loops
over the registered dashboards to register their callbacks. Adding a dashboard
or page requires no edits here.
"""

from __future__ import annotations

import logging

import dash

from . import shell
from .features_registry import DASHBOARDS

logging.basicConfig(level=logging.INFO)


def create_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        title="Wholesale Portfolio Model Monitoring Dashboard",
        suppress_callback_exceptions=True,
    )
    app.layout = shell.build_app_shell()

    for dashboard in DASHBOARDS:
        dashboard.register_callbacks(app)
    shell.register_callbacks(app)

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=False)
