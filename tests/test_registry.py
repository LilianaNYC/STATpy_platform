"""Registry-level tests: path uniqueness and reachability.

These are cheap, structure-aware checks that catch the most common mistakes
when adding a page or dashboard (duplicate routes, an unregistered page, a
missing root route).
"""

from __future__ import annotations

from STATpy_platform.features_registry import (
    DASHBOARDS,
    PRIMARY_DASHBOARD,
    dashboard_for_path,
    iter_nav_dashboards,
    iter_pages,
    page_builders,
)


def test_page_paths_are_unique_across_dashboards():
    paths = [page.path for page in iter_pages()]
    assert len(paths) == len(set(paths)), f"duplicate page paths: {paths}"


def test_every_page_is_reachable_from_app_registry():
    # Every page declared on a dashboard must be yielded by iter_pages().
    declared = {(d.key, p.key) for d in DASHBOARDS for p in d.pages}
    reachable = {
        (d.key, p.key)
        for d in DASHBOARDS
        for p in d.pages
        if p in set(iter_pages())
    }
    assert declared == reachable


def test_root_route_exists():
    assert "/" in page_builders()


def test_primary_dashboard_is_registered():
    assert PRIMARY_DASHBOARD in DASHBOARDS


def test_nav_dashboards_follow_registered_order():
    assert tuple(iter_nav_dashboards()) == DASHBOARDS


def test_dashboard_for_path_falls_back_to_primary_dashboard():
    assert dashboard_for_path("/missing-route") == PRIMARY_DASHBOARD


def test_page_definitions_have_callables():
    for page in iter_pages():
        assert callable(page.build_layout), page.key
        assert callable(page.register_callbacks), page.key
        assert page.path.startswith("/"), page.key
