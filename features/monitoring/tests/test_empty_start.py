"""The launching page opens with nothing selected.

Every filter leads with its "Select …" placeholder, holds no value, and Apply
stays disabled until all of them are answered. The fragile half is the
**cascade**: it runs on the first render, so any callback that falls back to
``options[0]`` when a value no longer fits would fill the whole bar in before
the user has touched it. Those fallbacks are checked here too.
"""

from __future__ import annotations

import pytest
from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import (
    ead_performance as ead_layout,
    lgd_performance as lgd_layout,
    loss_performance as loss_layout,
    overview as overview_layout,
)
from STATpy_platform.shared.ui import controls as pd_layout
from STATpy_platform.shared.ui.controls import UNSELECTED

# Filters that are not a choice on a given tab, so they stay pre-set. Only
# Loss's Region/Portfolio qualify: its single entity is the portfolio-wide
# "All Models", which carries neither attribute, so both are fixed "All"
# placeholders rather than real dropdowns.
#
# Model Group does not appear here because PD/LGD/EAD/Loss no longer have one:
# each shows a single group, so the control could only ever return its own name
# and its value drove nothing. Overview keeps its Model Group, where the choice
# is real, and it starts unanswered like every other filter.
FIXED = {
    "pd": set(),
    "lgd": set(),
    "ead": set(),
    "loss": {"loss-region", "loss-portfolio"},
    "overview": set(),
}

TABS = [
    ("Overview", overview_layout, "overview"),
    ("PD", pd_layout, "pd"),
    ("LGD", lgd_layout, "lgd"),
    ("EAD", ead_layout, "ead"),
    ("Loss", loss_layout, "loss"),
]


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in (children if isinstance(children, (list, tuple)) else [children]):
        if isinstance(child, Component):
            yield from _walk(child)


def _bar_controls(module, tab):
    """``{element id: component}`` for every filter cell's options component."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA

    if module is pd_layout:
        roots = [module.build_global_filters(PD_PERFORMANCE_DATA)]
    elif module is overview_layout:
        roots = module.page_layout(PD_PERFORMANCE_DATA)
    elif hasattr(module, "build_layout"):
        roots = module.build_layout()
    else:
        roots = module.page_layout()

    found = {}
    for root in roots:
        if not isinstance(root, Component):
            continue
        for node in _walk(root):
            if "monitoring-filter" not in (getattr(node, "className", None) or "").split():
                continue
            for inner in _walk(node):
                element_id = getattr(inner, "id", None)
                if isinstance(element_id, str) and getattr(inner, "options", None):
                    found.setdefault(element_id, inner)
    return found


@pytest.mark.parametrize("name,module,tab", TABS)
def test_the_scan_finds_the_bar(name, module, tab):
    """Without this every check below would pass on an empty dict."""
    found = _bar_controls(module, tab)
    assert len(found) >= 5, f"{name}: {sorted(found)}"


@pytest.mark.parametrize("name,module,tab", TABS)
def test_every_filter_opens_unanswered(name, module, tab):
    unanswered = []
    for element_id, control in _bar_controls(module, tab).items():
        if element_id in FIXED[tab]:
            continue
        value = control.value
        if isinstance(value, list):
            unanswered.append((element_id, value == []))
        else:
            unanswered.append((element_id, value == UNSELECTED))
    wrong = [element_id for element_id, ok in unanswered if not ok]
    assert not wrong, f"{name}: {wrong} opened with a value"


@pytest.mark.parametrize("name,module,tab", TABS)
def test_every_unanswered_filter_leads_with_a_select_prompt(name, module, tab):
    wrong = []
    for element_id, control in _bar_controls(module, tab).items():
        if element_id in FIXED[tab] or isinstance(control.value, list):
            continue  # multi-selects say "Select models" on their toggle instead
        first = control.options[0]
        if first["value"] != UNSELECTED or not first["label"].startswith("Select "):
            wrong.append(f"{element_id}: {first}")
    assert not wrong, f"{name}: " + "; ".join(wrong)


@pytest.mark.parametrize("name,module,tab", TABS)
def test_the_placeholder_is_never_added_twice(name, module, tab):
    for element_id, control in _bar_controls(module, tab).items():
        blanks = [o for o in control.options if o["value"] == UNSELECTED]
        assert len(blanks) <= 1, f"{name} {element_id}: {blanks}"


# --- the cascade must not answer a filter for the user ----------------------

def test_keep_or_unselected_never_invents_a_value():
    options = [{"label": "Select region", "value": UNSELECTED},
               {"label": "EU", "value": "EU"}, {"label": "HBUS", "value": "HBUS"}]
    assert pd_layout.keep_or_unselected(options, "HBUS") == "HBUS"   # still valid -> kept
    assert pd_layout.keep_or_unselected(options, "APAC") == UNSELECTED  # gone -> unanswered
    assert pd_layout.keep_or_unselected(options, UNSELECTED) == UNSELECTED
    assert pd_layout.keep_or_unselected([], "EU") == UNSELECTED


def test_no_cascade_callback_falls_back_to_the_first_option():
    """The specific regression: ``options[0]["value"]`` in a value fallback.

    The cascade fires on first render, so one of these would re-fill the bar
    before the user touched it -- silently undoing the empty start.
    """
    import inspect
    import re
    from STATpy_platform.features.monitoring.callbacks import (
        ead_performance, lgd_performance, loss_performance, overview, pd_performance,
    )

    offenders = []
    for module in (pd_performance, lgd_performance, ead_performance,
                   loss_performance, overview):
        source = inspect.getsource(module.register_callbacks)
        for line in source.splitlines():
            if re.search(r"value\s*=.*options\[0\]", line):
                offenders.append(f"{module.__name__}: {line.strip()}")
    assert not offenders, offenders


def test_apply_is_gated_on_every_filter_the_tab_empties():
    """Apply must not enable while part of the scope is still unanswered."""
    import inspect

    from STATpy_platform.features.monitoring.callbacks import (
        ead_performance, lgd_performance, loss_performance, pd_performance,
    )

    # Eight, not nine: Model Group was removed from these tabs.
    for module, count in ((pd_performance, 8), (lgd_performance, 8),
                          (ead_performance, 8), (loss_performance, 8)):
        source = inspect.getsource(module.register_callbacks)
        decorator = source.split('Output(layout.APPLY_FILTERS_ID, "disabled")')[1]
        decorator = decorator.split("def ")[0]
        assert decorator.count("Input(") == count, f"{module.__name__}: {decorator}"


def test_all_selected_is_the_gate():
    assert pd_layout.all_selected("EU", "C&I", "CECL") is True
    assert pd_layout.all_selected("EU", UNSELECTED) is False
    assert pd_layout.all_selected() is True  # vacuous, but explicit


# --- the scope must not offer a combination with nothing behind it ----------
#
# These narrowings existed on Overview but not on the performance tabs. They
# were survivable while Apply only needed a Model: you could apply against a
# thin scope and the page fell back. Once Apply required the *whole* scope they
# became dead ends -- pick a region/portfolio with no CECL data, pick CECL, and
# Reporting Cycle comes back empty with no way forward and no explanation.

def _captured(monkeypatch, module):
    class _App:
        def __init__(self):
            self.callbacks = {}

        def callback(self, *_a, **_k):
            def wrap(fn):
                self.callbacks[fn.__name__] = fn
                return fn
            return wrap

    monkeypatch.setattr(module, "already_registered", lambda *_a, **_k: False)
    app = _App()
    module.register_callbacks(app)
    return app.callbacks


@pytest.mark.parametrize("tab", ["pd", "lgd", "ead"])
def test_use_case_and_cycle_are_narrowed_by_region_and_portfolio(monkeypatch, tab):
    import importlib

    module = importlib.import_module(
        f"STATpy_platform.features.monitoring.callbacks.{tab}_performance"
    )
    cbs = _captured(monkeypatch, module)

    use_cases, _v = cbs[f"sync_{tab}_scope_to_use_case_options"]("EU", "C&I", UNSELECTED)
    offered = {o["value"] for o in use_cases} - {UNSELECTED}
    assert offered, f"{tab}: EU/C&I offered no use case at all"

    # Every use case offered must yield at least one cycle, and every cycle at
    # least one model -- otherwise the user can walk into a dead end.
    for use_case in offered:
        cycles, _v = cbs[f"sync_{tab}_use_case_to_cycle_options"](
            "EU", "C&I", use_case, UNSELECTED
        )
        real = [o["value"] for o in cycles if o["value"] != UNSELECTED]
        assert real, f"{tab}: use case {use_case!r} offered no cycle under EU/C&I"


@pytest.mark.parametrize("tab", ["pd", "lgd", "ead"])
def test_every_offered_cycle_still_has_a_model(monkeypatch, tab):
    import importlib

    module = importlib.import_module(
        f"STATpy_platform.features.monitoring.callbacks.{tab}_performance"
    )
    cbs = _captured(monkeypatch, module)
    model_cb = next(fn for name, fn in cbs.items() if name.endswith("_to_model_options"))

    # The model callback reads ctx.triggered_id to tell a real Segment click
    # from the menu remount. Stand in for a plain filter change (not a click).
    class _Ctx:
        triggered_id = None

    monkeypatch.setattr(module, "ctx", _Ctx())

    for region in ("EU", "HBUS"):
        for portfolio in ("C&I", "non-C&I"):
            use_cases, _v = cbs[f"sync_{tab}_scope_to_use_case_options"](
                region, portfolio, UNSELECTED)
            for use_case in {o["value"] for o in use_cases} - {UNSELECTED}:
                cycles, _v = cbs[f"sync_{tab}_use_case_to_cycle_options"](
                    region, portfolio, use_case, UNSELECTED)
                for cycle in [o["value"] for o in cycles if o["value"] != UNSELECTED]:
                    options, _v = model_cb(region, portfolio, cycle, [0], UNSELECTED, UNSELECTED)
                    models = [o["value"] for o in options if o["value"] != UNSELECTED]
                    assert models, (
                        f"{tab}: {region}/{portfolio}/{use_case}/{cycle} offers no model -- "
                        "Apply could never enable from there"
                    )


def test_select_prompts_fit_their_control():
    """The controls are 160px, which leaves room for ~18 characters at 12px.

    "Select model use case" and "Select monitoring point" both rendered with an
    ellipsis, which reads as a broken control. The label above each one supplies
    the qualifier, so the prompt does not have to repeat it in full.
    """
    from STATpy_platform.shared.ui.controls import SELECT_PROMPTS

    too_long = {key: text for key, text in SELECT_PROMPTS.items() if len(text) > 16}
    assert not too_long, too_long
    assert all(text.startswith("Select ") for text in SELECT_PROMPTS.values())


@pytest.mark.parametrize("tab", ["pd", "lgd", "ead", "loss"])
def test_picking_a_model_narrows_segment_but_never_answers_it(monkeypatch, tab):
    """Segment is the one filter a *later* action used to fill in.

    LGD/EAD/Loss ran ``resolve_<tab>_segment`` once a Model was picked, and that
    helper never returns empty: it falls back to "All", or to ``segments[0]``
    when the model has no "All" aggregate row. Harmless for a single-segment
    model, but a model with five segments had the choice made for it -- LGD
    Model A silently became "Cyclical". PD never did this, so the same
    interaction behaved differently depending on the tab.
    """
    import importlib

    module = importlib.import_module(
        f"STATpy_platform.features.monitoring.callbacks.{tab}_performance"
    )
    cbs = _captured(monkeypatch, module)
    segment_cb = next(fn for name, fn in cbs.items() if name.endswith("segment_dropdown")
                      or name.endswith("to_segment_options"))

    from STATpy_platform.shared.repositories.filters_config import model_names

    # PD also takes the cycle (as State) between the model and the segment.
    call = (lambda model, segment: segment_cb(model, UNSELECTED, segment)) if tab == "pd" \
        else (lambda model, segment: segment_cb(model, segment))

    models = model_names(tab)
    assert models, tab
    for model in models:
        options, value = call(model, UNSELECTED)
        assert value == UNSELECTED, (
            f"{tab}/{model}: picking a Model answered Segment with {value!r}"
        )
        # ... but the options are still narrowed to that model's own segments.
        assert options[0]["value"] == UNSELECTED, f"{tab}/{model}: no placeholder"

    # A segment the user already picked survives the model change if still valid.
    options, _v = call(models[0], UNSELECTED)
    real = [o["value"] for o in options if o["value"] != UNSELECTED]
    assert real, f"{tab}: {models[0]} offered no real segment to re-check"
    _options, kept = call(models[0], real[0])
    assert kept == real[0], f"{tab}: a valid Segment pick was discarded"


# --- Model search -----------------------------------------------------------

def _all_ids(module, tab):
    """Every element id in a tab's rendered bar (pattern ids excluded)."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA

    if module is pd_layout:
        roots = [module.build_global_filters(PD_PERFORMANCE_DATA)]
    elif module is overview_layout:
        roots = module.page_layout(PD_PERFORMANCE_DATA)
    elif hasattr(module, "build_layout"):
        roots = module.build_layout()
    else:
        roots = module.page_layout()

    out = set()
    for root in roots:
        if not isinstance(root, Component):
            continue
        for node in _walk(root):
            element_id = getattr(node, "id", None)
            if isinstance(element_id, str):
                out.add(element_id)
    return out


def _model_search_id(tab):
    from STATpy_platform.shared.ui import controls as pd_controls

    if tab == "pd":
        return pd_controls.MODELS_SEARCH_ID
    return {"lgd": lgd_layout, "ead": ead_layout, "loss": loss_layout}[tab].MODEL_SEARCH_ID


@pytest.mark.parametrize("name,module,tab", [t for t in TABS if t[2] != "overview"])
def test_the_model_menu_is_searchable(name, module, tab):
    """These tabs select one model out of a list that can get long, so the menu
    carries a search box -- the same "Type to search models…" affordance the
    SAAS and Overview checklists have."""
    assert _model_search_id(tab) in _all_ids(module, tab), name


@pytest.mark.parametrize("name,module,tab", [t for t in TABS if t[2] != "overview"])
def test_the_search_box_survives_a_menu_rebuild(name, module, tab):
    """The shell callback rewrites the menu on every value/options change. If
    the input were a child of what it rewrites it would be destroyed on each
    keystroke, losing focus and text -- so the option buttons live in their own
    container and *that* is what gets rewritten."""
    from STATpy_platform.shared.ui import controls as pd_controls

    menu_id = (pd_controls.MODELS_MENU_ID if tab == "pd"
               else {"lgd": lgd_layout, "ead": ead_layout, "loss": loss_layout}[tab].MODEL_MENU_ID)
    ids = _all_ids(module, tab)
    assert pd_controls.single_select_option_list_id(menu_id) in ids, name
    assert _model_search_id(tab) in ids, name


@pytest.mark.parametrize("name,module,tab", [t for t in TABS if t[2] != "overview"])
def test_no_other_filter_gets_a_search_box(name, module, tab):
    """One search box, on Model. A search on Scenario or Segment would be noise."""
    searches = {i for i in _all_ids(module, tab) if i.endswith("-search")}
    assert searches == {_model_search_id(tab)}, f"{name}: {sorted(searches)}"


def test_only_the_model_menu_is_searchable():
    """A search box on every filter would be noise. Scenario, Segment and the
    rest keep the plain menu."""
    from STATpy_platform.features.monitoring.ui import common as filter_shell

    assert filter_shell.filter_options_by_search(
        [{"label": "PD Model A", "value": "PD Model A"},
         {"label": "PD Corp Model", "value": "PD Corp Model"}], "corp",
    ) == [{"label": "PD Corp Model", "value": "PD Corp Model"}]
    # Empty search is a no-op, never an empty list.
    assert len(filter_shell.filter_options_by_search([{"label": "x", "value": "x"}], "")) == 1


def test_search_hides_options_but_the_toggle_still_names_the_selection():
    """The label resolves against the *full* option list, so a selected model
    filtered out of view still reads back -- the same rule the SAAS and Overview
    checklists follow."""
    from STATpy_platform.features.monitoring.ui import common as filter_shell

    options = [{"label": "PD Corp Model", "value": "PD Corp Model"},
               {"label": "PD Model F", "value": "PD Model F"}]
    label, buttons = filter_shell.build_single_select_shell(
        options=options, value="PD Corp Model", filter_key="specific-models", search="model f",
    )
    assert label == "PD Corp Model"
    assert len(buttons) == 1
