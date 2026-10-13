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


def filter_options_by_search(options: list[dict] | None, search: str | None) -> list[dict]:
    """``options`` narrowed to those matching ``search`` (label or value)."""
    text = str(search or "").strip().lower()
    if not text:
        return list(options or [])
    return [
        option for option in (options or [])
        if text in str(option.get("label", "")).lower()
        or text in str(option.get("value", "")).lower()
    ]


def build_single_select_shell(
    *, options: list[dict] | None, value: str | None, filter_key: str, search: str | None = None,
) -> tuple[str, list]:
    """Return the current toggle label + option buttons for a single-select shell.

    ``search`` hides options; it never removes them. The toggle label is resolved
    against the **full** list, so a selection stays readable while filtered out
    of view -- the same rule the SAAS/Overview model checklists follow.
    """
    return _option_label(options, value), build_single_select_options(
        options=filter_options_by_search(options, search),
        value=value,
        filter_key=filter_key,
    )


def resolve_monitoring_point_value(options: list[str] | None, value: str | None) -> str:
    """Use the current monitoring point when valid, otherwise fall back to the latest one."""
    return controls.resolve_monitoring_point_value(options, value)


def register_single_select_callbacks(
    app,
    *,
    value_id: str,
    toggle_id: str,
    menu_id: str,
    filter_key: str,
    search_id: str | None = None,
) -> None:
    """Wire a PD-style custom dropdown shell to a hidden ``dcc.Dropdown`` value.

    Pass ``search_id`` for a menu built with a search box. The rebuilt children
    then go to the menu's inner option-list container rather than to the menu
    itself, so the search input stays mounted while you type -- see
    ``controls.single_select_option_list_id``.
    """

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

    # ``value`` is allow_duplicate because each tab's own sync_*_dropdown
    # callback also writes it when a parent filter rebuilds the option list.
    # That one is the canonical writer -- it has to fire on the initial call to
    # populate the list at all -- so this click handler is the duplicate. Same
    # split SAAS already uses in _register_single_select_callbacks; without the
    # flag the renderer reports "Output ... is already in use" for every custom
    # dropdown on the four monitoring tabs.
    @app.callback(
        Output(value_id, "value", allow_duplicate=True),
        Output(menu_id, "className", allow_duplicate=True),
        Input({"type": controls.SINGLE_SELECT_OPTION_ID, "filter": filter_key, "value": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_single_select_option(_clicks):
        # The option buttons are re-created whenever the menu is rebuilt (e.g. a
        # dependent filter changing the options -- the Reporting Cycle rebuilding
        # the Monitoring Point list on load). Dash fires this pattern-matching
        # callback once on that remount even under prevent_initial_call, with
        # ctx.triggered_id pointing at an option but every n_clicks still 0.
        # Without checking n_clicks, that spurious fire silently resets the value
        # to whichever option mounted first (e.g. the earliest monitoring point),
        # leaving the hidden value out of sync with the toggle. Only act on a real
        # click, i.e. when some option's n_clicks has actually incremented.
        triggered = ctx.triggered_id
        if not triggered or not any(_clicks or []):
            return no_update, no_update
        return triggered["value"], _MENU_CLASS

    if search_id is None:
        @app.callback(
            Output(toggle_id, "children"),
            Output(menu_id, "children"),
            Input(value_id, "value"),
            Input(value_id, "options"),
        )
        def sync_single_select_shell(value, options):
            return build_single_select_shell(
                options=options,
                value=value,
                filter_key=filter_key,
            )
    else:
        @app.callback(
            Output(toggle_id, "children"),
            Output(controls.single_select_option_list_id(menu_id), "children"),
            Input(value_id, "value"),
            Input(value_id, "options"),
            Input(search_id, "value"),
        )
        def sync_searchable_single_select_shell(value, options, search):
            return build_single_select_shell(
                options=options,
                value=value,
                filter_key=filter_key,
                search=search,
            )
