"""Entry point for the multi-page Wholesale Portfolio Model Monitoring Dash app.

Run with::

    python -m pd_performance_dash.app
"""

from __future__ import annotations

import logging

import dash

from . import data_store, shell
from .callbacks import monitoring_ead_performance_callbacks as ead_performance_callbacks
from .callbacks import monitoring_lgd_performance_callbacks as lgd_performance_callbacks
from .callbacks import monitoring_pd_performance_callbacks as pd_performance_callbacks

logging.basicConfig(level=logging.INFO)


def create_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        title="Wholesale Portfolio Model Monitoring Dashboard",
        suppress_callback_exceptions=True,
    )
    app.layout = shell.build_app_shell()

    pd_performance_callbacks.register_callbacks(app, data_store.PD_PERFORMANCE_DATA)
    lgd_performance_callbacks.register_callbacks(app)
    ead_performance_callbacks.register_callbacks(app)
    shell.register_callbacks(app)

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True)
