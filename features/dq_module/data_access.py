"""Stable data interface for the DQ Wholesale dashboard.

Loads the prebuilt metrics payload once at import into :data:`DATA`. The
in-app "Update data" button calls :func:`recompute_into`, which re-runs the
bundled pipeline against the Excel in ``source_data/`` and swaps the result
into the dict IN PLACE, so every page/callback holding ``DATA`` sees the new
data without re-importing. :func:`get_app_meta` surfaces snapshot/run info for
the shell sidebar/footer.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from ...config.settings import settings

_HERE = Path(__file__).resolve().parent
_SEED = _HERE / "data_seed" / "metrics.json"
_PIPE_CONFIG = _HERE / "_pipeline" / "config.yaml"
_BUILD_LOCK = threading.Lock()

# Loaded once at import time; refreshed in place by recompute_into().
DATA: dict = json.loads(_SEED.read_text(encoding="utf-8"))


def get_metrics() -> dict:
    return DATA


def recompute_into(metrics: dict) -> str:
    """Rebuild from the Excel in source_data/ and swap into ``metrics`` in place."""
    with _BUILD_LOCK:
        fresh, run_id = _build_fresh()
    metrics.clear()
    metrics.update(fresh)
    _SEED.write_text(json.dumps(fresh, default=str, indent=2), encoding="utf-8")
    return run_id


def refresh() -> str:
    """Convenience: recompute the module-level DATA singleton."""
    return recompute_into(DATA)


def _build_fresh():
    from datetime import datetime

    from ._pipeline.build import compute_full_metrics
    from ._pipeline.config.load_config import load_config
    from ._pipeline.data_manager import load_portfolio, load_schema

    cfg = load_config(_PIPE_CONFIG)
    base = settings.source_data_dir           # the 3 Excel files live here
    df = load_portfolio(cfg, base)
    df24 = load_portfolio(cfg, base, key="portfolio_2024")
    schema_df = load_schema(cfg, base)
    run_id = f"DQ_{datetime.now():%Y%m%d_%H%M%S}"
    return compute_full_metrics(df, df24, schema_df, cfg, run_id), run_id


def get_app_meta() -> dict:
    """Sidebar/footer metadata the shell surfaces for this dashboard."""
    return {
        "latest_snapshot": DATA.get("data_as_of") or DATA.get("latest_quarter") or "\u2014",
        "last_refresh": DATA.get("last_refresh") or "\u2014",
        "source_file": DATA.get("source") or "\u2014",
        "run_id": DATA.get("run_id") or "DQ",
    }
