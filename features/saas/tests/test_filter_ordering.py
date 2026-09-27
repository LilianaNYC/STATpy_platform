"""SAAS's filter bar follows the same ordering rule as the monitoring tabs.

Text A-Z, cycles most-recent-first. The **mode selectors** are deliberately
exempt: Snapshot Period, Reference Lines, MEV Label and Historical Statistics
list modes, not data values, and their order carries meaning ("History ->
Projection -> History & Projection", "Off -> On") that alphabetizing destroys.
"""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.saas.ui.views import workspace as layout
from STATpy_platform.shared.domain.filter_order import alphabetical, composite_cycles_newest_first

# Sentinels that head a list rather than sorting into it. "Select ..." is the
# unanswered placeholder the Scope row opens on; "All" and "None" are real
# answers that stay pinned at the head of their list.
SENTINEL_LABELS = {"All", "None"}


def _is_sentinel(label: str) -> bool:
    return label in SENTINEL_LABELS or label.startswith("Select ")

# Filters whose values are modes, not data -- their order is their meaning.
MODE_FILTERS = {"Snapshot Period", "Reference Lines", "MEV Label", "Historical Statistics"}

# Compare To is labelled with the composite; Reporting Cycle is labelled with
# the bare cycle but *valued* with the composite, so it is checked on values.
COMPOSITE_LABEL_FILTERS = {"Compare To"}


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in (children if isinstance(children, (list, tuple)) else [children]):
        if isinstance(child, Component):
            yield from _walk(child)


def _labelled_filters():
    found: dict[str, list[str]] = {}
    for root in layout.page_layout():
        if not isinstance(root, Component):
            continue
        for node in _walk(root):
            if "monitoring-filter" not in (getattr(node, "className", None) or "").split():
                continue
            cell = list(_walk(node))
            label = next((n.children for n in cell
                          if type(n).__name__ == "Label" and isinstance(n.children, str)), None)
            if label is None or label in found:
                continue
            options = next((getattr(n, "options", None) for n in cell
                            if getattr(n, "options", None)), None)
            if options:
                found[label] = [
                    (o["label"], o["value"]) if isinstance(o, dict) else (str(o), str(o))
                    for o in options
                ]
    return found


def _labels(pairs):
    return [label for label, _v in pairs if not _is_sentinel(label)]


def _values(pairs):
    return [value for label, value in pairs if not _is_sentinel(label)]


def test_the_scan_actually_finds_the_bar():
    """Without this the checks below would pass on an empty dict."""
    found = _labelled_filters()
    assert "Region" in found and "Reporting Cycle" in found, sorted(found)


def test_value_filters_are_alphabetical():
    wrong = []
    for label, pairs in _labelled_filters().items():
        if label in MODE_FILTERS or label in COMPOSITE_LABEL_FILTERS:
            continue
        if label == "Reporting Cycle":
            continue  # periods, checked below
        labels = _labels(pairs)
        if len(labels) < 2:
            continue
        if labels != alphabetical(labels):
            wrong.append(f"{label}: {labels}")
    assert not wrong, "; ".join(wrong)


def test_cycle_filters_read_most_recent_first():
    found = _labelled_filters()
    # Compare To carries composite labels ...
    for label in COMPOSITE_LABEL_FILTERS:
        labels = _labels(found.get(label, []))
        assert labels == composite_cycles_newest_first(labels), f"{label}: {labels}"
    # ... while Reporting Cycle shows the bare cycle and keeps the composite as
    # its value, so its order is checked on the values.
    values = _values(found["Reporting Cycle"])
    assert values == composite_cycles_newest_first(values), values


def test_the_cycle_filter_labels_bare_but_values_composite():
    """The composite is the join key behind the applied store, Compare To and
    every export, so only the label may become the bare cycle."""
    for label, value in _labelled_filters()["Reporting Cycle"]:
        if _is_sentinel(label):
            continue
        assert " " in value, f"{value!r} is not a composite"
        assert label == value.split(" ", 1)[1], (label, value)


def test_mode_selectors_keep_their_meaningful_order():
    """Guards the exemption: these must not be swept into the alphabetizing."""
    found = _labelled_filters()
    assert _labels(found["Snapshot Period"]) == ["History", "Projection", "History & Projection"]
    assert _labels(found["Historical Statistics"]) == ["Off", "On"]


def test_the_dynamically_rebuilt_model_options_are_also_alphabetical():
    """The Model checklist is repopulated by a callback through
    ``selectors.model_options_for_filters``, not by the static layout above --
    so the layout-only checks miss it. Left in workbook order it interleaved the
    groups: "PD Model A, EAD Model A, LGD Model A, PD Model B, ...".
    """
    from STATpy_platform.features.saas.domain import selectors

    labels = [o["label"] for o in selectors.model_options_for_filters(None)]
    assert len(labels) > 2, labels
    assert labels == alphabetical(labels), labels


# --- the three-row arrangement ---------------------------------------------

def _row(class_name):
    for root in layout.page_layout():
        if not isinstance(root, Component):
            continue
        for node in _walk(root):
            if class_name in (getattr(node, "className", None) or "").split():
                return node
    return None


def test_the_bar_reads_as_scope_focus_view():
    """Scope (which data) over Focus (which models) over View (how it is drawn
    plus Apply) -- the monitoring tabs' Scope/Focus split, with a third row
    because SAAS carries presentation controls they do not have."""
    expected = {
        "saas-scope-filter-row": ("Scope", ["Region", "Portfolio", "Model Use Case", "Reporting Cycle"]),
        "saas-focus-filter-row": ("Focus", ["Model Group", "Model", "Segment"]),
        "saas-view-filter-row": ("View", ["Compare To", "Snapshot Period", "Reference Lines",
                                          "MEV Label", "Historical Statistics"]),
    }
    for class_name, (caption, labels) in expected.items():
        row = _row(class_name)
        assert row is not None, class_name
        first = row.children[0]
        assert getattr(first, "className", None) == "monitoring-filter-row-caption", class_name
        assert first.children == caption, (class_name, first.children)
        found = [n.children for n in _walk(row)
                 if type(n).__name__ == "Label" and isinstance(n.children, str)]
        assert found == labels, (class_name, found)


def test_apply_closes_the_view_row():
    """It used to close the Scope row. Moving it matches the monitoring tabs,
    where Apply follows the final filter rather than sitting mid-bar."""
    row = _row("saas-view-filter-row")
    ids = [getattr(n, "id", None) for n in _walk(row)]
    assert layout.APPLY_FILTERS_ID in ids
    assert layout.APPLY_FILTERS_ID not in [getattr(n, "id", None) for n in _walk(_row("saas-scope-filter-row"))]


def test_only_the_scope_row_opens_unanswered():
    """Scope is what Apply gates on. Focus and View keep their defaults: an
    all-models run is a normal SAAS analysis and MEV Label is presentation, so
    requiring them would be friction with no analytic meaning."""
    from STATpy_platform.shared.ui.controls import UNSELECTED

    for value in (layout.DEFAULT_REGION, layout.DEFAULT_PORTFOLIO,
                  layout.DEFAULT_MODEL_USE_CASE, layout.DEFAULT_RUN_FOR_VALUE):
        assert value == UNSELECTED
    assert layout.DEFAULT_MODEL_GROUP == layout.MODEL_GROUP_ALL_VALUE
    assert layout.DEFAULT_SEGMENT_VALUES
    assert layout.DEFAULT_SUBNAV_VIEW
    assert layout.DEFAULT_MEV_LABEL_MODE


def test_all_survives_as_a_real_answer_on_the_scope_row():
    """Unlike the monitoring tabs, "All" is a legitimate SAAS answer, so the
    placeholder and "All" must both be present and mean different things."""
    from STATpy_platform.shared.ui.controls import UNSELECTED

    for label, values in (("Region", layout.REGION_OPTIONS),
                          ("Portfolio", layout.PORTFOLIO_OPTIONS)):
        pairs = [(o["label"], o["value"]) for o in values]
        assert pairs[0][1] == UNSELECTED and pairs[0][0].startswith("Select "), label
        assert any(v not in (UNSELECTED,) and l == "All" for l, v in pairs), label
