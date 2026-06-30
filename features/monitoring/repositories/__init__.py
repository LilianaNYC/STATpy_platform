"""Persistence + external-system access (portfolio workbook, MEV catalog).

The ``Filters`` sheet reader (``filters_config``) lives in the dedicated
``shared/repositories/`` package instead of here -- it's read by the shared
``shared.ui.controls`` module, which both the monitoring and SAAS
dashboards depend on. See ``shared/repositories/__init__.py`` for the full
reasoning.
"""
