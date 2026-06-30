"""Shared dashboard-filter data layer.

Holds :mod:`filters_config` -- the ``Filters`` sheet reader that builds
dropdown options (reporting cycle, scenario, monitoring point, segment,
model). It's a dedicated top-level package (sibling to :mod:`data.analytics`
and :mod:`data.common`) rather than living inside a feature's
``repositories/`` package, because it's read by the shared
``components.filters`` module, which both the monitoring *and* SAAS
dashboards depend on -- the same "rule of two" that keeps
:mod:`data.analytics` in a shared location (see its docstring).

Feature-private data loading (the portfolio/MEV-catalog workbook reader, PD
performance observations, rating migration) lives in
``features/monitoring/repositories/`` instead.
"""
