"""Smoke test for the PD Performance page: the layout builds without raising."""

from __future__ import annotations

from STATpy_platform.features.monitoring.pages.pd_performance import page


def test_pd_performance_layout_builds():
    layout = page.build_layout()
    assert isinstance(layout, list) and layout


def test_pd_performance_build_stores():
    stores = page.build_stores()
    assert {store.id for store in stores} == {
        "pd-range-store",
        "pd-trend-horizon-store",
        "pd-mev-filter-store",
    }
