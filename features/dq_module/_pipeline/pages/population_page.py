"""D6 — Population Stability dashboard.

Includes 3 segment filters (Business Unit / Basel II Category / Risk Rating).
When a filter is active, KPIs + time-series charts show the sliced subset;
segment-level views (mix, migration, by_segment table) display a banner
explaining they're hidden in filtered mode.

The top control panel uses the "Tabbed comparison mode + Filter chips"
design: comparison mode renders as full-width browser-style tabs, and the
three segment filters render as clickable chips that open small option
popovers.
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 6: POPULATION STABILITY ──────────────────────────────
// ═══════════════════════════════════════════════════════════════
let POP_FILTER = {{ dim: null, value: null }};
// Retained Portfolio section state (independent of global CMP_MODE)
let RETAINED_SNAPSHOT = null;   // null = use global CQ; else specific quarter key like '2025Q4'
let CRR_VIEW = 'change';        // 'change' = CRR upgrade/downgrade counts; 'exposure' = balance Δ

// CRR Migration Matrix drilldown: set of "fromGrade|toGrade" keys (same shape
// as Completeness's MIG_SELECTION). When non-empty, the matrix cells render
// with orange-bordered selected styling and a Drilldown panel appears showing
// aggregated stats for the selected transitions.
let CRR_MIG_SELECTION = new Set();

function setRetainedSnapshot(q) {{ RETAINED_SNAPSHOT = q || null; renderTab('population'); }}
function setCrrView(v) {{ CRR_VIEW = v; renderTab('population'); }}
function toggleCrrMigCell(from, to, evt) {{
  if (evt && evt.stopPropagation) evt.stopPropagation();
  const key = from + '|' + to;
  const additive = !!(evt && (evt.shiftKey || evt.ctrlKey || evt.metaKey));
  if (additive) {{
    if (CRR_MIG_SELECTION.has(key)) CRR_MIG_SELECTION.delete(key);
    else CRR_MIG_SELECTION.add(key);
  }} else {{
    if (CRR_MIG_SELECTION.size === 1 && CRR_MIG_SELECTION.has(key)) {{
      CRR_MIG_SELECTION.clear();
    }} else {{
      CRR_MIG_SELECTION.clear();
      CRR_MIG_SELECTION.add(key);
    }}
  }}
  renderTab('population');
}}
function clearCrrMigSelection() {{ CRR_MIG_SELECTION.clear(); renderTab('population'); }}
function setPopFilter(dim, value) {{
  // Single-active filter: setting a value clears the other dimensions
  if (!value) {{
    POP_FILTER = {{ dim: null, value: null }};
  }} else {{
    POP_FILTER = {{ dim, value }};
  }}
  renderTab('population');
}}
function clearPopFilter() {{ POP_FILTER = {{ dim: null, value: null }}; renderTab('population'); }}

function _popSlice() {{
  if (!POP_FILTER.dim || !POP_FILTER.value) return null;
  const d = getQData(CQ);
  return ((d.population || {{}}).slices || {{}})[POP_FILTER.dim]?.[POP_FILTER.value] || null;
}}
function _popSliceTS() {{
  if (!POP_FILTER.dim || !POP_FILTER.value) return null;
  return ((DASH_DATA.time_series.population_slices || {{}})[POP_FILTER.dim] || {{}})[POP_FILTER.value] || [];
}}

// ───────────────────────────────────────────────────────────────
// Tabbed comparison mode + Filter chips (top control panel)
// ───────────────────────────────────────────────────────────────
// Uses the same _toggleCompPopover() helper that the Completeness page
// registers globally — no extra setup needed.
function _popTopTabbedChips(filterDims, totalCount) {{
  const _modeColor = CMP_MODE === 'qoq' ? '#2563eb'
                   : CMP_MODE === 'yoy' ? '#7c3aed' : '#0891b2';

  const tabBtn = (id,lbl) => `<button onclick="setCmpMode('${{id}}')" style="font-size:12px;padding:8px 18px;background:${{CMP_MODE===id?'#fff':'transparent'}};border:1px solid ${{CMP_MODE===id?'#e2e8f0':'transparent'}};border-bottom:${{CMP_MODE===id?'2px solid '+_modeColor:'2px solid transparent'}};margin-bottom:-2px;color:${{CMP_MODE===id?_modeColor:'#64748b'}};font-weight:${{CMP_MODE===id?'700':'500'}};cursor:pointer;border-radius:6px 6px 0 0">${{lbl}}</button>`;

  // Contextual quarter-pair row under the active tab (mirrors comparison_mode._quarterDropdowns)
  let ctxRow = '';
  if (CMP_MODE === 'qoq') {{
    const qOpts = (target) => [...DASH_DATA.quarters].reverse()
      .map(q => `<option value="${{q}}"${{q===target?' selected':''}}>${{qLabel(q)}}</option>`).join('');
    ctxRow = `<span style="font-size:11px;color:#64748b">Baseline</span><select onchange="setCompareQuarter(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">${{qOpts(PQ)}}</select>
              <span style="font-size:11px;color:#64748b">→ Current</span><select onchange="setCurrentQuarter(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">${{qOpts(CQ)}}</select>`;
  }} else if (CMP_MODE === 'historical') {{
    const allQ = DASH_DATA.quarters || [];
    const start = HIST_START || allQ[0];
    const end   = HIST_END   || allQ[allQ.length-1];
    const opts = (sel) => allQ.map(q => `<option value="${{q}}"${{q===sel?' selected':''}}>${{qLabel(q)}}</option>`).join('');
    ctxRow = `<span style="font-size:11px;color:#64748b">From</span><select onchange="setHistRange('start',this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">${{opts(start)}}</select>
              <span style="font-size:11px;color:#64748b">→ To</span><select onchange="setHistRange('end',this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">${{opts(end)}}</select>
              <button onclick="setHistRange('start','');setHistRange('end','')" style="font-size:10px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;color:#64748b;cursor:pointer">reset range</button>`;
  }} else {{
    const q25 = (DASH_DATA.quarters || []).slice(-1)[0] || '';
    const q24 = ((DASH_DATA.port24 || {{}}).quarters || []).slice(-1)[0] || '';
    ctxRow = `<span style="font-size:11px;color:#64748b">Fixed pair —</span><span style="font-size:11px;color:#0f172a;font-family:monospace;font-weight:600">P24 ${{qLabel(q24)}} → P25 ${{qLabel(q25)}}</span>`;
  }}

  // Filter chips — one per population segment dimension. Each chip opens a
  // small popover with "All" + the dim's values. Selecting a value calls
  // setPopFilter (which enforces single-active behaviour).
  const chipsHtml = Object.entries(filterDims).map(([dim, meta]) => {{
    const isActive  = POP_FILTER.dim === dim;
    const display   = isActive ? POP_FILTER.value : 'All';
    const popoverId = `pop-chip-${{dim}}`;
    const optsHtml = ['<div onclick="setPopFilter(\\''+dim+'\\',\\'\\');_toggleCompPopover(\\''+popoverId+'\\',event)" style="font-size:11px;padding:6px 12px;cursor:pointer;color:'+(isActive?'#0f172a':_modeColor)+';font-weight:'+(isActive?'500':'700')+';border-radius:4px" onmouseover="this.style.background=\\'#f1f5f9\\'" onmouseout="this.style.background=\\'transparent\\'">All'+(isActive?'':' ✓')+'</div>']
      .concat((meta.values||[]).map(v => `<div onclick="setPopFilter('${{dim}}','${{v}}');_toggleCompPopover('${{popoverId}}',event)" style="font-size:11px;padding:6px 12px;cursor:pointer;color:${{isActive && POP_FILTER.value===v?_modeColor:'#0f172a'}};font-weight:${{isActive && POP_FILTER.value===v?'700':'500'}};border-radius:4px" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='transparent'">${{v}}${{isActive && POP_FILTER.value===v?' ✓':''}}</div>`)).join('');
    return `<div style="position:relative;display:inline-block">
      <button data-comp-popover-trigger onclick="_toggleCompPopover('${{popoverId}}',event)" style="font-size:11px;padding:5px 12px;border:1px solid ${{isActive?_modeColor:'#cbd5e1'}};background:${{isActive?_modeColor:'#fff'}};color:${{isActive?'#fff':'#475569'}};border-radius:14px;cursor:pointer;font-weight:${{isActive?'600':'500'}}">
        ${{meta.label}}: <strong>${{display}}</strong> ▾
      </button>
      <div id="${{popoverId}}" data-comp-popover style="display:none;position:absolute;top:100%;left:0;z-index:50;background:#fff;border:1px solid #cbd5e1;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.12);padding:4px;min-width:200px;max-height:280px;overflow-y:auto;margin-top:6px">
        ${{optsHtml}}
      </div>
    </div>`;
  }}).join('');

  return `
    <div style="position:sticky;top:0;z-index:20;background:#fff;margin-bottom:14px;border-bottom:1px solid #e2e8f0;padding-bottom:10px">
      <!-- Mode tabs -->
      <div style="display:flex;gap:0;border-bottom:2px solid #e2e8f0;align-items:flex-end">
        ${{tabBtn('qoq','QoQ — Same Portfolio')}}
        ${{tabBtn('yoy','YoY — 2024 vs 2025')}}
        ${{tabBtn('historical','Historical')}}
        ${{POP_FILTER.dim ? `<span style="margin-left:auto;font-size:10px;color:#92400e;background:#fef3c7;border:1px solid #fbbf24;padding:3px 10px;border-radius:10px;margin:0 0 4px 0;font-weight:700">⚡ Filter active</span>` : ''}}
      </div>
      <!-- Contextual quarter row -->
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 4px 0">
        ${{ctxRow}}
      </div>
      <!-- Filter chips -->
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:8px 4px 0">
        <span style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;margin-right:2px">Filter Population</span>
        ${{chipsHtml}}
        ${{POP_FILTER.dim ? '<button onclick="clearPopFilter()" style="font-size:10px;padding:3px 10px;border:1px dashed #cbd5e1;background:transparent;border-radius:14px;color:#64748b;cursor:pointer">× Clear filter</button>' : ''}}
        <span style="margin-left:auto;font-size:10px;color:#64748b;font-style:italic">One filter at a time — selecting a value clears the others</span>
      </div>
    </div>`;
}}

function renderPopulation() {{
  const d   = getQData(CQ);
  const pd_ = getQData(PQ);
  const ts   = DASH_DATA.time_series;
  const gov  = d.governance || {{}};
  const fclPop = d.fcl_population || {{}};

  // Effective population metrics — sliced if filter is active, else the full unfiltered metrics
  const slice = _popSlice();
  const pop  = slice || (d.population || {{}});
  const ppop = pd_.population || {{}};
  const filterActive = !!slice;

  const filterDims = DASH_DATA.population_filter_dims || {{}};

  const filterBanner = filterActive
    ? `<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#fef3c7;border:1px solid #fbbf24;border-radius:6px;margin-bottom:12px;font-size:12px">
        <span style="font-weight:700;color:#92400e">⚡ Filter active:</span>
        <span style="color:#92400e">${{(filterDims[POP_FILTER.dim]||{{}}).label}} = <strong>${{POP_FILTER.value}}</strong></span>
        <span style="color:#92400e;font-style:italic">— ${{fmtN(pop.total)}} accounts in this slice</span>
        <button onclick="clearPopFilter()" style="margin-left:auto;font-size:10px;padding:3px 10px;border:1px solid #92400e;background:#fff;color:#92400e;border-radius:4px;cursor:pointer">Clear Filter</button>
       </div>`
    : '';

  // KPIs — use sliced metrics if filter is active
  const kpis = [
    {{icon:'👥',label:'Total Accounts',     val:fmtN(pop.total),       sub: filterActive ? 'in slice' : '',                           delta:arrow(pop.net_change,true)}},
    {{icon:'🆕',label:'New Accounts',       val:fmtN(pop.new),         sub:`${{pct(pop.new_pct)}} of total`,                           delta:''}},
    {{icon:'⬇️',label:'Dropped Accounts',   val:fmtN(pop.dropped),     sub:`${{pct(pop.dropped_pct)}} of prior total`,                 delta:''}},
    {{icon:'🔄',label:'Continuing Accounts',val:fmtN(pop.continuing),  sub:`${{pct(pop.continuing_pct)}} of total`,                    delta:''}},
    {{icon:'📊',label:'Net Change',         val:(pop.net_change||0)>=0?'+'+fmtN(pop.net_change):fmtN(pop.net_change), sub:`${{pct(pop.net_change_pct)}} vs prior`, delta:''}},
    {{icon:'📈',label:filterActive ? 'Retention %' : 'Population PSI', val: filterActive ? pct(pop.continuing_pct) : fmt(pop.psi,3), sub: filterActive ? 'of prior cohort' : (pop.psi_label||'—'), delta:''}},
  ];
  const kpiHtml = kpis.map(k=>`<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value">${{k.val}}</div>
    ${{k.sub?`<div class="kpi-sub">${{k.sub}}</div>`:''}}</div>`).join('');

  // Segment table — only when no filter (otherwise misleading)
  const segRows = filterActive ? '' : ((d.population||{{}}).by_segment||[]).map(s=>`<tr>
    <td>${{s.segment}}</td>
    <td>${{fmtN(s.prior_accounts)}}</td>
    <td>${{pct(s.new_pct)}}</td>
    <td>${{pct(s.dropped_pct)}}</td>
    <td>${{fmtN(s.current_accounts)}}</td>
    <td style="color:${{s.net_change>=0?'var(--green)':'var(--red)'}}">${{s.net_change>=0?'+':''}}${{fmtN(s.net_change)}}</td>
    <td style="color:${{s.net_change_pct>=0?'var(--green)':'var(--red)'}}">${{s.net_change_pct>=0?'+':''}}${{pct(s.net_change_pct)}}</td>
  </tr>`).join('');

  const filteredNotice = `<div style="padding:24px;text-align:center;color:#92400e;background:#fef3c7;border-radius:6px;font-size:12px">
    🔒 Segment-level breakdown is hidden when a filter is active.
    <br><span style="color:#64748b;font-size:11px">Clear the filter to see segment migrations and by-segment table.</span>
  </div>`;

  const insights = (gov.population_insights || [
    {{icon:'📈',text:'Population trend driven by new originations across all segments.'}},
    {{icon:'ℹ️',text:`PSI stands at ${{fmt(pop.psi||0,2)}} (${{pop.psi_label||'—'}}), indicating ${{pop.psi_label==='Stable'?'no significant':'notable'}} composition shift.`}},
  ]);

  // ── Retained Portfolio section: resolve local snapshot + its natural prior ──
  const retSnap = RETAINED_SNAPSHOT || CQ;
  const _allQ = DASH_DATA.quarters || [];
  const _retIdx = _allQ.indexOf(retSnap);
  const retPQ = _retIdx > 0 ? _allQ[_retIdx - 1] : retSnap;
  const retData = getQData(retSnap);
  const crrAnalysis = (retData.population || {{}}).crr_analysis;
  const mig = (crrAnalysis || {{}}).crr_migration_matrix || {{grades: [], matrix: {{}}}};

  const retSnapOpts = [..._allQ].reverse()
    .map(q => `<option value="${{q}}"${{q===retSnap?' selected':''}}>${{qLabel(q)}}</option>`).join('');

  let crrMatrixHtml = '';
  if (mig.grades && mig.grades.length) {{
    const grades = mig.grades;
    const M = mig.matrix || {{}};
    let maxCount = 0;
    grades.forEach(f => grades.forEach(t => {{
      if (f !== t) maxCount = Math.max(maxCount, (M[f] || {{}})[t]?.count || 0);
    }}));
    const cellHtml = (f, t) => {{
      const cell = (M[f] || {{}})[t] || {{count: 0, balance: 0}};
      const ff = parseFloat(f), tt = parseFloat(t);
      if (cell.count === 0) return '<td style="text-align:center;color:#cbd5e1;font-size:11px;border:1px solid #f1f5f9">—</td>';
      let bg, fg;
      if (ff === tt) {{ bg = 'rgba(99,102,241,0.18)'; fg = '#3730a3'; }}
      else if (tt < ff) {{
        const intensity = maxCount > 0 ? Math.min(1, cell.count / maxCount) : 0;
        bg = `rgba(22,163,74,${{0.15 + intensity * 0.55}})`;
        fg = intensity > 0.4 ? '#fff' : '#14532d';
      }} else {{
        const intensity = maxCount > 0 ? Math.min(1, cell.count / maxCount) : 0;
        bg = `rgba(220,38,38,${{0.15 + intensity * 0.55}})`;
        fg = intensity > 0.4 ? '#fff' : '#7f1d1d';
      }}
      const balStr = cell.balance >= 0 ? '+$' + fmt(cell.balance, 1) + 'M' : '-$' + fmt(-cell.balance, 1) + 'M';
      const key = f + '|' + t;
      const selected = CRR_MIG_SELECTION.has(key);
      const border = selected
        ? 'border:3px solid #9a3412;box-shadow:inset 0 0 0 2px #fff7ed'
        : 'border:1px solid #fff';
      const onClick = `onclick="toggleCrrMigCell('${{f}}','${{t}}',event)"`;
      const tooltip = `From CRR ${{f}} → ${{t}}: ${{cell.count}} facilities (${{balStr}})\\n(Click to drill into this transition. Shift / Ctrl-click for multi-select.)`;
      const cellLabel = selected ? `${{cell.count}}<div style="font-size:8px;color:#9a3412;font-weight:700;letter-spacing:.05em">SELECTED</div>` : cell.count;
      return `<td title="${{tooltip}}" ${{onClick}} style="background:${{bg}};color:${{fg}};text-align:center;font-weight:600;${{border}};padding:6px;cursor:pointer;user-select:none">${{cellLabel}}</td>`;
    }};
    const headerRow = `<tr>
      <th style="background:#0f1d35;color:#fff;font-size:10px;text-align:center;padding:6px;border:1px solid #fff">From \\\\ To</th>
      ${{grades.map(g => `<th style="background:#1e293b;color:#fff;font-size:11px;text-align:center;padding:6px;border:1px solid #fff">${{g}}</th>`).join('')}}
    </tr>`;
    const bodyRows = grades.map(f => `<tr>
      <th style="background:#1e293b;color:#fff;font-size:11px;text-align:right;padding:6px;border:1px solid #fff">${{f}}</th>
      ${{grades.map(t => cellHtml(f, t)).join('')}}
    </tr>`).join('');
    // Aggregate selection stats for the drilldown panel
    let selStats = null;
    if (CRR_MIG_SELECTION.size) {{
      let totFac = 0, totBal = 0, upN = 0, dnN = 0, diagN = 0;
      const sel = [];
      for (const key of CRR_MIG_SELECTION) {{
        const [f, t] = key.split('|');
        const cell = (M[f] || {{}})[t] || {{count: 0, balance: 0}};
        totFac += cell.count || 0;
        totBal += cell.balance || 0;
        const ff = parseFloat(f), tt = parseFloat(t);
        if (ff === tt) diagN += cell.count;
        else if (tt < ff) upN += cell.count;
        else dnN += cell.count;
        sel.push({{f, t, count: cell.count, balance: cell.balance}});
      }}
      sel.sort((a, b) => parseFloat(a.f) - parseFloat(b.f) || parseFloat(a.t) - parseFloat(b.t));
      const balStr = totBal >= 0 ? '+$' + fmt(totBal, 1) + 'M' : '-$' + fmt(-totBal, 1) + 'M';
      const selChips = sel.slice(0, 8).map(s => `<span style="display:inline-block;font-size:10px;font-family:monospace;color:#475569;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:1px 8px;margin-right:4px">${{s.f}} → ${{s.t}} · ${{s.count}}</span>`).join('');
      const moreCount = sel.length > 8 ? ` · +${{sel.length-8}} more` : '';
      selStats = `<div style="background:#fafafa;border:1px solid #e2e8f0;border-left:3px solid #9a3412;border-radius:6px;padding:10px 12px;margin-bottom:10px">
        <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:8px">
          <span style="font-size:10px;font-weight:700;color:#9a3412;text-transform:uppercase;letter-spacing:.05em">Selection drilldown</span>
          <span style="font-size:11px;color:#475569"><strong>${{CRR_MIG_SELECTION.size}}</strong> transition${{CRR_MIG_SELECTION.size===1?'':'s'}} · <strong>${{fmtN(totFac)}}</strong> facilit${{totFac===1?'y':'ies'}} · <strong style="color:${{totBal>=0?'#16a34a':'#dc2626'}}">${{balStr}}</strong> balance change</span>
          <button onclick="clearCrrMigSelection()" style="margin-left:auto;font-size:10px;padding:2px 10px;border:1px solid #e2e8f0;border-radius:4px;background:transparent;color:#64748b;cursor:pointer;font-weight:500">clear</button>
        </div>
        <div style="display:flex;gap:14px;font-size:11px;color:#475569;margin-bottom:6px">
          <span><span style="display:inline-block;width:10px;height:10px;background:#16a34a;border-radius:50%;margin-right:5px;vertical-align:middle"></span><strong>${{fmtN(upN)}}</strong> upgrades</span>
          <span><span style="display:inline-block;width:10px;height:10px;background:#6366f1;border-radius:50%;margin-right:5px;vertical-align:middle"></span><strong>${{fmtN(diagN)}}</strong> no-change</span>
          <span><span style="display:inline-block;width:10px;height:10px;background:#dc2626;border-radius:50%;margin-right:5px;vertical-align:middle"></span><strong>${{fmtN(dnN)}}</strong> downgrades</span>
        </div>
        <div style="line-height:1.8">${{selChips}}<span style="font-size:10px;color:#94a3b8;font-style:italic">${{moreCount}}</span></div>
      </div>`;
    }}

    crrMatrixHtml = `
      ${{selStats || ''}}
      <div style="overflow-x:auto">
        <table style="border-collapse:collapse;font-size:11px">
          <thead>${{headerRow}}</thead>
          <tbody>${{bodyRows}}</tbody>
        </table>
      </div>
      <div style="margin-top:10px;font-size:10px;color:var(--text-muted);display:flex;gap:14px;flex-wrap:wrap">
        <span><span style="display:inline-block;width:14px;height:14px;background:rgba(22,163,74,0.55);border-radius:2px;margin-right:6px;vertical-align:middle"></span>Upgrade (better grade)</span>
        <span><span style="display:inline-block;width:14px;height:14px;background:rgba(99,102,241,0.18);border-radius:2px;margin-right:6px;vertical-align:middle"></span>No change (diagonal)</span>
        <span><span style="display:inline-block;width:14px;height:14px;background:rgba(220,38,38,0.55);border-radius:2px;margin-right:6px;vertical-align:middle"></span>Downgrade (worse grade)</span>
        <span style="color:#9a3412;font-weight:500">Click any cell to drill in; Shift / Ctrl-click for multi-select</span>
        <span style="margin-left:auto;font-style:italic">Hover any cell for facility count + balance delta</span>
      </div>`;
  }}

  document.getElementById('tab-population').innerHTML = `
    <div class="dash-header">
      <h2>Population Stability Dashboard</h2>
      <p>Monitor population movements, account lifecycle, and segment stability over time.</p>
    </div>

    ${{_popTopTabbedChips(filterDims, fmtN(pop.total))}}
    ${{filterBanner}}

    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr)">${{kpiHtml}}</div>

    <div class="section-card">
      <div class="section-title">Total Records Over Time ${{_lensChip()}}</div>
      <div id="pop-chart-movement" class="chart-box"></div>
    </div>

    <div class="section-card">
      <div class="section-title">Churn Dynamics — New / Continuing / Dropped per Quarter${{filterActive?' (filtered)':''}} ${{_lensChip()}}</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">
        New (green) adds growth above the zero line, Dropped (red) extends below — net total tracked on the right axis.
        This view subsumes the Account Lifecycle donut, the Facility Flow Sankey, and the Population Movement Waterfall.
      </div>
      <div id="pop-chart-churn" style="min-height:420px"></div>
    </div>

    <div class="section-card">
      <div class="section-title">Segment Composition Over Time (% of Portfolio) ${{_lensChip()}}</div>
      ${{filterActive ? filteredNotice : '<div id="pop-chart-segment-mix" class="chart-box"></div><div style="font-size:10px;color:var(--text-muted);margin-top:6px">Stacked share of each Business Unit across quarters — reveals portfolio mix shifts.</div>'}}
    </div>

    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:14px">
        <div class="section-title" style="margin:0">Retained Portfolio — CRR Migration Analysis</div>
        <div style="display:flex;align-items:center;gap:8px;background:#f8fafc;border:1px solid var(--border);border-radius:6px;padding:6px 10px">
          <label style="font-size:10px;color:var(--text-muted);font-weight:700;text-transform:uppercase;letter-spacing:.05em">Snapshot Quarter</label>
          <select onchange="setRetainedSnapshot(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;background:#fff;min-width:110px">
            ${{retSnapOpts}}
          </select>
          <span style="font-size:11px;color:var(--text-muted);font-style:italic">vs ${{qLabel(retPQ)}}</span>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;align-items:stretch">
        <div style="border:1px solid var(--border);border-radius:8px;padding:14px;background:#fff">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;gap:12px;flex-wrap:wrap">
            <div style="font-size:12px;font-weight:700;color:#111827">
              ${{CRR_VIEW==='change' ? 'Customer Risk Rating Change — Retained Facilities' : 'Existing Customer Exposure Change ($M per CRR Grade)'}}
            </div>
            <div style="display:flex;align-items:center;gap:6px">
              <label style="font-size:10px;color:var(--text-muted);font-weight:700;text-transform:uppercase;letter-spacing:.05em">View</label>
              <select onchange="setCrrView(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;background:#fff">
                <option value="change"${{CRR_VIEW==='change'?' selected':''}}>↑↓ CRR Change (count)</option>
                <option value="exposure"${{CRR_VIEW==='exposure'?' selected':''}}>$ Exposure Change ($M)</option>
              </select>
            </div>
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
            ${{CRR_VIEW==='change'
              ? 'Number of facilities upgraded (↑ blue) vs downgraded (↓ red) within each CRR grade, with net change line'
              : 'Net balance change ($M) for retained facilities, bucketed by current Customer Risk Rating'}}
          </div>
          <div id="pop-chart-crr-view" style="min-height:320px"></div>
        </div>

        <div style="border:1px solid var(--border);border-radius:8px;padding:14px;background:#fff;display:flex;flex-direction:column">
          <div style="font-size:12px;font-weight:700;color:#111827;margin-bottom:4px">Retained Portfolio Summary</div>
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:12px">Aggregates over all retained facilities</div>
          <div id="pop-crr-summary" style="flex:1"></div>
        </div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">CRR Migration Matrix — ${{qLabel(retPQ)}} → ${{qLabel(retSnap)}}</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        Number of retained facilities that moved from each <strong>prior CRR grade (rows)</strong>
        to each <strong>current CRR grade (columns)</strong>. Diagonal cells = no change.
        Hover any cell for balance change.
      </div>
      ${{crrMatrixHtml || '<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">No retained-facility data available for this quarter pair.</div>'}}
    </div>

    ${{_popKeyColumnsSample()}}

    <div class="section-card">
      <div class="section-title">Population Stability by Business Segment</div>
      ${{filterActive ? filteredNotice : `<table><thead><tr><th>Segment</th><th>Prior Q Accounts</th><th>New %</th><th>Dropped %</th><th>Current Accounts</th><th>Net Change #</th><th>Net Change %</th></tr></thead><tbody>${{segRows}}</tbody></table>`}}
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">New vs Dropped Accounts by Reason</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <div>
            <div style="font-size:11px;font-weight:700;color:var(--green);margin-bottom:6px">Top Reasons — New Accounts</div>
            ${{((d.population||{{}}).new_reasons||[]).map(r=>`<div style="display:flex;justify-content:space-between;font-size:11px;padding:4px 0;border-bottom:1px solid #f1f5f9">
              <span>${{r.reason}}</span><span style="font-weight:600;color:var(--green)">${{r.pct}}%</span></div>`).join('')}}
          </div>
          <div>
            <div style="font-size:11px;font-weight:700;color:var(--red);margin-bottom:6px">Top Reasons — Dropped Accounts</div>
            ${{((d.population||{{}}).drop_reasons||[]).map(r=>`<div style="display:flex;justify-content:space-between;font-size:11px;padding:4px 0;border-bottom:1px solid #f1f5f9">
              <span>${{r.reason}}</span><span style="font-weight:600;color:var(--red)">${{r.pct}}%</span></div>`).join('')}}
          </div>
        </div>
      </div>
      <div class="section-card">
        <div class="section-title">Key Insights (AI-Generated)</div>
        ${{insights.map(i=>`<div class="insight-card"><span class="insight-icon">📌</span>${{i.text}}</div>`).join('')}}
      </div>
    </div>

  `;

  const PLcfg = {{responsive:true,displayModeBar:false}};
  const sliceTS = _popSliceTS();

  const applyCmpFilter = (arr) => {{
    if (!arr || !arr.length) return [];
    if (CMP_MODE === 'qoq') return arr.slice(-12);
    if (CMP_MODE === 'yoy') {{
      const yr = (typeof YOY_25_YEAR !== 'undefined' && YOY_25_YEAR !== null)
        ? YOY_25_YEAR
        : Math.max(...arr.map(r => +r.quarter.slice(0,4)));
      return arr.filter(r => +r.quarter.slice(0,4) === yr);
    }}
    return arr.filter(r => {{
      if (typeof HIST_START !== 'undefined' && HIST_START && r.quarter < HIST_START) return false;
      if (typeof HIST_END   !== 'undefined' && HIST_END   && r.quarter > HIST_END)   return false;
      return true;
    }});
  }};

  // Total records over time
  if (filterActive) {{
    const arr = applyCmpFilter(sliceTS);
    Plotly.react('pop-chart-movement', [{{
      x: arr.map(r => r.label),
      y: arr.map(r => r.total),
      name: 'Port 2025 — ' + POP_FILTER.value,
      type:'scatter', mode:'lines+markers',
      line:{{color:'#16a34a',width:2}}, marker:{{size:3,color:'#16a34a'}},
    }}], {{..._cmpLayout('Records (filtered)', 220), showlegend:true}}, _cmpCfg);
  }} else {{
    Plotly.react('pop-chart-movement', _cmpTraces('population_over_time','total','Port 2024 Total','Port 2025 Total'),
      _cmpLayout('Records',220), _cmpCfg);
  }}

  // Segment composition (stacked area) — only when no filter
  if (!filterActive) {{
    const segMix = {{}};
    const qList = (() => {{
      const allQ = DASH_DATA.quarters || [];
      if (CMP_MODE === 'qoq') return allQ.slice(-12);
      if (CMP_MODE === 'yoy') {{
        if (!allQ.length) return [];
        const yr = (typeof YOY_25_YEAR !== 'undefined' && YOY_25_YEAR !== null)
          ? YOY_25_YEAR
          : Math.max(...allQ.map(q => +q.slice(0,4)));
        return allQ.filter(q => +q.slice(0,4) === yr);
      }}
      return allQ.filter(q => {{
        if (typeof HIST_START !== 'undefined' && HIST_START && q < HIST_START) return false;
        if (typeof HIST_END   !== 'undefined' && HIST_END   && q > HIST_END)   return false;
        return true;
      }});
    }})();
    qList.forEach(q => {{
      const segs = ((DASH_DATA.by_quarter[q]||{{}}).population||{{}}).by_segment || [];
      segs.forEach(s => {{
        if (!segMix[s.segment]) segMix[s.segment] = qList.map(()=>0);
      }});
    }});
    qList.forEach((q, i) => {{
      const segs = ((DASH_DATA.by_quarter[q]||{{}}).population||{{}}).by_segment || [];
      segs.forEach(s => {{
        if (segMix[s.segment]) segMix[s.segment][i] = s.current_accounts || 0;
      }});
    }});
    const segColors = ['#2563eb','#16a34a','#dc2626','#d97706','#7c3aed','#0891b2','#db2777','#65a30d','#6b7280'];
    const xLabels = qList.map(q => CMP_MODE==='yoy' ? 'Q'+q.slice(5) : qLabel(q));
    const segTraces = Object.entries(segMix).map(([seg, vals], i) => ({{
      name: seg, x: xLabels, y: vals,
      type: 'scatter', mode: 'none',
      stackgroup: 'one', groupnorm: 'percent',
      fillcolor: segColors[i % segColors.length],
      hovertemplate: '%{{x}}<br>'+seg+': %{{y:.1f}}%<extra></extra>',
    }}));
    Plotly.react('pop-chart-segment-mix', segTraces, {{
      margin:{{t:10,r:10,b:50,l:50}}, height:220,
      paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
      xaxis:{{tickangle:-45,tickfont:{{size:8}}}},
      yaxis:{{title:'% of portfolio',gridcolor:'#f1f5f9',tickfont:{{size:9}},range:[0,100]}},
      legend:{{orientation:'h',y:-0.35,font:{{size:9}}}},
      showlegend: true,
    }}, _cmpCfg);
  }}

  // ── CRR Migration Analysis (Retained Customers) ──
  const crr = crrAnalysis;
  const crrViewEl = document.getElementById('pop-chart-crr-view');
  const summaryEl = document.getElementById('pop-crr-summary');

  if (!crr || !crr.by_crr || !crr.by_crr.length) {{
    if (crrViewEl) crrViewEl.innerHTML = '<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">No retained-facility migration data available for this quarter pair.</div>';
    if (summaryEl) summaryEl.innerHTML = '<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">—</div>';
  }} else {{
    const grades = crr.by_crr.map(r => r.crr);
    const xCommon = {{
      type: 'category',
      categoryorder: 'array',
      categoryarray: grades,
      title: {{ text: '<b>CRR Grade</b>', font: {{ size: 12, color: '#111827' }}, standoff: 12 }},
      tickfont: {{ size: 11, color: '#111827' }},
      tickangle: 0,
      showgrid: false,
    }};

    if (CRR_VIEW === 'change') {{
      Plotly.react('pop-chart-crr-view', [
        {{
          type:'bar', name:'↑ Upgrades', x:grades, y:crr.by_crr.map(r => r.upgrades),
          marker:{{color:'#2563eb', line:{{color:'#1d4ed8',width:1}}}},
          hovertemplate:'<b>CRR %{{x}}</b><br>Upgrades: +%{{y}}<extra></extra>',
        }},
        {{
          type:'bar', name:'↓ Downgrades', x:grades, y:crr.by_crr.map(r => r.downgrades),
          marker:{{color:'#dc2626', line:{{color:'#991b1b',width:1}}}},
          hovertemplate:'<b>CRR %{{x}}</b><br>Downgrades: %{{y}}<extra></extra>',
        }},
        {{
          type:'scatter', name:'Net change', x:grades, y:crr.by_crr.map(r => r.net),
          mode:'lines+markers',
          line:{{color:'#0f1d35',width:2.5}},
          marker:{{size:7, color:'#0f1d35', line:{{color:'#fff',width:1.5}}}},
          hovertemplate:'<b>CRR %{{x}}</b><br>Net: %{{y:+d}}<extra></extra>',
        }},
      ], {{
        barmode:'relative', bargap: 0.25,
        margin:{{t:50,r:20,b:60,l:60}}, height:320,
        paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
        xaxis: xCommon,
        yaxis:{{
          title:{{text:'<b>Facilities (±)</b>', font:{{size:12,color:'#111827'}}}},
          gridcolor:'#e5e7eb', zerolinecolor:'#0f1d35', zerolinewidth:2,
          tickfont:{{size:10,color:'#374151'}},
        }},
        legend:{{orientation:'h', y:1.10, x:0.5, xanchor:'center', font:{{size:11}}, bgcolor:'rgba(255,255,255,0.8)'}},
      }}, PLcfg);
    }} else {{
      const expVals = crr.by_crr.map(r => r.balance_change);
      const expFmt = (v) => (v >= 0 ? '+' : '') + fmt(v,1);
      Plotly.react('pop-chart-crr-view', [{{
        type:'bar', x:grades, y:expVals,
        marker:{{
          color: expVals.map(v => v >= 0 ? '#16a34a' : '#dc2626'),
          line:{{color: expVals.map(v => v >= 0 ? '#15803d' : '#991b1b'), width:1}},
        }},
        text: expVals.map(expFmt),
        textposition:'outside', textfont:{{size:10, color:'#111827'}},
        cliponaxis: false,
        hovertemplate:'<b>CRR %{{x}}</b><br>Δ Balance: $%{{y:.1f}}M<extra></extra>',
      }}], {{
        bargap: 0.25, margin:{{t:30,r:20,b:60,l:70}}, height:320,
        paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
        xaxis: xCommon,
        yaxis:{{
          title:{{text:'<b>Δ Balance ($M)</b>', font:{{size:12,color:'#111827'}}}},
          gridcolor:'#e5e7eb', zerolinecolor:'#0f1d35', zerolinewidth:2,
          tickfont:{{size:10,color:'#374151'}},
        }},
        showlegend:false,
      }}, PLcfg);
    }}

    const s = crr.retained_summary;
    const m = crr.retained_metrics;
    const fmtM = v => (v == null ? '—' : (v >= 0 ? '+' : '') + fmt(v,1) + 'M');
    const fmtPct = v => (v == null ? '—' : fmt(v,2) + '%');
    summaryEl.innerHTML = `
      <table style="font-size:12px;margin-bottom:14px">
        <thead>
          <tr><th>Upgrade / Downgrade</th><th style="text-align:right">Count</th><th style="text-align:right">Funded Δ Balance</th></tr>
        </thead>
        <tbody>
          <tr><td>Upgrades</td><td style="text-align:right;color:#16a34a;font-weight:600">${{fmtN(s.upgrades_count)}}</td><td style="text-align:right;color:#16a34a">${{fmtM(s.upgrades_balance)}}</td></tr>
          <tr><td>Downgrades</td><td style="text-align:right;color:#dc2626;font-weight:600">${{fmtN(s.downgrades_count)}}</td><td style="text-align:right;color:#dc2626">${{fmtM(s.downgrades_balance)}}</td></tr>
          <tr style="font-weight:700;background:#f8fafc">
            <td>Net</td>
            <td style="text-align:right;color:${{s.net_count>=0?'#16a34a':'#dc2626'}}">${{s.net_count>=0?'+':''}}${{fmtN(s.net_count)}}</td>
            <td style="text-align:right;color:${{s.net_balance>=0?'#16a34a':'#dc2626'}}">${{fmtM(s.net_balance)}}</td>
          </tr>
        </tbody>
      </table>
      <table style="font-size:12px">
        <thead>
          <tr><th>Retained Customers</th><th style="text-align:right">Avg CRR</th><th style="text-align:right">Imp PD</th></tr>
        </thead>
        <tbody>
          <tr><td>${{qLabel(retPQ)}}</td><td style="text-align:right">${{fmt(m.prior_avg_crr,2)}}</td><td style="text-align:right">${{fmtPct(m.prior_imp_pd)}}</td></tr>
          <tr><td>${{qLabel(retSnap)}}</td><td style="text-align:right">${{fmt(m.current_avg_crr,2)}}</td><td style="text-align:right">${{fmtPct(m.current_imp_pd)}}</td></tr>
        </tbody>
      </table>
      <div style="margin-top:10px;font-size:10px;color:var(--text-muted);font-style:italic">
        Based on ${{fmtN(crr.retained_count)}} retained facilities (FCL-ID present in both quarters).
      </div>
    `;
  }}

  // Churn Dynamics
  const churnTS = filterActive ? applyCmpFilter(sliceTS) : _cmpFilter(_cmpTS25('population_over_time'));
  const churnX = churnTS.map(r => CMP_MODE === 'yoy' ? 'Q'+r.quarter.slice(5) : r.label);
  Plotly.react('pop-chart-churn', [
    {{type:'bar', name:'New',        x:churnX, y:churnTS.map(r => r.new || 0),        marker:{{color:'#16a34a'}}, hovertemplate:'%{{x}}<br>New: +%{{y:,}}<extra></extra>'}},
    {{type:'bar', name:'Dropped',    x:churnX, y:churnTS.map(r => -(r.dropped || 0)), marker:{{color:'#dc2626'}}, hovertemplate:'%{{x}}<br>Dropped: %{{y:,}}<extra></extra>'}},
    {{type:'scatter', name:'Net total', x:churnX, y:churnTS.map(r => r.total || 0), yaxis:'y2', mode:'lines+markers', line:{{color:'#0f1d35',width:2}}, marker:{{size:4}}, hovertemplate:'%{{x}}<br>Total: %{{y:,}}<extra></extra>'}},
  ], {{
    barmode:'relative', margin:{{t:20,r:70,b:70,l:60}}, height:420,
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{{tickangle:-45,tickfont:{{size:10}}}},
    yaxis:{{title:'Accounts (± net flow)',gridcolor:'#f1f5f9',tickfont:{{size:11}},zerolinecolor:'#94a3b8',zerolinewidth:1}},
    yaxis2:{{title:'Total',overlaying:'y',side:'right',showgrid:false,tickfont:{{size:11}}}},
    legend:{{orientation:'h',y:-0.22,font:{{size:11}}}},
  }}, _cmpCfg);
}}

// ═══════════════════════════════════════════════════════════════
// KEY COLUMNS — SAMPLE RECORDS table
// ═══════════════════════════════════════════════════════════════
// Renders a pandas-DataFrame-style preview of the latest quarter's data,
// restricted to the schema-flagged key variables. Always shows the latest
// snapshot (precomputed in processor.py as DASH_DATA.key_sample_rows).
function _popKeyColumnsSample() {{
  // Two data sources:
  //   DEFAULT  → DASH_DATA.key_sample_rows (20 head rows of the latest quarter,
  //              no CRR transition info — used when no matrix cells are selected)
  //   FILTERED → DASH_DATA.crr_facility_sample (~150 retained facilities tagged
  //              with `_crr_transition`, narrowed to the active CRR selection)
  const selActive = CRR_MIG_SELECTION.size > 0;
  let titleSuffix, descPrefix, sourceQ, rowsAll, cols;

  if (selActive) {{
    const crrSample = DASH_DATA.crr_facility_sample || {{}};
    cols = crrSample.columns || [];
    rowsAll = (crrSample.rows || []).filter(r => CRR_MIG_SELECTION.has(r._crr_transition));
    sourceQ = crrSample.current_q;
    titleSuffix = ` — filtered to CRR selection`;
    descPrefix = `Retained facilities (FCL-ID present in both ${{qLabel(crrSample.prior_q)}} and ${{qLabel(crrSample.current_q)}}) whose CRR transition matches the cells you selected in the matrix above.`;
  }} else {{
    const sample = DASH_DATA.key_sample_rows || {{}};
    cols = sample.columns || [];
    rowsAll = sample.rows || [];
    sourceQ = sample.quarter;
    titleSuffix = '';
    descPrefix = `Pandas-style preview: the first ${{rowsAll.length}} rows of the latest quarter's dataframe restricted to the schema-flagged key variables. Use it to sanity-check value formats, null patterns, and ranges before drilling into per-column analytics on the Completeness or Drift tabs.`;
  }}

  if (!cols.length) {{
    return `<div class="section-card">
      <div class="section-title">Key Columns — Sample Records${{titleSuffix}}</div>
      <div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">No sample columns available.</div>
    </div>`;
  }}

  // Cap rendered rows to 30 for readability when the selection matches many facilities
  const CAP = 30;
  const rows = rowsAll.slice(0, CAP);
  const truncated = rowsAll.length - rows.length;

  if (selActive && !rowsAll.length) {{
    return `<div class="section-card">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        <div class="section-title" style="margin:0">Key Columns — Sample Records${{titleSuffix}}</div>
        <button onclick="clearCrrMigSelection()" style="font-size:10px;padding:3px 10px;border:1px solid #cbd5e1;background:#fff;color:#475569;border-radius:4px;cursor:pointer">Clear selection</button>
      </div>
      <div style="padding:24px;color:#92400e;background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;font-size:12px;text-align:center">
        No retained facilities in the sample match the selected transition${{CRR_MIG_SELECTION.size===1?'':'s'}}.
        The sample stratifies up to 5 facilities per matrix cell, so this should be rare — it may indicate stale data or a cell with edge-case grades. Try clearing the selection and inspecting the matrix counts.
      </div>
    </div>`;
  }}

  // Detect numeric columns from actual data
  const isNumericCol = cols.map(c => {{
    let seen = false;
    for (const r of rows) {{
      const v = r[c];
      if (v == null) continue;
      seen = true;
      if (typeof v !== 'number') return false;
    }}
    return seen;
  }});

  const fmtCell = (v, num) => {{
    if (v == null) return '<span style="color:#cbd5e1">—</span>';
    if (num) return Number.isInteger(v) ? fmtN(v) : fmt(v, 3);
    return String(v);
  }};

  const transitionCol = selActive
    ? `<th style="font-size:10px;padding:6px 10px;background:#9a3412;color:#fff;font-weight:700;border:1px solid #1e293b;white-space:nowrap">CRR Transition</th>`
    : '';
  const headRow = cols.map((c, i) => `<th style="font-size:10px;padding:6px 10px;background:#0f1d35;color:#fff;font-weight:700;text-transform:none;white-space:nowrap;border:1px solid #1e293b;text-align:${{isNumericCol[i]?'right':'left'}}">${{c}}</th>`).join('');
  const idxHeader = `<th style="font-size:10px;padding:6px 10px;background:#0f1d35;color:#94a3b8;font-weight:600;border:1px solid #1e293b;text-align:right">#</th>`;

  const bodyRows = rows.map((r, i) => {{
    const cells = cols.map((c, ci) => {{
      const num = isNumericCol[ci];
      return `<td style="font-size:11px;padding:5px 10px;border:1px solid #f1f5f9;white-space:nowrap;font-family:${{num?'monospace':'inherit'}};text-align:${{num?'right':'left'}};color:#0f172a">${{fmtCell(r[c], num)}}</td>`;
    }}).join('');
    const idxCell = `<td style="font-size:10px;padding:5px 10px;border:1px solid #f1f5f9;background:#f8fafc;color:#64748b;font-family:monospace;text-align:right">${{i}}</td>`;
    const transitionCell = selActive
      ? `<td style="font-size:11px;padding:5px 10px;border:1px solid #f1f5f9;font-family:monospace;color:#9a3412;font-weight:700;text-align:center;background:#fff7ed">${{(r._crr_transition || '—').replace('|', ' → ')}}</td>`
      : '';
    return `<tr${{i%2===1?' style="background:#fafafa"':''}}>${{idxCell}}${{transitionCell}}${{cells}}</tr>`;
  }}).join('');

  const headerMeta = selActive
    ? `<strong style="color:#9a3412">${{rowsAll.length}}</strong> retained facilit${{rowsAll.length===1?'y':'ies'}} matching ${{CRR_MIG_SELECTION.size}} selected transition${{CRR_MIG_SELECTION.size===1?'':'s'}}${{truncated>0?` · showing first ${{rows.length}}`:''}}`
    : `${{rows.length}} rows × ${{cols.length}} key column${{cols.length===1?'':'s'}} · snapshot <strong>${{qLabel(sourceQ)}}</strong>`;

  return `<div class="section-card" style="${{selActive?'border-left:3px solid #9a3412':''}}">
    <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:4px">
      <div class="section-title" style="margin:0">Key Columns — Sample Records${{titleSuffix}}</div>
      <div style="display:flex;align-items:center;gap:10px">
        <div style="font-size:11px;color:var(--text-muted)">${{headerMeta}}</div>
        ${{selActive ? `<button onclick="clearCrrMigSelection()" style="font-size:10px;padding:3px 10px;border:1px solid #9a3412;background:#fff;color:#9a3412;border-radius:4px;cursor:pointer;font-weight:600">Clear CRR filter</button>` : ''}}
      </div>
    </div>
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">${{descPrefix}}</div>
    <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:6px">
      <table style="border-collapse:collapse;margin:0">
        <thead><tr>${{idxHeader}}${{transitionCol}}${{headRow}}</tr></thead>
        <tbody>${{bodyRows}}</tbody>
      </table>
    </div>
  </div>`;
}}
"""
