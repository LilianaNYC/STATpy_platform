"""Shared theme-aware loading shells for dashboard content surfaces."""

from __future__ import annotations

from dash import dcc, html


def _build_loading_spinner(scope_label: str, title: str, note: str, card_class_name: str | None = None):
    class_name = "dashboard-loading-card"
    if card_class_name:
        class_name = f"{class_name} {card_class_name}"
    return html.Div(
        className=class_name,
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
    target_components: dict | None = None,
    parent_class_name: str = "dashboard-loading-shell",
    loading_class_name: str = "dashboard-loading-mask",
    overlay_style: dict | None = None,
    spinner_card_class_name: str | None = None,
    delay_show: int = 180,
):
    """Wrap a callback-driven content surface in the shared loading experience."""

    return dcc.Loading(
        id=loading_id or f"{content_id}-loading",
        parent_className=parent_class_name,
        className=loading_class_name,
        delay_show=delay_show,
        show_initially=False,
        color="transparent",
        overlay_style=overlay_style or {"visibility": "visible", "filter": "blur(2px) saturate(0.9)"},
        target_components=target_components,
        custom_spinner=_build_loading_spinner(scope_label, title, note, spinner_card_class_name),
        children=html.Div(
            id=content_id,
            className=content_class_name,
            children=children,
        ),
    )
