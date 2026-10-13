"""The Scenario filter lives in MEV Range, not the top bar.

Scenario only ever drove the MEV Range section -- not Sensitivity Analysis, and
not Scenario Ranking, which has its own in-section picker -- so it moved into
that section's display-filter row on PD, LGD and EAD. Loss has no MEV Range
section at all and keeps its bar control.

Three things have to hold for the moved control to work, and each of them fails
*silently* if broken, which is why they are pinned here rather than left to the
browser:

* the control must survive ``build_section_filter_item``'s child-splicing with
  its ``<label>`` intact;
* its id must be pattern-matching, or the callback's Input cannot be gathered
  before the section exists and the callback body never runs (rule 3);
* the store it writes must live outside the content container, or each
  re-render resets the pick.
"""

from __future__ import annotations

import importlib
import inspect

import pytest
from dash import dcc, html

from STATpy_platform.shared.ui.controls import (
    build_mev_scenario_control,
    build_section_filter_item,
)

TABS = [("pd", "pd-mev-scenario"), ("lgd", "lgd-mev-scenario"), ("ead", "ead-mev-scenario")]


def _view(tab):
    return importlib.import_module(
        f"STATpy_platform.features.monitoring.ui.views.{tab}_performance"
    )


def _callbacks(tab):
    return importlib.import_module(
        f"STATpy_platform.features.monitoring.callbacks.{tab}_performance"
    )


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "children") or hasattr(child, "id"):
            yield from _walk(child)


# --- the control's own shape ----------------------------------------------

def test_the_control_keeps_its_label_through_the_row_merge():
    """The trap. ``build_section_filter_item`` merges ``extra_controls`` by
    splicing in its *children*, so a bare ``html.Label`` is unwrapped away and
    renders as a stray caption beside an unlabelled dropdown -- no error, just a
    control that no longer reads as "Scenario". The wrapper Div is what makes
    the merge a no-op on the label itself.
    """
    control = build_mev_scenario_control(
        {}, id_type="pd-mev-scenario", scenario="baseline", reporting_cycle="CCAR 2026",
    )
    item = build_section_filter_item(
        "Display filters", range_key="mev", periods=["2025-Q1"], extra_controls=control,
    )

    labels = [n for n in _walk(item) if isinstance(n, html.Label)]
    captions = [n.children[0].children for n in labels if isinstance(n.children, list)]
    assert "Scenario" in captions, f"Scenario lost its label: {captions}"

    # and it shares the one range row with Window/From/To rather than sitting in
    # a row of its own
    rows = [n for n in _walk(item)
            if isinstance(n, html.Div) and n.className == "pd-range-controls"]
    assert len(rows) == 1, f"{len(rows)} range rows -- the merge did not happen"
    assert captions[:1] == ["Scenario"], "Scenario should read first in the row"


def test_the_id_is_pattern_matching():
    """A plain id would make the renderer fail to gather the Input on the first
    render, before the section exists -- and the callback body would never run
    (callback rule 3).
    """
    control = build_mev_scenario_control(
        {}, id_type="pd-mev-scenario", scenario=None, reporting_cycle=None,
    )
    dropdown = next(n for n in _walk(control) if isinstance(n, dcc.Dropdown))
    assert dropdown.id == {"type": "pd-mev-scenario", "key": "mev"}


def test_options_are_narrowed_to_the_cycles_the_mev_sheet_covers():
    """Carried over from the bar control's ``sync_*_cycle_to_scenario_options``:
    offering a scenario the sheet has no rows for is a dead end."""
    data = {"mev_scenarios_by_cycle": {"CCAR 2026": ["baseline"]}}
    control = build_mev_scenario_control(
        data, id_type="pd-mev-scenario", scenario="intsevere", reporting_cycle="CCAR 2026",
    )
    dropdown = next(n for n in _walk(control) if isinstance(n, dcc.Dropdown))
    assert [o["value"] for o in dropdown.options] == ["baseline"]
    # "intsevere" is no longer on offer, so the value must not stay on it
    assert dropdown.value == "baseline"


def test_a_cycle_the_sheet_does_not_cover_falls_back_to_the_full_list():
    """CECL cycles have no scenario-sheet rows at all. Narrowing to nothing
    would leave the section with an empty picker."""
    data = {"mev_scenarios_by_cycle": {"CCAR 2026": ["baseline"]}}
    control = build_mev_scenario_control(
        data, id_type="pd-mev-scenario", scenario=None, reporting_cycle="CECL 2026",
    )
    dropdown = next(n for n in _walk(control) if isinstance(n, dcc.Dropdown))
    assert len(dropdown.options) > 1


# --- per-tab wiring --------------------------------------------------------

@pytest.mark.parametrize("tab,id_type", TABS)
def test_the_tab_renders_it_in_the_mev_range_section(tab, id_type):
    view = _view(tab)
    assert view.MEV_SCENARIO_ID == id_type
    source = inspect.getsource(view)
    assert "build_mev_scenario_control(" in source, f"{tab} does not render the control"
    # ... and no longer builds a bar cell for it
    assert "SCENARIO_ID = " not in source.replace("MEV_SCENARIO_ID = ", ""), \
        f"{tab} still has a top-bar Scenario id"


@pytest.mark.parametrize("tab,id_type", TABS)
def test_the_store_lives_outside_the_content_container(tab, id_type):
    """A store rendered *inside* the content container would be reset to its
    default by the very re-render the pick triggers.

    The two dashboards put their shell-level stores in different places -- PD in
    ``build_stores`` (which survives navigation), LGD/EAD in ``page_layout``
    (rebuilt fresh on each navigation, see the note on their master render) --
    so this asserts the store sits beside ``RANGE_STORE_ID``, whose own live
    Window/From/To controls already prove that placement works.
    """
    view = _view(tab)
    source = inspect.getsource(view.build_stores if hasattr(view, "build_stores") else view.page_layout)
    assert "dcc.Store(id=SCENARIO_STORE_ID" in source
    assert "dcc.Store(id=RANGE_STORE_ID" in source


@pytest.mark.parametrize("tab,id_type", TABS)
def test_the_picker_writes_the_store_and_the_render_reads_it(tab, id_type):
    source = inspect.getsource(_callbacks(tab).register_callbacks)

    assert f'Output(layout.SCENARIO_STORE_ID, "data")' in source
    assert '{"type": layout.MEV_SCENARIO_ID, "key": ALL}' in source
    # read as an Input, not State: that is what makes the section re-render
    # live, the same way the Window/From/To controls beside it do
    assert 'Input(layout.SCENARIO_STORE_ID, "data")' in source
    # the pick must win over the applied scope, which Apply no longer snapshots
    assert "scenario_store or applied.get(\"scenario\")" in source

    # the bar must not gate Apply on a filter it no longer shows
    gate = source.split('Output(layout.APPLY_FILTERS_ID, "disabled")')[1].split("def ")[0]
    assert "SCENARIO_ID" not in gate


@pytest.mark.parametrize("tab,id_type", TABS)
def test_the_review_flow_write_back_persists_the_pick_not_the_stale_scope(tab, id_type):
    """Saving a review writes the scenario in effect into portfolio.xlsx so
    Overview can look up the scenario a row was reviewed under. Now that the
    control changes without Apply, reading the applied scope would persist a
    stale value.
    """
    source = inspect.getsource(_callbacks(tab).register_callbacks)
    save = source.split(f"def save_{tab}_review_flow_rag_changes")[1]
    assert "scenario_store or (applied or {}).get(\"scenario\")" in save


def test_loss_has_no_scenario_control_at_all():
    """Loss has no MEV Range section, so there was nowhere to move it to -- it
    was removed outright instead. Neither the bar id nor the in-section id
    should exist there; see test_no_tab_has_a_scenario_filter_in_its_bar.
    """
    loss = _view("loss")
    assert not hasattr(loss, "SCENARIO_ID")
    assert not hasattr(loss, "MEV_SCENARIO_ID")


# --- which scenario a page opens on ---------------------------------------

def test_the_default_is_the_severe_scenario_not_whatever_sorts_first():
    """``scenarios`` is alphabetical, so ``[0]`` meant "baseline" by accident of
    the alphabet. Monitoring is a stress dashboard: the severe scenario is the
    one to land on, and the MEV figure builders already defaulted to it.
    """
    from STATpy_platform.shared.repositories import filters_config

    assert filters_config.default_scenario() == "intsevere"
    # ... and it is a real workbook value, not a name only this module knows
    values = [o["value"] for o in filters_config.load_filter_config()["scenarios"]]
    assert "intsevere" in values
    assert values[0] == "baseline", "the option list stays alphabetical; only the default moved"


def test_the_default_degrades_to_a_real_value_if_the_data_lacks_it():
    """The options come from the MEV workbook. A data set without "intsevere"
    must still open on something the figures can resolve rather than on a dead
    value -- which would render an empty chart, not an error.
    """
    from STATpy_platform.shared.repositories import filters_config

    config = dict(filters_config.load_filter_config())
    config["scenarios"] = [{"value": "adverse", "label": "adverse"}]
    original = filters_config.load_filter_config
    filters_config.load_filter_config = lambda: config
    try:
        assert filters_config.default_scenario() == "adverse"
    finally:
        filters_config.load_filter_config = original


def test_the_control_opens_on_the_default():
    from STATpy_platform.shared.repositories.filters_config import default_scenario

    control = build_mev_scenario_control(
        {}, id_type="pd-mev-scenario", scenario=None, reporting_cycle="CCAR 2026",
    )
    dropdown = next(n for n in _walk(control) if isinstance(n, dcc.Dropdown))
    assert dropdown.value == default_scenario()


def test_every_fallback_goes_through_the_one_helper():
    """The drift risk. Overview falls back for rows with no saved scenario and
    the performance tabs for a scope that has not picked one; if those two
    disagreed, a deep link from an Overview escalation card would render under a
    different scenario than the RAG on the card was computed under.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3]
    offenders = []
    callers = []
    for path in sorted(root.rglob("*.py")):
        if ".venv" in path.parts or path.resolve() == pathlib.Path(__file__).resolve():
            continue
        text = path.read_text()
        if '"scenarios"][0]' in text or "'scenarios'][0]" in text:
            offenders.append(str(path.relative_to(root)))
        if "default_scenario()" in text:
            callers.append(str(path.relative_to(root)))

    # Not a vacuous scan: the sites that used to derive it by position are the
    # ones that must now call the helper.
    assert len(callers) >= 5, f"the scan found almost nothing -- is it looking in the right place? {callers}"

    assert not offenders, (
        "these derive the default scenario by position instead of calling "
        f"filters_config.default_scenario(): {offenders}"
    )
