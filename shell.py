"""Shared app shell: sidebar navigation, page routing, and page footer.

Ports the sidebar/top-level shell from ``components/monitoring_layout.py``'s
``build_layout``. The original single-page app rendered the PD Performance
tab directly inside this shell; now the shell hosts a small client-side
router (:func:`register_callbacks`) that swaps ``#page-content`` between the
PD/LGD/EAD performance pages based on the current URL, while the PD
Performance ``dcc.Store`` components
(:func:`pages.monitoring_pd_performance_layout.build_stores`) live in the
shell itself so filter/range state survives navigation.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, dcc, html

from . import monitoring_config as config
from .data_store import PD_PERFORMANCE_DATA
from .pages import monitoring_ead_performance_layout as ead_performance_layout
from .pages import monitoring_lgd_performance_layout as lgd_performance_layout
from .pages import monitoring_pd_performance_layout as pd_performance_layout

URL_ID = "app-url"
PAGE_CONTENT_ID = "page-content"

# (icon, label, path) for each registered page, in sidebar order.
NAV_LINKS = [
    ("🧠", "PD Performance", "/"),
    ("📉", "LGD Performance", "/lgd-performance"),
    ("📈", "EAD Performance", "/ead-performance"),
]

# Maps a URL path to the function that builds that page's content.
PAGE_BUILDERS = {
    "/": lambda: pd_performance_layout.page_layout(PD_PERFORMANCE_DATA),
    "/lgd-performance": lgd_performance_layout.page_layout,
    "/ead-performance": ead_performance_layout.page_layout,
}


def _build_nav_link(icon: str, label: str, href: str) -> html.Li:
    return html.Li(
        dcc.Link(
            [html.Span(icon, className="nav-icon"), html.Span(label, className="nav-label")],
            href=href,
            id={"type": "nav-link", "href": href},
            className="nav-item",
        )
    )


def _build_sidebar() -> html.Nav:
    latest_snapshot = PD_PERFORMANCE_DATA.get("latest_snapshot_date") or "—"
    refreshed_at = (PD_PERFORMANCE_DATA.get("app_meta") or {}).get("last_refresh") or "—"

    return html.Nav(
        className="sidebar",
        children=[
            html.Div(
                className="sidebar-logo",
                children=[
                    html.Div("📊", className="logo-icon"),
                    html.H1("Model Monitoring"),
                    html.P("Wholesale Credit Platform"),
                ],
            ),
            html.Ul(
                className="nav-list",
                children=[
                    html.Li(
                        html.Span(
                            [html.Span("📊", className="nav-icon"), html.Span("Overview", className="nav-label")],
                            className="nav-item is-disabled",
                            **{"aria-disabled": "true"},
                        )
                    ),
                    *[_build_nav_link(icon, label, href) for icon, label, href in NAV_LINKS],
                ],
            ),
            html.Div(
                className="sidebar-footer",
                children=[
                    "Data as of:",
                    html.Br(),
                    latest_snapshot,
                    html.Br(),
                    html.Br(),
                    "Last refresh:",
                    html.Br(),
                    refreshed_at,
                ],
            ),
        ],
    )


def _build_page_footer() -> html.Div:
    latest_snapshot = PD_PERFORMANCE_DATA.get("latest_snapshot_date") or "—"
    source_file = PD_PERFORMANCE_DATA.get("source_file") or config.PORTFOLIO_FILE.name
    app_meta = PD_PERFORMANCE_DATA.get("app_meta") or {}

    return html.Div(
        className="page-footer",
        children=[
            html.Span(f"Data as of: {latest_snapshot}"),
            html.Span(f"Source: {source_file}"),
            html.Span(f"Run ID: {app_meta.get('run_id') or 'DASH'}"),
            html.Span(f"Last refresh: {app_meta.get('last_refresh') or '—'}"),
        ],
    )


def build_app_shell() -> html.Div:
    return html.Div(
        className="monitoring-shell",
        children=[
            dcc.Location(id=URL_ID, refresh=False),
            *pd_performance_layout.build_stores(),
            _build_sidebar(),
            html.Div(
                className="main",
                children=[
                    html.Div(id=PAGE_CONTENT_ID, className="page-shell", children=PAGE_BUILDERS["/"]()),
                    _build_page_footer(),
                ],
            ),
        ],
    )


def register_callbacks(app) -> None:
    """Register the page router and sidebar active-link highlighting."""

    @app.callback(Output(PAGE_CONTENT_ID, "children"), Input(URL_ID, "pathname"))
    def render_page(pathname):
        builder = PAGE_BUILDERS.get(pathname, PAGE_BUILDERS["/"])
        return builder()

    @app.callback(
        Output({"type": "nav-link", "href": ALL}, "className"),
        Input(URL_ID, "pathname"),
        State({"type": "nav-link", "href": ALL}, "id"),
    )
    def highlight_active_nav(pathname, link_ids):
        return ["nav-item active" if link_id["href"] == pathname else "nav-item" for link_id in link_ids]
