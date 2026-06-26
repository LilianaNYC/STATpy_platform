"""YAML config loader and schema key-variable resolution."""

from __future__ import annotations

import yaml
from pathlib import Path

# Single source of truth for the bundled config.yaml location (it sits beside
# this module). services.metrics_service / report_service import CONFIG_PATH
# rather than each constructing the path — see the refactor's config.yaml risk.
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_config(path: str | Path = CONFIG_PATH) -> dict:
    """Load the dashboard config.yaml file (defaults to the bundled CONFIG_PATH)."""
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_key_vars(schema_df, df_columns) -> list[str]:
    """Return the list of schema variables flagged key_variable=Y that exist in df."""
    return [
        row["variable_name"] for _, row in schema_df.iterrows()
        if str(row.get("key_variable", "")).strip().upper() == "Y"
        and row["variable_name"] in df_columns
    ]
