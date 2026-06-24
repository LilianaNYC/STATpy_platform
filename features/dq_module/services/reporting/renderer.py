"""Thin HTML assembler — concatenates pages + components into one self-contained file.

This is the equivalent of `app1.py`'s layout wiring in STATpy: it knows nothing about
the metrics; it just stitches the static skeleton (components/) with the per-tab
JS modules (pages/) and the JSON payload.
"""

from __future__ import annotations

import json

from .components import styles, helpers_js, comparison_mode, layout
from .pages import (
    overview_page,
    schema_page,
    completeness_page,
    business_rules_page,
    population_page,
    drift_page,
    timeseries_page,
    summary_details_page,
)


# Tabs are wired in the order they appear in components.layout.TABS
PAGE_MODULES = [
    overview_page,
    schema_page,
    completeness_page,
    business_rules_page,
    population_page,
    summary_details_page,
    drift_page,
    timeseries_page,
]


def _script_tags(cfg: dict) -> str:
    """Plotly + html2pdf script tags. asset_mode 'local' expects the vendored
    files copied next to the HTML (build.py does this), so the run dir stays
    self-contained and works offline / from file://."""
    if cfg.get("render", {}).get("asset_mode", "cdn") == "local":
        return (
            '<script src="plotly-2.35.2.min.js"></script>\n'
            '<script src="html2pdf.bundle.min.js"></script>\n'
        )
    return (
        '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.2/html2pdf.bundle.min.js"></script>\n'
    )


def render_html(metrics: dict, cfg: dict) -> str:
    data_json = json.dumps(metrics, default=str, ensure_ascii=False)
    nav = layout.nav_html()
    panels = layout.tab_panels_html()
    dispatch = layout.dispatch_js()
    pages_js = "\n".join(p.JS for p in PAGE_MODULES)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>Wholesale Portfolio DQ Dashboard</title>\n"
        f"{_script_tags(cfg)}"
        f"<style>{styles.CSS}</style>\n"
        "</head>\n<body>\n"
        '<nav class="sidebar">\n'
        '  <div class="sidebar-logo">\n'
        '    <div class="logo-icon">📊</div>\n'
        "    <h1>DQ Monitor</h1>\n"
        "    <p>Wholesale Credit Platform</p>\n"
        "  </div>\n"
        f'  <ul class="nav-list">{nav}</ul>\n'
        '  <div class="sidebar-footer" id="sidebar-footer"></div>\n'
        "</nav>\n"
        '<div class="main">\n'
        '  <div class="top-bar">\n'
        '    <div style="flex:1">\n'
        '      <div style="font-size:14px;font-weight:700;color:#111">Wholesale Portfolio DQ Dashboard</div>\n'
        '      <div style="font-size:11px;color:#6b7280">Quarter pair selection now lives inside each tab\'s Comparison Mode bar</div>\n'
        "    </div>\n"
        '    <div class="export-menu-wrap">\n'
        '      <button class="btn btn-primary export-btn-main" id="export-btn" onclick="exportData()">📄 Export PDF</button>\n'
        '      <button class="export-btn-chevron" onclick="toggleExportMenu(event)" aria-label="More export options">▼</button>\n'
        '      <div class="export-menu" id="export-menu">\n'
        '        <div class="export-menu-item" onclick="event.stopPropagation();closeExportMenu();exportData()">\n'
        '          <span class="icon">📄</span>\n'
        '          <div><div class="label">Export current tab</div><div class="sub">Just the visible dashboard</div></div>\n'
        '        </div>\n'
        '        <div class="export-menu-item" onclick="event.stopPropagation();closeExportMenu();exportAllTabs()">\n'
        '          <span class="icon">📚</span>\n'
        '          <div><div class="label">Export all tabs</div><div class="sub">Full multi-page report (~30s)</div></div>\n'
        '        </div>\n'
        '      </div>\n'
        '    </div>\n'
        "  </div>\n"
        '  <div class="content">\n'
        f"    {panels}\n"
        "  </div>\n"
        '  <div class="page-footer">\n'
        '    <span id="footer-data-as-of"></span>\n'
        '    <span id="footer-source"></span>\n'
        '    <span id="footer-run-id"></span>\n'
        '    <span id="footer-refresh"></span>\n'
        "  </div>\n"
        "</div>\n"
        "<script>\n"
        f"const DASH_DATA = {data_json};\n"
        "let CQ = DASH_DATA.latest_quarter;\n"
        "let PQ = DASH_DATA.prior_quarter;\n"
        f"{helpers_js.JS}\n"
        f"{comparison_mode.JS}\n"
        f"{dispatch}\n"
        f"{pages_js}\n"
        f"{layout.INIT_JS}\n"
        "</script>\n"
        "</body>\n</html>\n"
    )
