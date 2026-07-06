"""Shared callback wiring for Monitoring single-select filter shells."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, html, no_update

from ....shared.ui import controls

_MENU_CLASS = "checkbox-dropdown-menu single-select-menu"


def _option_label(options: list[dict] | None, value: str | None) -> str:
    for option in options or []:
        if option.get("value") == value:
            return option.get("label") or value or "Select"
    return value or "Select"


def build_single_select_options(*, options: list[dict] | None, value: str | None, filter_key: str) -> list:
    """Render custom option buttons for the shared single-select dropdown."""
    return [
        html.Button(
            [
                html.Span(option.get("label") or option.get("value"), className="single-select-option-label"),
                html.Span("✓", className="single-select-option-check", **{"aria-hidden": "true"}),
            ],
            id={"type": controls.SINGLE_SELECT_OPTION_ID, "filter": filter_key, "value": option.get("value")},
            type="button",
            n_clicks=0,
            className="single-select-option is-selected" if option.get("value") == value else "single-select-option",
        )
        for option in options or []
    ]


def register_single_select_callbacks(
    app,
    *,
    value_id: str,
    toggle_id: str,
    menu_id: str,
    filter_key: str,
) -> None:
    """Wire a PD-style custom dropdown shell to a hidden ``dcc.Dropdown`` value."""

    @app.callback(
        Output(menu_id, "className"),
        Input(toggle_id, "n_clicks"),
        State(menu_id, "className"),
        prevent_initial_call=True,
    )
    def toggle_single_select_menu(_n_clicks, current_class):
        if "open" in (current_class or "").split():
            return _MENU_CLASS
        return f"{_MENU_CLASS} open"

    @app.callback(
        Output(value_id, "value"),
        Output(menu_id, "className", allow_duplicate=True),
        Input({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": filter_key, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_single_select_option(_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update
        return triggered["value"], _MENU_CLASS

    @app.callback(
        Output(toggle_id, "children"),
        Output(menu_id, "children"),
        Input(value_id, "value"),
        Input(value_id, "options"),
    )
    def sync_single_select_shell(value, options):
        return _option_label(options, value), build_single_select_options(
            options=options,
            value=value,
            filter_key=filter_key,
        )
