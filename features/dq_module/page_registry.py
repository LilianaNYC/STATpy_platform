"""Page registry for the DQ Wholesale dashboard."""
from __future__ import annotations

from ...shared.types import PageDefinition
from .pages.overview import callbacks as overview_cb, page as overview_page
from .pages.schema import callbacks as schema_cb, page as schema_page
from .pages.completeness import callbacks as completeness_cb, page as completeness_page
from .pages.rules import callbacks as rules_cb, page as rules_page
from .pages.population import callbacks as population_cb, page as population_page
from .pages.balance import callbacks as balance_cb, page as balance_page
from .pages.drift import callbacks as drift_cb, page as drift_page
from .pages.timeseries import callbacks as timeseries_cb, page as timeseries_page

PAGES: tuple[PageDefinition, ...] = (
    PageDefinition(key="overview", label="Overview", path="/dq-overview", icon="\U0001f4cb",
                   build_layout=overview_page.page_layout,
                   register_callbacks=overview_cb.register_callbacks),
    PageDefinition(key="schema", label="Schema", path="/dq-schema", icon="\U0001f5c4",
                   build_layout=schema_page.page_layout,
                   register_callbacks=schema_cb.register_callbacks),
    PageDefinition(key="completeness", label="Completeness", path="/dq-completeness", icon="\u2705",
                   build_layout=completeness_page.page_layout,
                   register_callbacks=completeness_cb.register_callbacks),
    PageDefinition(key="rules", label="Business Rules", path="/dq-rules", icon="\u2696",
                   build_layout=rules_page.page_layout,
                   register_callbacks=rules_cb.register_callbacks),
    PageDefinition(key="population", label="Population", path="/dq-population", icon="\U0001f465",
                   build_layout=population_page.page_layout,
                   register_callbacks=population_cb.register_callbacks),
    PageDefinition(key="balance", label="Balance & Composition", path="/dq-balance", icon="\U0001f4cb",
                   build_layout=balance_page.page_layout,
                   register_callbacks=balance_cb.register_callbacks),
    PageDefinition(key="drift", label="Distribution Drift", path="/dq-drift", icon="\U0001f4c8",
                   build_layout=drift_page.page_layout,
                   register_callbacks=drift_cb.register_callbacks),
    PageDefinition(key="timeseries", label="Time Series", path="/dq-timeseries", icon="\U0001f4c5",
                   build_layout=timeseries_page.page_layout,
                   register_callbacks=timeseries_cb.register_callbacks),
)
