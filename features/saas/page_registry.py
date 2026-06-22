"""Page registry for the SAAS dashboard."""

from __future__ import annotations

from ...shared.types import PageDefinition
from .pages.workspace import callbacks as workspace_callbacks
from .pages.workspace import page as workspace_page

PAGES: tuple[PageDefinition, ...] = (
    PageDefinition(
        key="workspace",
        label="SAAS",
        path="/saas",
        icon="🗂️",
        nav_label="Workspace",
        build_layout=workspace_page.page_layout,
        register_callbacks=workspace_callbacks.register_callbacks,
    ),
)
