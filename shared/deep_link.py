"""Query-string deep-linking shared by the app router and every Performance tab.

The Overview page's escalation cards link to a specific tab with ``?model=``/
``?segment=``/``?cycle=``/``?monitoring_point=``/``?scenario=`` query params
(see ``_esc_tab_href`` in ``features/monitoring/ui/views/overview.py``) so the
target tab can pre-populate its top filters and render that exact scope
immediately, instead of landing on the getting-started prompt and requiring
an extra "Apply filters" click.
"""

from __future__ import annotations

from urllib.parse import parse_qs

DEEP_LINK_KEYS = ("model", "segment", "cycle", "monitoring_point", "scenario")


def parse_deep_link_params(search: str | None) -> dict[str, str]:
    """Parse a ``dcc.Location`` "search" string (e.g. ``"?model=Foo&cycle=Bar"``)
    into a plain dict with only the recognized, non-empty keys."""
    if not search:
        return {}
    query = search.lstrip("?")
    if not query:
        return {}
    parsed = parse_qs(query)
    return {
        key: parsed[key][0]
        for key in DEEP_LINK_KEYS
        if parsed.get(key) and parsed[key][0]
    }
