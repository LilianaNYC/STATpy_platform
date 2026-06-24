"""D4 — Completeness dashboard.

Now distinguishes between Key Columns (flagged `key_variable=Y` in the schema)
and All Columns, and provides filters by column scope / severity / data type /
usage. Adds a per-key-variable time-series chart and a Pareto-style cumulative
contribution view.

Architecture:
- Single sticky control panel at top: Comparison Mode + global Filters + (optional)
  Migration-Matrix drilldown chip. Every chart and table on the page derives its
  data from the same filter state (`_passesFilter` + active drilldown var set).
- KPI cards above the panel remain unfiltered portfolio snapshots (they are
  reference values; filters and drilldowns drive the detail views below).
- The Top 20 table is paginated in groups of 20 when the filtered set has more
  rows.
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 4: COMPLETENESS ──────────────────────────────────────
// ═══════════════════════════════════════════════════════════════
let COMP_SCOPE   = 'all';      // 'all' | 'key' | 'non_key'
let COMP_SEV     = 'all';      // 'all' | 'Critical' | 'High' | 'Medium' | 'Low'
let COMP_DTYPE   = 'all';      // 'all' | 'Numeric' | 'Text' | 'Date'
let COMP_USAGE   = 'all';      // 'all' | <any value from schema 'usage' column>
let COMP_KEY_VAR = null;       // for per-key-variable time series; null = first available
let COMP_TOP_PAGE = 1;         // pagination for "Top 20" — page is 20 rows wide
const COMP_PAGE_SIZE = 20;

// Migration-Matrix drilldown: a set of "priorBucket|currentBucket" keys.
// When non-empty, every other chart on the page is filtered to the union of
// columns whose (priorBucket → currentBucket) transition is in this set.
let MIG_SELECTION = new Set();
// Cached set of variable names selected by MIG_SELECTION — computed once at the
// start of renderCompleteness and consulted by _passesFilter.
let _MIG_VAR_SET = null;

// ═══════════════════════════════════════════════════════════════
// TOP CONTROL PANEL — Tabbed comparison mode + Filter chips
// ═══════════════════════════════════════════════════════════════
// The control surface uses a "Tabbed + Chips" design: comparison mode
// renders as full-width browser-style tabs, filters render as clickable
// chips that open small option popovers. Mirrors the same pattern used
// on the Population page.

// Generic popover toggle (chip dropdowns)
function _toggleCompPopover(id, evt) {{
  if (evt && evt.stopPropagation) evt.stopPropagation();
  const el = document.getElementById(id);
  if (!el) return;
  const wasOpen = (el.style.display === 'block');
  document.querySelectorAll('[data-comp-popover]').forEach(e => {{ if (e !== el) e.style.display = 'none'; }});
  el.style.display = wasOpen ? 'none' : 'block';
}}

// Click-outside dismiss for popovers (registered once)
if (!window._compPopoverHandler) {{
  window._compPopoverHandler = (e) => {{
    if (e.target.closest('[data-comp-popover]')) return;
    if (e.target.closest('[data-comp-popover-trigger]')) return;
    document.querySelectorAll('[data-comp-popover]').forEach(el => el.style.display = 'none');
  }};
  document.addEventListener('click', window._compPopoverHandler);
}}

function setCompFilter(dim, value) {{
  if (dim === 'scope')   COMP_SCOPE = value || 'all';
  if (dim === 'sev')     COMP_SEV   = value || 'all';
  if (dim === 'dtype')   COMP_DTYPE = value || 'all';
  if (dim === 'usage')   COMP_USAGE = value || 'all';
  COMP_TOP_PAGE = 1;
  renderTab('completeness');
}}
function setCompKeyVar(v) {{ COMP_KEY_VAR = v; _drawCompKeyVarTrend(); }}
function clearCompFilters() {{
  COMP_SCOPE = 'all'; COMP_SEV = 'all'; COMP_DTYPE = 'all'; COMP_USAGE = 'all';
  MIG_SELECTION.clear();
  COMP_TOP_PAGE = 1;
  renderTab('completeness');
}}
function setCompTopPage(p) {{
  const next = Math.max(1, (p|0) || 1);
  if (next === COMP_TOP_PAGE) return;
  COMP_TOP_PAGE = next;
  renderTab('completeness');
}}

// Migration-Matrix cell click handler.
// Click  → exclusive single-cell selection (re-click clears).
// Shift / Ctrl / Cmd-click → additive (toggle membership without dropping others).
function toggleMigCell(prior, current, evt) {{
  if (evt && evt.stopPropagation) evt.stopPropagation();
  const key = prior + '|' + current;
  const additive = !!(evt && (evt.shiftKey || evt.ctrlKey || evt.metaKey));
  if (additive) {{
    if (MIG_SELECTION.has(key)) MIG_SELECTION.delete(key);
    else MIG_SELECTION.add(key);
  }} else {{
    if (MIG_SELECTION.size === 1 && MIG_SELECTION.has(key)) {{
      MIG_SELECTION.clear();
    }} else {{
      MIG_SELECTION.clear();
      MIG_SELECTION.add(key);
    }}
  }}
  COMP_TOP_PAGE = 1;
  renderTab('completeness');
}}
function clearMigSelection() {{
  MIG_SELECTION.clear();
  COMP_TOP_PAGE = 1;
  renderTab('completeness');
}}

// Classify pandas/schema data_type into a simple bucket
function _dtypeBucket(row) {{
  const t = (row.schema_dtype || '').toLowerCase();
  if (t.includes('float') || t.includes('int') || t.includes('decimal') || t.includes('number')) return 'Numeric';
  if (t.includes('date') || t.includes('time')) return 'Date';
  if (t.includes('text') || t.includes('varchar') || t.includes('char') || t.includes('string')) return 'Text';
  return 'Other';
}}

function _passesFilter(r) {{
  // Migration-Matrix drilldown — only variables whose transition is selected.
  if (_MIG_VAR_SET && !_MIG_VAR_SET.has(r.column)) return false;
  if (COMP_SCOPE === 'key'     && !r.is_key_var) return false;
  if (COMP_SCOPE === 'non_key' &&  r.is_key_var) return false;
  if (COMP_SEV   !== 'all' && r.severity !== COMP_SEV) return false;
  if (COMP_DTYPE !== 'all' && _dtypeBucket(r) !== COMP_DTYPE) return false;
  if (COMP_USAGE !== 'all' && (r.usage || '—') !== COMP_USAGE) return false;
  return true;
}}

// Compute the set of variables selected by MIG_SELECTION against the active
// comparison pair. Called once per render before any filtering happens.
function _computeMigVarSet() {{
  if (!MIG_SELECTION.size) return null;
  const pair = _resolveMigrationPair();
  const priorMap = {{}};
  (pair.prior   || []).forEach(r => {{ priorMap[r.column]   = r; }});
  const curMap   = {{}};
  (pair.current || []).forEach(r => {{ curMap[r.column]     = r; }});
  const out = new Set();
  const cols = new Set([...Object.keys(priorMap), ...Object.keys(curMap)]);
  cols.forEach(col => {{
    const p = priorMap[col], c = curMap[col];
    if (!p || !c) return;
    const key = _missingBucket(p.missing_pct) + '|' + _missingBucket(c.missing_pct);
    if (MIG_SELECTION.has(key)) out.add(col);
  }});
  return out;
}}

function renderCompleteness() {{
  const d   = getQData(CQ);
  const pd_ = getQData(PQ);
  const comp  = d.completeness || {{}};
  const qoq   = d.qoq || {{}};
  const ts    = DASH_DATA.time_series;
  const allCols = comp.by_column || [];

  // ── Resolve the active lens baseline (Phase C) ──
  const lensPair = _resolveMigrationPair();
  const baselineCols = lensPair.prior || [];
  const baselineByCol = {{}};
  baselineCols.forEach(r => {{ baselineByCol[r.column] = r.missing_pct; }});

  // Overall completeness % at the baseline snapshot
  const baselineOverallPct = baselineCols.length
    ? 100 - (baselineCols.reduce((s,c)=>s + (+c.missing_pct||0), 0) / baselineCols.length)
    : null;

  // Refresh the cached MIG drilldown set against the current comparison pair.
  _MIG_VAR_SET = _computeMigVarSet();
  const migActive = !!_MIG_VAR_SET;
  const migVarsCount = migActive ? _MIG_VAR_SET.size : 0;

  // Short "vs <baseline>" text used in KPI deltas — honors user's explicit PQ in QoQ
  function _baselineLabel() {{
    const m = CMP_MODE;
    if (m === 'qoq') {{
      const allQ = DASH_DATA.quarters || [];
      const i = allQ.indexOf(CQ);
      const natural = i > 0 ? allQ[i-1] : CQ;
      const baseline = PQ || natural;
      return `vs ${{qLabel(baseline)}}`;
    }}
    if (m === 'yoy') {{
      const q24 = ((DASH_DATA.port24||{{}}).quarters||[]).slice(-1)[0] || '';
      return `vs P24 ${{qLabel(q24)}}`;
    }}
    const allQ = DASH_DATA.quarters || [];
    return `vs ${{qLabel(HIST_START || allQ[0])}}`;
  }}
  const blLabel = _baselineLabel();

  // KPI delta builder for missing-count cards (more = worse → red ▲)
  function _kpiCountDelta(currentCols, baselinePool, threshold) {{
    if (!baselinePool || !baselinePool.length) return '';
    const cur = currentCols.filter(c => c.missing_pct > threshold).length;
    const blN = baselinePool.filter(c => c.missing_pct > threshold).length;
    const d = cur - blN;
    if (d === 0) return `<div class="kpi-delta" style="color:var(--gray);font-size:10px">— ${{blLabel}}</div>`;
    if (d > 0)  return `<div class="kpi-delta" style="color:#dc2626;font-size:10px">▲ +${{d}} cols ${{blLabel}}</div>`;
    return `<div class="kpi-delta" style="color:#16a34a;font-size:10px">▼ ${{d}} cols ${{blLabel}}</div>`;
  }}

  // Headline "Overall Completeness" delta — vs the active lens baseline
  const lensCompDelta = (comp.overall_pct != null && baselineOverallPct != null)
    ? +(comp.overall_pct - baselineOverallPct).toFixed(2)
    : null;
  const lensCompDeltaHtml = lensCompDelta == null
    ? ''
    : lensCompDelta === 0
      ? `<span style="color:var(--gray)">— ${{blLabel}}</span>`
      : (lensCompDelta > 0
          ? `<span style="color:#16a34a">▲ +${{fmt(lensCompDelta,2)}}pp ${{blLabel}}</span>`
          : `<span style="color:#dc2626">▼ ${{fmt(lensCompDelta,2)}}pp ${{blLabel}}</span>`);

  // ── Headline KPIs (always reflect full dataset — portfolio reference values) ──
  const headline = [
    {{icon:'✅',label:'Overall Completeness', val:pct(comp.overall_pct,2), sub:'all columns',  delta:lensCompDeltaHtml}},
    {{icon:'🗂️',label:'Total Records',        val:fmtN(comp.total_records),sub:'this snapshot',delta:''}},
    {{icon:'📊',label:'Total Columns',        val:fmtN(comp.columns_analyzed),sub:`${{fmtN(allCols.filter(c=>c.is_key_var).length)}} flagged as key`, delta:''}},
  ];
  const headlineHtml = headline.map(k=>`<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value">${{k.val}}</div>
    <div class="kpi-sub">${{k.sub}}</div>
    ${{k.delta?`<div class="kpi-delta">${{k.delta}}</div>`:''}}</div>`).join('');

  // ── Bucket counts: key columns vs all columns at >1%, >10%, >25% ──
  const keyCols = allCols.filter(c => c.is_key_var);
  const baselineKeyCols = baselineCols.filter(c => c.is_key_var);
  const _countAbove = (cols, t) => cols.filter(c => c.missing_pct > t).length;

  const keySub = `of ${{keyCols.length}} key columns`;
  const allSub = `of ${{allCols.length}} columns`;
  const keyBuckets = [
    {{icon:'🟢',label:'> 1% missing',  val:fmtN(_countAbove(keyCols, 1)), sub:keySub, tone:'#16a34a', delta:_kpiCountDelta(keyCols, baselineKeyCols, 1)}},
    {{icon:'🟡',label:'> 10% missing', val:fmtN(_countAbove(keyCols,10)), sub:keySub, tone:'#d97706', delta:_kpiCountDelta(keyCols, baselineKeyCols,10)}},
    {{icon:'🔴',label:'> 25% missing', val:fmtN(_countAbove(keyCols,25)), sub:keySub, tone:'#dc2626', delta:_kpiCountDelta(keyCols, baselineKeyCols,25)}},
  ];
  const allBuckets = [
    {{icon:'🟢',label:'> 1% missing',  val:fmtN(_countAbove(allCols, 1)), sub:allSub, tone:'#16a34a', delta:_kpiCountDelta(allCols, baselineCols, 1)}},
    {{icon:'🟡',label:'> 10% missing', val:fmtN(_countAbove(allCols,10)), sub:allSub, tone:'#d97706', delta:_kpiCountDelta(allCols, baselineCols,10)}},
    {{icon:'🔴',label:'> 25% missing', val:fmtN(_countAbove(allCols,25)), sub:allSub, tone:'#dc2626', delta:_kpiCountDelta(allCols, baselineCols,25)}},
  ];

  const bucketCard = (k) => `<div class="kpi-card" style="border-left:4px solid ${{k.tone}}">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value" style="color:${{k.tone}}">${{k.val}}</div>
    <div class="kpi-sub">${{k.sub}}</div>
    ${{k.delta || ''}}</div>`;

  const keyKpiHtml = keyBuckets.map(bucketCard).join('');
  const allKpiHtml = allBuckets.map(bucketCard).join('');

  // ── Filter dropdown options ──
  const usageValues = [...new Set(allCols.map(c => c.usage || '—'))].filter(u => u !== '—').sort();
  const usageOpts = ['all', ...usageValues].map(u =>
    `<option value="${{u}}"${{u===COMP_USAGE?' selected':''}}>${{u==='all'?'All usages':u}}</option>`).join('');

  // ── Apply filters to detail view ──
  const filteredCols = allCols.filter(_passesFilter);

  // Severity donut data (from filtered set)
  const sevCounts = {{Critical:0,High:0,Medium:0,Low:0,'Very Low':0}};
  filteredCols.forEach(c => {{ sevCounts[c.severity] = (sevCounts[c.severity]||0) + 1; }});
  const sevLabels = ['Critical','High','Medium','Low','Very Low'];
  const sevColors = ['#dc2626','#ea580c','#d97706','#16a34a','#6b7280'];

  // Delta column resolves the per-column missing% against the active lens baseline.
  function _rowDelta(r) {{
    const bl = baselineByCol[r.column];
    if (bl == null) return '<td style="color:var(--gray);font-size:10px;text-align:center">— n/a</td>';
    const d = +(r.missing_pct - bl).toFixed(2);
    if (d === 0) return '<td style="color:var(--gray);font-size:10px;text-align:center">0.00pp</td>';
    if (d > 0)  return `<td style="color:#dc2626;font-size:11px;font-weight:600;text-align:center">▲ +${{fmt(d,2)}}pp</td>`;
    return `<td style="color:#16a34a;font-size:11px;font-weight:600;text-align:center">▼ ${{fmt(d,2)}}pp</td>`;
  }}

  // Sparkline column — last 8 quarters of missing % per column (port25 only)
  const _sparkQs = (DASH_DATA.quarters || []).slice(-8);
  function _rowSpark(colName) {{
    const vals = _sparkQs.map(q => {{
      const cols = ((DASH_DATA.by_quarter[q]||{{}}).completeness||{{}}).by_column || [];
      const found = cols.find(c => c.column === colName);
      return found ? +found.missing_pct : null;
    }}).filter(v => v != null);
    if (!vals.length) return '<td style="color:var(--gray);font-size:10px;text-align:center">—</td>';
    const peak = Math.max(...vals);
    const color = peak > 25 ? '#dc2626' : peak > 10 ? '#d97706' : '#16a34a';
    const tooltip = `${{_sparkQs[0]?qLabel(_sparkQs[0]):''}} → ${{_sparkQs[_sparkQs.length-1]?qLabel(_sparkQs[_sparkQs.length-1]):''}}: ${{vals.map(v=>fmt(v,1)+'%').join(' · ')}}`;
    return `<td style="text-align:center" title="${{tooltip}}"><span class="sparkline-cell" style="color:${{color}};font-size:13px;letter-spacing:1px">${{spark(vals)}}</span></td>`;
  }}

  // ── Pagination for the Top 20 table ──
  // Filtered set is sorted by missing % (highest first). Page size is 20.
  // Page number is clamped to a valid range here so external changes (e.g. mode
  // switches that shrink the result set) don't leave the user stranded.
  const totalRows  = filteredCols.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / COMP_PAGE_SIZE));
  if (COMP_TOP_PAGE > totalPages) COMP_TOP_PAGE = totalPages;
  const pageStart = (COMP_TOP_PAGE - 1) * COMP_PAGE_SIZE;
  const pageEnd   = Math.min(pageStart + COMP_PAGE_SIZE, totalRows);
  const pageRows  = filteredCols.slice(pageStart, pageEnd);

  const compRows = pageRows.map(r=>`<tr>
    <td style="font-family:monospace;font-size:11px">${{r.column}}${{r.is_key_var?' <span style="color:#dc2626;font-size:9px" title="Key variable">🔑</span>':''}}</td>
    ${{completenessCell(r.missing_pct)}}
    ${{_rowDelta(r)}}
    ${{_rowSpark(r.column)}}
    <td>${{badge(r.severity)}}</td>
    <td>${{fmtN(r.missing_n)}}</td>
    <td style="font-size:10px;color:var(--text-muted)">${{r.usage}}</td>
    <td style="font-size:10px;color:var(--text-muted)">${{_dtypeBucket(r)}}</td>
  </tr>`).join('');

  // Pagination footer — Prev / page indicator / Next, with numeric page jumps
  // (max 7 buttons; collapses with ellipses for large ranges).
  function _pageBtns() {{
    if (totalPages <= 1) return '';
    const cur = COMP_TOP_PAGE;
    const want = new Set([1, totalPages, cur-1, cur, cur+1]);
    const pages = [...want].filter(p => p >= 1 && p <= totalPages).sort((a,b)=>a-b);
    let html = '';
    let last = 0;
    for (const p of pages) {{
      if (last && p - last > 1) html += `<span style="padding:0 4px;color:var(--text-muted)">…</span>`;
      const active = (p === cur);
      html += `<button onclick="setCompTopPage(${{p}})" style="min-width:26px;padding:3px 8px;border:1px solid ${{active?'#0369a1':'#cbd5e1'}};background:${{active?'#0369a1':'#fff'}};color:${{active?'#fff':'#0f172a'}};border-radius:4px;font-size:11px;font-weight:${{active?'700':'500'}};cursor:${{active?'default':'pointer'}}">${{p}}</button>`;
      last = p;
    }}
    return html;
  }}
  const pagerHtml = totalPages > 1 ? `
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:10px;padding-top:10px;border-top:1px solid #e2e8f0">
      <span style="font-size:11px;color:var(--text-muted)">Showing <strong>${{totalRows ? pageStart+1 : 0}}–${{pageEnd}}</strong> of <strong>${{totalRows}}</strong> variables</span>
      <div style="margin-left:auto;display:flex;align-items:center;gap:4px">
        <button onclick="setCompTopPage(${{Math.max(1,COMP_TOP_PAGE-1)}})" ${{COMP_TOP_PAGE<=1?'disabled':''}} style="padding:3px 10px;border:1px solid #cbd5e1;background:#fff;border-radius:4px;font-size:11px;cursor:${{COMP_TOP_PAGE<=1?'not-allowed':'pointer'}};opacity:${{COMP_TOP_PAGE<=1?'0.5':'1'}}">‹ Prev</button>
        ${{_pageBtns()}}
        <button onclick="setCompTopPage(${{Math.min(totalPages,COMP_TOP_PAGE+1)}})" ${{COMP_TOP_PAGE>=totalPages?'disabled':''}} style="padding:3px 10px;border:1px solid #cbd5e1;background:#fff;border-radius:4px;font-size:11px;cursor:${{COMP_TOP_PAGE>=totalPages?'not-allowed':'pointer'}};opacity:${{COMP_TOP_PAGE>=totalPages?'0.5':'1'}}">Next ›</button>
      </div>
    </div>` : (totalRows ? `<div style="margin-top:8px;font-size:11px;color:var(--text-muted)">Showing all <strong>${{totalRows}}</strong> filtered variable${{totalRows===1?'':'s'}}.</div>` : '');

  // Aggregate breakdowns — segment / type / source
  // These are pre-aggregated server-side over the full portfolio (they aggregate
  // over data rows, not columns), so the column-level filters cannot rewrite
  // them. We label this explicitly so the user understands.
  const segRows = (comp.by_segment||[]).map(s=>`<tr>
    <td>${{s.segment}}</td>
    <td><div style="background:var(--gray-light);border-radius:4px;height:10px;width:100%">
      <div style="background:var(--green);border-radius:4px;height:10px;width:${{s.completeness_pct}}%"></div></div></td>
    <td>${{pct(s.completeness_pct)}}</td>
    <td>${{pct(s.missing_pct)}}</td>
  </tr>`).join('');

  // By Data Type — recompute from filteredCols so the table reflects active filters.
  const typeAgg = {{}};
  filteredCols.forEach(c => {{
    const t = _dtypeBucket(c);
    if (!typeAgg[t]) typeAgg[t] = {{n:0, sumMiss:0}};
    typeAgg[t].n += 1;
    typeAgg[t].sumMiss += (+c.missing_pct || 0);
  }});
  const typeRows = Object.keys(typeAgg).sort().map(t => {{
    const a = typeAgg[t];
    const miss = a.n ? a.sumMiss / a.n : 0;
    return `<tr><td>${{t}} <span style="font-size:9px;color:var(--text-muted)">(${{a.n}})</span></td><td>${{pct(100-miss)}}</td><td>${{pct(miss)}}</td></tr>`;
  }}).join('');

  const srcRows = (comp.by_source||[]).map(s=>`<tr>
    <td>${{s.source}}</td>
    <td><div style="background:var(--gray-light);border-radius:4px;height:10px;width:100%">
      <div style="background:var(--green);border-radius:4px;height:10px;width:${{s.completeness_pct}}%"></div></div></td>
    <td>${{pct(s.completeness_pct)}}</td>
    <td>${{pct(s.missing_pct)}}</td>
  </tr>`).join('');

  // Per-key-variable time-series dropdown — restricted to filtered key vars
  // (so the dropdown is coherent with the rest of the page).
  const keyVarsAll = DASH_DATA.key_vars || [];
  const filteredColNames = new Set(filteredCols.map(c => c.column));
  const keyVarsFiltered = keyVarsAll.filter(v => filteredColNames.has(v));
  const keyVars = keyVarsFiltered.length ? keyVarsFiltered : keyVarsAll;
  if (!COMP_KEY_VAR || !keyVars.includes(COMP_KEY_VAR)) {{
    COMP_KEY_VAR = keyVars.length ? keyVars[0] : null;
  }}
  const keyVarOpts = keyVars.map(v =>
    `<option value="${{v}}"${{v===COMP_KEY_VAR?' selected':''}}>${{v}}</option>`).join('');

  // Active filter summary — shown in the sticky bar so the user can see at a
  // glance which scopes/severities/etc. are active.
  const _activeFilterPills = [];
  if (COMP_SCOPE !== 'all')  _activeFilterPills.push(COMP_SCOPE === 'key' ? '🔑 Key only' : 'Non-key only');
  if (COMP_SEV   !== 'all')  _activeFilterPills.push(COMP_SEV);
  if (COMP_DTYPE !== 'all')  _activeFilterPills.push(COMP_DTYPE);
  if (COMP_USAGE !== 'all')  _activeFilterPills.push(COMP_USAGE);
  const activeFiltersHtml = _activeFilterPills.length
    ? _activeFilterPills.map(p => `<span style="display:inline-block;font-size:10px;background:#fff;color:#0369a1;border:1px solid #bae6fd;padding:2px 8px;border-radius:10px;font-weight:600">${{p}}</span>`).join(' ')
    : '';

  // (The drilldown chip is rendered by _compMigBlock() from the top control panel.)

  document.getElementById('tab-completeness').innerHTML = `
    <div class="dash-header">
      <h2>Completeness Dashboard — ${{qLabel(CQ)}}</h2>
      <p>Monitor missing data patterns by variable, segment, source, and data type. Key variables (🔑 flagged in schema) are highlighted.</p>
    </div>

    <!-- Top control panel: tabbed comparison mode + filter chips -->
    ${{_compTopTabbedChips({{
      allColsCount: allCols.length,
      filteredCount: filteredCols.length,
      usageValues, usageOpts,
      activeFilterPills: _activeFilterPills,
      migActive, migVarsCount,
    }})}}

    <!-- HEADLINE KPIs — portfolio reference values (deliberately NOT filter-driven). -->
    <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Portfolio Snapshot — reference values (not filtered)</div>
    <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:14px">${{headlineHtml}}</div>

    <div style="font-size:10px;font-weight:700;color:#dc2626;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">🔑 Key Columns with Missing Data</div>
    <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:14px">${{keyKpiHtml}}</div>

    <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">All Columns with Missing Data</div>
    <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:14px">${{allKpiHtml}}</div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Overall Completeness % Over Time (filtered) ${{_lensChip()}}</div>
        <div id="comp-chart-trend" class="chart-sm"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Missing % Over Time — Per Key Variable ${{_lensChip()}}</div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <label style="font-size:11px;color:var(--text-muted);font-weight:600">Variable</label>
          <select onchange="setCompKeyVar(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;background:#fff;min-width:200px"${{keyVars.length?'':' disabled'}}>
            ${{keyVarOpts || '<option>No matching variables</option>'}}
          </select>
        </div>
        <div id="comp-chart-keyvar-trend" class="chart-sm"></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Missing Data by Severity (filtered)</div>
        <div style="display:flex;gap:12px;align-items:center">
          <div id="comp-chart-donut" style="min-width:180px;min-height:180px"></div>
          <table style="flex:1"><thead><tr><th>Severity</th><th>Columns</th><th>%</th></tr></thead><tbody>
            ${{sevLabels.map(s=>{{
              const tot = filteredCols.length || 1;
              return `<tr><td>${{badge(s)}}</td><td>${{fmtN(sevCounts[s]||0)}}</td><td>${{pct((sevCounts[s]||0)/tot*100)}}</td></tr>`;
            }}).join('')}}
          </tbody></table>
        </div>
      </div>
      <div class="section-card">
        <div class="section-title">Pareto — Top Columns by Missing Records (filtered)</div>
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">
          Which columns account for the bulk of all missing values? Cumulative line tracks the % concentration.
        </div>
        <div id="comp-chart-pareto" class="chart-sm"></div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title" style="margin-bottom:4px">Missing Values Migration Matrix ${{_lensChip()}}</div>
      <div id="comp-mig-subtitle" style="font-size:11px;color:var(--text-muted);margin-bottom:4px"></div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:14px">
        Rows = missing-value bucket in the prior snapshot. Columns = bucket in the current snapshot.
        Cells <strong style="color:#16a34a">above</strong> the diagonal = improved.
        <strong style="color:#dc2626">Below</strong> the diagonal = worsened. Diagonal = same bucket.
        <span style="margin-left:6px;color:#9a3412;font-weight:600">💡 Click a cell to drill into those variables; Shift / Ctrl-click to select multiple.</span>
      </div>
      <div id="comp-mig-content"></div>
    </div>

    <div class="section-card">
      <div class="section-title">Missing % by Variable — Top ${{COMP_PAGE_SIZE}} (filtered) — ${{qLabel(CQ)}}</div>
      ${{filteredCols.length ? `<div style="overflow-x:auto"><table>
        <thead><tr><th>Variable</th><th>Missing %</th><th style="text-align:center" title="Change in missing % vs the active comparison baseline">Δ ${{blLabel}}</th><th style="text-align:center" title="Missing % across the last 8 quarters of Port 2025">Trend (8Q)</th><th>Severity</th><th>Missing Records</th><th>Usage</th><th>Type</th></tr></thead>
        <tbody>${{compRows}}</tbody>
      </table></div>${{pagerHtml}}` : '<div style="color:var(--gray);font-size:12px;padding:16px;text-align:center">No columns match the current filter.</div>'}}
    </div>

    <div class="grid-3">
      <div class="section-card">
        <div class="section-title">By Business Segment <span style="font-size:9px;font-weight:500;color:var(--text-muted)">(portfolio, not filtered)</span></div>
        <table><thead><tr><th>Segment</th><th>Completeness</th><th>%</th><th>Missing %</th></tr></thead>
        <tbody>${{segRows}}</tbody></table>
      </div>
      <div class="section-card">
        <div class="section-title">By Data Type (filtered)</div>
        <table><thead><tr><th>Type</th><th>Completeness %</th><th>Missing %</th></tr></thead>
        <tbody>${{typeRows || '<tr><td colspan="3" style="color:var(--gray);font-size:11px">No matching columns.</td></tr>'}}</tbody></table>
      </div>
      <div class="section-card">
        <div class="section-title">By Source System <span style="font-size:9px;font-weight:500;color:var(--text-muted)">(portfolio, not filtered)</span></div>
        <table><thead><tr><th>Source</th><th>Completeness</th><th>%</th><th>Missing %</th></tr></thead>
        <tbody>${{srcRows}}</tbody></table>
      </div>
    </div>

    ${{_renderCompExtraSegments()}}
  `;

  // ── Plotly charts ──
  // Build a filter-aware completeness time series (respects the active filters).
  function _filteredCompTS(portfolio) {{
    const out = [];
    if (portfolio === 'port24') {{
      const byQ = ((DASH_DATA.port24 || {{}}).time_series || {{}}).completeness_by_column || {{}};
      const quarters = Object.keys(byQ).sort();
      for (const q of quarters) {{
        const cols = (byQ[q] || []).filter(_passesFilter);
        const value = cols.length ? 100 - (cols.reduce((s,c)=>s + (+c.missing_pct||0), 0) / cols.length) : null;
        out.push({{quarter:q, label:qLabel(q), value}});
      }}
    }} else {{
      for (const q of (DASH_DATA.quarters || [])) {{
        const cols = (((DASH_DATA.by_quarter[q]||{{}}).completeness||{{}}).by_column||[]).filter(_passesFilter);
        const value = cols.length ? 100 - (cols.reduce((s,c)=>s + (+c.missing_pct||0), 0) / cols.length) : null;
        out.push({{quarter:q, label:qLabel(q), value}});
      }}
    }}
    return out;
  }}

  const trendTraces = [];
  const trend25 = _cmpFilter(_filteredCompTS('port25'));
  if (CMP_MODE !== 'qoq') {{
    const trend24 = _cmpFilter(_filteredCompTS('port24'));
    if (trend24.length) trendTraces.push({{
      x:_cmpX(trend24), y:trend24.map(r=>r.value), name:'Port 2024',
      type:'scatter', mode:'lines+markers',
      line:{{color:'#2563eb',width:2}}, marker:{{size:3}}, connectgaps:true,
    }});
  }}
  trendTraces.push({{
    x:_cmpX(trend25), y:trend25.map(r=>r.value), name:'Port 2025',
    type:'scatter', mode:'lines+markers',
    line:{{color:'#16a34a',width:2}}, marker:{{size:3}}, connectgaps:true,
  }});
  Plotly.react('comp-chart-trend', trendTraces,
    {{..._cmpLayout('%',160), yaxis:{{range:[Math.max(0,Math.min(...trend25.map(r=>r.value||100))-2),101],gridcolor:'#f1f5f9',tickfont:{{size:9}},title:'%'}}}}, _cmpCfg);

  if (filteredCols.length) {{
    Plotly.newPlot('comp-chart-donut',[{{
      type:'pie',values:sevLabels.map(s=>sevCounts[s]||0),labels:sevLabels,hole:0.6,
      marker:{{colors:sevColors}},textinfo:'none',
      hovertemplate:'%{{label}}: %{{value}}<extra></extra>',
    }}],{{margin:{{t:5,r:5,b:5,l:5}},height:180,
      paper_bgcolor:'rgba(0,0,0,0)',showlegend:false}},{{responsive:true,displayModeBar:false}});
  }}

  _drawCompKeyVarTrend();
  _drawCompPareto(filteredCols);
  _renderCompMigration();
}}

function _drawCompKeyVarTrend() {{
  const el = document.getElementById('comp-chart-keyvar-trend');
  if (!el) return;
  if (!COMP_KEY_VAR) {{
    el.innerHTML = '<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">No variable available under current filters.</div>';
    return;
  }}
  const series25 = ((DASH_DATA.time_series||{{}}).missing_by_variable||{{}})[COMP_KEY_VAR] || [];
  const series24 = (((DASH_DATA.port24||{{}}).time_series||{{}}).missing_by_variable||{{}})[COMP_KEY_VAR] || [];
  const s25 = _cmpFilter(series25);
  const s24 = _cmpFilter(series24);
  const traces = [];
  if (CMP_MODE !== 'qoq' && s24.length) {{
    traces.push({{
      x:_cmpX(s24), y:s24.map(r=>r.missing_pct), name:'Port 2024',
      type:'scatter', mode:'lines+markers',
      line:{{color:'#2563eb',width:2}}, marker:{{size:3}}, connectgaps:true,
    }});
  }}
  traces.push({{
    x:_cmpX(s25), y:s25.map(r=>r.missing_pct), name:'Port 2025',
    type:'scatter', mode:'lines+markers',
    line:{{color:'#16a34a',width:2}}, marker:{{size:3}}, connectgaps:true,
  }});
  Plotly.react('comp-chart-keyvar-trend', traces,
    {{..._cmpLayout('Missing %',180), yaxis:{{title:'Missing %',gridcolor:'#f1f5f9',tickfont:{{size:9}},rangemode:'tozero'}}}}, _cmpCfg);
}}

function _drawCompPareto(filteredCols) {{
  const el = document.getElementById('comp-chart-pareto');
  if (!el) return;
  const sorted = [...filteredCols].sort((a,b)=>b.missing_n - a.missing_n).slice(0,15);
  if (!sorted.length) {{
    el.innerHTML = '<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">No data to display.</div>';
    return;
  }}
  const totalMissing = filteredCols.reduce((sum,r)=>sum+r.missing_n,0) || 1;
  let running = 0;
  const cumulative = sorted.map(r => {{ running += r.missing_n; return (running / totalMissing) * 100; }});
  Plotly.react('comp-chart-pareto', [
    {{
      type:'bar',
      x:sorted.map(r=>r.column),
      y:sorted.map(r=>r.missing_n),
      marker:{{color:sorted.map(r => r.is_key_var ? '#dc2626' : '#94a3b8')}},
      name:'Missing records',
      hovertemplate:'<b>%{{x}}</b><br>%{{y:,}} missing<extra></extra>',
    }},
    {{
      type:'scatter', mode:'lines+markers',
      x:sorted.map(r=>r.column),
      y:cumulative,
      yaxis:'y2',
      line:{{color:'#0f1d35',width:2}}, marker:{{size:4}},
      name:'Cumulative %',
      hovertemplate:'<b>%{{x}}</b><br>Cumulative: %{{y:.1f}}%<extra></extra>',
    }},
  ], {{
    margin:{{t:10,r:60,b:90,l:50}}, height:200,
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{{type:'category', tickangle:-40, tickfont:{{size:9}}}},
    yaxis:{{title:'Missing records',gridcolor:'#f1f5f9',tickfont:{{size:9}}}},
    yaxis2:{{title:'Cumulative %',overlaying:'y',side:'right',range:[0,105],showgrid:false,tickfont:{{size:9}}}},
    legend:{{orientation:'h',y:1.18,font:{{size:9}}}},
  }}, _cmpCfg);
}}

// ═══════════════════════════════════════════════════════════════
// MISSING VALUES MIGRATION MATRIX — comparison driven by CMP_MODE
// ═══════════════════════════════════════════════════════════════
const _SEV_ORDER = ['No Missings','Low','Medium','High','Critical'];
const _SEV_COLORS = {{
  'No Missings': '#dcfce7',
  'Low':         '#bbf7d0',
  'Medium':      '#fef3c7',
  'High':        '#ffedd5',
  'Critical':    '#fee2e2',
}};
const _SEV_RANGE_LABEL = {{
  'No Missings': '0% (no nulls)',
  'Low':         '0% < missing ≤ 1%',
  'Medium':      '1% < missing ≤ 10%',
  'High':        '10% < missing ≤ 25%',
  'Critical':    '> 25%',
}};

function _missingBucket(missing_pct) {{
  const v = (missing_pct == null) ? 0 : +missing_pct;
  if (v <= 0)     return 'No Missings';
  if (v <= 1)     return 'Low';
  if (v <= 10)    return 'Medium';
  if (v <= 25)    return 'High';
  return 'Critical';
}}

function _yearEndQuarter(year, quartersList) {{
  const candidates = (quartersList || []).filter(q => +q.slice(0,4) === +year);
  return candidates.length ? candidates[candidates.length-1] : null;
}}

function _getSnapshotByColumn(quarter, portfolio) {{
  if (!quarter) return [];
  if (portfolio === 'port24') {{
    const ts = ((DASH_DATA.port24 || {{}}).time_series || {{}});
    return (ts.completeness_by_column || {{}})[quarter] || [];
  }}
  return ((DASH_DATA.by_quarter[quarter] || {{}}).completeness || {{}}).by_column || [];
}}

function _resolveMigrationPair() {{
  let priorQ, priorPort, currentQ, currentPort, label;
  if (CMP_MODE === 'qoq') {{
    priorQ = PQ; currentQ = CQ;
    priorPort = 'port25'; currentPort = 'port25';
    label = `Port 2025 ${{qLabel(priorQ)}} → Port 2025 ${{qLabel(currentQ)}} (same portfolio, quarter over quarter)`;
  }} else if (CMP_MODE === 'yoy') {{
    const y24q = (DASH_DATA.port24 || {{}}).quarters || [];
    const y25q = DASH_DATA.quarters || [];
    const yr24 = YOY_24_YEAR ?? Math.max(...y24q.map(q => +q.slice(0,4)));
    const yr25 = YOY_25_YEAR ?? Math.max(...y25q.map(q => +q.slice(0,4)));
    priorQ   = _yearEndQuarter(yr24, y24q);
    currentQ = _yearEndQuarter(yr25, y25q);
    priorPort = 'port24'; currentPort = 'port25';
    label = `Port 2024 ${{qLabel(priorQ)||yr24+'Q?'}} → Port 2025 ${{qLabel(currentQ)||yr25+'Q?'}} (cross-portfolio, year-end snapshots)`;
  }} else {{
    const allQ = DASH_DATA.quarters || [];
    priorQ   = HIST_START || allQ[0];
    currentQ = HIST_END   || allQ[allQ.length-1];
    priorPort = 'port25'; currentPort = 'port25';
    label = `Port 2025 ${{qLabel(priorQ)}} → Port 2025 ${{qLabel(currentQ)}} (same portfolio, range endpoints)`;
  }}
  return {{
    prior:   _getSnapshotByColumn(priorQ,   priorPort),
    current: _getSnapshotByColumn(currentQ, currentPort),
    label, priorLabel: qLabel(priorQ) || '—', currentLabel: qLabel(currentQ) || '—',
    priorPort, currentPort,
  }};
}}

function _buildMigrationMatrix(priorRows, currentRows, keyOnly) {{
  const priorMap = {{}};
  priorRows.forEach(r => {{ if (!keyOnly || r.is_key_var) priorMap[r.column] = r; }});
  const currentMap = {{}};
  currentRows.forEach(r => {{ if (!keyOnly || r.is_key_var) currentMap[r.column] = r; }});

  const matrix = {{}};
  for (const s1 of _SEV_ORDER) {{
    matrix[s1] = {{}};
    for (const s2 of _SEV_ORDER) matrix[s1][s2] = [];
  }}

  const added = [];
  const removed = [];
  let improved = 0, stable = 0, worsened = 0;

  const allCols = new Set([...Object.keys(priorMap), ...Object.keys(currentMap)]);
  allCols.forEach(col => {{
    const p = priorMap[col];
    const c = currentMap[col];
    if (!p && c)  {{ added.push(c);   return; }}
    if (p && !c)  {{ removed.push(p); return; }}
    if (!p || !c) return;
    const psev = _missingBucket(p.missing_pct);
    const csev = _missingBucket(c.missing_pct);
    if (!matrix[psev] || !matrix[psev][csev]) return;
    matrix[psev][csev].push({{column: col, prior_pct: p.missing_pct, current_pct: c.missing_pct,
                              is_key_var: c.is_key_var || p.is_key_var}});
    const pIdx = _SEV_ORDER.indexOf(psev);
    const cIdx = _SEV_ORDER.indexOf(csev);
    if (cIdx < pIdx)      improved++;
    else if (cIdx > pIdx) worsened++;
    else                  stable++;
  }});

  return {{matrix, added, removed, improved, stable, worsened}};
}}

function _renderCompMigration() {{
  const subtitleEl = document.getElementById('comp-mig-subtitle');
  const contentEl  = document.getElementById('comp-mig-content');
  if (!contentEl) return;

  const pair = _resolveMigrationPair();
  if (subtitleEl) subtitleEl.textContent = pair.label;

  if (!pair.prior.length && !pair.current.length) {{
    contentEl.innerHTML = '<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">No completeness snapshots available for this comparison. (Port 2024 per-column data is required for YoY mode.)</div>';
    return;
  }}

  // Apply the FULL filter set to the matrix universe so it stays coherent with
  // the rest of the page. The MIG drilldown itself is intentionally NOT applied
  // here — we always want the user to see the full matrix so they can pick new
  // cells. (Doing otherwise would collapse the matrix to just the cells they
  // already clicked.)
  const prevMig = _MIG_VAR_SET;
  _MIG_VAR_SET = null;
  const priorScoped   = (pair.prior   || []).filter(_passesFilter);
  const currentScoped = (pair.current || []).filter(_passesFilter);
  _MIG_VAR_SET = prevMig;

  const M = _buildMigrationMatrix(priorScoped, currentScoped, false);
  const total = M.improved + M.stable + M.worsened;

  // Build the 5×5 table HTML — each cell is clickable.
  const cellBg = (i1, i2, n) => {{
    if (n === 0) return '#fafafa';
    if (i1 === i2) return '#e2e8f0';
    if (i2 < i1)   return '#bbf7d0';
    return '#fecaca';
  }};
  const cellTextColor = (i1, i2, n) => {{
    if (n === 0) return '#cbd5e1';
    if (i1 === i2) return '#475569';
    if (i2 < i1)   return '#166534';
    return '#991b1b';
  }};

  let matrixRows = '';
  for (let i = 0; i < _SEV_ORDER.length; i++) {{
    const sPrior = _SEV_ORDER[i];
    let row = `<tr>
      <td style="padding:6px 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;text-align:right;background:${{_SEV_COLORS[sPrior]}};border:1px solid #e2e8f0">${{sPrior}}</td>`;
    for (let j = 0; j < _SEV_ORDER.length; j++) {{
      const sCurrent = _SEV_ORDER[j];
      const cell = M.matrix[sPrior][sCurrent] || [];
      const n = cell.length;
      const bg = cellBg(i, j, n);
      const fg = cellTextColor(i, j, n);
      const key = sPrior + '|' + sCurrent;
      const selected = MIG_SELECTION.has(key);
      const isClickable = n > 0;
      const tooltipBase = n ? cell.slice(0,5).map(c => c.column).join(', ') + (n>5?` (+${{n-5}} more)`:'') : '';
      const tooltip = isClickable
        ? `${{sPrior}} → ${{sCurrent}} · ${{n}} variable${{n===1?'':'s'}}` + (tooltipBase?` · ${{tooltipBase}}`:'') + '\\n(Click to filter the page to these variables. Shift / Ctrl-click to add to selection.)'
        : tooltipBase;
      const onClick = isClickable ? `onclick="toggleMigCell('${{sPrior}}','${{sCurrent}}',event)"` : '';
      const border = selected
        ? 'border:3px solid #9a3412;box-shadow:inset 0 0 0 2px #fff7ed'
        : 'border:1px solid #e2e8f0';
      const cursor = isClickable ? 'pointer' : 'default';
      const cellLabel = selected ? `${{n}}<div style="font-size:8px;color:#9a3412;font-weight:700;letter-spacing:.05em">SELECTED</div>` : (n||'');
      row += `<td title="${{tooltip}}" ${{onClick}} style="padding:10px;text-align:center;font-weight:700;font-size:14px;background:${{bg}};color:${{fg}};${{border}};min-width:64px;cursor:${{cursor}};user-select:none">${{cellLabel}}</td>`;
    }}
    matrixRows += row + '</tr>';
  }}

  const matrixHeader = `<tr>
    <td style="background:#f8fafc;border:1px solid #e2e8f0"></td>
    ${{_SEV_ORDER.map(s => `<th style="padding:6px 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;text-align:center;background:${{_SEV_COLORS[s]}};border:1px solid #e2e8f0">${{s}}</th>`).join('')}}
  </tr>`;

  const legendRows = _SEV_ORDER.map(s => `
    <tr>
      <td style="padding:6px 8px;background:${{_SEV_COLORS[s]}};border:1px solid #e2e8f0;font-weight:700;font-size:11px;color:#111827;white-space:nowrap">${{s}}</td>
      <td style="padding:6px 8px;border:1px solid #e2e8f0;font-size:11px;color:var(--text-muted);font-family:monospace">${{_SEV_RANGE_LABEL[s]}}</td>
    </tr>`).join('');

  const selectionLine = MIG_SELECTION.size
    ? `<br><span style="color:#9a3412;font-weight:700">🎯 Drilldown active:</span> ${{MIG_SELECTION.size}} cell${{MIG_SELECTION.size===1?'':'s'}} selected — every other chart filtered to the matching variables. <a href="#" onclick="clearMigSelection();return false;" style="color:#9a3412;text-decoration:underline">Clear</a>.`
    : '';

  contentEl.innerHTML = `
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;align-items:start">
      <div>
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
          <span style="font-size:10px;color:var(--text-muted);font-weight:700;text-transform:uppercase">↓ Prior (${{pair.priorLabel}}) &nbsp; &nbsp; → &nbsp; &nbsp; Current (${{pair.currentLabel}}) →</span>
        </div>
        <table style="border-collapse:collapse;font-size:11px">
          <thead>${{matrixHeader}}</thead>
          <tbody>${{matrixRows}}</tbody>
        </table>
        <div style="margin-top:10px;font-size:10px;color:var(--text-muted)">
          Hover any cell to see the column names. Click to filter; Shift / Ctrl-click to add to a multi-cell selection.
          ${{M.added.length||M.removed.length ? `<br>Schema diff: <strong style="color:#16a34a">+${{M.added.length}} added</strong>, <strong style="color:#dc2626">−${{M.removed.length}} removed</strong> between snapshots.` : ''}}
          ${{selectionLine}}
        </div>
      </div>

      <div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px">
          <div style="text-align:center;padding:10px;background:#dcfce7;border-radius:6px">
            <div style="font-size:11px;color:#15803d;font-weight:700">Improved</div>
            <div style="font-size:22px;font-weight:800;color:#15803d">${{M.improved}}</div>
            <div style="font-size:9px;color:#15803d">${{total?Math.round(M.improved/total*100):0}}%</div>
          </div>
          <div style="text-align:center;padding:10px;background:#e2e8f0;border-radius:6px">
            <div style="font-size:11px;color:#475569;font-weight:700">Stable</div>
            <div style="font-size:22px;font-weight:800;color:#475569">${{M.stable}}</div>
            <div style="font-size:9px;color:#475569">${{total?Math.round(M.stable/total*100):0}}%</div>
          </div>
          <div style="text-align:center;padding:10px;background:#fecaca;border-radius:6px">
            <div style="font-size:11px;color:#991b1b;font-weight:700">Worsened</div>
            <div style="font-size:22px;font-weight:800;color:#991b1b">${{M.worsened}}</div>
            <div style="font-size:9px;color:#991b1b">${{total?Math.round(M.worsened/total*100):0}}%</div>
          </div>
        </div>

        <div style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Bucket Definitions</div>
        <table style="border-collapse:collapse;width:100%;font-size:11px">
          <thead>
            <tr>
              <th style="padding:6px 8px;background:#f8fafc;border:1px solid #e2e8f0;text-align:left;font-size:10px;color:var(--text-muted)">Bucket</th>
              <th style="padding:6px 8px;background:#f8fafc;border:1px solid #e2e8f0;text-align:left;font-size:10px;color:var(--text-muted)">Missing % range</th>
            </tr>
          </thead>
          <tbody>${{legendRows}}</tbody>
        </table>
        <div style="margin-top:8px;font-size:10px;color:var(--text-muted);font-style:italic">
          A column is classified into a bucket based on what fraction of its rows are null/missing.
        </div>
      </div>
    </div>
  `;
}}

// ═══════════════════════════════════════════════════════════════
// TOP CONTROL PANEL RENDERER (Tabbed + Chips)
// ═══════════════════════════════════════════════════════════════
// ctx = {{ allColsCount, filteredCount, usageValues, usageOpts, activeFilterPills, migActive, migVarsCount }}

// ── Shared helpers ─────────────────────────────────────────────
function _compModeLabel() {{
  if (CMP_MODE === 'qoq') return 'QoQ — Same Portfolio';
  if (CMP_MODE === 'yoy') return 'YoY — 2024 vs 2025';
  return 'Historical Comparison';
}}
function _compPairText() {{
  if (CMP_MODE === 'qoq') {{
    const allQ = DASH_DATA.quarters || [];
    const i = allQ.indexOf(CQ);
    const naturalPrior = i > 0 ? allQ[i-1] : CQ;
    const baseline = PQ || naturalPrior;
    return `${{qLabel(baseline)}} → ${{qLabel(CQ)}}`;
  }}
  if (CMP_MODE === 'yoy') {{
    const q24 = ((DASH_DATA.port24 || {{}}).quarters || []).slice(-1)[0] || '';
    const q25 = (DASH_DATA.quarters || []).slice(-1)[0] || '';
    return `P24 ${{qLabel(q24)}} → P25 ${{qLabel(q25)}}`;
  }}
  const allQ = DASH_DATA.quarters || [];
  return `${{qLabel(HIST_START || allQ[0])}} → ${{qLabel(HIST_END || allQ[allQ.length-1])}}`;
}}
function _compModeColor() {{
  return CMP_MODE === 'qoq' ? '#2563eb' : CMP_MODE === 'yoy' ? '#7c3aed' : '#0891b2';
}}

// Filter dimension metadata — used by chip/popover variants
function _compFilterDims(ctx) {{
  const dims = [
    {{ key:'scope', label:'Scope', value:COMP_SCOPE,
       options:[{{v:'all',l:'All columns'}},{{v:'key',l:'🔑 Key columns only'}},{{v:'non_key',l:'Non-key columns'}}],
       display: COMP_SCOPE==='all' ? 'All' : (COMP_SCOPE==='key' ? '🔑 Key only' : 'Non-key') }},
    {{ key:'sev', label:'Severity', value:COMP_SEV,
       options:[{{v:'all',l:'All severities'}},{{v:'Critical',l:'Critical (>25%)'}},{{v:'High',l:'High (>10%)'}},{{v:'Medium',l:'Medium (>5%)'}},{{v:'Low',l:'Low (>1%)'}}],
       display: COMP_SEV==='all' ? 'All' : COMP_SEV }},
    {{ key:'dtype', label:'Type', value:COMP_DTYPE,
       options:[{{v:'all',l:'All types'}},{{v:'Numeric',l:'Numeric'}},{{v:'Text',l:'Text'}},{{v:'Date',l:'Date'}}],
       display: COMP_DTYPE==='all' ? 'All' : COMP_DTYPE }},
  ];
  if (ctx.usageValues && ctx.usageValues.length) {{
    dims.push({{ key:'usage', label:'Usage', value:COMP_USAGE,
       options:[{{v:'all',l:'All usages'}}].concat(ctx.usageValues.map(u => ({{v:u, l:u}}))),
       display: COMP_USAGE==='all' ? 'All' : COMP_USAGE }});
  }}
  return dims;
}}

// All four filter selects, as a compact stacked column (used inside popovers/drawer)
function _compFilterStack(ctx) {{
  const dims = _compFilterDims(ctx);
  return dims.map(d => `
    <div style="display:flex;flex-direction:column;gap:4px;margin-bottom:10px">
      <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">${{d.label}}</label>
      <select class="filter-select" onchange="setCompFilter('${{d.key}}',this.value)" style="font-size:12px;padding:5px 8px;width:100%">
        ${{d.options.map(o => `<option value="${{o.v}}"${{d.value===o.v?' selected':''}}>${{o.l}}</option>`).join('')}}
      </select>
    </div>`).join('');
}}

// Mig-drilldown summary block — quiet inline notice shown only when cells are selected.
// Muted gray so it doesn't compete with the rest of the control panel.
function _compMigBlock() {{
  if (!MIG_SELECTION.size) return '';
  const keys = [...MIG_SELECTION].slice(0,3).map(k => k.replace('|',' → ')).join(' · ');
  return `<div style="display:flex;align-items:center;gap:8px;padding:4px 10px;background:transparent;border-top:1px dashed #e2e8f0;margin-top:8px;padding-top:8px">
    <span style="font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.03em">Matrix drilldown</span>
    <span style="font-size:11px;color:#64748b">${{keys}}${{MIG_SELECTION.size>3?' · …':''}}</span>
    <button onclick="clearMigSelection()" style="margin-left:auto;font-size:10px;padding:1px 8px;border:1px solid #e2e8f0;border-radius:4px;background:transparent;color:#64748b;cursor:pointer;font-weight:500">clear</button>
  </div>`;
}}


// ───────────────────────────────────────────────────────────────
// TABBED COMPARISON MODE + FILTER CHIPS
// ───────────────────────────────────────────────────────────────
// Mode renders as full-width browser-style tabs with a colored underline
// on the active tab. Each filter dimension renders as a clickable chip
// ("Label: Value ▾") that opens a small popover with the option list.
// Active chips highlight in solid color; the drilldown chip joins the
// chip row when matrix cells are selected.
function _compTopTabbedChips(ctx) {{
  const tabBtn = (id,lbl) => `<button onclick="setCmpMode('${{id}}')" style="font-size:12px;padding:8px 18px;background:${{CMP_MODE===id?'#fff':'transparent'}};border:1px solid ${{CMP_MODE===id?'#e2e8f0':'transparent'}};border-bottom:${{CMP_MODE===id?'2px solid '+_compModeColor():'2px solid transparent'}};margin-bottom:-2px;color:${{CMP_MODE===id?_compModeColor():'#64748b'}};font-weight:${{CMP_MODE===id?'700':'500'}};cursor:pointer;border-radius:6px 6px 0 0">${{lbl}}</button>`;

  // Contextual quarter pickers under the active tab (compact)
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
    ctxRow = `<span style="font-size:11px;color:#64748b">Fixed pair —</span><span style="font-size:11px;color:#0f172a;font-family:monospace;font-weight:600">${{_compPairText()}}</span>`;
  }}

  // Filter chips with mini-popovers
  const dims = _compFilterDims(ctx);
  const chipsHtml = dims.map(d => {{
    const active = d.value !== 'all';
    const optsHtml = d.options.map(o => `<div onclick="setCompFilter('${{d.key}}','${{o.v}}');_toggleCompPopover('chip-v2-${{d.key}}',event)" style="font-size:11px;padding:6px 12px;cursor:pointer;color:${{d.value===o.v?_compModeColor():'#0f172a'}};font-weight:${{d.value===o.v?'700':'500'}};border-radius:4px" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='transparent'">${{o.l}}${{d.value===o.v?' ✓':''}}</div>`).join('');
    return `<div style="position:relative;display:inline-block">
      <button data-comp-popover-trigger onclick="_toggleCompPopover('chip-v2-${{d.key}}',event)" style="font-size:11px;padding:5px 12px;border:1px solid ${{active?_compModeColor():'#cbd5e1'}};background:${{active?_compModeColor():'#fff'}};color:${{active?'#fff':'#475569'}};border-radius:14px;cursor:pointer;font-weight:${{active?'600':'500'}}">
        ${{d.label}}: <strong>${{d.display}}</strong> ▾
      </button>
      <div id="chip-v2-${{d.key}}" data-comp-popover style="display:none;position:absolute;top:100%;left:0;z-index:50;background:#fff;border:1px solid #cbd5e1;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.12);padding:4px;min-width:180px;margin-top:6px">
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
        <span style="margin-left:auto;font-size:10px;color:var(--text-muted);padding:8px 4px 6px 0">${{ctx.filteredCount}} / ${{ctx.allColsCount}} columns</span>
      </div>
      <!-- Contextual quarter row -->
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 4px 0">
        ${{ctxRow}}
      </div>
      <!-- Filter chips -->
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:8px 4px 0">
        <span style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;margin-right:2px">Filter</span>
        ${{chipsHtml}}
        ${{ctx.activeFilterPills.length ? '<button onclick="clearCompFilters()" style="font-size:10px;padding:3px 10px;border:1px dashed #cbd5e1;background:transparent;border-radius:14px;color:#64748b;cursor:pointer">× Clear all</button>' : ''}}
      </div>
      ${{_compMigBlock()}}
    </div>`;
}}

// ═══════════════════════════════════════════════════════════════
// ADDITIONAL SEGMENTATIONS — completeness by 7 extra dimensions
// ═══════════════════════════════════════════════════════════════
// Cards live in a grid-2 layout below the existing By Segment / By Type /
// By Source row. Each row shows: segment | accounts | completeness % |
// missing % | Δ vs prior snapshot. Data is precomputed server-side in
// processor.py → DASH_DATA.completeness_segments.
function _renderCompExtraSegments() {{
  const segs = DASH_DATA.completeness_segments || {{}};
  const dims = Object.keys(segs);
  if (!dims.length) return '';

  // One card per dimension. Each card includes a tiny header with the
  // active comparison ("vs Q3 2025" etc.) so the Δ column is interpretable.
  const cards = dims.map(dimKey => {{
    const entry = segs[dimKey];
    const rows = entry.rows || [];
    const priorLabel = entry.prior_q ? `vs ${{qLabel(entry.prior_q)}}` : 'no prior snapshot';
    const cellAccts = r => fmtN(r.accounts || 0);
    const cellComp  = r => `<span style="font-weight:600;color:${{r.completeness_pct>=99?'#16a34a':r.completeness_pct>=95?'#65a30d':r.completeness_pct>=90?'#d97706':'#dc2626'}}">${{pct(r.completeness_pct,2)}}</span>`;
    const cellMiss  = r => `<span style="font-weight:500;color:${{r.missing_pct<=1?'#64748b':r.missing_pct<=10?'#d97706':'#dc2626'}}">${{pct(r.missing_pct,2)}}</span>`;
    const cellDelta = r => {{
      if (r.comp_delta == null) return '<span style="color:#94a3b8">—</span>';
      const d = +r.comp_delta;
      if (Math.abs(d) < 0.01) return '<span style="color:#64748b">0.00pp</span>';
      const c = d > 0 ? '#16a34a' : '#dc2626';
      const arrow = d > 0 ? '▲' : '▼';
      return `<span style="color:${{c}};font-weight:600">${{arrow}} ${{(d>0?'+':'')}}${{fmt(d,2)}}pp</span>`;
    }};
    const body = rows.length
      ? rows.map(r => `<tr>
          <td style="font-weight:600;color:#0f172a">${{r.segment}}</td>
          <td style="text-align:right;font-family:monospace">${{cellAccts(r)}}</td>
          <td style="text-align:right">${{cellComp(r)}}</td>
          <td style="text-align:right">${{cellMiss(r)}}</td>
          <td style="text-align:right">${{cellDelta(r)}}</td>
        </tr>`).join('')
      : `<tr><td colspan="5" style="color:#94a3b8;text-align:center;padding:14px;font-size:11px">No data for this dimension.</td></tr>`;
    return `<div class="section-card">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        <div class="section-title" style="margin:0">${{entry.label}}</div>
        <div style="font-size:10px;color:var(--text-muted);font-family:monospace">${{rows.length}} segment${{rows.length===1?'':'s'}} · ${{priorLabel}}</div>
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">
        Completeness across the schema-flagged key variables, grouped by <code>${{entry.column}}</code>. Δ compares against the prior quarter's snapshot for the same segment.
      </div>
      <div style="overflow-x:auto"><table style="font-size:11px;width:100%">
        <thead><tr>
          <th style="text-align:left">Segment</th>
          <th style="text-align:right">Accounts</th>
          <th style="text-align:right">Completeness %</th>
          <th style="text-align:right">Missing %</th>
          <th style="text-align:right">Δ vs prior</th>
        </tr></thead>
        <tbody>${{body}}</tbody>
      </table></div>
    </div>`;
  }}).join('');

  return `<div style="font-size:12px;font-weight:700;color:#0f172a;text-transform:uppercase;letter-spacing:.05em;margin:18px 0 8px;padding-top:14px;border-top:1px solid #e2e8f0">
    Additional Segmentations <span style="font-size:10px;font-weight:500;color:var(--text-muted)">(completeness across the schema-flagged key variables, by ${{dims.length}} extra dimensions)</span>
  </div>
  <div class="grid-2">${{cards}}</div>`;
}}
"""
