"""D0 — Overview dashboard.

Uses f-string syntax so the doubled `{{...}}` in JS code resolves to literal `{...}`
when the module is imported. The resulting `JS` is plain JavaScript ready to inject.
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 0: OVERVIEW ──────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════
let OV_VAR = (DASH_DATA.key_vars||[])[0] || 'Balance';

function renderOverview() {{
  const d = getQData(CQ);
  const qoq = getQoQ(CQ);
  const comp = d.completeness || {{}};
  const rules= d.business_rules || {{}};
  const pop  = d.population || {{}};
  const drift= d.drift || {{}};
  const gov  = d.governance || {{}};

  const ratingColor = {{GREEN:'green',MODERATE:'amber',RED:'red'}}[gov.dq_rating] || 'gray';

  const cards = [
    {{tab:'completeness',title:'Completeness',    icon:'✅',
      lines:[`Overall: ${{pct(comp.overall_pct)}}`,`Cols w/ Missing: ${{comp.columns_with_missing||0}}`,`Critical >25%: ${{comp.critical_missing_count||0}}`],
      status: (comp.overall_pct||100)<95?'red':(comp.overall_pct||100)<98?'amber':'green'}},
    {{tab:'rules',      title:'Business Rules',     icon:'📋',
      lines:[`Executed: ${{rules.total_executed||0}}`,`Passed: ${{rules.rules_passed||0}}`,`Failure Rate: ${{pct(rules.failure_rate_pct)}}`],
      status: (rules.critical_failures||0)>0?'red':(rules.rules_failed||0)>0?'amber':'green'}},
    {{tab:'population', title:'Population Stability',icon:'👥',
      lines:[`Total: ${{fmtN(pop.total)}}`,`New: ${{pop.new||0}} (${{pct(pop.new_pct)}})`,`PSI: ${{fmt(pop.psi,2)}} (${{pop.psi_label||'—'}})`],
      status: pop.psi_label==='Significant'?'red':pop.psi_label==='Moderate'?'amber':'green'}},
    {{tab:'drift',      title:'Distribution Drift',  icon:'📈',
      lines:[`Avg PSI: ${{fmt(drift.avg_psi,3)}}`,`Sig. Drift: ${{drift.sig_drift_count||0}} cols`,`Status: ${{drift.drift_status||'—'}}`],
      status: drift.drift_status==='Critical'?'red':drift.drift_status==='Elevated'?'amber':'green'}},
    {{tab:'schema',     title:'Schema Quality',      icon:'🗄️',
      lines:[`Columns: ${{d.schema && d.schema.total_columns||0}}`,`Quality: ${{pct(d.schema && d.schema.quality_score)}}`,`Changes: ${{d.schema && d.schema.tables_with_changes||0}}`],
      status: (d.schema && d.schema.breaking_changes||0)>0?'red':(d.schema&&d.schema.modified_columns||0)>0?'amber':'green'}},
    {{tab:'governance', title:'Business & Gov.',     icon:'🏛️',
      lines:[`DQ Rating: ${{gov.dq_rating||'—'}}`,`Issues: ${{(gov.issues||[]).length}}`,`Recommendations: ${{(gov.recommendations||[]).length}}`],
      status: ratingColor}},
    {{tab:'completeness',title:'Missing Data',       icon:'📉',
      lines:[`High Missing >10%: ${{comp.high_missing_count||0}}`,`Critical >25%: ${{comp.critical_missing_count||0}}`,`QoQ: ${{arrow(qoq.completeness_delta,true)}}`],
      status: (comp.critical_missing_count||0)>0?'red':(comp.high_missing_count||0)>0?'amber':'green'}},
  ];

  const cardsHtml = cards.map(c => `
    <div class="ov-card" onclick="switchTab('${{c.tab}}')">
      <div class="ov-card-title">${{c.icon}} ${{c.title}}</div>
      <div style="margin-bottom:8px">
        <span class="status-dot" style="background:var(--${{c.status==='green'?'green':c.status==='amber'?'amber':'red'}})"></span>
        <span class="badge badge-${{c.status==='red'?'critical':c.status==='amber'?'medium':'green'}}">${{c.status.toUpperCase()}}</span>
      </div>
      ${{c.lines.map(l=>`<div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">${{l}}</div>`).join('')}}
    </div>`).join('');

  const varOptions = (DASH_DATA.key_vars||[]).map(v=>
    `<option value="${{v}}" ${{v===OV_VAR?'selected':''}}>${{v}}</option>`).join('');

  document.getElementById('tab-overview').innerHTML = `
    <div class="dash-header">
      <h2>Portfolio DQ Overview — ${{qLabel(CQ)}}</h2>
      <p>Comparing Port 2024 vs Port 2025. Overall DQ Rating (Port 2025): ${{badge(gov.dq_rating||'—')}}</p>
    </div>

    <div class="section-card" style="margin-bottom:16px">
      <div class="section-title">Executive Summary (Port 2025 — ${{qLabel(CQ)}})</div>
      <div class="summary-text">${{gov.exec_summary||'Run the pipeline to generate summary.'}}</div>
    </div>

    <div class="overview-grid" style="grid-template-columns:repeat(4,1fr)">${{cardsHtml}}</div>

    <div class="section-card" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span style="font-size:12px;font-weight:600;color:var(--text-muted)">COMPARISON MODE:</span>
        <button onclick="setCmpMode('qoq')"        class="ov-mode-btn${{CMP_MODE==='qoq'?' ov-mode-active':''}}">QoQ — Same Portfolio</button>
        <button onclick="setCmpMode('yoy')"        class="ov-mode-btn${{CMP_MODE==='yoy'?' ov-mode-active':''}}">YoY — 2024 vs 2025</button>
        <button onclick="setCmpMode('historical')" class="ov-mode-btn${{CMP_MODE==='historical'?' ov-mode-active':''}}">Historical Comparison</button>
        <span style="font-size:12px;color:var(--text-muted);margin-left:auto">
          <span style="display:inline-block;width:12px;height:3px;background:#2563eb;border-radius:2px;vertical-align:middle"></span> Port 2024 &nbsp;
          <span style="display:inline-block;width:12px;height:3px;background:#16a34a;border-radius:2px;vertical-align:middle"></span> Port 2025
        </span>
      </div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <div class="section-title" style="margin:0">Missing % —</div>
          <select id="ov-var-select" onchange="setOvVar(this.value)"
            style="font-size:11px;padding:3px 6px;border:1px solid #e5e7eb;border-radius:4px;background:#fff">${{varOptions}}</select>
        </div>
        <div id="ov-chart-completeness" class="chart-sm"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Avg PSI (Distribution Drift) Over Time</div>
        <div id="ov-chart-psi" class="chart-sm"></div>
      </div>
    </div>
    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Rule Failure Rate % Over Time</div>
        <div id="ov-chart-failures" class="chart-sm"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Population Size (Records) Over Time</div>
        <div id="ov-chart-population" class="chart-sm"></div>
      </div>
    </div>
  `;

  drawOvCharts();
}}

function setOvMode(mode) {{ setCmpMode(mode); }}
function setOvVar(v) {{ OV_VAR = v; drawOvCompleteness(); }}

function _ovSlices(mode_unused) {{
  const mode = CMP_MODE;
  const p25 = DASH_DATA.time_series || {{}};
  const p24 = (DASH_DATA.port24 || {{}}).time_series || {{}};

  if (mode === 'qoq') {{
    const sl = arr => (arr||[]).slice(-12);
    return {{
      label24: null, label25: 'Port 2025',
      x25:   sl(p25.completeness_over_time).map(r=>r.label),
      yc25:  sl(p25.completeness_over_time).map(r=>r.value),
      ypsi25:sl(p25.psi_over_time).map(r=>r.avg_psi),
      yf25:  sl(p25.failure_rate_over_time).map(r=>r.failure_rate_pct),
      yp25:  sl(p25.population_over_time).map(r=>r.total),
      ym25:  sl((p25.missing_by_variable||{{}})[OV_VAR]||[]).map(r=>r.missing_pct),
      x24:[], yc24:[], ypsi24:[], yf24:[], yp24:[], ym24:[],
    }};
  }} else if (mode === 'yoy') {{
    const yr24 = Math.max(...(p24.completeness_over_time||[]).map(r=>+r.quarter.slice(0,4)));
    const yr25 = Math.max(...(p25.completeness_over_time||[]).map(r=>+r.quarter.slice(0,4)));
    const f24 = arr => (arr||[]).filter(r=>r.quarter && +r.quarter.slice(0,4)===yr24);
    const f25 = arr => (arr||[]).filter(r=>r.quarter && +r.quarter.slice(0,4)===yr25);
    const ql = r => 'Q'+r.quarter.slice(5);
    return {{
      label24: 'Port 2024 ('+yr24+')', label25: 'Port 2025 ('+yr25+')',
      x24:   f24(p24.completeness_over_time).map(ql),
      yc24:  f24(p24.completeness_over_time).map(r=>r.value),
      ypsi24:f24(p24.psi_over_time).map(r=>r.avg_psi),
      yf24:  f24(p24.failure_rate_over_time).map(r=>r.failure_rate_pct),
      yp24:  f24(p24.population_over_time).map(r=>r.total),
      ym24:  f24((p24.missing_by_variable||{{}})[OV_VAR]||[]).map(r=>r.missing_pct),
      x25:   f25(p25.completeness_over_time).map(ql),
      yc25:  f25(p25.completeness_over_time).map(r=>r.value),
      ypsi25:f25(p25.psi_over_time).map(r=>r.avg_psi),
      yf25:  f25(p25.failure_rate_over_time).map(r=>r.failure_rate_pct),
      yp25:  f25(p25.population_over_time).map(r=>r.total),
      ym25:  f25((p25.missing_by_variable||{{}})[OV_VAR]||[]).map(r=>r.missing_pct),
    }};
  }} else {{
    return {{
      label24: 'Port 2024', label25: 'Port 2025',
      x24:   (p24.completeness_over_time||[]).map(r=>r.label),
      yc24:  (p24.completeness_over_time||[]).map(r=>r.value),
      ypsi24:(p24.psi_over_time||[]).map(r=>r.avg_psi),
      yf24:  (p24.failure_rate_over_time||[]).map(r=>r.failure_rate_pct),
      yp24:  (p24.population_over_time||[]).map(r=>r.total),
      ym24:  ((p24.missing_by_variable||{{}})[OV_VAR]||[]).map(r=>r.missing_pct),
      x25:   (p25.completeness_over_time||[]).map(r=>r.label),
      yc25:  (p25.completeness_over_time||[]).map(r=>r.value),
      ypsi25:(p25.psi_over_time||[]).map(r=>r.avg_psi),
      yf25:  (p25.failure_rate_over_time||[]).map(r=>r.failure_rate_pct),
      yp25:  (p25.population_over_time||[]).map(r=>r.total),
      ym25:  ((p25.missing_by_variable||{{}})[OV_VAR]||[]).map(r=>r.missing_pct),
    }};
  }}
}}

function _ovTrace(x, y, name, color, dash) {{
  return {{
    x, y, name, type:'scatter', mode:'lines+markers',
    line:{{color, width:2, dash:dash||'solid'}},
    marker:{{size:3, color}},
    connectgaps: true,
  }};
}}

const _ovLayout = (yTitle) => ({{
  margin:{{t:10,r:10,b:50,l:50}},
  height: 180,
  paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  xaxis:{{showgrid:false, tickfont:{{size:8}}, tickangle:-45}},
  yaxis:{{title:yTitle, gridcolor:'#f1f5f9', tickfont:{{size:9}}}},
  legend:{{orientation:'h', y:1.18, x:0, font:{{size:9}}}},
  showlegend: true,
}});

const _ovCfg = {{responsive:true, displayModeBar:false}};

function drawOvCompleteness() {{
  if (!document.getElementById('ov-chart-completeness')) return;
  const s = _ovSlices(CMP_MODE);
  const traces = [];
  if (s.label24 && s.x24.length) traces.push(_ovTrace(s.x24, s.ym24, s.label24, '#2563eb'));
  if (s.x25.length)              traces.push(_ovTrace(s.x25, s.ym25, s.label25, '#16a34a'));
  Plotly.react('ov-chart-completeness', traces, {{..._ovLayout('Missing %'), yaxis:{{..._ovLayout().yaxis, title:'Missing %', autorange:'reversed', tickformat:'.1f'}}}}, _ovCfg);
}}

function drawOvCharts() {{
  if (!document.getElementById('ov-chart-completeness')) return;
  const s = _ovSlices(CMP_MODE);

  drawOvCompleteness();

  const psiTraces = [];
  if (s.label24 && s.x24.length) psiTraces.push(_ovTrace(s.x24, s.ypsi24, s.label24, '#2563eb'));
  if (s.x25.length)              psiTraces.push(_ovTrace(s.x25, s.ypsi25, s.label25, '#16a34a'));
  Plotly.react('ov-chart-psi', psiTraces, _ovLayout('PSI'), _ovCfg);

  const failTraces = [];
  if (s.label24 && s.x24.length) failTraces.push(_ovTrace(s.x24, s.yf24, s.label24, '#2563eb'));
  if (s.x25.length)              failTraces.push(_ovTrace(s.x25, s.yf25, s.label25, '#16a34a'));
  Plotly.react('ov-chart-failures', failTraces, _ovLayout('%'), _ovCfg);

  const popTraces = [];
  if (s.label24 && s.x24.length) popTraces.push(_ovTrace(s.x24, s.yp24, s.label24, '#2563eb'));
  if (s.x25.length)              popTraces.push(_ovTrace(s.x25, s.yp25, s.label25, '#16a34a'));
  Plotly.react('ov-chart-population', popTraces, _ovLayout('Records'), _ovCfg);
}}
"""
