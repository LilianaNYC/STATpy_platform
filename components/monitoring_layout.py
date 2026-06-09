"""Monitoring-only sidebar, top-bar controls, and browser initialization."""

TABS = [
    ("overview", "Overview", "📊", "renderOverview"),
    ("pd_models", "PD Performance", "🧠", "renderPdModels"),
    ("lgd_models", "LGD Performance", "📉", "renderLgdModels"),
    ("ead_models", "EAD Performance", "📈", "renderEadModels"),
]

SIDEBAR_TITLE = "Model Monitoring"
TOP_TITLE = "Wholesale Portfolio Model Monitoring Dashboard"
TOP_BAR_CONTROLS_HTML = (
    '      <div class="monitoring-controls">'
    '<div class="monitoring-filter">'
    '<label>Monitoring Point</label>'
    '<select id="monitoring-quarter-select" aria-label="Monitoring point" '
    'onchange="setCurrentMonitoringPoint(this.value)"></select>'
    '</div>'
    '<div class="monitoring-filter monitoring-mode-filter">'
    '<label>Filter By</label>'
    '<div class="monitoring-mode-switch" role="group" aria-label="Monitoring filter mode">'
    '<button type="button" id="monitoring-mode-group" onclick="setMonitoringFilterMode(\'group\')">Group &amp; Segment</button>'
    '<button type="button" id="monitoring-mode-models" onclick="setMonitoringFilterMode(\'models\')">Specific Models</button>'
    '</div>'
    '</div>'
    '<div class="monitoring-filter monitoring-model-group-filter">'
    '<label>Model Group</label>'
    '<select id="monitoring-metric-segment-select" aria-label="Metric segment" '
    'onchange="setMonitoringSegment(\'metric\',this.value)">'
    '<option value="all">All</option>'
    '<option value="ead">EAD</option><option value="lgd">LGD</option><option value="pd">PD</option>'
    '</select>'
    '</div>'
    '<div class="monitoring-filter">'
    '<label>Segment</label>'
    '<select id="monitoring-portfolio-segment-select" aria-label="Portfolio segment" '
    'onchange="setMonitoringSegment(\'portfolio\',this.value)">'
    '</select>'
    '</div>'
    '<div class="monitoring-filter monitoring-model-filter">'
    '<label>Specific Models</label>'
    '<div class="checkbox-dropdown">'
    '<button type="button" class="checkbox-dropdown-toggle" id="monitoring-model-toggle" '
    'onclick="toggleMonitoringModelMenu(event)">Select models</button>'
    '<div class="checkbox-dropdown-menu" id="monitoring-model-menu"></div>'
    '</div>'
    '</div>'
    '<div class="monitoring-filter-help" id="monitoring-filter-help"></div>'
    '<div class="monitoring-section-subnav" id="monitoring-pd-subnav" hidden>'
    '<div class="monitoring-section-subnav-group">'
    '<div class="monitoring-section-subnav-label">RAG Assignment</div>'
    '<div class="monitoring-section-subnav-links">'
    '<button type="button" data-monitoring-target="pd-analysis-scope" onclick="jumpToMonitoringSection(\'pd-analysis-scope\')">Overview</button>'
    '<button type="button" data-monitoring-target="pd-calibration-rag" onclick="jumpToMonitoringSection(\'pd-calibration-rag\')">ECL PIT PD - Calibration Conservatism</button>'
    '<button type="button" data-monitoring-target="pd-discrimination-rag" onclick="jumpToMonitoringSection(\'pd-discrimination-rag\')">ECL PIT PD - Discriminatory Power</button>'
    '<button type="button" data-monitoring-target="pd-balance-sheet-calibration" onclick="jumpToMonitoringSection(\'pd-balance-sheet-calibration\')">Balance Sheet PD - Calibration Conservatism</button>'
    '</div>'
    '</div>'
    '<div class="monitoring-section-subnav-group monitoring-section-subnav-group-secondary">'
    '<div class="monitoring-section-subnav-label">Post Subjective Review Analysis</div>'
    '<div class="monitoring-section-subnav-links">'
    '<button type="button" data-monitoring-target="pd-post-subjective-overview" onclick="jumpToMonitoringSection(\'pd-post-subjective-overview\')">Overview</button>'
    '<button type="button" data-monitoring-target="pd-transition-matrix-distance" onclick="jumpToMonitoringSection(\'pd-transition-matrix-distance\')">Transition Matrix</button>'
    '<button type="button" data-monitoring-target="pd-population-stability-index" onclick="jumpToMonitoringSection(\'pd-population-stability-index\')">PSI</button>'
    '<button type="button" data-monitoring-target="pd-rank-ordering" onclick="jumpToMonitoringSection(\'pd-rank-ordering\')">Scenario Rank Ordering</button>'
    '<button type="button" data-monitoring-target="pd-sensitivity-analysis" onclick="jumpToMonitoringSection(\'pd-sensitivity-analysis\')">Sensitivity Analysis</button>'
    '<button type="button" data-monitoring-target="pd-mev-range" onclick="jumpToMonitoringSection(\'pd-mev-range\')">MEV Range</button>'
    '</div>'
    '</div>'
    '</div>'
    '</div>\n'
)


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
    """JS dispatch table mapping monitoring tab_id to render function."""
    body = ",\n    ".join(f"{tid:<13}: {fn}" for tid, _, _, fn in TABS)
    return f"""
let activeTab = 'overview';
function switchTab(tabId) {{
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('tab-'+tabId).classList.add('active');
  document.querySelector(`[data-tab="${{tabId}}"]`).classList.add('active');
  activeTab = tabId;
  if (activeTab === 'lgd_models' || activeTab === 'ead_models') MONITORING_TIME_HORIZON = '1y';
  buildMonitoringModelMenu();
  buildMonitoringSegmentOptions();
  renderTab(tabId);
  syncMonitoringFilterControls();}}

function renderTab(tabId) {{
  const renders = {{
    {body}
  }};
  if (renders[tabId]) renders[tabId]();
}}
"""


INIT_JS = r"""
// ── Monitoring selectors ────────────────────────────────────────
let MONITORING_METRIC_SEGMENT = 'all';
let MONITORING_PORTFOLIO_SEGMENT = 'all';
let MONITORING_MODELS = [];
let MONITORING_FILTER_MODE = 'group';
let MONITORING_TIME_HORIZON = '1y';
let MONITORING_PD_INPUT = 'time_horizon';
let MONITORING_POINT = DASH_DATA.latest_quarter || '';
const MONITORING_POINT_OPTIONS = (DASH_DATA.quarters || []).slice().sort().reverse();
const MONITORING_PD_SECTION_IDS = [
  'pd-analysis-scope',
  'pd-calibration-rag',
  'pd-discrimination-rag',
  'pd-balance-sheet-calibration',
  'pd-post-subjective-overview',
  'pd-transition-matrix-distance',
  'pd-population-stability-index',
  'pd-rank-ordering',
  'pd-sensitivity-analysis',
  'pd-mev-range',
];
let MONITORING_SCROLL_SYNC_BOUND = false;
let MONITORING_SECTION_SCROLL_FRAME = null;

function getMonitoringFilterPayload() {
  const monitoring = DASH_DATA.monitoring || {};
  if (activeTab === 'pd_models') return monitoring.pd_models || {};
  if (activeTab === 'lgd_models') return monitoring.lgd_models || {};
  if (activeTab === 'ead_models') return monitoring.ead_models || {};
  return monitoring.overview || {};
}
function getMonitoringModelNames() {
  return getMonitoringFilterPayload().model_names || [];
}
function getMonitoringSegmentValues() {
  return getMonitoringFilterPayload().segment_values || [];
}
function initSelectors() {
  const sel = document.getElementById('monitoring-quarter-select');
  if (sel) {
    MONITORING_POINT_OPTIONS.forEach(point => {
      const opt = document.createElement('option');
      opt.value = point;
      opt.text = point;
      if (point === MONITORING_POINT) opt.selected = true;
      sel.appendChild(opt);
    });
  }
  buildMonitoringModelMenu();
  buildMonitoringSegmentOptions();
  initMonitoringSectionSync();
  syncMonitoringFilterControls();
}
function initMonitoringSectionSync() {
  if (MONITORING_SCROLL_SYNC_BOUND) return;
  const content = document.querySelector('.content');
  if (!content) return;
  content.addEventListener('scroll', function() {
    if (MONITORING_SECTION_SCROLL_FRAME !== null) return;
    MONITORING_SECTION_SCROLL_FRAME = window.requestAnimationFrame(function() {
      MONITORING_SECTION_SCROLL_FRAME = null;
      updateMonitoringPdSubnavActiveState();
    });
  }, {passive: true});
  MONITORING_SCROLL_SYNC_BOUND = true;
}
function setMonitoringPdSubnavActive(sectionId) {
  document.querySelectorAll('#monitoring-pd-subnav [data-monitoring-target]').forEach(button => {
    const isActive = button.getAttribute('data-monitoring-target') === sectionId;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-current', isActive ? 'location' : 'false');
  });
  document.querySelectorAll('#monitoring-pd-subnav .monitoring-section-subnav-group').forEach(group => {
    const hasActiveButton = !!group.querySelector('[data-monitoring-target].active');
    group.classList.toggle('active', hasActiveButton);
  });
}
function updateMonitoringPdSubnavActiveState() {
  const pdSubnav = document.getElementById('monitoring-pd-subnav');
  if (!pdSubnav || pdSubnav.hidden || activeTab !== 'pd_models') return;
  const content = document.querySelector('.content');
  if (!content) return;
  const contentRect = content.getBoundingClientRect();
  const anchorLine = contentRect.top + 36;
  let activeSectionId = MONITORING_PD_SECTION_IDS[0];
  for (const sectionId of MONITORING_PD_SECTION_IDS) {
    const section = document.getElementById(sectionId);
    if (!section) continue;
    if (section.getBoundingClientRect().top <= anchorLine) {
      activeSectionId = sectionId;
    } else {
      break;
    }
  }
  setMonitoringPdSubnavActive(activeSectionId);
}
function buildMonitoringSegmentOptions() {
  const sel = document.getElementById('monitoring-portfolio-segment-select');
  if (!sel) return;

  const segmentValues = getMonitoringSegmentValues();
  sel.innerHTML = '';

  const allOption = document.createElement('option');
  allOption.value = 'all';
  allOption.text = 'All';
  allOption.selected = MONITORING_PORTFOLIO_SEGMENT === 'all';
  sel.appendChild(allOption);

  segmentValues.forEach(value => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.text = value;
    opt.selected = value === MONITORING_PORTFOLIO_SEGMENT;
    sel.appendChild(opt);
  });
  if (!segmentValues.includes(MONITORING_PORTFOLIO_SEGMENT)) {
    MONITORING_PORTFOLIO_SEGMENT = 'all';
    sel.value = 'all';
  }
}
function buildMonitoringModelMenu() {
  const menu = document.getElementById('monitoring-model-menu');
  if (!menu) return;

  const modelNames = getMonitoringModelNames();
  const nodes = [];
  nodes.push(
    `<label><input type="checkbox" value="All" data-model-all onchange="setMonitoringModels(this)" checked>All</label>`
  );
  modelNames.forEach(name => {
    nodes.push(
      `<label><input type="checkbox" value="${name}" onchange="setMonitoringModels(this)" checked>${name}</label>`
    );
  });
  menu.innerHTML = nodes.join('');
  MONITORING_MODELS = modelNames.slice();
}
function setCurrentMonitoringPoint(point) {
  if (!MONITORING_POINT_OPTIONS.includes(point)) return;
  MONITORING_POINT = point;
  CQ = point;
  renderAll();
}
function setMonitoringTimeHorizon(horizon) {
  if (horizon !== '1y' && horizon !== '2y') return;
  if (activeTab === 'lgd_models' || activeTab === 'ead_models') {
    MONITORING_TIME_HORIZON = '1y';
    syncMonitoringFilterControls();
    return;
  }
  MONITORING_TIME_HORIZON = horizon;
  renderAll();
}
function setMonitoringPdInput(input) {
  if (input !== 'time_horizon' && input !== 'nco_1y') return;
  MONITORING_PD_INPUT = input;
  syncMonitoringFilterControls();
  renderAll();
}
function setMonitoringFilterMode(mode) {
  if (mode !== 'group' && mode !== 'models') return;
  MONITORING_FILTER_MODE = mode;
  syncMonitoringFilterControls();
  renderAll();
}
function setMonitoringSegment(which, value) {
  if (which === 'metric') MONITORING_METRIC_SEGMENT = value;
  if (which === 'portfolio') MONITORING_PORTFOLIO_SEGMENT = value;
  syncMonitoringFilterControls();
  renderAll();
}
function setMonitoringModels(changedInput) {
  const inputs = Array.from(document.querySelectorAll('#monitoring-model-menu input[type="checkbox"]'));
  const allInput = inputs.find(input => input.hasAttribute('data-model-all'));
  const modelInputs = inputs.filter(input => !input.hasAttribute('data-model-all'));
  if (changedInput && changedInput.hasAttribute('data-model-all')) {
    modelInputs.forEach(input => { input.checked = changedInput.checked; });
  } else if (allInput) {
    allInput.checked = modelInputs.length > 0 && modelInputs.every(input => input.checked);
  }
  MONITORING_MODELS = modelInputs.filter(input => input.checked).map(input => input.value);
  syncMonitoringFilterControls();
  renderAll();
}
function syncMonitoringFilterControls() {
  const isPerformanceTab = activeTab === 'pd_models' || activeTab === 'lgd_models' || activeTab === 'ead_models';
  const isPdTab = activeTab === 'pd_models';
  const groupMode = !isPerformanceTab && MONITORING_FILTER_MODE === 'group';
  const modelMode = isPerformanceTab || MONITORING_FILTER_MODE === 'models';
  const metricSelect = document.getElementById('monitoring-metric-segment-select');
  const portfolioSelect = document.getElementById('monitoring-portfolio-segment-select');
  const modeFilter = document.querySelector('.monitoring-mode-filter');
  const modelGroupFilter = document.querySelector('.monitoring-model-group-filter');
  const toggle = document.getElementById('monitoring-model-toggle');
  const menu = document.getElementById('monitoring-model-menu');
  const inputs = document.querySelectorAll('#monitoring-model-menu input[type="checkbox"]');
  const groupButton = document.getElementById('monitoring-mode-group');
  const modelsButton = document.getElementById('monitoring-mode-models');
  const help = document.getElementById('monitoring-filter-help');
  const pdSubnav = document.getElementById('monitoring-pd-subnav');
  const modelNames = getMonitoringModelNames();
  const hasSpecificModelSelection = (
    MONITORING_MODELS.length > 0
    && MONITORING_MODELS.length < modelNames.length
  );
  const hasSegmentSelection = MONITORING_PORTFOLIO_SEGMENT !== 'all';

  if (groupMode) {
    MONITORING_MODELS = [];
    inputs.forEach(input => { input.checked = false; });
    if (menu) menu.classList.remove('open');
  }

  if (modeFilter) {
    modeFilter.style.display = isPerformanceTab ? 'none' : 'flex';
  }
  if (modelGroupFilter) {
    modelGroupFilter.style.display = isPerformanceTab ? 'none' : 'flex';
  }
  if (metricSelect) metricSelect.disabled = isPerformanceTab || !groupMode;
  if (portfolioSelect) {
    portfolioSelect.disabled = isPerformanceTab
      ? hasSpecificModelSelection
      : !groupMode;
  }
  inputs.forEach(input => {
    input.disabled = isPerformanceTab
      ? hasSegmentSelection
      : !modelMode;
  });

  if (toggle) {
    toggle.disabled = isPerformanceTab ? hasSegmentSelection : !modelMode;
    const totalModelCount = Math.max(0, inputs.length - 1);
    if (isPerformanceTab && hasSegmentSelection) toggle.textContent = 'Disabled while Segment is selected';
    else if (!modelMode) toggle.textContent = 'Switch mode to select models';
    else if (!MONITORING_MODELS.length) toggle.textContent = 'Select models';
    else if (MONITORING_MODELS.length === totalModelCount) toggle.textContent = 'All models';
    else if (MONITORING_MODELS.length === 1) toggle.textContent = MONITORING_MODELS[0];
    else toggle.textContent = `${MONITORING_MODELS.length} models selected`;
  }

  if (groupButton) groupButton.classList.toggle('active', groupMode);
  if (modelsButton) modelsButton.classList.toggle('active', modelMode);
  if (help) {
    if (isPerformanceTab) {
      if (hasSegmentSelection) {
        help.textContent = 'Segment filtering is active. Reset Segment to All to select specific models.';
      } else if (hasSpecificModelSelection) {
        help.textContent = 'Specific Models filtering is active. Reset models to All to select a portfolio segment.';
      } else {
        help.textContent = 'Choose a portfolio segment or specific models. These filters cannot be combined.';
      }
    } else {
      help.textContent = groupMode
        ? 'Choose a model group and segment. Switch to Specific Models to select individual models.'
        : 'Results include any selected model. Model Group and Segment are disabled in this mode.';
    }
  }
  if (pdSubnav) {
    pdSubnav.hidden = !isPdTab;
  }
  if (isPdTab) updateMonitoringPdSubnavActiveState();
}
function jumpToMonitoringSection(sectionId) {
  const target = document.getElementById(sectionId);
  if (!target) return;
  setMonitoringPdSubnavActive(sectionId);
  const content = document.querySelector('.content');
  if (!content) {
    target.scrollIntoView({behavior: 'smooth', block: 'start'});
    return;
  }
  const contentRect = content.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const top = Math.max(0, content.scrollTop + targetRect.top - contentRect.top - 10);
  content.scrollTo({top, behavior: 'smooth'});
}
function toggleMonitoringModelMenu(e) {
  if (e) e.stopPropagation();
  const toggle = document.getElementById('monitoring-model-toggle');
  const menu = document.getElementById('monitoring-model-menu');
  if (toggle && !toggle.disabled && menu) menu.classList.toggle('open');
}
function renderAll() { renderTab(activeTab); }

function initFooter() {
  document.getElementById('footer-data-as-of').textContent = 'Data as of: '+DASH_DATA.data_as_of;
  document.getElementById('footer-source').textContent = 'Source: '+DASH_DATA.source;
  document.getElementById('footer-run-id').textContent = 'Run ID: '+DASH_DATA.run_id;
  document.getElementById('footer-refresh').textContent = 'Last refresh: '+DASH_DATA.last_refresh;
  document.getElementById('sidebar-footer').innerHTML =
    `Data as of:<br>${DASH_DATA.data_as_of}<br><br>Last refresh:<br>${DASH_DATA.last_refresh}`;
}

const TAB_LABELS_FOR_PDF = {
  overview: 'Overview',
  pd_models: 'PD_Performance',
  lgd_models: 'LGD_Performance',
  ead_models: 'EAD_Performance',
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
      <div class="sub" id="export-overlay-sub">${sub || ''}</div>
    </div>`;
    document.body.appendChild(ov);
  } else {
    document.getElementById('export-overlay-msg').textContent = msg;
    document.getElementById('export-overlay-sub').textContent = sub || '';
  }
  ov.classList.add('active');
}

function _hideExportOverlay() {
  const ov = document.getElementById('export-overlay');
  if (ov) ov.classList.remove('active');
}

function _escapePdfHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function _pdfStyles() {
  const inlineStyles = Array.from(document.querySelectorAll('style'))
    .map(node => node.outerHTML)
    .join('\n');
  return `${inlineStyles}
  <style>
    @page { size: A3 landscape; margin: 8mm; }
    html, body { margin: 0; padding: 0; background: #f8fafc; }
    body {
      font-family: "Segoe UI", Arial, sans-serif;
      color: #111827;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .pdf-report {
      padding: 14px 18px;
      background: #f8fafc;
    }
    .pdf-tab {
      break-after: page;
      page-break-after: always;
      padding: 0;
    }
    .pdf-tab:last-child {
      break-after: auto;
      page-break-after: auto;
    }
    .pdf-shell {
      background: #f8fafc;
    }
    .pdf-header {
      margin-bottom: 14px;
      padding: 14px 18px;
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,.08);
    }
    .pdf-header h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
      color: #0f1d35;
    }
    .pdf-header p {
      margin: 4px 0 0;
      font-size: 11px;
      color: #6b7280;
    }
    .pdf-content {
      width: 100%;
      padding: 0;
    }
    .pdf-content > .dash-header,
    .pdf-content > .pd-content-section,
    .pdf-content > .section-card {
      max-width: none;
    }
    .monitoring-section-subnav,
    .pd-chart-actions,
    .pd-section-actions,
    .pd-expand-button,
    .pd-expanded-close,
    .lgd-window-control,
    .ead-window-control,
    .pd-range-controls,
    button,
    select {
      display: none !important;
    }
    .pd-content-section,
    .section-card,
    .pd-signal-card,
    .pd-test-card,
    .pd-performance-card,
    .pd-domain-status,
    .pd-subchart-panel,
    .pd-migration-summary,
    .chart-box,
    .js-plotly-plot {
      break-inside: avoid-page;
      page-break-inside: avoid;
    }
    .pd-content-section { margin-top: 14px; }
    .pd-page-header,
    .pd-domain-heading,
    .pd-section-heading,
    .pd-chart-heading,
    .pd-retention-card-heading {
      display: flex !important;
    }
    .pd-executive-grid,
    .pd-test-grid,
    .pd-performance-grid,
    .pd-primary-analysis-grid,
    .pd-trend-detail-grid,
    .pd-discrimination-trend-grid,
    .pd-stability-trend-grid,
    .pd-migration-grid,
    .pd-overview-row.pd-test-grid-4,
    .pd-overview-row.pd-test-grid-3,
    .lgd-kpi-grid,
    .ead-kpi-grid {
      display: grid !important;
      width: 100% !important;
    }
    .pd-executive-grid,
    .pd-overview-row.pd-test-grid-4,
    .pd-test-grid-4,
    .lgd-kpi-grid,
    .ead-kpi-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
      gap: 14px !important;
    }
    .pd-overview-row.pd-test-grid-3,
    .pd-test-grid-3,
    .pd-calibration-test-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
      gap: 12px !important;
    }
    .pd-discrimination-test-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
      gap: 12px !important;
    }
    .pd-performance-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
      gap: 14px !important;
    }
    .pd-performance-test-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
      gap: 12px !important;
    }
    .pd-primary-analysis-grid {
      grid-template-columns: 1fr !important;
      gap: 16px !important;
    }
    .pd-trend-detail-grid,
    .pd-discrimination-trend-grid,
    .pd-stability-trend-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      gap: 14px !important;
    }
    .pd-migration-grid {
      grid-template-columns: minmax(220px, .72fr) minmax(420px, 1.28fr) !important;
      gap: 14px !important;
    }
    .pd-default-rate-trend-chart,
    .pd-rating-default-rate-chart,
    .pd-discrimination-trend-chart,
    .pd-stability-trend-chart,
    .pd-rating-direction-chart {
      min-height: 220px !important;
    }
    .section-card,
    .pd-test-card,
    .pd-performance-card,
    .pd-signal-card {
      margin-bottom: 0 !important;
    }
    .pd-content-heading {
      margin-bottom: 10px !important;
    }
  </style>`;
}

function _buildPdfDocument(title, bodyHtml) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${_escapePdfHtml(title)}</title>
${_pdfStyles()}
</head>
<body>
<div class="pdf-report">${bodyHtml}</div>
<script>
  window.onload = function() {
    setTimeout(function() {
      window.focus();
      window.print();
    }, 500);
  };
  window.onafterprint = function() { window.close(); };
<\/script>
</body>
</html>`;
}

function _openPdfWindow(title) {
  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    throw new Error('Pop-up blocked. Allow pop-ups to export PDF.');
  }
  printWindow.document.open();
  printWindow.document.write(`<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${_escapePdfHtml(title)}</title></head><body style="font-family:Segoe UI,Arial,sans-serif;padding:24px;color:#111827;">Preparing PDF...</body></html>`);
  printWindow.document.close();
  return printWindow;
}

async function _settlePrintableTab(tabId) {
  switchTab(tabId);
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  try {
    document.querySelectorAll(`#tab-${tabId} .js-plotly-plot`).forEach(el => {
      if (window.Plotly) Plotly.Plots.resize(el);
    });
  } catch (err) {
    console.warn('Plotly resize skipped for PDF export', err);
  }
  await new Promise(resolve => setTimeout(resolve, 200));
}

function _monitoringPdfFilename(prefix, tabName) {
  const point = MONITORING_POINT || CQ || 'snapshot';
  return `${prefix}_${tabName}_${point}.pdf`;
}

function _buildPdfSection(title, tabHtml, pointLabel) {
  return `<section class="pdf-tab">
    <div class="pdf-shell">
      <div class="pdf-header">
        <h1>${_escapePdfHtml(title.replace(/_/g, ' '))}</h1>
        <p>Monitoring point: ${_escapePdfHtml(pointLabel)} | Source: ${_escapePdfHtml(DASH_DATA.source || '')}</p>
      </div>
      <div class="pdf-content">${tabHtml}</div>
    </div>
  </section>`;
}

async function exportData() {
  const tabId = activeTab;
  const tabName = TAB_LABELS_FOR_PDF[tabId] || tabId;
  const filename = _monitoringPdfFilename('Monitoring_Dashboard', tabName);
  _showExportOverlay('Preparing PDF…', tabName.replace(/_/g, ' '));
  let printWindow;
  try {
    printWindow = _openPdfWindow(filename);
    await _settlePrintableTab(tabId);
    const tab = document.getElementById('tab-' + tabId);
    if (!tab) throw new Error('Active tab could not be rendered for export.');

    const html = _buildPdfDocument(
      filename,
      _buildPdfSection(tabName, tab.innerHTML, MONITORING_POINT || CQ || '')
    );
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    _showExportOverlay('Print dialog opened', filename);
    setTimeout(_hideExportOverlay, 1400);
  } catch (err) {
    if (printWindow && !printWindow.closed) printWindow.close();
    console.error('PDF export failed:', err);
    _showExportOverlay('Export failed', err.message || 'Unknown error');
    setTimeout(_hideExportOverlay, 2500);
  }
}

async function exportAllTabs() {
  const tabIds = ['overview', 'pd_models', 'lgd_models', 'ead_models'];
  const originalTab = activeTab;
  const filename = _monitoringPdfFilename('Monitoring_Dashboard_Full_Report', 'All_Tabs');
  _showExportOverlay('Preparing full PDF…', `0 / ${tabIds.length} tabs`);
  let printWindow;
  try {
    printWindow = _openPdfWindow(filename);
    const sections = [];
    for (let i = 0; i < tabIds.length; i++) {
      const tabId = tabIds[i];
      const tabName = TAB_LABELS_FOR_PDF[tabId] || tabId;
      _showExportOverlay('Preparing full PDF…', `${i + 1} / ${tabIds.length} — ${tabName.replace(/_/g, ' ')}`);
      await _settlePrintableTab(tabId);
      const tab = document.getElementById('tab-' + tabId);
      if (!tab) continue;
      sections.push(_buildPdfSection(tabName, tab.innerHTML, MONITORING_POINT || CQ || ''));
    }

    const html = _buildPdfDocument(filename, sections.join(''));
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    _showExportOverlay('Print dialog opened', filename);
    setTimeout(_hideExportOverlay, 1400);
  } catch (err) {
    if (printWindow && !printWindow.closed) printWindow.close();
    console.error('Full PDF export failed:', err);
    _showExportOverlay('Export failed', err.message || 'Unknown error');
    setTimeout(_hideExportOverlay, 2500);
  } finally {
    if (originalTab && originalTab !== activeTab) switchTab(originalTab);
  }
}

function toggleExportMenu(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('export-menu');
  if (menu) menu.classList.toggle('open');
}

function closeExportMenu() {
  const menu = document.getElementById('export-menu');
  if (menu) menu.classList.remove('open');
}

document.addEventListener('click', function(evt) {
  const menu = document.getElementById('export-menu');
  if (menu && menu.classList.contains('open') && !menu.contains(evt.target)) {
    closeExportMenu();
  }
});

(function init() {
  initSelectors();
  initFooter();
  document.querySelector('[data-tab="overview"]').classList.add('active');
  renderOverview();
})();

"""
