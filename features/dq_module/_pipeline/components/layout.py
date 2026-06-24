"""HTML skeleton + sidebar + tabs nav + global init (selectors, footer, switchTab).

The tab list is the single source of truth — drives the sidebar, the tab-panel
divs, and the JS dispatch table.
"""

# Order matters — sidebar items appear in this order, tab panels are emitted
# in this order, and the JS renderTab() dispatch is generated from this list.
TABS = [
    # (tab_id, label,                       icon,   render_fn_name)
    ("overview",     "Overview",            "📊",  "renderOverview"),
    ("schema",       "Schema",              "🗄️", "renderSchema"),
    ("completeness", "Completeness",        "✅",  "renderCompleteness"),
    ("rules",        "Business Rules & Gov.","⚖️", "renderRules"),
    ("population",   "Population",          "👥",  "renderPopulation"),
    ("summary_details","Summary Details",   "📋",  "renderSummaryDetails"),
    ("drift",        "Distribution Drift",  "📈",  "renderDrift"),
    ("timeseries",   "Time Series",         "📅",  "renderTimeseries"),
]


def nav_html() -> str:
    """Sidebar <li> items."""
    return "\n".join(
        f'<li class="nav-item" data-tab="{tid}" onclick="switchTab(\'{tid}\')">'
        f'<span class="nav-icon">{icon}</span><span class="nav-label">{label}</span></li>'
        for tid, label, icon, _ in TABS
    )


def tab_panels_html() -> str:
    """The empty <div> tab containers that each page fills in via JS."""
    panels = []
    for i, (tid, _, _, _) in enumerate(TABS):
        cls = "tab-panel active" if i == 0 else "tab-panel"
        panels.append(f'<div id="tab-{tid}" class="{cls}"></div>')
    return "\n    ".join(panels)


def dispatch_js() -> str:
    """JS dispatch table mapping tab_id → render function."""
    body = ",\n    ".join(f"{tid:<13}: {fn}" for tid, _, _, fn in TABS)
    return f"""
let activeTab = 'overview';
function switchTab(tabId) {{
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('tab-'+tabId).classList.add('active');
  document.querySelector(`[data-tab="${{tabId}}"]`).classList.add('active');
  activeTab = tabId;
  renderTab(tabId);
}}

function renderTab(tabId) {{
  const renders = {{
    {body}
  }};
  if (renders[tabId]) renders[tabId]();
}}
"""


INIT_JS = r"""
// ── Quarter selectors ──────────────────────────────────────────
// Global Snapshot/Compare dropdowns were removed from the top-bar.
// Each tab now renders its own selectors inside _modeBar() when CMP_MODE === 'qoq'.
function initSelectors() {
  // No-op kept for backwards compatibility with init() call order.
}
function setCurrentQuarter(q) { CQ=q; renderAll(); }
function setCompareQuarter(q) { PQ=q; renderAll(); }

// ── Footer & sidebar ───────────────────────────────────────────
function initFooter() {
  document.getElementById('footer-data-as-of').textContent = 'Data as of: '+DASH_DATA.data_as_of;
  document.getElementById('footer-source').textContent     = 'Source: '+DASH_DATA.source;
  document.getElementById('footer-run-id').textContent     = 'Run ID: '+DASH_DATA.run_id;
  document.getElementById('footer-refresh').textContent    = 'Last refresh: '+DASH_DATA.last_refresh;
  document.getElementById('sidebar-footer').innerHTML =
    `Data as of:<br>${DASH_DATA.data_as_of}<br><br>Last refresh:<br>${DASH_DATA.last_refresh}`;
}

function renderAll() { renderTab(activeTab); }

// ── PDF Export ─────────────────────────────────────────────────
// Capture the active tab as a high-resolution PDF using html2pdf
// (html2canvas + jsPDF). Interactive controls are hidden via the
// `.exporting-pdf` body class so the PDF shows just the dashboard.
const TAB_LABELS_FOR_PDF = {
  overview:     'Overview',
  schema:       'Schema',
  completeness: 'Completeness',
  rules:        'Business_Rules_Governance',
  population:   'Population',
  summary_details: 'Summary_Details',
  drift:        'Distribution_Drift',
  timeseries:   'Time_Series',
};

function _showExportOverlay(msg, sub) {
  let ov = document.getElementById('export-overlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'export-overlay';
    ov.className = 'export-overlay';
    ov.innerHTML = `<div class="export-overlay-card">
      <div class="spinner"></div>
      <div class="msg" id="export-overlay-msg">${msg}</div>
      <div class="sub" id="export-overlay-sub">${sub||''}</div>
    </div>`;
    document.body.appendChild(ov);
  } else {
    document.getElementById('export-overlay-msg').textContent = msg;
    document.getElementById('export-overlay-sub').textContent = sub||'';
  }
  ov.classList.add('active');
}
function _hideExportOverlay() {
  const ov = document.getElementById('export-overlay');
  if (ov) ov.classList.remove('active');
}

async function exportData() {
  if (typeof html2pdf === 'undefined') {
    alert('PDF library failed to load. Check your internet connection and reload the page.');
    return;
  }
  const tab = document.getElementById('tab-' + activeTab);
  if (!tab) return;

  const tabName = TAB_LABELS_FOR_PDF[activeTab] || activeTab;
  const filename = `DQ_Dashboard_${tabName}_${CQ}.pdf`;

  _showExportOverlay('Generating PDF…', `Capturing ${tabName} (${qLabel(CQ)})`);

  // Hide interactive controls for the snapshot
  document.body.classList.add('exporting-pdf');

  // Allow paint to flush
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

  // Resize Plotly charts to ensure SVG rendering picks up final layout
  try {
    tab.querySelectorAll('.js-plotly-plot').forEach(el => {
      if (window.Plotly) Plotly.Plots.resize(el);
    });
  } catch(e) { /* non-fatal */ }

  const opt = {
    margin: [8, 8, 12, 8],   // top, left, bottom, right (mm)
    filename: filename,
    image: { type: 'jpeg', quality: 0.96 },
    html2canvas: {
      scale: 2,
      useCORS: true,
      backgroundColor: '#ffffff',
      logging: false,
      windowWidth: Math.max(1400, tab.scrollWidth),
    },
    jsPDF: { unit: 'mm', format: 'a3', orientation: 'landscape', compress: true },
    pagebreak: { mode: ['css', 'legacy'], avoid: ['.section-card', '.kpi-card'] },
  };

  try {
    await html2pdf().from(tab).set(opt).save();
    _showExportOverlay('PDF downloaded ✓', filename);
    setTimeout(_hideExportOverlay, 1200);
  } catch (e) {
    console.error('PDF export failed:', e);
    _showExportOverlay('Export failed', e.message || 'Unknown error');
    setTimeout(_hideExportOverlay, 2500);
  } finally {
    document.body.classList.remove('exporting-pdf');
  }
}

// ── Export ALL tabs to a single multi-page PDF ────────────────
// Uses html2pdf's chained API (.toPdf/.toCanvas/.get) so we don't need
// separate jsPDF or html2canvas globals — everything goes through html2pdf.
async function exportAllTabs() {
  if (typeof html2pdf === 'undefined') {
    alert('PDF library failed to load. Check your internet connection and reload the page.');
    return;
  }

  const tabIds = Object.keys(TAB_LABELS_FOR_PDF);
  const originalTab = activeTab;
  const filename = `DQ_Dashboard_Full_Report_${CQ}.pdf`;

  _showExportOverlay('Generating full report…', `0 / ${tabIds.length} tabs`);
  document.body.classList.add('exporting-pdf');

  // Common options for every page capture
  const commonOpt = (tabEl) => ({
    margin: 0,
    image: { type: 'jpeg', quality: 0.9 },
    html2canvas: {
      scale: 1.6, useCORS: true, backgroundColor: '#ffffff', logging: false,
      windowWidth: Math.max(1400, tabEl.scrollWidth),
    },
    jsPDF: { unit: 'mm', format: 'a3', orientation: 'landscape', compress: true },
  });

  let pdf = null;
  let pageWidth = 0, pageHeight = 0, margin = 8, usableW = 0, usableH = 0;

  try {
    for (let i = 0; i < tabIds.length; i++) {
      const tid = tabIds[i];
      const tabName = TAB_LABELS_FOR_PDF[tid] || tid;
      _showExportOverlay('Generating full report…', `${i+1} / ${tabIds.length} — ${tabName.replace(/_/g,' ')}`);

      switchTab(tid);
      // switchTab may re-render and lose body class; re-apply
      document.body.classList.add('exporting-pdf');
      await new Promise(r => setTimeout(r, 700));
      // Force Plotly to settle layout
      try {
        document.querySelectorAll(`#tab-${tid} .js-plotly-plot`).forEach(el => {
          if (window.Plotly) Plotly.Plots.resize(el);
        });
      } catch(e) { /* non-fatal */ }
      await new Promise(r => setTimeout(r, 200));

      const tabEl = document.getElementById('tab-' + tid);
      if (!tabEl) continue;

      const opt = commonOpt(tabEl);

      if (i === 0) {
        // First page — let html2pdf build the PDF for us, then keep the instance
        pdf = await html2pdf().from(tabEl).set(opt).toPdf().get('pdf');
        pageWidth  = pdf.internal.pageSize.getWidth();
        pageHeight = pdf.internal.pageSize.getHeight();
        usableW = pageWidth  - 2*margin;
        usableH = pageHeight - 2*margin;
        // (html2pdf already added the first page image; we just overlay the footer)
        pdf.setFontSize(8); pdf.setTextColor(120);
        pdf.text(`${tabName.replace(/_/g, ' ')} — Snapshot ${qLabel(CQ)}`, margin, pageHeight - 3);
        pdf.text(`1 / ${tabIds.length}`, pageWidth - margin, pageHeight - 3, { align: 'right' });
      } else {
        // Subsequent pages — render to canvas, add new page, place image, footer
        const canvas = await html2pdf().from(tabEl).set(opt).toCanvas().get('canvas');
        const ratio = canvas.width / canvas.height;
        let w = usableW, h = usableW / ratio;
        if (h > usableH) { h = usableH; w = usableH * ratio; }
        const x = margin + (usableW - w) / 2;
        const y = margin + (usableH - h) / 2;
        pdf.addPage();
        pdf.addImage(canvas.toDataURL('image/jpeg', 0.9), 'JPEG', x, y, w, h);
        pdf.setFontSize(8); pdf.setTextColor(120);
        pdf.text(`${tabName.replace(/_/g, ' ')} — Snapshot ${qLabel(CQ)}`, margin, pageHeight - 3);
        pdf.text(`${i+1} / ${tabIds.length}`, pageWidth - margin, pageHeight - 3, { align: 'right' });
      }
    }

    pdf.save(filename);
    _showExportOverlay('Full report downloaded ✓', filename);
    setTimeout(_hideExportOverlay, 1500);
  } catch (e) {
    console.error('Full export failed:', e);
    _showExportOverlay('Export failed', e.message || 'Unknown error');
    setTimeout(_hideExportOverlay, 2500);
  } finally {
    document.body.classList.remove('exporting-pdf');
    if (originalTab && originalTab !== activeTab) switchTab(originalTab);
  }
}

// ── Export dropdown menu toggle ───────────────────────────────
function toggleExportMenu(e) {
  if (e) e.stopPropagation();
  const m = document.getElementById('export-menu');
  if (m) m.classList.toggle('open');
}
function closeExportMenu() {
  const m = document.getElementById('export-menu');
  if (m) m.classList.remove('open');
}
// Close menu when clicking anywhere outside it
document.addEventListener('click', (e) => {
  const wrap = e.target.closest('.export-menu-wrap');
  if (!wrap) closeExportMenu();
});

// INIT (runs at script load)
(function init() {
  initSelectors();
  initFooter();
  document.querySelector('[data-tab="overview"]').classList.add('active');
  renderOverview();
})();
"""
