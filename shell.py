"""Shared app shell: sidebar navigation, page routing, and page footer.

The shell is registry-driven: the sidebar links, the page-content router and
the app-level stores are all derived from :mod:`features_registry` rather than
hardcoded here. Adding a page or dashboard to the registry makes it appear in
navigation and routing automatically. Sidebar/footer metadata (snapshot date,
last refresh, source file) comes from the registry's primary dashboard.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, dcc, html

from datetime import datetime

from . import __version__, features_registry as registry
from .shared.types import DashboardDefinition, PageDefinition
from .shared.theme import (
    APP_SHELL_ID,
    APP_THEME_ID,
    DEFAULT_THEME_VALUE,
    PAGE_CONTENT_ID,
    THEME_CLASS_NAMES,
    THEME_OPTIONS,
    URL_ID,
    normalize_theme_value,
)

ROOT_PATH = "/"


def _page_builders() -> dict:
    return registry.page_builders()


def _page_count_label(page_total: int) -> str:
    return f"{page_total} page" if page_total == 1 else f"{page_total} pages"


def _build_page_nav_link(page: PageDefinition, *, active: bool = False) -> html.Li:
    return html.Li(
        dcc.Link(
            [html.Span(page.icon, className="nav-icon"), html.Span(page.sidebar_label, className="nav-label")],
            href=page.path,
            id={"type": "nav-link", "href": page.path},
            className="nav-item active" if active else "nav-item",
        )
    )


def _build_nav_group(dashboard: DashboardDefinition, *, active: bool = False) -> html.Details:
    """A collapsible "folder" for one dashboard: a header (summary) with its
    pages nested beneath. Implemented as a native ``<details>`` so groups start
    collapsed and toggle on click without any extra callbacks. The header of the
    dashboard owning the active route is highlighted (via the URL-driven
    callback); clicking a page link inside the folder performs navigation.
    """
    pages = tuple(dashboard.iter_nav_pages())
    page_total = len(pages)
    return html.Details(
        id={"type": "dashboard-page-panel", "key": dashboard.key},
        className="nav-group",
        # Collapsed on first launch; user expands the folders they need.
        open=False,
        children=[
            html.Summary(
                children=[
                    html.Span(dashboard.icon or "•", className="nav-group-icon"),
                    html.Span(dashboard.label, className="nav-group-title"),
                    html.Span(
                        str(page_total),
                        className="nav-group-count",
                        title=_page_count_label(page_total),
                        **{"aria-label": _page_count_label(page_total)},
                    ),
                    html.Span("⌄", className="nav-group-chevron", **{"aria-hidden": "true"}),
                ],
                id={"type": "dashboard-nav-link", "key": dashboard.key},
                className="nav-group-header active" if active else "nav-group-header",
            ),
            html.Ul(
                className="nav-group-pages-list",
                children=[_build_page_nav_link(page) for page in pages],
            ),
        ],
    )


def _build_sidebar() -> html.Nav:
    default_dashboard = registry.dashboard_for_path(ROOT_PATH)
    nav_dashboards = tuple(registry.iter_nav_dashboards())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return html.Nav(
        className="sidebar",
        children=[
            html.Div(
                className="sidebar-logo",
                children=[
                    html.Div("📊", className="logo-icon"),
                    html.H1("Credit Risk Analytics"),
                    html.P("Wholesale Credit Platform"),
                ],
            ),
            html.Div(
                className="sidebar-nav-eyebrow",
                children=[
                    html.Span("Dashboards", className="sidebar-nav-eyebrow-label"),
                    html.Span(str(len(nav_dashboards)), className="sidebar-nav-eyebrow-count"),
                ],
            ),
            html.Div(
                className="nav-tree",
                children=[
                    _build_nav_group(dashboard, active=dashboard.key == default_dashboard.key)
                    for dashboard in nav_dashboards
                ],
            ),
            html.Div(
                className="sidebar-footer",
                children=[
                    html.Span(f"Last refresh: {now}", className="sidebar-footer-refresh"),
                    html.Span(f"v{__version__}", className="sidebar-footer-version"),
                    html.Div(
                        className="app-theme-control",
                        children=[
                            html.Div("Theme", className="app-theme-label"),
                            dcc.RadioItems(
                                id=APP_THEME_ID,
                                options=THEME_OPTIONS,
                                value=DEFAULT_THEME_VALUE,
                                className="app-theme-toggle",
                                inputClassName="app-theme-toggle-input",
                                labelClassName="app-theme-toggle-option",
                                persistence=True,
                                persistence_type="session",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_app_stores() -> list:
    stores: list = []
    for dashboard in registry.DASHBOARDS:
        stores.extend(dashboard.build_stores())
    return stores


def build_app_shell() -> html.Div:
    page_builders = _page_builders()
    root_builder = page_builders.get(ROOT_PATH)
    return html.Div(
        id=APP_SHELL_ID,
        className="monitoring-shell theme-light",
        children=[
            dcc.Location(id=URL_ID, refresh=False),
            *_build_app_stores(),
            _build_sidebar(),
            html.Div(
                className="main",
                children=[
                    html.Div(
                        id=PAGE_CONTENT_ID,
                        className="page-shell",
                        children=root_builder() if root_builder else None,
                    ),
                ],
            ),
        ],
    )


def register_callbacks(app) -> None:
    """Register the page router and sidebar active-link highlighting."""

    page_builders = _page_builders()
    root_builder = page_builders.get(ROOT_PATH)

    @app.callback(Output(APP_SHELL_ID, "className"), Input(APP_THEME_ID, "value"))
    def sync_app_theme(theme_value):
        return f"monitoring-shell {THEME_CLASS_NAMES[normalize_theme_value(theme_value)]}"

    @app.callback(Output(PAGE_CONTENT_ID, "children"), Input(URL_ID, "pathname"))
    def render_page(pathname):
        builder = page_builders.get(pathname, root_builder)
        return builder() if builder else None

    # Note: this only sets *highlight* classes. It deliberately never touches the
    # ``dashboard-page-panel`` (<details>) element, so each folder's open/closed
    # state stays purely user-controlled and survives navigation.
    @app.callback(
        Output({"type": "dashboard-nav-link", "key": ALL}, "className"),
        Output({"type": "nav-link", "href": ALL}, "className"),
        Input(URL_ID, "pathname"),
        State({"type": "dashboard-nav-link", "key": ALL}, "id"),
        State({"type": "nav-link", "href": ALL}, "id"),
    )
    def highlight_active_nav(pathname, dashboard_link_ids, link_ids):
        active_dashboard = registry.dashboard_for_path(pathname)
        dashboard_link_classes = [
            "nav-group-header active"
            if link_id["key"] == active_dashboard.key
            else "nav-group-header"
            for link_id in dashboard_link_ids
        ]
        link_classes = ["nav-item active" if link_id["href"] == pathname else "nav-item" for link_id in link_ids]
        return dashboard_link_classes, link_classes
