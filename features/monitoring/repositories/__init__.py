"""Persistence + external-system access (portfolio workbook, MEV catalog).

The ``Filters`` sheet reader (``filters_config``) lives in the dedicated
``data/filters/`` package instead of here -- it's read by the shared
``components.filters`` module, which both the monitoring and SAAS
dashboards depend on. See ``data/filters/__init__.py`` for the full
reasoning.
"""
