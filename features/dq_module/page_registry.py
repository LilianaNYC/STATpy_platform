"""Page registry for the DQ Wholesale dashboard."""
from __future__ import annotations

from ...shared.types import PageDefinition
from .ui.pages import (
    overview as overview_page, schema as schema_page,
    completeness as completeness_page, rules as rules_page,
    population as population_page, balance as balance_page,
    drift as drift_page, timeseries as timeseries_page,
)
from .callbacks import (
    overview as overview_cb, schema as schema_cb,
    completeness as completeness_cb, rules as rules_cb,
    population as population_cb, balance as balance_cb,
    drift as drift_cb, timeseries as timeseries_cb,
)

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
