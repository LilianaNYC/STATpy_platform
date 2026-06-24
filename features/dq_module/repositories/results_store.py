"""Read/write the prebuilt DQ metrics payload (the seed snapshot).

Today the canonical store is ``data_seed/metrics.json`` (a committed seed,
overwritten in place by an in-app recompute). When the SQL pipeline lands, a
results table can back these same two functions without touching callers.
"""

from __future__ import annotations

import json
from pathlib import Path

# data_seed/ sits at the feature root, one level above repositories/.
_SEED = Path(__file__).resolve().parents[1] / "data_seed" / "metrics.json"


def load_metrics() -> dict:
    """Load the current metrics payload."""
    return json.loads(_SEED.read_text(encoding="utf-8"))


def save_metrics(metrics: dict) -> None:
    """Persist a freshly computed metrics payload as the new seed."""
    _SEED.write_text(json.dumps(metrics, default=str, indent=2), encoding="utf-8")
