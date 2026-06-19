"""Shared app shell: sidebar navigation, page routing, and page footer.

Ports the sidebar/top-level shell from ``components/monitoring_layout.py``'s
``build_layout``. The shell hosts a small router that swaps ``#page-content``
between the PD/LGD/EAD performance pages based on the current URL, while the
PD Performance ``dcc.Store`` components live in the shell itself so
filter/range state survives navigation.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, dcc, html

from . import monitoring_config as config
from .pages import monitoring_ead_performance_layout as ead_performance_layout
from .pages import monitoring_lgd_performance_layout as lgd_performance_layout
from .pages import monitoring_loss_performance_layout as loss_performance_layout
from .pages import monitoring_overview_layout as overview_layout
from .pages import monitoring_pd_performance_layout as pd_performance_layout

URL_ID = "app-url"
PAGE_CONTENT_ID = "page-content"

# (label, path) for each registered page, in sidebar order.
NAV_LINKS = [
    ("Overview", "/"),
    ("PD Performance", "/pd-performance"),
    ("LGD Performance", "/lgd-performance"),
    ("EAD Performance", "/ead-performance"),
    ("Loss Performance", "/loss-performance"),
]


def _page_builders(pd_performance_data: dict, overview_rows: list[dict]) -> dict:
    return {
        "/": lambda: overview_layout.page_layout(pd_performance_data, overview_rows),
        "/pd-performance": lambda: pd_performance_layout.page_layout(pd_performance_data),
        "/lgd-performance": lambda: lgd_performance_layout.page_layout(pd_performance_data),
        "/ead-performance": lambda: ead_performance_layout.page_layout(pd_performance_data),
        "/loss-performance": lambda: loss_performance_layout.page_layout(pd_performance_data),
    }


def _build_nav_link(label: str, href: str) -> html.Li:
    return html.Li(
        dcc.Link(
            label,
            href=href,
            id={"type": "nav-link", "href": href},
            className="nav-item",
        )
    )


def _build_sidebar(pd_performance_data: dict) -> html.Nav:
    latest_snapshot = pd_performance_data.get("latest_snapshot_date") or "-"
    refreshed_at = (pd_performance_data.get("app_meta") or {}).get("last_refresh") or "-"

    return html.Nav(
        className="sidebar",
        children=[
            html.Div(
                className="sidebar-logo",
                children=[
                    html.H1("Model Monitoring"),
                    html.P("Wholesale Credit Platform"),
                ],
            ),
            html.Ul(
                className="nav-list",
                children=[
                    *[_build_nav_link(label, href) for label, href in NAV_LINKS],
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


def _build_page_footer(pd_performance_data: dict) -> html.Div:
    latest_snapshot = pd_performance_data.get("latest_snapshot_date") or "-"
    source_file = pd_performance_data.get("source_file") or config.PORTFOLIO_FILE.name
    app_meta = pd_performance_data.get("app_meta") or {}

    return html.Div(
        className="page-footer",
        children=[
            html.Span(f"Data as of: {latest_snapshot}"),
            html.Span(f"Source: {source_file}"),
            html.Span(f"Run ID: {app_meta.get('run_id') or 'DASH'}"),
            html.Span(f"Last refresh: {app_meta.get('last_refresh') or '-'}"),
        ],
    )


def build_app_shell(pd_performance_data: dict, overview_rows: list[dict]) -> html.Div:
    page_builders = _page_builders(pd_performance_data, overview_rows)
    return html.Div(
        className="monitoring-shell",
        children=[
            dcc.Location(id=URL_ID, refresh=False),
            *pd_performance_layout.build_stores(),
            dcc.Store(id=overview_layout.RANGE_STORE_ID, data={}),
            _build_sidebar(pd_performance_data),
            html.Div(
                className="main",
                children=[
                    html.Div(id=PAGE_CONTENT_ID, className="page-shell", children=page_builders["/"]()),
                    _build_page_footer(pd_performance_data),
                ],
            ),
        ],
    )


def register_callbacks(app, pd_performance_data: dict, overview_rows: list[dict]) -> None:
    """Register the page router and sidebar active-link highlighting."""
    page_builders = _page_builders(pd_performance_data, overview_rows)

    @app.callback(Output(PAGE_CONTENT_ID, "children"), Input(URL_ID, "pathname"))
    def render_page(pathname):
        builder = page_builders.get(pathname, page_builders["/"])
        return builder()

    @app.callback(
        Output({"type": "nav-link", "href": ALL}, "className"),
        Input(URL_ID, "pathname"),
        State({"type": "nav-link", "href": ALL}, "id"),
    )
    def highlight_active_nav(pathname, link_ids):
        return ["nav-item active" if link_id["href"] == pathname else "nav-item" for link_id in link_ids]
