"""Shared CMP_MODE state + mode bar with conditional, mode-specific selectors.

Each comparison mode gets its own contextual sub-bar of dropdowns:

  QoQ:          [Snapshot Quarter ▼]   [Compare With ▼]
  YoY:          [Port 2024 Year ▼]     [Port 2025 Year ▼]
  Historical:   [Start Quarter ▼]      [End Quarter ▼]

State lives in a few module-level JS variables (YOY_24_YEAR, YOY_25_YEAR,
HIST_START, HIST_END) that are read by `_cmpFilter()` to slice the time series.
"""

JS = r"""
// ── COMPARISON MODE (shared across all tabs) ──────────────────
let CMP_MODE = 'historical'; // 'qoq' | 'yoy' | 'historical'

// Per-mode contextual state
let YOY_24_YEAR = null;   // selected year of Port 2024 (default: latest)
let YOY_25_YEAR = null;   // selected year of Port 2025 (default: latest)
let HIST_START  = null;   // historical range start quarter (e.g. '2010Q1')
let HIST_END    = null;   // historical range end quarter

function setCmpMode(mode) {
  CMP_MODE = mode;
  renderTab(activeTab);
}

function setYoyYear(side, year) {
  if (side === '24') YOY_24_YEAR = +year;
  else YOY_25_YEAR = +year;
  renderTab(activeTab);
}

function setHistRange(which, q) {
  if (which === 'start') HIST_START = q || null;
  else HIST_END = q || null;
  renderTab(activeTab);
}

// Available years per portfolio (cached at first access)
function _years24() {
  const qs = (DASH_DATA.port24 || {}).quarters || [];
  return [...new Set(qs.map(q => +q.slice(0,4)))].sort((a,b)=>a-b);
}
function _years25() {
  const qs = DASH_DATA.quarters || [];
  return [...new Set(qs.map(q => +q.slice(0,4)))].sort((a,b)=>a-b);
}

function _quarterDropdowns() {
  // === QoQ: Snapshot + Compare With ===
  if (CMP_MODE === 'qoq') {
    const qOpts = (target) => [...DASH_DATA.quarters].reverse()
      .map(q => `<option value="${q}"${q===target?' selected':''}>${qLabel(q)}</option>`).join('');
    return `
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:8px 12px;margin-top:-8px;margin-bottom:14px;background:#f1f5f9;border:1px solid var(--border);border-radius:0 0 8px 8px;border-top:none">
        <span style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Quarter Pair:</span>
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Snapshot</label>
          <select class="filter-select" onchange="setCurrentQuarter(this.value)" style="font-size:11px;padding:3px 8px;min-width:120px">
            ${qOpts(CQ)}
          </select>
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Compare With</label>
          <select class="filter-select" onchange="setCompareQuarter(this.value)" style="font-size:11px;padding:3px 8px;min-width:120px">
            ${qOpts(PQ)}
          </select>
        </div>
        <span style="font-size:10px;color:var(--text-muted);margin-left:auto;font-style:italic">
          Drives KPI deltas, waterfall, migration matrix, and lifecycle donut
        </span>
      </div>`;
  }

  // === YoY: pick year for each portfolio ===
  if (CMP_MODE === 'yoy') {
    const y24 = _years24();
    const y25 = _years25();
    const cur24 = YOY_24_YEAR ?? (y24[y24.length-1] || null);
    const cur25 = YOY_25_YEAR ?? (y25[y25.length-1] || null);
    const opt = (y, sel) => `<option value="${y}"${y===sel?' selected':''}>${y}</option>`;
    return `
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:8px 12px;margin-top:-8px;margin-bottom:14px;background:#f1f5f9;border:1px solid var(--border);border-radius:0 0 8px 8px;border-top:none">
        <span style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Years to compare:</span>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="display:inline-block;width:10px;height:3px;background:#2563eb;border-radius:2px"></span>
          <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Port 2024</label>
          <select class="filter-select" onchange="setYoyYear('24',this.value)" style="font-size:11px;padding:3px 8px;min-width:90px">
            ${y24.map(y=>opt(y,cur24)).reverse().join('')}
          </select>
        </div>
        <span style="font-size:14px;color:var(--text-muted)">vs</span>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="display:inline-block;width:10px;height:3px;background:#16a34a;border-radius:2px"></span>
          <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Port 2025</label>
          <select class="filter-select" onchange="setYoyYear('25',this.value)" style="font-size:11px;padding:3px 8px;min-width:90px">
            ${y25.map(y=>opt(y,cur25)).reverse().join('')}
          </select>
        </div>
        <span style="font-size:10px;color:var(--text-muted);margin-left:auto;font-style:italic">
          Each portfolio overlaid on the same Q1–Q4 axis
        </span>
      </div>`;
  }

  // === Historical: pick start + end quarter ===
  if (CMP_MODE === 'historical') {
    const allQ = DASH_DATA.quarters || [];
    if (!allQ.length) return '';
    const start = HIST_START || allQ[0];
    const end   = HIST_END   || allQ[allQ.length-1];
    const opts = (sel) => allQ.map(q => `<option value="${q}"${q===sel?' selected':''}>${qLabel(q)}</option>`).join('');
    return `
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:8px 12px;margin-top:-8px;margin-bottom:14px;background:#f1f5f9;border:1px solid var(--border);border-radius:0 0 8px 8px;border-top:none">
        <span style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Date Range:</span>
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Start</label>
          <select class="filter-select" onchange="setHistRange('start',this.value)" style="font-size:11px;padding:3px 8px;min-width:110px">
            ${opts(start)}
          </select>
        </div>
        <span style="font-size:14px;color:var(--text-muted)">→</span>
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">End</label>
          <select class="filter-select" onchange="setHistRange('end',this.value)" style="font-size:11px;padding:3px 8px;min-width:110px">
            ${opts(end)}
          </select>
        </div>
        <button onclick="setHistRange('start','');setHistRange('end','')"
          style="font-size:10px;padding:3px 10px;border:1px solid var(--border);border-radius:4px;background:#fff;cursor:pointer;color:var(--text-muted)">
          Reset
        </button>
        <span style="font-size:10px;color:var(--text-muted);margin-left:auto;font-style:italic">
          Trims every time-series chart to this window
        </span>
      </div>`;
  }

  return '';
}

function _modeBar() {
  const m = CMP_MODE;
  const btn = (id,lbl) => `<button onclick="setCmpMode('${id}')"
    class="ov-mode-btn${m===id?' ov-mode-active':''}">${lbl}</button>`;
  const hasSubBar = (m === 'qoq' || m === 'yoy' || m === 'historical');
  const radius = hasSubBar ? '8px 8px 0 0' : '8px';
  return `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:${hasSubBar?'0':'14px'};padding:8px 12px;background:#f8fafc;border:1px solid var(--border);border-radius:${radius}">
    <span style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px">Comparison Mode:</span>
    ${btn('qoq','QoQ — Same Portfolio')}
    ${btn('yoy','YoY — 2024 vs 2025')}
    ${btn('historical','Historical Comparison')}
    <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">
      <span style="display:inline-block;width:14px;height:3px;background:#2563eb;border-radius:2px;vertical-align:middle"></span>&nbsp;Port 2024 &nbsp;
      <span style="display:inline-block;width:14px;height:3px;background:#16a34a;border-radius:2px;vertical-align:middle"></span>&nbsp;Port 2025
    </span>
  </div>${_quarterDropdowns()}`;
}

function _cmpTS25(key) { return (DASH_DATA.time_series||{})[key] || []; }
function _cmpTS24(key) { return ((DASH_DATA.port24||{}).time_series||{})[key] || []; }

// Portfolio-aware filter. When called from _cmpTraces we pass '24' or '25';
// pages that only deal with port25 can omit the arg (defaults to port25 semantics).
function _cmpFilter(arr, portfolio) {
  if (CMP_MODE === 'qoq') return arr.slice(-12);

  if (CMP_MODE === 'yoy') {
    if (!arr.length) return arr;
    let yr;
    if (portfolio === '24') yr = YOY_24_YEAR;
    else if (portfolio === '25') yr = YOY_25_YEAR;
    if (yr === null || yr === undefined) {
      yr = Math.max(...arr.map(r => +r.quarter.slice(0,4)));
    }
    return arr.filter(r => +r.quarter.slice(0,4) === yr);
  }

  if (CMP_MODE === 'historical') {
    if (HIST_START || HIST_END) {
      return arr.filter(r => {
        if (HIST_START && r.quarter < HIST_START) return false;
        if (HIST_END   && r.quarter > HIST_END)   return false;
        return true;
      });
    }
    return arr;
  }

  return arr;
}

function _cmpX(arr) {
  if (CMP_MODE === 'yoy') return arr.map(r => 'Q'+r.quarter.slice(5));
  return arr.map(r => r.label);
}

function _cmpTraces(tsKey, yKey, name24, name25, color24, color25) {
  const c24 = color24 || '#2563eb';
  const c25 = color25 || '#16a34a';
  const a24 = _cmpFilter(_cmpTS24(tsKey), '24');
  const a25 = _cmpFilter(_cmpTS25(tsKey), '25');
  const traces = [];
  if (CMP_MODE !== 'qoq' && a24.length) {
    // In YoY, name the trace with the selected year for clarity
    const lbl24 = (CMP_MODE === 'yoy')
      ? `Port 2024 (${(YOY_24_YEAR ?? a24[0].quarter.slice(0,4))})`
      : (name24 || 'Port 2024');
    traces.push({ x:_cmpX(a24), y:a24.map(r=>r[yKey]), name:lbl24,
      type:'scatter', mode:'lines+markers', line:{color:c24,width:2}, marker:{size:3,color:c24}, connectgaps:true });
  }
  const lbl25 = (CMP_MODE === 'yoy')
    ? `Port 2025 (${(YOY_25_YEAR ?? (a25[0]?.quarter.slice(0,4) || ''))})`
    : (name25 || 'Port 2025');
  traces.push({ x:_cmpX(a25), y:a25.map(r=>r[yKey]), name:lbl25,
    type:'scatter', mode:'lines+markers', line:{color:c25,width:2}, marker:{size:3,color:c25}, connectgaps:true });
  return traces;
}

function _cmpLayout(yTitle, height) {
  return {
    margin:{t:10,r:10,b:50,l:50}, height:height||180,
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{showgrid:false,tickfont:{size:8},tickangle:-45},
    yaxis:{title:yTitle,gridcolor:'#f1f5f9',tickfont:{size:9}},
    legend:{orientation:'h',y:1.18,x:0,font:{size:9}},
    showlegend: CMP_MODE !== 'qoq',
  };
}
const _cmpCfg = {responsive:true,displayModeBar:false};
"""
