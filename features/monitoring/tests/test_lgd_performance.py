"""Smoke test for the LGD Performance page (placeholder)."""

from __future__ import annotations

from STATpy_platform.features.monitoring.ui.views import lgd_performance as page


def test_lgd_performance_layout_builds():
    layout = page.build_layout()
    assert isinstance(layout, list) and layout
