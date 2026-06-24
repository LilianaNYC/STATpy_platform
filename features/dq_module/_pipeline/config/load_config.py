"""YAML config loader and schema key-variable resolution."""

from __future__ import annotations

import yaml
from pathlib import Path


def load_config(path: str | Path) -> dict:
    """Load the dashboard config.yaml file."""
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_key_vars(schema_df, df_columns) -> list[str]:
    """Return the list of schema variables flagged key_variable=Y that exist in df."""
    return [
        row["variable_name"] for _, row in schema_df.iterrows()
        if str(row.get("key_variable", "")).strip().upper() == "Y"
        and row["variable_name"] in df_columns
    ]
