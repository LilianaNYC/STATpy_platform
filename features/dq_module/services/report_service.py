"""Whole-dashboard export + recompute use-cases.

Orchestrates the reporting/repositories/domain layers so the root
``data_access`` facade (and through it the UI) never imports the pipeline
directly. Heavy compute is imported lazily inside ``compute_fresh`` so merely
importing this module (which happens at app import, via data_access) stays cheap.
"""

from __future__ import annotations

from datetime import datetime

from ..repositories.config_loader import load_config, CONFIG_PATH
from ..repositories.artifacts import render_excel
from .reporting.renderer import render_html


def export_html(metrics: dict) -> str:
    """Full self-contained HTML report (every tab). ``asset_mode`` is forced to
    ``cdn`` so the single downloaded file is portable (pulls plotly + html2pdf
    from CDN rather than expecting vendored siblings)."""
    cfg = dict(load_config(CONFIG_PATH) or {})
    cfg["render"] = {**(cfg.get("render") or {}), "asset_mode": "cdn"}
    return render_html(metrics, cfg)


def export_excel(metrics: dict) -> bytes:
    """Metrics workbook (.xlsx)."""
    return render_excel(metrics)


def compute_fresh(source_data_dir):
    """Recompute the full metrics payload from the source Excel in
    ``source_data_dir``. Returns ``(metrics, run_id)``. Imports the compute
    engine lazily so app import doesn't pull pandas/the full pipeline."""
    from .metrics_service import compute_full_metrics
    from ..repositories.source_data import load_portfolio, load_schema

    cfg = load_config(CONFIG_PATH)
    df = load_portfolio(cfg, source_data_dir)
    df24 = load_portfolio(cfg, source_data_dir, key="portfolio_2024")
    schema_df = load_schema(cfg, source_data_dir)
    run_id = f"DQ_{datetime.now():%Y%m%d_%H%M%S}"
    return compute_full_metrics(df, df24, schema_df, cfg, run_id), run_id
