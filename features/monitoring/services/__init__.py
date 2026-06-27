"""Application services for the monitoring dashboard.

Orchestration / use-case layer: loads the source snapshot via the shared
``data`` repositories, enriches it, and exposes it to ``data_access`` (the
in-memory bridge the UI and callbacks read).
"""
