"""Shared theme-aware loading shells for dashboard content surfaces."""

from __future__ import annotations

from dash import dcc, html


def _build_loading_spinner(scope_label: str, title: str, note: str):
    return html.Div(
        className="dashboard-loading-card",
        role="status",
        **{"aria-live": "polite"},
        children=[
            html.Div(
                className="dashboard-loading-beacon",
                children=[
                    html.Span(className="dashboard-loading-orbit dashboard-loading-orbit-outer"),
                    html.Span(className="dashboard-loading-orbit dashboard-loading-orbit-inner"),
                    html.Span(className="dashboard-loading-node dashboard-loading-node-top"),
                    html.Span(className="dashboard-loading-node dashboard-loading-node-right"),
                    html.Span(className="dashboard-loading-node dashboard-loading-node-left"),
                    html.Span(className="dashboard-loading-core"),
                ],
            ),
            html.Div(
                className="dashboard-loading-copy",
                children=[
                    html.Div(scope_label, className="dashboard-loading-kicker"),
                    html.Div(title, className="dashboard-loading-title"),
                    html.Div(note, className="dashboard-loading-note"),
                ],
            ),
        ],
    )


def build_dashboard_loading_shell(
    *,
    content_id: str,
    children,
    scope_label: str,
    title: str,
    note: str,
    content_class_name: str | None = None,
    loading_id: str | None = None,
):
    """Wrap a callback-driven content surface in the shared loading experience."""

    return dcc.Loading(
        id=loading_id or f"{content_id}-loading",
        parent_className="dashboard-loading-shell",
        className="dashboard-loading-mask",
        delay_show=180,
        color="transparent",
        overlay_style={"visibility": "visible", "filter": "blur(2px) saturate(0.9)"},
        custom_spinner=_build_loading_spinner(scope_label, title, note),
        children=html.Div(
            id=content_id,
            className=content_class_name,
            children=children,
        ),
    )
