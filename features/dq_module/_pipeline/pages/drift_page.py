"""D7 — Distribution Drift dashboard, redesigned around two questions.

Q1 · Within-Portfolio Drift   — is Port 2025 moving relative to its own recent history?
Q2 · Cross-Portfolio Comparison — does Port 2025 behave differently than Port 2024 at the
                                  same quarters? (focus on deltas)

The page replaces the QoQ / YoY / Historical mode bar with an explicit
two-question selector. As a WIREFRAME the three candidate selector designs
(Radio Cards · Tabs · Toggle) all render together so the user can compare and
pick one. All three designs drive the same DRIFT_QUESTION state, so the page
content below renders only once.

Sections:
  1 · Summary — distribution of variables across drift severity for all 5 tests
  2 · Drift Metric Over Time — chart with variable + stat-test dropdowns
  3 · Drift Heatmap — variables × quarters, with stat-test dropdown + Verdict column
  4 · Ranked variables (combines old Top Columns + Statistical Tests table)
  5 · Variable detail drilldown — appears when a row in the heatmap is clicked
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 7: DISTRIBUTION DRIFT (redesigned around two questions) ─
// ═══════════════════════════════════════════════════════════════

// State
let DRIFT_QUESTION = 'q1';        // 'q1' (within) | 'q2' (cross)
let DRIFT_WINDOW = '8q';          // '4q' | '8q' | '12q' | 'all'
let DRIFT_STAT_TEST = 'psi';      // 'psi' | 'ks_p' | 'anova_p' | 'cohens_d' | 'js_div'
let DRIFT_PSI_VAR = 'avg';        // dropdown for Section 2
let DRIFT_SELECTED_VAR = null;    // Section 5 drilldown target

function setDriftQuestion(q) {{
  if (q !== 'q1' && q !== 'q2') return;
  DRIFT_QUESTION = q;
  DRIFT_SELECTED_VAR = null;
  renderTab('drift');
}}
function setDriftWindow(w) {{ DRIFT_WINDOW = w; renderTab('drift'); }}
function setDriftStatTest(t) {{ DRIFT_STAT_TEST = t; renderTab('drift'); }}
function setDriftPsiVar(v) {{ DRIFT_PSI_VAR = v || 'avg'; _drawDriftPsiTrend(); }}
function selectDriftVar(name) {{
  DRIFT_SELECTED_VAR = (DRIFT_SELECTED_VAR === name) ? null : name;
  renderTab('drift');
}}

// ── Stat-test metadata ────────────────────────────────────────
// Each test exposes: key, label, short formatter, and a level fn
// returning 'red' | 'amber' | 'green' | 'none' for a given raw value.
// Levels drive the heatmap cell color, the verdict counter, and the
// summary distribution buckets.
const TEST_META = [
  {{
    key:'psi', label:'PSI', short:'PSI',
    fmt: v => v == null ? '—' : fmt(v, 3),
    level: v => v == null ? 'none' : v > 0.20 ? 'red' : v > 0.10 ? 'amber' : 'green',
    bucketLabels: ['≤0.10', '0.10–0.20', '>0.20'],
  }},
  {{
    key:'ks_p', label:'KS p-value', short:'KS',
    fmt: v => v == null ? '—' : fmt(v, 4),
    level: v => v == null ? 'none' : v < 0.01 ? 'red' : v < 0.05 ? 'amber' : 'green',
    bucketLabels: ['p ≥ 0.05', 'p 0.01–0.05', 'p < 0.01'],
  }},
  {{
    key:'anova_p', label:'ANOVA p-value', short:'ANOVA',
    fmt: v => v == null ? '—' : fmt(v, 4),
    level: v => v == null ? 'none' : v < 0.01 ? 'red' : v < 0.05 ? 'amber' : 'green',
    bucketLabels: ['p ≥ 0.05', 'p 0.01–0.05', 'p < 0.01'],
  }},
  {{
    key:'cohens_d', label:"Cohen's d", short:"Cohen",
    fmt: v => v == null ? '—' : (v >= 0 ? '+' : '') + fmt(v, 3),
    level: v => {{ if (v == null) return 'none'; const a = Math.abs(v); return a > 0.5 ? 'red' : a > 0.2 ? 'amber' : 'green'; }},
    bucketLabels: ['|d| ≤ 0.2', '0.2–0.5', '> 0.5'],
  }},
  {{
    key:'js_div', label:'JS Divergence', short:'JS',
    fmt: v => v == null ? '—' : fmt(v, 3),
    level: v => v == null ? 'none' : v > 0.5 ? 'red' : v > 0.2 ? 'amber' : 'green',
    bucketLabels: ['≤ 0.2', '0.2–0.5', '> 0.5'],
  }},
];
const TEST_BY_KEY = Object.fromEntries(TEST_META.map(t => [t.key, t]));

function _testLevelColors(level) {{
  if (level === 'red')   return {{bg:'#fee2e2', fg:'#991b1b'}};
  if (level === 'amber') return {{bg:'#fef3c7', fg:'#92400e'}};
  if (level === 'green') return {{bg:'#dcfce7', fg:'#166534'}};
  return {{bg:'#f1f5f9', fg:'#64748b'}};
}}

// Verdict across the 5 tests for one variable (latest snapshot):
//   3+ red  → Drift · 1-2 red → Mixed · else Stable
function _verdictFor(row) {{
  let red = 0;
  for (const t of TEST_META) {{
    if (t.level(row[t.key]) === 'red') red++;
  }}
  const level = red >= 3 ? 'red' : red >= 1 ? 'amber' : 'green';
  const label = red >= 3 ? '⚠ Drift' : red >= 1 ? '◐ Mixed' : '✓ Stable';
  return {{level, label, redCount: red}};
}}

// ── Data accessors ────────────────────────────────────────────
function _driftActive() {{
  return DRIFT_QUESTION === 'q1' ? (DASH_DATA.drift_q1 || {{}}) : (DASH_DATA.drift_q2 || {{}});
}}
function _driftWindowSize() {{
  if (DRIFT_WINDOW === '4q') return 4;
  if (DRIFT_WINDOW === '8q') return 8;
  if (DRIFT_WINDOW === '12q') return 12;
  return Infinity;
}}
function _driftVisibleQuarters() {{
  const active = _driftActive();
  const recent = active.recent_quarters || [];
  const all = DRIFT_QUESTION === 'q1' ? (active.all_quarters || []) : (active.shared_quarters || []);
  const N = _driftWindowSize();
  // 'all' uses the broadest list (heatmap may use PSI-only for older Qs in Q2).
  if (!isFinite(N)) return all;
  return recent.slice(-N);
}}
// Latest available by_quarter (most recent in recent_quarters)
function _driftLatestQ() {{
  const recent = _driftActive().recent_quarters || [];
  return recent[recent.length - 1] || null;
}}

function _driftQuestionChip() {{
  const a = _driftActive();
  const visible = _driftVisibleQuarters();
  const range = visible.length ? `${{qLabel(visible[0])}} → ${{qLabel(visible[visible.length-1])}}` : '—';
  const bg = DRIFT_QUESTION === 'q1' ? '#2563eb' : '#7c3aed';
  const label = DRIFT_QUESTION === 'q1' ? 'Within-Portfolio Drift' : 'Cross-Portfolio Drift';
  return `<span style="display:inline-block;font-size:10px;font-weight:700;color:#fff;background:${{bg}};padding:2px 10px;border-radius:10px;letter-spacing:.03em;vertical-align:middle;margin-left:10px;text-transform:none;white-space:nowrap" title="Active question">${{label}} · ${{range}}</span>`;
}}

// ═══════════════════════════════════════════════════════════════
// QUESTION SELECTOR — compact toggle + active question description
// ═══════════════════════════════════════════════════════════════
function _questionSelector() {{
  const isQ1 = DRIFT_QUESTION === 'q1';
  const isQ2 = DRIFT_QUESTION === 'q2';
  return `<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px">
      <div style="display:inline-flex;background:#f1f5f9;border-radius:14px;padding:2px;gap:2px">
        <button onclick="setDriftQuestion('q1')" style="font-size:11px;padding:5px 14px;border:none;border-radius:12px;background:${{isQ1?'#2563eb':'transparent'}};color:${{isQ1?'#fff':'#475569'}};font-weight:600;cursor:pointer;white-space:nowrap">Within-Portfolio Drift</button>
        <button onclick="setDriftQuestion('q2')" style="font-size:11px;padding:5px 14px;border:none;border-radius:12px;background:${{isQ2?'#7c3aed':'transparent'}};color:${{isQ2?'#fff':'#475569'}};font-weight:600;cursor:pointer;white-space:nowrap">Cross-Portfolio Drift</button>
      </div>
      <span style="font-size:11px;color:#475569;font-weight:600">${{isQ1 ? 'Comparing Port 2025 against its own recent history' : 'Comparing Port 2025 vs Port 2024 (deltas at shared quarters)'}}</span>
    </div>
    <div style="font-size:11px;color:#475569;line-height:1.45;padding-top:8px;border-top:1px dashed #e2e8f0">
      ${{isQ1
        ? 'Is there a significant change in the behavior of the new portfolio relative to its own previous periods? Each quarter is compared against the previous quarter, same portfolio.'
        : 'Is there a significant difference between the new portfolio and the old one at the same shared quarters? Each shared quarter compared across portfolios, with focus on the deltas.'}}
    </div>
  </div>`;
}}

// ═══════════════════════════════════════════════════════════════
// WINDOW PICKER
// ═══════════════════════════════════════════════════════════════
function _windowPicker() {{
  const opts = [
    {{key:'4q',  label:'Last 4Q'}},
    {{key:'8q',  label:'Last 8Q'}},
    {{key:'12q', label:'Last 12Q'}},
    {{key:'all', label: DRIFT_QUESTION === 'q1' ? 'All history' : 'All shared history'}},
  ];
  const chips = opts.map(o => {{
    const active = DRIFT_WINDOW === o.key;
    return `<button onclick="setDriftWindow('${{o.key}}')" style="font-size:11px;padding:4px 12px;border-radius:14px;border:1px solid ${{active?'#0f172a':'#cbd5e1'}};background:${{active?'#0f172a':'#fff'}};color:${{active?'#fff':'#475569'}};cursor:pointer;font-weight:${{active?'600':'500'}}">${{o.label}}</button>`;
  }}).join('');
  const visible = _driftVisibleQuarters();
  const recentN = (_driftActive().recent_quarters || []).length;
  const partialPsi = (DRIFT_WINDOW === 'all') ? `<span style="margin-left:8px;font-size:10px;color:#854d0e;font-style:italic">Only PSI is available beyond the last ${{recentN}}Q (the other 4 tests are precomputed only for the recent window)</span>` : '';
  return `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:14px">
    <span style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em">Window</span>
    ${{chips}}
    <span style="font-size:11px;color:#475569;font-family:monospace">${{visible.length}} Q · ${{visible.length?qLabel(visible[0]):'—'}} → ${{visible.length?qLabel(visible[visible.length-1]):'—'}}</span>
    ${{partialPsi}}
  </div>`;
}}

// Stat-test dropdown (used by Sections 2, 3, 4)
function _statTestDropdown() {{
  return `<div style="display:flex;align-items:center;gap:6px">
    <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">Stat Test</label>
    <select onchange="setDriftStatTest(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;min-width:140px">
      ${{TEST_META.map(t => `<option value="${{t.key}}"${{DRIFT_STAT_TEST===t.key?' selected':''}}>${{t.label}}</option>`).join('')}}
    </select>
  </div>`;
}}

// ═══════════════════════════════════════════════════════════════
// MAIN RENDER
// ═══════════════════════════════════════════════════════════════
function renderDrift() {{
  const tabEl = document.getElementById('tab-drift');
  if (!tabEl) return;

  const active = _driftActive();
  const visibleQs = _driftVisibleQuarters();
  const latestQ = _driftLatestQ();
  const latestRow = latestQ ? (active.by_quarter || {{}})[latestQ] : null;
  const latestVars = latestRow ? (latestRow.by_variable || []) : [];

  // Snapshot KPIs based on the LATEST row of the active question
  const kpis = _driftLatestKpis(latestVars);
  const kpiHtml = kpis.map(k => `<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value" style="font-size:${{(''+k.val).length>8?'16px':'22px'}}">${{k.val}}</div>
    ${{k.sub?`<div class="kpi-sub">${{k.sub}}</div>`:''}}</div>`).join('');

  tabEl.innerHTML = `
    <div class="dash-header">
      <h2>Distribution Drift · ${{active.label || ''}}</h2>
      <p>${{active.description || ''}} ${{_driftQuestionChip()}}</p>
    </div>

    ${{_questionSelector()}}
    ${{_windowPicker()}}

    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr);margin-bottom:14px">${{kpiHtml}}</div>

    <!-- Section 1: Summary across all 5 tests -->
    <div class="section-card">
      <div class="section-title">Drift Summary — distribution by stat test ${{_driftQuestionChip()}}</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        For each of the 5 tests, how many variables fall in each band (green / amber / red) in the latest snapshot (${{latestQ ? qLabel(latestQ) : '—'}}).
      </div>
      <div id="ts-summary-grid" style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px"></div>
    </div>

    <!-- Section 2: Drift metric over time -->
    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:6px">
        <div class="section-title" style="margin:0">Drift Metric Over Time ${{_driftQuestionChip()}}</div>
        <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          ${{_statTestDropdown()}}
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">Variable</label>
            <select onchange="setDriftPsiVar(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;min-width:200px">
              <option value="avg"${{DRIFT_PSI_VAR==='avg'?' selected':''}}>Average (all variables)</option>
              ${{_driftAllVarNames().map(c => `<option value="${{c}}"${{c===DRIFT_PSI_VAR?' selected':''}}>${{c}}</option>`).join('')}}
            </select>
          </div>
        </div>
      </div>
      <div id="drift-chart-trend" style="min-height:220px"></div>
      <div id="drift-trend-footer" style="margin-top:8px;font-size:10px;color:var(--text-muted)"></div>
    </div>

    <!-- Section 3: Heatmap with Verdict column -->
    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:6px">
        <div class="section-title" style="margin:0">Drift Heatmap — variable × quarter ${{_driftQuestionChip()}}</div>
        ${{_statTestDropdown()}}
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        Cell color reflects <strong>${{TEST_BY_KEY[DRIFT_STAT_TEST].label}}</strong> for each quarter in the visible window. The <strong>Verdict</strong> column summarizes all 5 tests for the latest snapshot. Click a row to see the variable's detail below.
      </div>
      <div id="drift-heatmap-wrap"></div>
    </div>

    <!-- Section 4: Ranked variables (Top + Stat Tests combined) -->
    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:6px">
        <div class="section-title" style="margin:0">Ranked Variables — Statistical Tests for the Latest Snapshot</div>
        ${{_statTestDropdown()}}
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        One variable per row (no duplicates), sorted by the selected stat test (worst first). Each cell shows the test value for the latest snapshot with its severity color. The <strong>Verdict</strong> column counts how many of the 5 tests fail.
      </div>
      <div id="drift-ranked-wrap"></div>
    </div>

    <!-- Section 5: Variable detail drilldown -->
    <div class="section-card" id="drift-detail-card" style="${{DRIFT_SELECTED_VAR ? '' : 'opacity:0.6'}}">
      <div class="section-title">Variable Detail ${{DRIFT_SELECTED_VAR ? `· <code>${{DRIFT_SELECTED_VAR}}</code>` : ''}}</div>
      <div id="drift-detail-wrap">
        ${{DRIFT_SELECTED_VAR ? '' : '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:12px;font-style:italic">Click any row in the heatmap or the ranked table to see that variable\\'s detail here.</div>'}}
      </div>
    </div>
  `;

  _renderDriftSummaryGrid(latestVars);
  _drawDriftPsiTrend();
  _renderDriftHeatmap(visibleQs);
  _renderDriftRanked(latestVars);
  if (DRIFT_SELECTED_VAR) _renderDriftDetail(DRIFT_SELECTED_VAR, latestVars, latestQ);
}}

// ─── Latest-snapshot KPIs ────────────────────────────────────
function _driftLatestKpis(rows) {{
  const test = TEST_BY_KEY[DRIFT_STAT_TEST];
  const N = rows.length;
  let bRed = 0, bAmber = 0, bGreen = 0;
  let avgPsi = 0, maxPsi = 0;
  for (const r of rows) {{
    const l = test.level(r[DRIFT_STAT_TEST]);
    if (l === 'red') bRed++; else if (l === 'amber') bAmber++; else if (l === 'green') bGreen++;
    avgPsi += (r.psi || 0);
    if ((r.psi || 0) > maxPsi) maxPsi = r.psi || 0;
  }}
  avgPsi = N > 0 ? avgPsi / N : 0;
  // Cross-test composite: # vars that fail ≥3 of 5
  let driftVars = 0, mixedVars = 0, stableVars = 0;
  for (const r of rows) {{
    const v = _verdictFor(r);
    if (v.level === 'red') driftVars++;
    else if (v.level === 'amber') mixedVars++;
    else stableVars++;
  }}
  return [
    {{icon:'📊', label:'Variables Analyzed', val:fmtN(N), sub:'latest snapshot'}},
    {{icon:'⚠️', label:`Red in ${{test.short}}`, val:fmtN(bRed), sub:'test threshold'}},
    {{icon:'🔴', label:'Verdict: Drift (3+ red)', val:fmtN(driftVars), sub:'across all 5 tests'}},
    {{icon:'◐', label:'Verdict: Mixed (1-2 red)', val:fmtN(mixedVars), sub:''}},
    {{icon:'📈', label:'Avg PSI', val:fmt(avgPsi, 3), sub:''}},
    {{icon:'📉', label:'Max PSI', val:fmt(maxPsi, 3), sub:''}},
  ];
}}

// Union of all variable names appearing in either drift_q1 or drift_q2 latest rows.
function _driftAllVarNames() {{
  const set = new Set();
  // Q1 latest
  const r1 = (DASH_DATA.drift_q1 || {{}}).by_quarter || {{}};
  for (const q of Object.keys(r1)) (r1[q].by_variable || []).forEach(v => set.add(v.column));
  // Q2 latest
  const r2 = (DASH_DATA.drift_q2 || {{}}).by_quarter || {{}};
  for (const q of Object.keys(r2)) (r2[q].by_variable || []).forEach(v => set.add(v.column));
  // psi_heatmap (Q2 has its own)
  const hm = ((DASH_DATA.time_series || {{}}).psi_heatmap || {{}});
  Object.keys(hm).forEach(c => set.add(c));
  return [...set].sort();
}}

// ═══════════════════════════════════════════════════════════════
// SECTION 1 · Drift Summary across the 5 tests
// ═══════════════════════════════════════════════════════════════
function _renderDriftSummaryGrid(rows) {{
  const el = document.getElementById('ts-summary-grid');
  if (!el) return;
  const cards = TEST_META.map(test => {{
    let g = 0, a = 0, r = 0;
    for (const row of rows) {{
      const l = test.level(row[test.key]);
      if (l === 'green') g++;
      else if (l === 'amber') a++;
      else if (l === 'red') r++;
    }}
    const total = g + a + r;
    const w = (n) => total > 0 ? (n / total * 100).toFixed(1) : 0;
    const active = test.key === DRIFT_STAT_TEST;
    return `<div onclick="setDriftStatTest('${{test.key}}')" style="background:#fff;border:1px solid ${{active?'#0f172a':'#e2e8f0'}};border-radius:8px;padding:12px;cursor:pointer;${{active?'box-shadow:0 0 0 2px #0f172a30;':''}}">
      <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:8px">
        <div style="font-size:12px;font-weight:700;color:#0f172a">${{test.label}}</div>
        <div style="font-size:10px;color:#94a3b8">${{total}} vars</div>
      </div>
      <div style="display:flex;height:10px;border-radius:5px;overflow:hidden;background:#f1f5f9;margin-bottom:8px">
        <div style="background:#16a34a;width:${{w(g)}}%" title="Stable: ${{g}}"></div>
        <div style="background:#d97706;width:${{w(a)}}%" title="Mixed: ${{a}}"></div>
        <div style="background:#dc2626;width:${{w(r)}}%" title="Drift: ${{r}}"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px">
        <span style="color:#166534"><strong>${{g}}</strong> · ${{test.bucketLabels[0]}}</span>
        <span style="color:#92400e"><strong>${{a}}</strong></span>
        <span style="color:#991b1b"><strong>${{r}}</strong> · ${{test.bucketLabels[2]}}</span>
      </div>
    </div>`;
  }}).join('');
  el.innerHTML = cards;
}}

// ═══════════════════════════════════════════════════════════════
// SECTION 2 · Drift Metric Over Time
// ═══════════════════════════════════════════════════════════════
function _drawDriftPsiTrend() {{
  const el = document.getElementById('drift-chart-trend');
  if (!el) return;
  const footer = document.getElementById('drift-trend-footer');
  const test = TEST_BY_KEY[DRIFT_STAT_TEST];
  const visibleQs = _driftVisibleQuarters();
  const active = _driftActive();

  // Build the value series:
  //   PSI: uses psi_heatmap when DRIFT_QUESTION=='q1' (existing) or
  //        drift_q2.psi_heatmap when 'q2' for the wide window;
  //        otherwise from active.by_quarter[q].by_variable
  //   Other tests: only from active.by_quarter[q].by_variable (recent window)
  function getValue(q, varName) {{
    const row = (active.by_quarter || {{}})[q];
    if (row) {{
      const found = (row.by_variable || []).find(v => v.column === varName);
      if (found) return found[DRIFT_STAT_TEST];
    }}
    // Fallback for PSI only
    if (DRIFT_STAT_TEST === 'psi') {{
      if (DRIFT_QUESTION === 'q2') {{
        return ((active.psi_heatmap || {{}})[varName] || {{}})[q];
      }} else {{
        // Q1: fall back to global time_series.psi_heatmap
        return (((DASH_DATA.time_series || {{}}).psi_heatmap || {{}})[varName] || {{}})[q];
      }}
    }}
    return null;
  }}

  const xLabels = visibleQs.map(q => qLabel(q));
  let traces = [];
  if (DRIFT_PSI_VAR === 'avg') {{
    // Average across all variables for each Q
    const allVars = _driftAllVarNames();
    const yVals = visibleQs.map(q => {{
      const vals = allVars.map(v => getValue(q, v)).filter(x => x != null && Number.isFinite(x));
      return vals.length ? vals.reduce((s,x)=>s+x,0) / vals.length : null;
    }});
    traces.push({{
      x: xLabels, y: yVals, name: `Average ${{test.short}}`,
      type: 'scatter', mode: 'lines+markers',
      line: {{color: DRIFT_QUESTION==='q1'?'#2563eb':'#7c3aed', width: 2}}, marker: {{size: 4}},
      connectgaps: true,
    }});
  }} else {{
    const yVals = visibleQs.map(q => getValue(q, DRIFT_PSI_VAR));
    traces.push({{
      x: xLabels, y: yVals, name: `${{test.short}} · ${{DRIFT_PSI_VAR}}`,
      type: 'scatter', mode: 'lines+markers',
      line: {{color: '#dc2626', width: 2}}, marker: {{size: 4}},
      connectgaps: true,
    }});
  }}

  // Threshold lines per test
  const refX = xLabels;
  const thresholds = (() => {{
    if (test.key === 'psi')      return [{{y: 0.20, c:'#dc2626', dash:'dot',  label:'Significant (0.20)'}}, {{y: 0.10, c:'#d97706', dash:'dash', label:'Moderate (0.10)'}}];
    if (test.key === 'ks_p')     return [{{y: 0.05, c:'#dc2626', dash:'dot',  label:'p = 0.05'}}, {{y: 0.01, c:'#7c2d12', dash:'dash', label:'p = 0.01'}}];
    if (test.key === 'anova_p')  return [{{y: 0.05, c:'#dc2626', dash:'dot',  label:'p = 0.05'}}, {{y: 0.01, c:'#7c2d12', dash:'dash', label:'p = 0.01'}}];
    if (test.key === 'cohens_d') return [{{y: 0.50, c:'#dc2626', dash:'dot',  label:'|d| = 0.5'}}, {{y: 0.20, c:'#d97706', dash:'dash', label:'|d| = 0.2'}}, {{y: -0.20, c:'#d97706', dash:'dash', label:'|d| = -0.2'}}, {{y: -0.50, c:'#dc2626', dash:'dot', label:'|d| = -0.5'}}];
    if (test.key === 'js_div')   return [{{y: 0.50, c:'#dc2626', dash:'dot',  label:'0.50'}}, {{y: 0.20, c:'#d97706', dash:'dash', label:'0.20'}}];
    return [];
  }})();
  for (const th of thresholds) {{
    traces.push({{
      x: refX, y: refX.map(()=>th.y), name: th.label,
      type:'scatter', mode:'lines', line:{{color:th.c, width:1, dash:th.dash}},
      hoverinfo:'skip',
    }});
  }}

  const allY = traces.flatMap(t => (t.y || []).filter(v => v != null && Number.isFinite(v)));
  const yMaxData = allY.length ? Math.max(...allY) : 1;
  const yMinData = allY.length ? Math.min(...allY) : 0;
  const yRange = (test.key === 'cohens_d')
    ? [Math.min(-1, yMinData * 1.1), Math.max(1, yMaxData * 1.1)]
    : [0, Math.max(0.5, yMaxData * 1.1)];

  Plotly.react('drift-chart-trend', traces, {{
    margin:{{t:10,r:10,b:50,l:60}},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{{tickfont:{{size:9}}, tickangle:-45}},
    yaxis:{{range: yRange, gridcolor:'#f1f5f9', tickfont:{{size:9}}, title: test.label}},
    showlegend: true, legend:{{orientation:'h', y:1.18, font:{{size:9}}}},
  }}, {{responsive:true, displayModeBar:false}});

  if (footer) {{
    const recentN = (active.recent_quarters || []).length;
    footer.innerHTML = DRIFT_WINDOW === 'all' && DRIFT_STAT_TEST !== 'psi'
      ? `Note: ${{test.label}} is precomputed only for the last ${{recentN}} quarters. Older quarters are omitted from this chart.`
      : '';
  }}
}}

// ═══════════════════════════════════════════════════════════════
// SECTION 3 · Heatmap with Verdict column
// ═══════════════════════════════════════════════════════════════
function _renderDriftHeatmap(visibleQs) {{
  const el = document.getElementById('drift-heatmap-wrap');
  if (!el) return;
  const test = TEST_BY_KEY[DRIFT_STAT_TEST];
  const active = _driftActive();
  const allVars = _driftAllVarNames();

  // Use only vars that appear in at least one visible Q
  function valueAt(q, v) {{
    const row = (active.by_quarter || {{}})[q];
    if (row) {{
      const f = (row.by_variable || []).find(x => x.column === v);
      if (f) return f[DRIFT_STAT_TEST];
    }}
    if (DRIFT_STAT_TEST === 'psi') {{
      if (DRIFT_QUESTION === 'q2') return ((active.psi_heatmap || {{}})[v] || {{}})[q];
      return (((DASH_DATA.time_series || {{}}).psi_heatmap || {{}})[v] || {{}})[q];
    }}
    return null;
  }}

  // Rank by latest Q value desc (red first)
  const latestQ = visibleQs[visibleQs.length - 1];
  const varsOrdered = [...allVars].sort((a, b) => {{
    const va = valueAt(latestQ, a);
    const vb = valueAt(latestQ, b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    // For p-values, lower = worse; for others, higher = worse
    const reverse = (test.key === 'ks_p' || test.key === 'anova_p');
    return reverse ? (va - vb) : (vb - va);
  }}).slice(0, 30); // cap to 30 for readability

  // Verdict per variable using the LATEST snapshot row (across all 5 tests)
  const latestRow = (active.by_quarter || {{}})[latestQ];
  const latestByVar = {{}};
  if (latestRow) for (const r of (latestRow.by_variable || [])) latestByVar[r.column] = r;

  const cellHtml = (q, v) => {{
    const val = valueAt(q, v);
    if (val == null || !Number.isFinite(val)) {{
      return '<td style="text-align:center;padding:4px;background:#fafafa;color:#cbd5e1;font-size:10px;border:1px solid #fff">—</td>';
    }}
    const lvl = test.level(val);
    const c = _testLevelColors(lvl);
    const onClick = `onclick="selectDriftVar('${{v.replace(/'/g, "\\\\'")}}')"`;
    return `<td ${{onClick}} style="text-align:center;padding:4px 6px;background:${{c.bg}};color:${{c.fg}};font-size:10px;font-weight:600;border:1px solid #fff;cursor:pointer">${{test.fmt(val)}}</td>`;
  }};

  const headerRow = `<tr>
    <th style="text-align:left;padding:5px 8px;background:#0f1d35;color:#fff;font-size:10px;font-weight:700;border:1px solid #1e293b;position:sticky;left:0;z-index:2">Variable</th>
    ${{visibleQs.map(q => `<th style="text-align:center;padding:5px 6px;background:#1e293b;color:#fff;font-size:9px;font-weight:600;border:1px solid #1e293b;white-space:nowrap">${{qLabel(q)}}</th>`).join('')}}
    <th style="text-align:center;padding:5px 8px;background:#0f1d35;color:#fff;font-size:10px;font-weight:700;border:1px solid #1e293b">Verdict</th>
  </tr>`;

  const bodyRows = varsOrdered.map(v => {{
    const r = latestByVar[v];
    const verdict = r ? _verdictFor(r) : {{level:'none', label:'—', redCount:0}};
    const vc = _testLevelColors(verdict.level);
    const isSel = DRIFT_SELECTED_VAR === v;
    const selBg = isSel ? 'background:#fff7ed;' : '';
    return `<tr style="${{selBg}}">
      <td onclick="selectDriftVar('${{v.replace(/'/g, "\\\\'")}}')" style="font-family:monospace;font-size:10px;padding:5px 8px;background:${{isSel?'#fff7ed':'#fff'}};color:#0f172a;font-weight:${{isSel?'700':'500'}};border:1px solid #f1f5f9;cursor:pointer;white-space:nowrap;position:sticky;left:0;z-index:1;${{isSel?'border-left:3px solid #9a3412;':''}}">${{v}}</td>
      ${{visibleQs.map(q => cellHtml(q, v)).join('')}}
      <td style="text-align:center;padding:5px 8px;background:${{vc.bg}};color:${{vc.fg}};font-size:10px;font-weight:700;border:1px solid #fff">${{verdict.label}}<br><span style="font-size:8px;font-weight:500;opacity:.7">${{verdict.redCount}}/5 fail</span></td>
    </tr>`;
  }}).join('');

  el.innerHTML = `<div style="overflow-x:auto;max-height:560px;border:1px solid #e2e8f0;border-radius:6px">
    <table style="border-collapse:collapse;font-size:11px">
      <thead>${{headerRow}}</thead>
      <tbody>${{bodyRows}}</tbody>
    </table>
  </div>
  <div style="margin-top:8px;font-size:10px;color:var(--text-muted);display:flex;gap:12px;flex-wrap:wrap">
    <span><span style="display:inline-block;width:12px;height:12px;background:#dcfce7;border-radius:2px;margin-right:4px"></span>Stable · ${{test.bucketLabels[0]}}</span>
    <span><span style="display:inline-block;width:12px;height:12px;background:#fef3c7;border-radius:2px;margin-right:4px"></span>Mixed · ${{test.bucketLabels[1]}}</span>
    <span><span style="display:inline-block;width:12px;height:12px;background:#fee2e2;border-radius:2px;margin-right:4px"></span>Drift · ${{test.bucketLabels[2]}}</span>
    <span style="margin-left:auto;font-style:italic">Top ${{varsOrdered.length}} variables (ranked by ${{test.label}} in the latest quarter). Click a row for detail.</span>
  </div>`;
}}

// ═══════════════════════════════════════════════════════════════
// SECTION 4 · Ranked variables (combined Top Columns + Stat Tests)
// ═══════════════════════════════════════════════════════════════
function _renderDriftRanked(rows) {{
  const el = document.getElementById('drift-ranked-wrap');
  if (!el) return;
  const test = TEST_BY_KEY[DRIFT_STAT_TEST];

  if (!rows.length) {{
    el.innerHTML = '<div style="padding:18px;text-align:center;color:#94a3b8;font-size:12px">No data available for the latest snapshot.</div>';
    return;
  }}

  // Sort: by selected stat test value (worst first)
  const reverse = (test.key === 'ks_p' || test.key === 'anova_p');
  const sorted = [...rows].sort((a, b) => {{
    const va = a[test.key], vb = b[test.key];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (test.key === 'cohens_d') return Math.abs(vb) - Math.abs(va);
    return reverse ? (va - vb) : (vb - va);
  }});

  const body = sorted.map(r => {{
    const verdict = _verdictFor(r);
    const vc = _testLevelColors(verdict.level);
    const isSel = DRIFT_SELECTED_VAR === r.column;
    const cells = TEST_META.map(t => {{
      const v = r[t.key];
      const lvl = t.level(v);
      const c = _testLevelColors(lvl);
      const active = t.key === DRIFT_STAT_TEST;
      const bonus = active ? ';outline:2px solid #0f172a;outline-offset:-2px' : '';
      return `<td style="text-align:center;background:${{c.bg}};color:${{c.fg}};font-weight:600;padding:6px${{bonus}}">${{t.fmt(v)}}</td>`;
    }}).join('');
    return `<tr style="${{isSel?'background:#fff7ed':''}}">
      <td onclick="selectDriftVar('${{r.column.replace(/'/g, "\\\\'")}}')" style="font-family:monospace;font-size:11px;font-weight:${{isSel?'700':'600'}};padding:6px 10px;cursor:pointer;${{isSel?'border-left:3px solid #9a3412;':''}}">${{r.column}}</td>
      ${{cells}}
      <td style="text-align:center;background:${{vc.bg}};color:${{vc.fg}};font-weight:700;padding:6px">${{verdict.label}}<br><span style="font-size:9px;font-weight:500;opacity:.7">${{verdict.redCount}}/5 fail</span></td>
    </tr>`;
  }}).join('');

  el.innerHTML = `<div style="overflow-x:auto"><table style="font-size:12px;width:100%">
    <thead><tr>
      <th style="text-align:left">Variable</th>
      ${{TEST_META.map(t => `<th style="text-align:center" title="${{t.label}}">${{t.short}}</th>`).join('')}}
      <th style="text-align:center">Verdict</th>
    </tr></thead>
    <tbody>${{body}}</tbody>
  </table></div>`;
}}

// ═══════════════════════════════════════════════════════════════
// SECTION 5 · Variable detail drilldown
// ═══════════════════════════════════════════════════════════════
function _renderDriftDetail(varName, latestVars, latestQ) {{
  const el = document.getElementById('drift-detail-wrap');
  if (!el) return;
  const row = latestVars.find(v => v.column === varName);
  if (!row) {{
    el.innerHTML = `<div style="padding:16px;color:var(--gray);font-size:12px">No data for <code>${{varName}}</code> at ${{qLabel(latestQ)}}.</div>`;
    return;
  }}
  const verdict = _verdictFor(row);
  const vc = _testLevelColors(verdict.level);
  const cmpLabels = DRIFT_QUESTION === 'q1'
    ? {{ref: 'Prior Q', cur: qLabel(latestQ)}}
    : {{ref: 'Port 2024 · ' + qLabel(latestQ), cur: 'Port 2025 · ' + qLabel(latestQ)}};

  const distStats = `<table style="font-size:11px;width:100%"><thead><tr>
    <th></th><th style="text-align:right">${{cmpLabels.cur}}</th><th style="text-align:right">${{cmpLabels.ref}}</th><th style="text-align:right">Δ</th>
  </tr></thead><tbody>
    ${{_renderStatLine('Mean',    row.cur_mean,    row.ref_mean)}}
    ${{_renderStatLine('Median',  row.cur_median,  row.ref_median)}}
    ${{_renderStatLine('Std Dev', row.cur_std,     row.ref_std)}}
    ${{_renderStatLine('Missing %', row.cur_missing_pct, row.ref_missing_pct, '%')}}
  </tbody></table>`;

  const testCells = TEST_META.map(t => {{
    const v = row[t.key];
    const lvl = t.level(v);
    const c = _testLevelColors(lvl);
    return `<div style="background:${{c.bg}};color:${{c.fg}};padding:8px 10px;border-radius:6px;text-align:center">
      <div style="font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase">${{t.label}}</div>
      <div style="font-size:16px;font-weight:800;margin-top:2px">${{t.fmt(v)}}</div>
    </div>`;
  }}).join('');

  el.innerHTML = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start">
    <div>
      <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:10px;flex-wrap:wrap">
        <div style="font-size:14px;font-weight:700;font-family:monospace">${{varName}}</div>
        <div style="font-size:10px;font-weight:700;color:#fff;background:${{vc.fg}};padding:2px 8px;border-radius:10px">${{verdict.label}} · ${{verdict.redCount}}/5 fail</div>
        <button onclick="selectDriftVar(null)" style="margin-left:auto;font-size:10px;padding:3px 10px;border:1px solid #cbd5e1;background:#fff;color:#64748b;border-radius:4px;cursor:pointer">close</button>
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Distribution comparison at the ${{qLabel(latestQ)}} snapshot.</div>
      ${{distStats}}
    </div>
    <div>
      <div style="font-size:11px;font-weight:700;color:#0f172a;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Stat Tests at ${{qLabel(latestQ)}}</div>
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px">${{testCells}}</div>
    </div>
  </div>`;
}}

function _renderStatLine(label, cur, ref, suffix) {{
  suffix = suffix || '';
  const dRaw = (cur != null && ref != null && Number.isFinite(cur) && Number.isFinite(ref)) ? (cur - ref) : null;
  const dColor = dRaw == null ? '#64748b' : Math.abs(dRaw) < 1e-6 ? '#64748b' : dRaw > 0 ? '#dc2626' : '#16a34a';
  const dArrow = dRaw == null ? '—' : Math.abs(dRaw) < 1e-6 ? '—' : dRaw > 0 ? '▲' : '▼';
  return `<tr>
    <td style="color:#64748b">${{label}}</td>
    <td style="text-align:right;font-family:monospace">${{cur == null ? '—' : fmt(cur, 3) + suffix}}</td>
    <td style="text-align:right;font-family:monospace">${{ref == null ? '—' : fmt(ref, 3) + suffix}}</td>
    <td style="text-align:right;color:${{dColor}};font-weight:600">${{dRaw == null ? '—' : dArrow + ' ' + (dRaw >= 0 ? '+' : '') + fmt(dRaw, 3) + suffix}}</td>
  </tr>`;
}}
"""
