"""D6 — Population Stability dashboard.

Includes 3 segment filters (Business Unit / Basel II Category / Risk Rating).
When a filter is active, KPIs + time-series charts show the sliced subset;
segment-level views (mix, migration, by_segment table) display a banner
explaining they're hidden in filtered mode.
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 6: POPULATION STABILITY ──────────────────────────────
// ═══════════════════════════════════════════════════════════════
let POP_FILTER = {{ dim: null, value: null }};
// Retained Portfolio section state (independent of global CMP_MODE)
let RETAINED_SNAPSHOT = null;   // null = use global CQ; else specific quarter key like '2025Q4'
let CRR_VIEW = 'change';        // 'change' = CRR upgrade/downgrade counts; 'exposure' = balance Δ

function setRetainedSnapshot(q) {{
  RETAINED_SNAPSHOT = q || null;
  renderTab('population');
}}
function setCrrView(v) {{
  CRR_VIEW = v;
  renderTab('population');
}}

function setPopFilter(dim, value) {{
  // Single-active filter: setting a value clears the other dimensions
  if (!value) {{
    POP_FILTER = {{ dim: null, value: null }};
  }} else {{
    POP_FILTER = {{ dim, value }};
  }}
  renderTab('population');
}}
function clearPopFilter() {{
  POP_FILTER = {{ dim: null, value: null }};
  renderTab('population');
}}

function _popSlice() {{
  // Returns the sliced population metrics for the current quarter, or null if no filter.
  if (!POP_FILTER.dim || !POP_FILTER.value) return null;
  const d = getQData(CQ);
  return ((d.population || {{}}).slices || {{}})[POP_FILTER.dim]?.[POP_FILTER.value] || null;
}}

function _popSliceTS() {{
  // Returns sliced population_over_time array for the active filter, or null.
  if (!POP_FILTER.dim || !POP_FILTER.value) return null;
  return ((DASH_DATA.time_series.population_slices || {{}})[POP_FILTER.dim] || {{}})[POP_FILTER.value] || [];
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

  // Build the filter dropdowns
  const filterDims = DASH_DATA.population_filter_dims || {{}};
  const filterControls = (() => {{
    const blocks = [];
    for (const [dim, meta] of Object.entries(filterDims)) {{
      const isActive = POP_FILTER.dim === dim;
      const opts = ['<option value="">All</option>']
        .concat((meta.values||[]).map(v =>
          `<option value="${{v}}"${{isActive && POP_FILTER.value===v?' selected':''}}>${{v}}</option>`
        )).join('');
      // When another filter is active, dim this dropdown to indicate it's bypassed
      const dim_style = (POP_FILTER.dim && !isActive)
        ? 'opacity:0.5'
        : '';
      blocks.push(`
        <div style="display:flex;align-items:center;gap:6px;${{dim_style}}">
          <label style="font-size:10px;color:var(--text-muted);font-weight:600;white-space:nowrap">${{meta.label}}</label>
          <select class="filter-select" onchange="setPopFilter('${{dim}}', this.value)" style="font-size:11px;padding:3px 8px;min-width:120px">
            ${{opts}}
          </select>
        </div>`);
    }}
    return blocks.join('');
  }})();

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

  const matrix = (d.population||{{}}).migration_matrix || {{}};
  const segs   = matrix.segments || [];
  const mat    = matrix.matrix || {{}};
  const matHtml = (segs.length && !filterActive) ? `
    <div style="overflow-x:auto"><table>
      <thead><tr><th>From \\\\ To</th>${{segs.map(s=>`<th style="white-space:nowrap">${{s}}</th>`).join('')}}<th>Dropped</th></tr></thead>
      <tbody>${{segs.map(from=>`<tr>
        <td style="font-weight:600">${{from}}</td>
        ${{segs.map(to=>{{
          const val = (mat[from]||{{}})[to]||0;
          const total = Object.values(mat[from]||{{}}).reduce((a,b)=>a+b,0)||1;
          const pctVal = (val/total*100).toFixed(1);
          const isDiag = from===to;
          return `<td style="${{isDiag?'background:#dbeafe;font-weight:700':''}}">
            ${{val}} (${{pctVal}}%)</td>`;
        }}).join('')}}
        <td style="color:var(--red)">${{(mat[from]||{{}}).Dropped||0}}</td>
      </tr>`).join('')}}
      </tbody>
    </table></div>` : '';

  const filteredNotice = `<div style="padding:24px;text-align:center;color:#92400e;background:#fef3c7;border-radius:6px;font-size:12px">
    🔒 Segment-level breakdown is hidden when a filter is active.
    <br><span style="color:#64748b;font-size:11px">Clear the filter to see segment migrations and by-segment table.</span>
  </div>`;

  const insights = (gov.population_insights || [
    {{icon:'📈',text:'Population trend driven by new originations across all segments.'}},
    {{icon:'ℹ️',text:`PSI stands at ${{fmt(pop.psi||0,2)}} (${{pop.psi_label||'—'}}), indicating ${{pop.psi_label==='Stable'?'no significant':'notable'}} composition shift.`}},
  ]);

  // ── Retained Portfolio section: resolve local snapshot + its natural prior ──
  // Default to global CQ if user hasn't picked locally
  const retSnap = RETAINED_SNAPSHOT || CQ;
  const _allQ = DASH_DATA.quarters || [];
  const _retIdx = _allQ.indexOf(retSnap);
  const retPQ = _retIdx > 0 ? _allQ[_retIdx - 1] : retSnap;
  const retData = getQData(retSnap);
  const crrAnalysis = (retData.population || {{}}).crr_analysis;
  const mig = (crrAnalysis || {{}}).crr_migration_matrix || {{grades: [], matrix: {{}}}};

  // Quarter dropdown options for the snapshot selector
  const retSnapOpts = [..._allQ].reverse()
    .map(q => `<option value="${{q}}"${{q===retSnap?' selected':''}}>${{qLabel(q)}}</option>`).join('');
  let crrMatrixHtml = '';
  if (mig.grades && mig.grades.length) {{
    const grades = mig.grades;
    const M = mig.matrix || {{}};
    // Find max non-diagonal count for color normalization
    let maxCount = 0;
    grades.forEach(f => grades.forEach(t => {{
      if (f !== t) maxCount = Math.max(maxCount, (M[f] || {{}})[t]?.count || 0);
    }}));
    // Diagonal totals don't compete with off-diagonal for color intensity
    const cellHtml = (f, t) => {{
      const cell = (M[f] || {{}})[t] || {{count: 0, balance: 0}};
      const ff = parseFloat(f), tt = parseFloat(t);
      if (cell.count === 0) {{
        return '<td style="text-align:center;color:#cbd5e1;font-size:11px;border:1px solid #f1f5f9">—</td>';
      }}
      let bg, fg;
      if (ff === tt) {{
        // Diagonal — neutral indigo, intensity based on % of retained
        bg = 'rgba(99,102,241,0.18)'; fg = '#3730a3';
      }} else if (tt < ff) {{
        // Upgrade (lower CRR is better)
        const intensity = maxCount > 0 ? Math.min(1, cell.count / maxCount) : 0;
        bg = `rgba(22,163,74,${{0.15 + intensity * 0.55}})`;
        fg = intensity > 0.4 ? '#fff' : '#14532d';
      }} else {{
        // Downgrade
        const intensity = maxCount > 0 ? Math.min(1, cell.count / maxCount) : 0;
        bg = `rgba(220,38,38,${{0.15 + intensity * 0.55}})`;
        fg = intensity > 0.4 ? '#fff' : '#7f1d1d';
      }}
      const balStr = cell.balance >= 0 ? '+$' + fmt(cell.balance, 1) + 'M' : '-$' + fmt(-cell.balance, 1) + 'M';
      return `<td style="background:${{bg}};color:${{fg}};text-align:center;font-weight:600;border:1px solid #fff;padding:6px"
               title="From CRR ${{f}} → ${{t}}: ${{cell.count}} facilities (${{balStr}})">${{cell.count}}</td>`;
    }};
    const headerRow = `<tr>
      <th style="background:#0f1d35;color:#fff;font-size:10px;text-align:center;padding:6px;border:1px solid #fff">From \\\\ To</th>
      ${{grades.map(g => `<th style="background:#1e293b;color:#fff;font-size:11px;text-align:center;padding:6px;border:1px solid #fff">${{g}}</th>`).join('')}}
    </tr>`;
    const bodyRows = grades.map(f => `<tr>
      <th style="background:#1e293b;color:#fff;font-size:11px;text-align:right;padding:6px;border:1px solid #fff">${{f}}</th>
      ${{grades.map(t => cellHtml(f, t)).join('')}}
    </tr>`).join('');
    crrMatrixHtml = `
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
        <span style="margin-left:auto;font-style:italic">Hover any cell for facility count + balance delta</span>
      </div>`;
  }}

  document.getElementById('tab-population').innerHTML = `
    <div class="dash-header">
      <h2>Population Stability Dashboard</h2>
      <p>Monitor population movements, account lifecycle, and segment stability over time.</p>
    </div>

    ${{_modeBar()}}

    <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:10px 14px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;margin-bottom:14px">
      <span style="font-size:10px;font-weight:700;color:#0369a1;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap">🔎 Filter Population By:</span>
      ${{filterControls}}
      ${{POP_FILTER.dim ? `<button onclick="clearPopFilter()" style="font-size:10px;padding:4px 10px;border:1px solid #0369a1;border-radius:4px;background:#fff;color:#0369a1;cursor:pointer">Reset</button>` : ''}}
      <span style="margin-left:auto;font-size:10px;color:#64748b;font-style:italic">One filter at a time — selecting a value clears the others</span>
    </div>

    ${{filterBanner}}

    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr)">${{kpiHtml}}</div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Total Records Over Time</div>
        <div id="pop-chart-movement" class="chart-box"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Account Lifecycle — ${{qLabel(CQ)}}${{filterActive?' (filtered)':''}}</div>
        <div id="pop-chart-donut" style="min-height:220px"></div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">Facility Flow (FCL-ID) — ${{qLabel(PQ)}} → ${{qLabel(CQ)}}</div>
      <div id="pop-fcl-sankey" class="chart-box" style="height:300px"></div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Population Movement Waterfall — ${{qLabel(PQ)}} → ${{qLabel(CQ)}}${{filterActive?' (filtered)':''}}</div>
        <div id="pop-chart-waterfall" class="chart-box"></div>
      </div>
      <div class="section-card">
        <div class="section-title">PSI Over Time</div>
        <div id="pop-chart-psi" class="chart-sm"></div>
        <div style="margin-top:8px;font-size:10px;color:var(--text-muted)">
          <span style="color:var(--red)">■</span> &gt;0.20 Significant &nbsp;
          <span style="color:var(--amber)">■</span> 0.10–0.20 Moderate &nbsp;
          <span style="color:var(--green)">■</span> &lt;0.10 Stable
          ${{filterActive ? '<span style="color:#92400e;margin-left:8px">⚡ PSI shown is portfolio-wide (filter not applied to PSI calc)</span>' : ''}}
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Segment Composition Over Time (% of Portfolio)</div>
        ${{filterActive ? filteredNotice : '<div id="pop-chart-segment-mix" class="chart-box"></div><div style="font-size:10px;color:var(--text-muted);margin-top:6px">Stacked share of each Business Unit across quarters — reveals portfolio mix shifts.</div>'}}
      </div>
      <div class="section-card">
        <div class="section-title">Churn Dynamics — New / Continuing / Dropped per Quarter${{filterActive?' (filtered)':''}}</div>
        <div id="pop-chart-churn" class="chart-box"></div>
        <div style="font-size:10px;color:var(--text-muted);margin-top:6px">
          Continuing (blue) stacks up, New (green) adds growth, Dropped (red) extends down.
        </div>
      </div>
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
  const sliceTS = _popSliceTS();  // null if no filter

  // ── Helper: apply CMP_MODE filter to a time series ──
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

  // Total records over time — use sliced TS if filter active, else dual-line port24/port25
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

  // Account lifecycle donut — use sliced or unfiltered
  Plotly.newPlot('pop-chart-donut',[{{
    type:'pie',hole:0.65,
    values:[pop.continuing||0,pop.new||0,pop.dropped||0],
    labels:['Continuing','New','Dropped'],
    marker:{{colors:['#3b82f6','#16a34a','#dc2626']}},
    textinfo:'percent+label',textfont:{{size:10}},
  }}],{{margin:{{t:10,r:10,b:10,l:10}},height:220,
    paper_bgcolor:'rgba(0,0,0,0)',legend:{{font:{{size:10}}}},
    annotations:[{{text:`${{fmtN(pop.total)}}<br>${{filterActive?'in slice':'Total'}}`,showarrow:false,font:{{size:12,color:'#111827'}}}}]}},PLcfg);

  // Facility Flow Sankey (FCL-ID level) — prior → continuing/dropped + new → current
  if (!fclPop.prior_total) {{
    document.getElementById('pop-fcl-sankey').innerHTML = '<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">No prior quarter data for facility-level comparison.</div>';
  }} else {{
    const cont = fclPop.continuing || 0;
    const drop = fclPop.dropped || 0;
    const newN = fclPop.new || 0;
    const pql = qLabel(PQ) || 'Prior';
    const cql = qLabel(CQ);
    Plotly.newPlot('pop-fcl-sankey', [{{
      type: 'sankey',
      orientation: 'h',
      node: {{
        pad: 20, thickness: 24, line: {{color: '#e5e7eb', width: 0.5}},
        label: [pql+' ('+fmtN(fclPop.prior_total)+')', 'Continuing', 'Dropped', 'New Entries', cql+' ('+fmtN(fclPop.total)+')'],
        color: ['#6366f1', '#3b82f6', '#ef4444', '#22c55e', '#6366f1'],
      }},
      link: {{
        source: [0, 0, 1, 3],
        target: [1, 2, 4, 4],
        value: [Math.max(cont,1), Math.max(drop,1), Math.max(cont,1), Math.max(newN,1)],
        color: ['rgba(59,130,246,0.30)','rgba(239,68,68,0.30)','rgba(59,130,246,0.30)','rgba(34,197,94,0.30)'],
        customdata: [
          pql+' → Continuing: '+fmtN(cont)+' ('+fclPop.continuing_pct.toFixed(1)+'%)',
          pql+' → Dropped: '+fmtN(drop)+' ('+fclPop.dropped_pct.toFixed(1)+'%)',
          'Continuing → '+cql+': '+fmtN(cont),
          'New → '+cql+': '+fmtN(newN)+' ('+fclPop.new_pct.toFixed(1)+'%)',
        ],
        hovertemplate: '%{{customdata}}<extra></extra>',
      }},
    }}], {{
      margin: {{t:20,r:20,b:20,l:20}}, height: 280,
      paper_bgcolor: 'rgba(0,0,0,0)', font: {{size:11, color:'#374151'}},
    }}, PLcfg);
  }}

  // Waterfall — sliced if filter active
  Plotly.newPlot('pop-chart-waterfall',[{{
    type:'waterfall',
    x:[qLabel(PQ),'New Accounts','Dropped Accounts',qLabel(CQ)],
    y:[pop.prior_total||0,pop.new||0,-(pop.dropped||0),pop.total||0],
    measure:['absolute','relative','relative','total'],
    connector:{{line:{{color:'#e5e7eb'}}}},
    increasing:{{marker:{{color:'#16a34a'}}}},decreasing:{{marker:{{color:'#dc2626'}}}},
    totals:{{marker:{{color:'#2563eb'}}}},
    text:[fmtN(pop.prior_total||0),'+'+fmtN(pop.new||0),'-'+fmtN(pop.dropped||0),fmtN(pop.total||0)],
    textposition:'outside',
  }}],{{margin:{{t:10,r:40,b:50,l:50}},height:220,
    paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
    yaxis:{{gridcolor:'#f1f5f9',tickfont:{{size:9}}}},xaxis:{{tickfont:{{size:10}}}},showlegend:false}},PLcfg);

  // PSI over time — dual line with threshold reference lines (portfolio-wide always)
  const psiBase25 = _cmpFilter(_cmpTS25('psi_over_time'));
  const psiTraces = _cmpTraces('psi_over_time','avg_psi','Port 2024 PSI','Port 2025 PSI');
  psiTraces.push({{ x:_cmpX(psiBase25), y:psiBase25.map(()=>0.2), name:'Significant (0.2)',
    type:'scatter', mode:'lines', line:{{color:'#dc2626',width:1,dash:'dot'}} }});
  psiTraces.push({{ x:_cmpX(psiBase25), y:psiBase25.map(()=>0.1), name:'Moderate (0.1)',
    type:'scatter', mode:'lines', line:{{color:'#d97706',width:1,dash:'dash'}} }});
  Plotly.react('pop-chart-psi', psiTraces,
    {{..._cmpLayout('PSI',160), yaxis:{{range:[0,0.35],gridcolor:'#f1f5f9',tickfont:{{size:9}},title:'PSI'}}}}, _cmpCfg);

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

  // ── CRR Migration Analysis (Retained Customers) — uses retSnap / retPQ ──
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
      // === View 1: Customer Risk Rating Change (upgrades + / downgrades − / net line) ===
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
        barmode:'relative',
        bargap: 0.25,
        margin:{{t:50,r:20,b:60,l:60}}, height:320,
        paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
        xaxis: xCommon,
        yaxis:{{
          title:{{text:'<b>Facilities (±)</b>', font:{{size:12,color:'#111827'}}}},
          gridcolor:'#e5e7eb', zerolinecolor:'#0f1d35', zerolinewidth:2,
          tickfont:{{size:10,color:'#374151'}},
        }},
        legend:{{
          orientation:'h', y:1.10, x:0.5, xanchor:'center',
          font:{{size:11}}, bgcolor:'rgba(255,255,255,0.8)',
        }},
      }}, PLcfg);
    }} else {{
      // === View 2: Existing Customer Exposure Change (Δ Balance $M per CRR grade) ===
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
        bargap: 0.25,
        margin:{{t:30,r:20,b:60,l:70}}, height:320,
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

    // Summary tables (right side)
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

  // Churn Dynamics — sliced if filter, else port25 full
  const churnTS = filterActive ? applyCmpFilter(sliceTS) : _cmpFilter(_cmpTS25('population_over_time'));
  const churnX = churnTS.map(r => CMP_MODE === 'yoy' ? 'Q'+r.quarter.slice(5) : r.label);
  Plotly.react('pop-chart-churn', [
    {{
      type:'bar', name:'Continuing',
      x:churnX, y:churnTS.map(r => r.continuing || 0),
      marker:{{color:'#3b82f6'}},
      hovertemplate:'%{{x}}<br>Continuing: %{{y:,}}<extra></extra>',
    }},
    {{
      type:'bar', name:'New',
      x:churnX, y:churnTS.map(r => r.new || 0),
      marker:{{color:'#16a34a'}},
      hovertemplate:'%{{x}}<br>New: +%{{y:,}}<extra></extra>',
    }},
    {{
      type:'bar', name:'Dropped',
      x:churnX, y:churnTS.map(r => -(r.dropped || 0)),
      marker:{{color:'#dc2626'}},
      hovertemplate:'%{{x}}<br>Dropped: %{{y:,}}<extra></extra>',
    }},
    {{
      type:'scatter', name:'Net total',
      x:churnX, y:churnTS.map(r => r.total || 0),
      yaxis:'y2', mode:'lines+markers',
      line:{{color:'#0f1d35',width:2}}, marker:{{size:4}},
      hovertemplate:'%{{x}}<br>Total: %{{y:,}}<extra></extra>',
    }},
  ], {{
    barmode:'relative', margin:{{t:10,r:60,b:50,l:50}}, height:220,
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{{tickangle:-45,tickfont:{{size:8}}}},
    yaxis:{{title:'Accounts (± net flow)',gridcolor:'#f1f5f9',tickfont:{{size:9}},zerolinecolor:'#94a3b8',zerolinewidth:1}},
    yaxis2:{{title:'Total',overlaying:'y',side:'right',showgrid:false,tickfont:{{size:9}}}},
    legend:{{orientation:'h',y:-0.35,font:{{size:9}}}},
  }}, _cmpCfg);
}}
"""
