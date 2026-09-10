"""Page registry for the backtesting dashboard."""

from __future__ import annotations

from ...shared.types import PageDefinition
from .callbacks import backtesting as backtesting_callbacks
from .ui.pages import backtesting as backtesting_page

PAGES: tuple[PageDefinition, ...] = (
    PageDefinition(
        key="backtesting",
        label="Backtesting",
        path="/backtesting",
        icon="🎯",
        nav_label="Backtest",
        build_layout=backtesting_page.page_layout,
        register_callbacks=backtesting_callbacks.register_callbacks,
    ),
)
