"""Registry types that describe dashboards and their pages.

These dataclasses are the single source of truth that routing
(:mod:`shell`) and callback registration (:mod:`app`) read from, so adding a
page or a dashboard never requires editing those central files by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class PageDefinition:
    """One navigable page within a dashboard."""

    key: str
    label: str
    path: str
    build_layout: Callable[[], Any]
    register_callbacks: Callable[[Any], None]
    icon: str = ""
    # Label shown in the sidebar nav (defaults to ``label``).
    nav_label: Optional[str] = None
    # Whether the page appears as a sidebar nav link.
    in_nav: bool = True

    @property
    def sidebar_label(self) -> str:
        return self.nav_label or self.label


def _no_stores() -> list:
    return []


@dataclass(frozen=True)
class DashboardDefinition:
    """A top-level product unit that owns a set of pages."""

    key: str
    label: str
    register_callbacks: Callable[[Any], None]
    pages: tuple[PageDefinition, ...]
    icon: str = ""
    base_path: str = ""
    # App-level ``dcc.Store`` components this dashboard contributes to the shell
    # so its filter/range state survives navigation.
    build_stores: Callable[[], list] = field(default=_no_stores)
    # Optional metadata (snapshot date, refresh time, source file) the shell can
    # surface in the sidebar/footer. Returns a dict or ``None``.
    get_app_meta: Optional[Callable[[], dict]] = None

    def iter_nav_pages(self):
        return (page for page in self.pages if page.in_nav)
