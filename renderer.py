"""Thin HTML assembler — concatenates pages + components into one self-contained file.

This is the equivalent of `app1.py`'s layout wiring in STATpy: it knows nothing about
the metrics; it just stitches the static skeleton (components/) with the per-tab
JS modules (pages/) and the JSON payload.
"""

from __future__ import annotations

import json

from components import (
    comparison_mode,
    helpers_js,
    layout,
    monitoring_helpers_js,
    monitoring_layout,
    monitoring_style,
    styles,
)
from pages import (
    overview_page,
    governance_page,
    schema_page,
    completeness_page,
    business_rules_page,
    population_page,
    drift_page,
    scorecard_page,
    monitoring_overview_page,
    monitoring_ead_models_page,
    monitoring_lgd_models_page,
    monitoring_pd_models_page,
)


# Tabs are wired in the order they appear in their dashboard layout module.
PAGE_MODULES_BY_TYPE = {
    "dq": [
        overview_page,
        governance_page,
        schema_page,
        completeness_page,
        business_rules_page,
        population_page,
        drift_page,
        scorecard_page,
    ],
    "monitoring": [
        monitoring_overview_page,
        monitoring_pd_models_page,
        monitoring_lgd_models_page,
        monitoring_ead_models_page,
    ],
}


def render_html(metrics: dict, cfg: dict) -> str:
    data_json = json.dumps(metrics, default=str, ensure_ascii=False)
    dashboard_type = cfg.get("dashboard", {}).get("type", "dq")
    page_modules = PAGE_MODULES_BY_TYPE.get(dashboard_type, PAGE_MODULES_BY_TYPE["dq"])

    if dashboard_type == "monitoring":
        layout_module = monitoring_layout
        style_module = monitoring_style
        helpers_module = monitoring_helpers_js
        sidebar_title = monitoring_layout.SIDEBAR_TITLE
        top_title = monitoring_layout.TOP_TITLE
        top_bar_controls = monitoring_layout.TOP_BAR_CONTROLS_HTML
    else:
        layout_module = layout
        style_module = styles
        helpers_module = helpers_js
        sidebar_title = "DQ Monitor"
        top_title = "Wholesale Portfolio DQ Dashboard"
        top_bar_controls = ""

    nav = layout_module.nav_html()
    panels = layout_module.tab_panels_html()
    dispatch = layout_module.dispatch_js()
    pages_js = "\n".join(p.JS for p in page_modules)

    parts: list[str] = []
    parts.append("<!DOCTYPE html>\n")
    parts.append('<html lang="en">\n<head>\n')
    parts.append('<meta charset="UTF-8">\n')
    parts.append('<meta name="viewport" content="width=device-width,initial-scale=1">\n')
    parts.append(f"<title>{top_title}</title>\n")
    parts.append('<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>\n')
    parts.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.2/html2pdf.bundle.min.js"></script>\n')
    parts.append(f"<style>{style_module.CSS}</style>\n")
    parts.append("</head>\n<body>\n")

    parts.append('<nav class="sidebar">\n'
                 '  <div class="sidebar-logo">\n'
                 '    <div class="logo-icon">📊</div>\n')
    parts.append(f'    <h1>{sidebar_title}</h1>\n')
    parts.append("    <p>Wholesale Credit Platform</p>\n"
                 "  </div>\n")
    parts.append(f'  <ul class="nav-list">{nav}</ul>\n')
    parts.append('  <div class="sidebar-footer" id="sidebar-footer"></div>\n</nav>\n')

    parts.append('<div class="main">\n'
                 '  <div class="top-bar">\n'
                 '    <div style="flex:1">\n')
    parts.append(f'      <div style="font-size:14px;font-weight:700;color:#111">{top_title}</div>\n')
    parts.append(top_bar_controls)
    parts.append("    </div>\n")

    parts.append(
        '    <div class="monitoring-filter monitoring-export-filter">\n'
        '      <label aria-hidden="true">Export</label>\n'
        '      <div class="export-menu-wrap">\n'
        '        <button class="btn btn-primary export-btn-main" id="export-btn" onclick="exportData()">📄 Export PDF</button>\n'
        '        <button class="export-btn-chevron" onclick="toggleExportMenu(event)" aria-label="More export options">▼</button>\n'
        '        <div class="export-menu" id="export-menu">\n'
        '          <div class="export-menu-item" onclick="event.stopPropagation();closeExportMenu();exportData()">\n'
        '            <span class="icon">📄</span>\n'
        '            <div><div class="label">Export current tab</div><div class="sub">Just the visible dashboard</div></div>\n'
        '          </div>\n'
        '          <div class="export-menu-item" onclick="event.stopPropagation();closeExportMenu();exportAllTabs()">\n'
        '            <span class="icon">📚</span>\n'
        '            <div><div class="label">Export all tabs</div><div class="sub">Full multi-page report (~30s)</div></div>\n'
        '          </div>\n'
        '        </div>\n'
        '      </div>\n'
        '    </div>\n'
    )

    parts.append("  </div>\n")
    parts.append(f"  <div class=\"content\">\n    {panels}\n  </div>\n")
    parts.append('  <div class="page-footer">\n'
                 '    <span id="footer-data-as-of"></span>\n'
                 '    <span id="footer-source"></span>\n'
                 '    <span id="footer-run-id"></span>\n'
                 '    <span id="footer-refresh"></span>\n'
                 '  </div>\n'
                 '</div>\n')

    parts.append("<script>\n")
    parts.append("const DASH_DATA = " + data_json + ";\n")
    parts.append(f"const DASHBOARD_TYPE = '{dashboard_type}';\n")
    parts.append("let CQ = DASH_DATA.latest_quarter;\n")
    parts.append("let PQ = DASH_DATA.prior_quarter;\n")
    parts.append(helpers_module.JS + "\n")
    if dashboard_type != "monitoring":
        parts.append(comparison_mode.JS + "\n")
    parts.append(dispatch + "\n")
    parts.append(pages_js + "\n")
    parts.append(layout_module.INIT_JS + "\n")
    parts.append("</script>\n</body>\n</html>\n")

    return "".join(parts)
