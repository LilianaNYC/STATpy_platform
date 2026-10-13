"""Overview's Model picker matches SAAS's workspace control.

Both are multi-select checklists in a popover, and the two dashboards should
behave identically: search narrows only what is *visible*, and "All" means
"all of these" rather than "everything".
"""

from __future__ import annotations

import pytest
from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import overview as layout


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in (children if isinstance(children, (list, tuple)) else [children]):
        if isinstance(child, Component):
            yield from _walk(child)


def _nodes():
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA

    out = []
    for root in layout.page_layout(PD_PERFORMANCE_DATA):
        if isinstance(root, Component):
            out.extend(_walk(root))
    return out


def _by_id(element_id):
    return next((n for n in _nodes() if getattr(n, "id", None) == element_id), None)


def test_the_menu_has_the_same_four_parts_as_saas():
    """Toggle summary, search box, "All", checklist -- in that order."""
    for element_id in (layout.OVERVIEW_MODEL_TOGGLE_ID, layout.OVERVIEW_MODEL_SEARCH_ID,
                       layout.OVERVIEW_MODEL_SELECT_ALL_ID, layout.OVERVIEW_MODEL_ID):
        assert _by_id(element_id) is not None, element_id

    menu = _by_id(layout.OVERVIEW_MODEL_MENU_ID)
    order = [getattr(c, "id", None) for c in menu.children]
    assert order == [layout.OVERVIEW_MODEL_SEARCH_ID,
                     layout.OVERVIEW_MODEL_SELECT_ALL_ID,
                     layout.OVERVIEW_MODEL_ID], order


def test_the_search_box_matches_saas():
    search = _by_id(layout.OVERVIEW_MODEL_SEARCH_ID)
    from STATpy_platform.features.saas.ui.views import workspace as saas

    saas_search = next(
        (n for root in saas.page_layout() if isinstance(root, Component)
         for n in _walk(root)
         if getattr(n, "id", None) == saas.MODEL_NAME_SEARCH_ID),
        None,
    )
    assert saas_search is not None, "SAAS search box not found -- parity check is vacuous"
    assert search.placeholder == saas_search.placeholder
    assert search.className == saas_search.className == "pd-models-search"


def test_the_cell_carries_the_class_the_menu_width_rule_keys_on():
    """``.monitoring-model-filter`` is what gives the menu its max-content width
    and 190px floor -- the floor the "Type to search models…" placeholder needs.
    That rule used to be row-scoped and silently stopped applying whenever the
    Model picker moved rows."""
    cell = next(
        (n for n in _nodes()
         if "monitoring-model-filter" in (getattr(n, "className", None) or "").split()),
        None,
    )
    assert cell is not None
    ids = [getattr(x, "id", None) for x in _walk(cell)]
    assert layout.OVERVIEW_MODEL_ID in ids


# --- behaviour --------------------------------------------------------------

def _captured(monkeypatch):
    from STATpy_platform.features.monitoring.callbacks import overview as callbacks

    class _App:
        def __init__(self):
            self.callbacks = {}

        def callback(self, *_a, **_k):
            def wrap(fn):
                self.callbacks[fn.__name__] = fn
                return fn
            return wrap

    monkeypatch.setattr(callbacks, "already_registered", lambda *_a, **_k: False)
    app = _App()
    callbacks.register_callbacks(app)
    return app.callbacks, callbacks


def test_search_hides_options_without_dropping_the_selection(monkeypatch):
    """The SAAS rule: a model checked before searching stays selected while
    hidden, so typing never silently narrows what you applied."""
    cbs, _m = _captured(monkeypatch)
    sync = cbs["sync_overview_model_options"]

    unsearched, _v = sync("All", "All", "", "All", "", [])
    names = [o["value"] for o in unsearched]
    assert len(names) > 2

    picked = [names[0], names[-1]]
    searched, kept = sync("All", "All", "", "All", names[-1], picked)
    assert [o["value"] for o in searched] == [names[-1]], "search should hide the rest"
    assert kept == picked, "a hidden but checked model must stay selected"


def test_select_all_only_touches_the_visible_options(monkeypatch):
    """"All" means "all of these", not "everything" -- same as SAAS."""
    cbs, module = _captured(monkeypatch)
    sync_all = cbs["sync_overview_model_select_all"]

    class _Ctx:
        triggered_id = module.layout.OVERVIEW_MODEL_SELECT_ALL_ID

    monkeypatch.setattr(module, "ctx", _Ctx())
    visible = [{"label": "B", "value": "B"}, {"label": "C", "value": "C"}]

    # Checking "All" adds the visible ones and keeps the hidden "A".
    value, _sa = sync_all(["all"], ["A"], visible)
    assert value == ["A", "B", "C"], value

    # Un-checking removes only the visible ones; "A" survives.
    value, _sa = sync_all([], ["A", "B", "C"], visible)
    assert value == ["A"], value
