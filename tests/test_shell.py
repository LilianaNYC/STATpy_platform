"""Shell-level tests for registry-driven sidebar navigation."""

from __future__ import annotations

from STATpy_platform import features_registry, shell


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children"):
                yield from _walk(child)
    elif hasattr(children, "children"):
        yield from _walk(children)


def test_sidebar_groups_pages_by_dashboard():
    sidebar = shell._build_sidebar()

    dashboard_titles = [
        component.children
        for component in _walk(sidebar)
        if getattr(component, "className", None) == "nav-group-title"
    ]
    page_hrefs = [
        component.href
        for component in _walk(sidebar)
        if isinstance(getattr(component, "id", None), dict) and component.id.get("type") == "nav-link"
    ]

    expected_dashboards = list(features_registry.iter_nav_dashboards())

    assert dashboard_titles == [dashboard.label for dashboard in expected_dashboards]
    assert page_hrefs == [page.path for dashboard in expected_dashboards for page in dashboard.iter_nav_pages()]


def test_sidebar_uses_page_counts_and_descriptive_nav_labels():
    sidebar = shell._build_sidebar()
    expected_dashboards = list(features_registry.iter_nav_dashboards())

    counts = [
        component.children
        for component in _walk(sidebar)
        if getattr(component, "className", None) == "nav-group-count"
    ]
    labels_by_href = {
        component.href: component.children[1].children
        for component in _walk(sidebar)
        if isinstance(getattr(component, "id", None), dict) and component.id.get("type") == "nav-link"
    }

    assert counts == [str(len(tuple(dashboard.iter_nav_pages()))) for dashboard in expected_dashboards]
    assert labels_by_href["/saas"] == "Workspace"


def test_sidebar_builds_a_collapsed_nav_group_for_each_dashboard():
    sidebar = shell._build_sidebar()
    expected_dashboards = list(features_registry.iter_nav_dashboards())

    groups = [
        component
        for component in _walk(sidebar)
        if isinstance(getattr(component, "id", None), dict)
        and component.id.get("type") == "dashboard-page-panel"
    ]

    assert [group.id["key"] for group in groups] == [dashboard.key for dashboard in expected_dashboards]
    # Every dashboard folder is collapsed on first launch.
    assert all(getattr(group, "open", False) is False for group in groups)
