"""Entry point for the multi-page Wholesale Portfolio Model Monitoring Dash app.

Run with::

    python -m Dashboards.app
"""

from __future__ import annotations

import logging
import os

import dash

from . import data_store, shell
from .callbacks import monitoring_ead_performance_callbacks as ead_performance_callbacks
from .callbacks import monitoring_lgd_performance_callbacks as lgd_performance_callbacks
from .callbacks import monitoring_loss_performance_callbacks as loss_performance_callbacks
from .callbacks import monitoring_overview_callbacks as overview_callbacks
from .callbacks import monitoring_pd_performance_callbacks as pd_performance_callbacks
from .data.overview import build_overview_rows

logging.basicConfig(level=logging.INFO)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_app() -> dash.Dash:
    pd_performance_data = data_store.get_pd_performance_data()
    overview_rows = build_overview_rows(pd_performance_data)
    app = dash.Dash(
        __name__,
        title="Wholesale Portfolio Model Monitoring Dashboard",
        suppress_callback_exceptions=True,
    )
    app.layout = shell.build_app_shell(pd_performance_data, overview_rows)

    overview_callbacks.register_callbacks(app, pd_performance_data, overview_rows)
    pd_performance_callbacks.register_callbacks(app, pd_performance_data)
    lgd_performance_callbacks.register_callbacks(app, pd_performance_data)
    ead_performance_callbacks.register_callbacks(app, pd_performance_data)
    loss_performance_callbacks.register_callbacks(app, pd_performance_data)
    shell.register_callbacks(app, pd_performance_data, overview_rows)

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=_env_flag("DASH_DEBUG", default=False))
