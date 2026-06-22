"""Smoke test for the EAD Performance page (placeholder)."""

from __future__ import annotations

from STATpy_platform.features.monitoring.pages.ead_performance import page


def test_ead_performance_layout_builds():
    layout = page.page_layout()
    assert isinstance(layout, list) and layout
