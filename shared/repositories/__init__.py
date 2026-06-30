"""Shared repository layer (cross-feature persistence/data access).

Holds :mod:`filters_config` -- the ``Filters`` sheet reader that builds
dropdown options (reporting cycle, scenario, monitoring point, segment,
model). Reading a workbook sheet is repository-layer work, but it lives here
(``shared/repositories/``) rather than inside a single feature's
``repositories/`` package because it's read by the shared
``shared.ui.controls`` module, which both the monitoring *and* SAAS
dashboards depend on -- the same "rule of two" that keeps
:mod:`shared.domain` in a shared location (see its docstring).

Feature-private data loading (the portfolio/MEV-catalog workbook reader, PD
performance observations, rating migration) lives in
``features/monitoring/repositories/`` instead.
"""
