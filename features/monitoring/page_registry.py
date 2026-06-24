"""Page registry for the monitoring dashboard.

Defines the pages this dashboard owns. Routing (:mod:`shell`) and callback
registration (:mod:`features.monitoring.dashboard`) read this list, so adding
a page means adding one :class:`PageDefinition` here and nothing else.
"""

from __future__ import annotations

from ...shared.types import PageDefinition
from .pages.ead_performance import callbacks as ead_callbacks
from .pages.ead_performance import page as ead_page
from .pages.lgd_performance import callbacks as lgd_callbacks
from .pages.lgd_performance import page as lgd_page
from .pages.loss_performance import callbacks as loss_callbacks
from .pages.loss_performance import page as loss_page
from .pages.overview import callbacks as overview_callbacks
from .pages.overview import page as overview_page
from .pages.pd_performance import callbacks as pd_callbacks
from .pages.pd_performance import page as pd_page

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
