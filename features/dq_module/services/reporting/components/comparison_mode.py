"""Shared CMP_MODE state + mode bar with mode-specific parameter sub-rows.

Each comparison mode shows the same sub-row pattern: [Current ▼] [Baseline ▼]
(or a static caption when the mode has a fixed pair). The vocabulary is
unified across modes so deltas always read as 'Current minus Baseline'.

  QoQ:          [Current quarter ▼]   [Baseline quarter ▼]
  YoY:          static caption — Port 2025 latest Q vs Port 2024 latest Q (fixed)
  Historical:   [Current = End ▼]     [Baseline = Start ▼]

State lives in module-level JS variables (HIST_START, HIST_END) and the global
CQ / PQ (for QoQ). YoY uses each portfolio's latest available quarter (fixed).
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

// Shared sub-row wrapper for visual consistency across all 3 modes
function _subBarWrap(innerHtml) {
  return `<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:8px 12px;margin-top:-8px;margin-bottom:14px;background:#f1f5f9;border:1px solid var(--border);border-radius:0 0 8px 8px;border-top:none;min-height:38px">
    ${innerHtml}
  </div>`;
}

function _quarterDropdowns() {
  // === QoQ: Current + Baseline (same portfolio, P25) ===
  if (CMP_MODE === 'qoq') {
    const qOpts = (target) => [...DASH_DATA.quarters].reverse()
      .map(q => `<option value="${q}"${q===target?' selected':''}>${qLabel(q)}</option>`).join('');
    return _subBarWrap(`
      <span style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Quarter Pair:</span>
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Current</label>
        <select class="filter-select" onchange="setCurrentQuarter(this.value)" style="font-size:11px;padding:3px 8px;min-width:120px">
          ${qOpts(CQ)}
        </select>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Baseline</label>
        <select class="filter-select" onchange="setCompareQuarter(this.value)" style="font-size:11px;padding:3px 8px;min-width:120px">
          ${qOpts(PQ)}
        </select>
      </div>
    `);
  }

  // === YoY: fixed pair — Port 2025 latest Q vs Port 2024 latest Q (no selectors) ===
  if (CMP_MODE === 'yoy') {
    const q25 = (DASH_DATA.quarters || []).slice(-1)[0] || '';
    const q24 = ((DASH_DATA.port24 || {}).quarters || []).slice(-1)[0] || '';
    return _subBarWrap(`
      <span style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Fixed Pair:</span>
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Current</label>
        <span style="font-size:11px;font-weight:600;color:#16a34a;background:#dcfce7;border:1px solid #bbf7d0;border-radius:4px;padding:2px 8px">Port 2025 — ${qLabel(q25)}</span>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Baseline</label>
        <span style="font-size:11px;font-weight:600;color:#2563eb;background:#dbeafe;border:1px solid #bfdbfe;border-radius:4px;padding:2px 8px">Port 2024 — ${qLabel(q24)}</span>
      </div>
    `);
  }

  // === Historical: Current = End, Baseline = Start (Current on left, like the other modes) ===
  if (CMP_MODE === 'historical') {
    const allQ = DASH_DATA.quarters || [];
    if (!allQ.length) return _subBarWrap('');
    const start = HIST_START || allQ[0];
    const end   = HIST_END   || allQ[allQ.length-1];
    const opts = (sel) => allQ.map(q => `<option value="${q}"${q===sel?' selected':''}>${qLabel(q)}</option>`).join('');
    return _subBarWrap(`
      <span style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Date Range:</span>
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Current (End)</label>
        <select class="filter-select" onchange="setHistRange('end',this.value)" style="font-size:11px;padding:3px 8px;min-width:110px">
          ${opts(end)}
        </select>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <label style="font-size:11px;color:var(--text-muted);white-space:nowrap">Baseline (Start)</label>
        <select class="filter-select" onchange="setHistRange('start',this.value)" style="font-size:11px;padding:3px 8px;min-width:110px">
          ${opts(start)}
        </select>
      </div>
      <button onclick="setHistRange('start','');setHistRange('end','')"
        style="font-size:10px;padding:3px 10px;border:1px solid var(--border);border-radius:4px;background:#fff;cursor:pointer;color:var(--text-muted)">
        Reset
      </button>
    `);
  }

  return '';
}

function _modeBar() {
  const m = CMP_MODE;
  const btn = (id,lbl) => `<button onclick="setCmpMode('${id}')"
    class="ov-mode-btn${m===id?' ov-mode-active':''}">${lbl}</button>`;
  // All three modes show a sub-row of the same visual height (parameters or fixed caption)
  const hasSubBar = (m === 'qoq' || m === 'yoy' || m === 'historical');
  const radius = hasSubBar ? '8px 8px 0 0' : '8px';
  // Legend: in QoQ only Port 2025 is plotted; in YoY/Historical both portfolios may appear
  const legend = (m === 'qoq')
    ? `<span style="margin-left:auto;font-size:11px;color:var(--text-muted)">
         <span style="display:inline-block;width:14px;height:3px;background:#16a34a;border-radius:2px;vertical-align:middle"></span>&nbsp;Port 2025
       </span>`
    : `<span style="margin-left:auto;font-size:11px;color:var(--text-muted)">
         <span style="display:inline-block;width:14px;height:3px;background:#2563eb;border-radius:2px;vertical-align:middle"></span>&nbsp;Port 2024 &nbsp;
         <span style="display:inline-block;width:14px;height:3px;background:#16a34a;border-radius:2px;vertical-align:middle"></span>&nbsp;Port 2025
       </span>`;
  return `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:${hasSubBar?'0':'14px'};padding:8px 12px;background:#f8fafc;border:1px solid var(--border);border-radius:${radius}">
    <span style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px">Comparison Mode:</span>
    ${btn('qoq','QoQ — Same Portfolio')}
    ${btn('yoy','YoY — 2024 vs 2025')}
    ${btn('historical','Historical Comparison')}
    ${legend}
  </div>${_quarterDropdowns()}`;
}

// ── Tier 3: persistent context chip ─────────────────────────────
// Small badge sprinkled near chart titles that echoes the active lens.
// Provides ambient awareness of what's being compared without forcing the
// user to scroll back up to the mode bar.
function _lensChip() {
  const m = CMP_MODE;
  let prefix, text, bg;
  if (m === 'qoq') {
    // Honor the user's explicit Baseline (PQ) — falls back to CQ-1 only if PQ unset
    const allQ = DASH_DATA.quarters || [];
    const i = allQ.indexOf(CQ);
    const naturalPrior = i > 0 ? allQ[i-1] : CQ;
    const baseline = PQ || naturalPrior;
    prefix = 'QoQ';
    text = `${qLabel(baseline)} → ${qLabel(CQ)}`;
    bg = '#2563eb';
  } else if (m === 'yoy') {
    const q24 = ((DASH_DATA.port24 || {}).quarters || []).slice(-1)[0] || '';
    const q25 = (DASH_DATA.quarters || []).slice(-1)[0] || '';
    prefix = 'YoY';
    text = `P24 ${qLabel(q24)} → P25 ${qLabel(q25)}`;
    bg = '#7c3aed';
  } else {
    const allQ = DASH_DATA.quarters || [];
    const start = HIST_START || allQ[0];
    const end   = HIST_END   || allQ[allQ.length-1];
    prefix = 'Historical';
    text = `${qLabel(start)} → ${qLabel(end)}`;
    bg = '#0891b2';
  }
  return `<span style="display:inline-block;font-size:9px;font-weight:700;color:#fff;background:${bg};padding:2px 8px;border-radius:10px;letter-spacing:.03em;vertical-align:middle;margin-left:10px;text-transform:none;white-space:nowrap" title="Active comparison lens">${prefix} · ${text}</span>`;
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
