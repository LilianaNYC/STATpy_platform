"""Unit tests for the SAAS workbook loader's derived structures."""

from __future__ import annotations

from STATpy_platform.features.saas.repositories.loader import load_saas_mev_workbook_data


def test_descriptive_groups_file_children_under_their_parent():
    data = load_saas_mev_workbook_data()
    groups = data["descriptive_groups"]
    descriptive_map = data["model_descriptive_name_map"]

    assert groups, "expected the workbook to yield at least one descriptive group"

    for parent, children in groups.items():
        assert children, f"parent {parent!r} has no children"
        # No duplicate children (multi-segment rows must not double-list a model).
        assert children == list(dict.fromkeys(children))
        # Every child files under the parent it resolves to: its Descriptive
        # Name when present, else its own Model Name (the singleton fallback).
        for child in children:
            assert (descriptive_map.get(child) or child) == parent


def test_descriptive_groups_collapse_the_collision_fixture():
    # The committed fixture deliberately gives two distinct Model Names one
    # shared Descriptive Name; they must surface as siblings under one parent.
    data = load_saas_mev_workbook_data()
    collisions = {parent: children for parent, children in data["descriptive_groups"].items() if len(children) > 1}
    assert collisions, "expected a descriptive-name collision in the fixture workbook"
