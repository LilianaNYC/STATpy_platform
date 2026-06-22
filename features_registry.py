"""App-level registry of dashboards.

Single source of truth for the dashboards the app exposes. Navigation
(:mod:`shell`) and callback registration (:mod:`app`) iterate this list, so
onboarding a new dashboard is a one-line addition here -- no edits to several
unrelated central files.
"""

from __future__ import annotations

from .features.monitoring.dashboard import DASHBOARD as monitoring_dashboard
from .features.saas.dashboard import DASHBOARD as saas_dashboard
from .shared.types import DashboardDefinition, PageDefinition

# Order here is the order dashboards/pages appear in the sidebar.
DASHBOARDS: tuple[DashboardDefinition, ...] = (
    monitoring_dashboard,
    saas_dashboard,
)

# The dashboard whose metadata the shell surfaces in the sidebar/footer and
# whose landing page backs the root ("/") route.
PRIMARY_DASHBOARD = monitoring_dashboard


def iter_pages():
    """Yield every :class:`PageDefinition` across all dashboards."""
    for dashboard in DASHBOARDS:
        yield from dashboard.pages


def iter_nav_pages():
    """Yield every page that should appear as a sidebar nav link."""
    for dashboard in DASHBOARDS:
        yield from dashboard.iter_nav_pages()


def iter_nav_dashboards():
    """Yield dashboards that expose at least one sidebar nav page."""
    for dashboard in DASHBOARDS:
        if any(page.in_nav for page in dashboard.pages):
            yield dashboard


def dashboard_for_path(pathname: str | None) -> DashboardDefinition:
    """Return the dashboard that owns ``pathname`` or the primary dashboard."""
    for dashboard in DASHBOARDS:
        if any(page.path == pathname for page in dashboard.pages):
            return dashboard
    return PRIMARY_DASHBOARD


def page_builders() -> dict:
    """Map each page path to its no-arg layout builder."""
    return {page.path: page.build_layout for page in iter_pages()}
