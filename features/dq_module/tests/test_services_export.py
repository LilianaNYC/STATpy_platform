"""Services + repositories — seed load and whole-dashboard exports."""

from STATpy_platform.features.dq_module.domain.grading import missing_bucket, MISSING_BUCKETS
from STATpy_platform.features.dq_module.repositories import results_store
from STATpy_platform.features.dq_module.services import report_service


def test_seed_loads():
    m = results_store.load_metrics()
    assert m.get("latest_quarter") and m.get("quarters")


def test_export_html_is_full_report():
    m = results_store.load_metrics()
    html = report_service.export_html(m)
    assert html.lstrip().startswith("<!DOCTYPE")
    assert "DASH_DATA" in html and "html2pdf" in html


def test_export_excel_is_xlsx():
    m = results_store.load_metrics()
    data = report_service.export_excel(m)
    assert isinstance(data, (bytes, bytearray)) and data[:2] == b"PK"


def test_seed_completeness_buckets_are_canonical():
    """Every column's missing_pct in the seed maps to one of the 4 buckets."""
    m = results_store.load_metrics()
    q = m["latest_quarter"]
    comp = ((m.get("by_quarter") or {}).get(q) or {}).get("completeness") or {}
    by_col = comp.get("by_column")
    cols = list(by_col.values()) if isinstance(by_col, dict) else (by_col or [])
    for c in cols:
        if isinstance(c, dict) and "missing_pct" in c:
            assert missing_bucket(c["missing_pct"]) in MISSING_BUCKETS
