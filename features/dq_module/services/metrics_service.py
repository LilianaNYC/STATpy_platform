"""Wholesale Portfolio DQ Pipeline — build entry point.

CLI:  python -m dashboards.dq_wholesale.build [--config config.yaml] [--quarter 2025Q4] [--dry-run]

Importable: `run_build()` runs the full pipeline and returns a BuildResult —
this is what STATpy's "Refresh & open" callback calls. Top-level wiring pulls
data via `data_manager`, runs computation through `processor` + `callbacks/`,
then renders the dashboard via `renderer` (pages/ + components/).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..repositories.config_loader import load_config, CONFIG_PATH
from ..repositories.source_data import (
    load_portfolio,
    load_schema,
    get_quarters,
    get_quarter_df,
    source_label,
)
from .processor import process_all, compute_comparison_ts
from ..domain.metrics.schema import build_schema_diff
from ..domain.metrics.scorecard import build_scorecard
from .reporting.renderer import render_html
from ..repositories.artifacts import render_excel
from ..domain.validation import compute_drift, compute_psi

log = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = CONFIG_PATH                      # config.yaml now lives in repositories/
VENDOR_DIR = PACKAGE_DIR.parent / "_vendor"       # dead: 'local' asset mode unused in-platform
VENDOR_FILES = ["plotly-2.35.2.min.js", "html2pdf.bundle.min.js"]


@dataclass
class BuildResult:
    run_id: str            # output dir name, e.g. "20260610_152233" — used in URLs
    out_dir: Path
    html_filename: str
    target_quarter: str
    elapsed_s: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wholesale Portfolio DQ Pipeline")
    p.add_argument("--config",    default=None,            help=f"Path to config.yaml (default: {DEFAULT_CONFIG})")
    p.add_argument("--quarter",   default=None,            help="Target quarter (e.g. 2025Q4). Default: latest available.")
    p.add_argument("--dry-run",   action="store_true",     help="Validate inputs only; do not write output files.")
    p.add_argument("--log-level", default="INFO",          choices=["DEBUG","INFO","WARNING","ERROR"])
    return p.parse_args()


def make_output_dir(cfg: dict, base_dir: Path) -> Path:
    out_root = base_dir / cfg["output"]["directory"]
    if cfg["output"].get("versioned", True):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = out_root / ts
    else:
        out_dir = out_root / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _write_manifest(out_root: Path, run_dir_name: str, cfg: dict, target: str) -> None:
    """Atomically write output/manifest.json pointing at the latest successful run."""
    manifest = {
        "latest": run_dir_name,
        "html_filename": cfg["output"]["html_filename"],
        "completed_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": source_label(cfg),
        "target_quarter": target,
    }
    tmp = out_root / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(tmp, out_root / "manifest.json")


def _prune_old_runs(out_root: Path, keep_last_n: int) -> None:
    """Delete oldest versioned run dirs beyond keep_last_n (timestamp-named only)."""
    runs = sorted(d for d in out_root.iterdir()
                  if d.is_dir() and len(d.name) == 15 and d.name[8] == "_"
                  and d.name.replace("_", "").isdigit())
    for stale in runs[:-keep_last_n]:
        shutil.rmtree(stale, ignore_errors=True)
        log.info("Pruned old run: %s", stale.name)


def compute_full_metrics(df: pd.DataFrame,
                         df24: pd.DataFrame,
                         schema_df: pd.DataFrame,
                         cfg: dict,
                         run_id: str) -> dict:
    """Stages 2+3 — the complete metrics payload (the DASH_DATA contract).

    process_all + port24 comparison TS + scorecard + schema_diff + the four
    drift snapshots (yoy / historical / q1 / q2 incl. the cross-portfolio PSI
    heatmap). Single source of truth shared by run_build() and the live Dash
    app (dashboards/dq_wholesale_dash).
    """
    quarters = get_quarters(df)
    q24 = get_quarters(df24)

    metrics = process_all(df, schema_df, cfg, run_id)
    log.info("Processing port 2025 complete.")
    log.info("Processing port 2024 comparison time series...")
    port24_ts = compute_comparison_ts(df24, schema_df, cfg)
    metrics["port24"] = {"quarters": q24, "time_series": port24_ts}
    log.info("Computing port24 vs port25 scorecard...")
    sc_rows = build_scorecard(df, df24, schema_df, cfg)
    metrics["scorecard"] = {"rows": sc_rows, "quarter_24": "Q4 2024", "quarter_25": "Q4 2025"}
    metrics["schema_diff"] = build_schema_diff(df, df24, schema_df)

    # Drift test snapshots for mode-driven Statistical Tests section
    # (QoQ uses per-quarter precomputed drift; YoY and Historical need explicit pairs)
    p25_latest_q = quarters[-1]
    p24_latest_q = q24[-1]
    p25_first_q  = quarters[0]

    df_p25_latest = get_quarter_df(df,    p25_latest_q)
    df_p24_latest = get_quarter_df(df24,  p24_latest_q)
    df_p25_first  = get_quarter_df(df,    p25_first_q)

    # YoY: last quarter of P24 vs last quarter of P25 (cross-portfolio)
    metrics["drift_yoy"] = {
        "prior_q":      p24_latest_q,
        "current_q":    p25_latest_q,
        "prior_label":  "Port 2024",
        "current_label":"Port 2025",
        **compute_drift(df_p25_latest, df_p24_latest, cfg),
    }
    # Historical: first available Q of P25 vs latest Q of P25 (same portfolio, long span)
    metrics["drift_historical"] = {
        "prior_q":      p25_first_q,
        "current_q":    p25_latest_q,
        "prior_label":  "Port 2025",
        "current_label":"Port 2025",
        **compute_drift(df_p25_latest, df_p25_first, cfg),
    }

    # === Drift redesign: two-question data structure ===
    #   drift_q1 — within-portfolio (port25), full 5-test drift for last 12 Q vs Q-1
    #   drift_q2 — cross-portfolio (port24 vs port25), full 5-test drift for last 12
    #              shared Qs + PSI-only heatmap for all shared Qs (cheap fallback
    #              when the user opens the "all shared history" window)
    N_RECENT_DRIFT = 12

    # Q1: within port25, last N+1 Qs to make N pairs
    log.info("Computing drift_q1 (within-portfolio, last %d Qs)...", N_RECENT_DRIFT)
    q1_window = quarters[-(N_RECENT_DRIFT + 1):] if len(quarters) > N_RECENT_DRIFT else quarters
    drift_q1_by_q: dict[str, dict] = {}
    for i in range(1, len(q1_window)):
        q_cur = q1_window[i]
        q_prv = q1_window[i - 1]
        cur_i = get_quarter_df(df, q_cur)
        prv_i = get_quarter_df(df, q_prv)
        drift_q1_by_q[q_cur] = {"prior_q": q_prv, **compute_drift(cur_i, prv_i, cfg)}
    metrics["drift_q1"] = {
        "label": "Within-Portfolio Drift",
        "description": "Each quarter compared against the previous quarter of the same portfolio (Port 2025).",
        "all_quarters": list(quarters),
        "recent_quarters": sorted(drift_q1_by_q.keys()),
        "by_quarter": drift_q1_by_q,
    }

    # Q2: cross-portfolio (port25[Q] vs port24[Q]) — full drift for last 12 shared,
    # plus PSI-only heatmap for ALL shared Qs
    shared_qs = sorted(set(quarters) & set(q24))
    recent_shared = shared_qs[-N_RECENT_DRIFT:] if len(shared_qs) >= N_RECENT_DRIFT else shared_qs[:]
    log.info("Computing drift_q2 (cross-portfolio, %d recent + %d total shared Qs)...",
             len(recent_shared), len(shared_qs))
    drift_q2_by_q: dict[str, dict] = {}
    for q in recent_shared:
        df25q = get_quarter_df(df, q)
        df24q = get_quarter_df(df24, q)
        drift_q2_by_q[q] = {"prior_q": q, **compute_drift(df25q, df24q, cfg)}

    # PSI-only heatmap for all shared Qs (supports the 'all' window)
    numeric_cols_drift = cfg.get("drift", {}).get("numeric_columns", [])
    bins_drift = cfg.get("drift", {}).get("bins", 5)
    cross_psi_heatmap: dict[str, dict[str, float]] = {}
    for q in shared_qs:
        df25q = get_quarter_df(df, q)
        df24q = get_quarter_df(df24, q)
        for col in numeric_cols_drift:
            if col not in df25q.columns or col not in df24q.columns:
                continue
            s25 = pd.to_numeric(df25q[col], errors="coerce")
            s24 = pd.to_numeric(df24q[col], errors="coerce")
            cross_psi_heatmap.setdefault(col, {})[q] = compute_psi(s24, s25, bins_drift)

    metrics["drift_q2"] = {
        "label": "Cross-Portfolio Comparison",
        "description": "Each shared quarter compared between portfolios (Port 2025 vs Port 2024) — focus on deltas.",
        "shared_quarters": shared_qs,
        "recent_quarters": recent_shared,
        "by_quarter": drift_q2_by_q,
        "psi_heatmap": cross_psi_heatmap,
    }

    return metrics


def run_build(config_path: str | Path | None = None,
              quarter: str | None = None,
              dry_run: bool = False) -> BuildResult | None:
    """Run the full DQ pipeline. Returns BuildResult, or None for a dry run.

    Raises on any failure (bad quarter, missing file, …) — CLI and Dash
    callback callers handle/report the exception themselves.
    """
    t0 = time.perf_counter()
    config_path = Path(config_path) if config_path else DEFAULT_CONFIG
    base_dir = config_path.parent.resolve()
    log.info("Base directory: %s", base_dir)

    cfg = load_config(config_path)
    log.info("Config loaded from %s", config_path)

    # Stage 1 — Ingestion
    log.info("=== Stage 1: Ingestion ===")
    df = load_portfolio(cfg, base_dir)
    schema_df = load_schema(cfg, base_dir)
    quarters = get_quarters(df)
    log.info("Available quarters: %s … %s (%d total)", quarters[0], quarters[-1], len(quarters))

    # Load port 2024 for comparison
    df24 = load_portfolio(cfg, base_dir, key="portfolio_2024")
    q24 = get_quarters(df24)
    log.info("Port 2024 quarters: %s … %s (%d total)", q24[0], q24[-1], len(q24))

    if quarter:
        if quarter not in quarters:
            raise ValueError(f"Quarter {quarter} not found. Available: {quarters}")
        target = quarter
    else:
        target = quarters[-1]
    log.info("Target quarter: %s", target)

    if dry_run:
        log.info("DRY RUN — ingestion OK, skipping processing and output.")
        return None

    # Stage 2+3 — Validation & Processing (shared with the Dash app)
    log.info("=== Stage 2+3: Validation & Processing ===")
    run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
    metrics = compute_full_metrics(df, df24, schema_df, cfg, run_id)
    log.info("Processing complete. Run ID: %s", run_id)

    # Stage 4 — Output
    log.info("=== Stage 4: Rendering Outputs ===")
    out_dir = make_output_dir(cfg, base_dir)

    html_path = out_dir / cfg["output"]["html_filename"]
    html_content = render_html(metrics, cfg)
    html_path.write_text(html_content, encoding="utf-8")
    log.info("HTML dashboard written: %s  (%d KB)", html_path, len(html_content) // 1024)

    # asset_mode 'local': ship vendored JS next to the HTML so the run dir is
    # fully self-contained (no CDN — works offline, from file://, and via the
    # STATpy file route).
    if cfg.get("render", {}).get("asset_mode", "cdn") == "local":
        for name in VENDOR_FILES:
            src = VENDOR_DIR / name
            if not src.is_file():
                raise FileNotFoundError(
                    f"asset_mode is 'local' but {src} is missing — "
                    "restore dashboards/_vendor/ or switch render.asset_mode to 'cdn'"
                )
            shutil.copy2(src, out_dir / name)
        log.info("Vendored JS copied into run dir (%s)", ", ".join(VENDOR_FILES))

    xlsx_path = out_dir / cfg["output"]["excel_filename"]
    xlsx_bytes = render_excel(metrics)
    xlsx_path.write_bytes(xlsx_bytes)
    log.info("Excel report written:   %s  (%d KB)", xlsx_path, len(xlsx_bytes) // 1024)

    json_path = out_dir / "metrics.json"
    json_path.write_text(json.dumps(metrics, default=str, indent=2), encoding="utf-8")
    log.info("Metrics JSON written:   %s", json_path)

    _write_manifest(out_dir.parent, out_dir.name, cfg, target)
    keep_last_n = cfg["output"].get("keep_last_n")
    if keep_last_n:
        _prune_old_runs(out_dir.parent, int(keep_last_n))

    log.info("=== Pipeline Complete ===")
    log.info("Open: %s", html_path)
    return BuildResult(
        run_id=out_dir.name,
        out_dir=out_dir,
        html_filename=cfg["output"]["html_filename"],
        target_quarter=target,
        elapsed_s=time.perf_counter() - t0,
    )


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        run_build(args.config, args.quarter, args.dry_run)
        return 0
    except Exception as e:
        log.error("Build failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
