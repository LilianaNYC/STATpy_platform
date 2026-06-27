"""Page registry for the monitoring dashboard.

Defines the pages this dashboard owns. Routing (:mod:`shell`) and callback
registration (:mod:`features.monitoring.dashboard`) read this list, so adding
a page means adding one :class:`PageDefinition` here and nothing else.
"""

from __future__ import annotations

from ...shared.types import PageDefinition
from .callbacks import ead_performance as ead_callbacks
from .callbacks import lgd_performance as lgd_callbacks
from .callbacks import loss_performance as loss_callbacks
from .callbacks import overview as overview_callbacks
from .callbacks import pd_performance as pd_callbacks
from .ui.pages import ead_performance as ead_page
from .ui.pages import lgd_performance as lgd_page
from .ui.pages import loss_performance as loss_page
from .ui.pages import overview as overview_page
from .ui.pages import pd_performance as pd_page

PAGES: tuple[PageDefinition, ...] = (
    PageDefinition(
        key="overview",
        label="Overview",
        path="/overview",
        icon="📋",
        build_layout=overview_page.build_layout,
        register_callbacks=overview_callbacks.register_callbacks,
    ),
    PageDefinition(
        key="pd_performance",
        label="PD Performance",
        path="/",
        icon="🧠",
        build_layout=pd_page.build_layout,
        register_callbacks=pd_callbacks.register_callbacks,
    ),
    PageDefinition(
        key="lgd_performance",
        label="LGD Performance",
        path="/lgd-performance",
        icon="📉",
        build_layout=lgd_page.build_layout,
        register_callbacks=lgd_callbacks.register_callbacks,
    ),
    PageDefinition(
        key="ead_performance",
        label="EAD Performance",
        path="/ead-performance",
        icon="📈",
        build_layout=ead_page.page_layout,
        register_callbacks=ead_callbacks.register_callbacks,
    ),
    PageDefinition(
        key="loss_performance",
        label="Loss Performance",
        path="/loss-performance",
        icon="💰",
        build_layout=loss_page.build_layout,
        register_callbacks=loss_callbacks.register_callbacks,
    ),
)
