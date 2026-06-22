"""Smoke test for the SAAS workspace page: the layout builds without raising."""

from __future__ import annotations

from STATpy_platform.features.saas.pages.workspace import page


def test_workspace_layout_builds():
    layout = page.page_layout()
    assert isinstance(layout, list) and layout
