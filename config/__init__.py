"""Centralised application configuration.

:mod:`config.settings` exposes a single, typed :data:`settings` object that is
built once at import time from the active environment (see
:mod:`config.environments`). Dashboards and data-access modules should read
configuration from :data:`config.settings.settings` rather than reading
``os.environ`` ad hoc.
"""
