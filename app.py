"""Wholesale Portfolio DQ Pipeline — entry point.

CLI:  python app.py --config config.yaml [--quarter 2025Q4] [--dry-run]

This is the STATpy `app1.py` equivalent: top-level wiring that pulls data via
`data_manager`, runs computation through `processor` + `callbacks/`, then renders
the dashboard via `renderer` (pages/ + components/).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wholesale Portfolio DQ Pipeline")
    p.add_argument("--config",    default="config.yaml", help="Path to config.yaml")
    p.add_argument("--quarter",   default=None,           help="Target quarter (e.g. 2025Q4). Default: latest available.")
    p.add_argument("--dry-run",   action="store_true",    help="Validate inputs only; do not write output files.")
    p.add_argument("--log-level", default="INFO",         choices=["DEBUG","INFO","WARNING","ERROR"])
    return p.parse_args()


def make_output_dir(cfg: dict, base_dir: Path, dry_run: bool, run_timestamp: datetime):
    if dry_run:
        return None
    out_root = base_dir / cfg["output"]["directory"]
    if cfg["output"].get("versioned", True):
        run_date = run_timestamp.strftime("%Y%m%d")
        out_dir = out_root / run_date
    else:
        out_dir = out_root / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main() -> int:
    args = parse_args()
    logging.getLogger().setLevel(args.log_level)

    base_dir = Path(args.config).parent.resolve()
    log.info("Base directory: %s", base_dir)

    sys.path.insert(0, str(base_dir))

    from config.load_config import load_config
    from data_manager import load_portfolio, load_schema, get_quarters, load_monitoring_thresholds
    from processor import process_all, compute_comparison_ts, process_monitoring
    from callbacks.schema_callbacks import build_schema_diff
    from callbacks.scorecard_callbacks import build_scorecard
    from renderer import render_html
    from excel_export import render_excel

    cfg = load_config(args.config)
    log.info("Config loaded from %s", args.config)

    # Stage 1 — Ingestion
    log.info("=== Stage 1: Ingestion ===")
    df = load_portfolio(cfg, base_dir)

    is_monitoring = cfg.get("dashboard", {}).get("type") == "monitoring"
    monitoring_thresholds = None
    if is_monitoring:
        monitoring_thresholds = load_monitoring_thresholds(cfg, base_dir)
        
    schema_df = None
    if not is_monitoring:
        schema_df = load_schema(cfg, base_dir)
    
    quarters = get_quarters(df)
    log.info("Available quarters: %s … %s (%d total)", quarters[0], quarters[-1], len(quarters))

    # Load port 2024 for comparison
    cfg24 = dict(cfg, data=dict(cfg["data"], portfolio_file=cfg["data"].get("portfolio_2024_file", cfg["data"]["portfolio_file"])))
    df24 = load_portfolio(cfg24, base_dir)
    q24 = get_quarters(df24)
    log.info("Port 2024 quarters: %s … %s (%d total)", q24[0], q24[-1], len(q24))

    if args.quarter:
        if args.quarter not in quarters:
            log.error("Quarter %s not found. Available: %s", args.quarter, quarters)
            return 1
        target = args.quarter
    else:
        target = quarters[-1]
    log.info("Target quarter: %s", target)

    if args.dry_run:
        log.info("DRY RUN — ingestion OK, skipping processing and output.")
        return 0

    # Stage 2+3 — Validation & Processing
    log.info("=== Stage 2+3: Validation & Processing ===")
    run_timestamp = datetime.now()
    run_id = f"RUN_{run_timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
    if is_monitoring:
        metrics = process_monitoring(df, cfg, run_id, monitoring_thresholds)
    else:
        metrics = process_all(df, schema_df, cfg, run_id)
        metrics = process_all(df, schema_df, cfg, run_id)
        log.info("Processing port 2025 complete.")
        log.info("Processing port 2024 comparison time series...")
        port24_ts = compute_comparison_ts(df24, schema_df, cfg)
        metrics["port24"] = {"quarters": q24, "time_series": port24_ts}
        log.info("Computing port24 vs port25 scorecard...")
        sc_rows = build_scorecard(df, df24, schema_df, cfg)
        metrics["scorecard"] = {"rows": sc_rows, "quarter_24": "Q4 2024", "quarter_25": "Q4 2025"}
        metrics["schema_diff"] = build_schema_diff(df, df24)
        log.info("Processing complete. Run ID: %s", run_id)

    # Stage 4 — Output
    log.info("=== Stage 4: Rendering Outputs ===")
    out_dir = make_output_dir(cfg, base_dir, dry_run=False, run_timestamp=run_timestamp)

    html_path = out_dir / cfg["output"]["html_filename"]
    html_content = render_html(metrics, cfg)
    html_path.write_text(html_content, encoding="utf-8")
    log.info("HTML dashboard written: %s  (%d KB)", html_path, len(html_content) // 1024)

    if not is_monitoring:
        xlsx_path = out_dir / cfg["output"]["excel_filename"]
        xlsx_bytes = render_excel(metrics)
        xlsx_path.write_bytes(xlsx_bytes)
        log.info("Excel report written:   %s  (%d KB)", xlsx_path, len(xlsx_bytes) // 1024)

    json_filename = "monitoring_metrics.json" if is_monitoring else "metrics.json"
    json_path = out_dir / json_filename
    json_path.write_text(json.dumps(metrics, default=str, indent=2), encoding="utf-8")
    log.info("Metrics JSON written:   %s", json_path)

    log.info("=== Pipeline Complete ===")
    log.info("Open: %s", html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
