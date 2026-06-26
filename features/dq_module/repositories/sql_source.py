"""SQL portfolio source — reuses STATpy's root data_manager (the DB gateway).

Only callable inside the STATpy repo on the Windows machine, where the root
`data_manager.py` and its SQL Server LocalDB connection live. On the Mac,
data.source stays 'excel' and this module is never executed (the STATpy import
below is deferred inside the function for exactly that reason).

Finalized on Windows (Phase 7 of the integration runbook): confirm the
DataManager subclass + constructor args against the real Dash/data_manager.py.
Everything else is insulated behind fetch_portfolio().
"""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)


def fetch_portfolio(cfg: dict, key: str) -> pd.DataFrame:
    """Fetch one portfolio snapshot table from SQL Server via STATpy's gateway.

    `key` is "portfolio" or "portfolio_2024" — selects the query from
    cfg["data"]["sql"][f"{key}_query"]. Returns the raw DataFrame (the caller
    normalizes it); column names must match the schema workbook after the
    optional column_map renames.
    """
    # STATpy ROOT module — resolves because the import root is Dash/.
    from data_manager import JumpoffDataManager  # noqa: deferred on purpose

    sql_cfg = cfg["data"]["sql"]
    query = sql_cfg[f"{key}_query"]
    log.info("Fetching %s from SQL database %s", key, sql_cfg["database"])

    dm = JumpoffDataManager(sql_cfg["database"], sql_cfg.get("table_label", "Jumpoff"))
    df = dm.get_data_from_sql(query)
    log.info("Fetched %d rows × %d columns", len(df), len(df.columns))

    rename = sql_cfg.get("column_map") or {}
    if rename:
        df = df.rename(columns=rename)

    _check_expected_columns(df, cfg)
    return df


def _check_expected_columns(df: pd.DataFrame, cfg: dict) -> None:
    """Fail fast at ingestion if the SQL result is missing columns the
    pipeline depends on — far clearer than a KeyError deep in processor.py."""
    data_cfg = cfg["data"]
    expected = [
        data_cfg["date_column"],
        data_cfg["facility_id_column"],
        data_cfg["instrument_id_column"],
        *cfg.get("completeness", {}).get("critical_columns", []),
    ]
    missing = sorted({c for c in expected if c not in df.columns})
    if missing:
        raise ValueError(
            "SQL result is missing expected columns (add renames to "
            f"data.sql.column_map in config.yaml?): {missing}"
        )
