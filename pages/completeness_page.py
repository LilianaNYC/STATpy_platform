"""D4 — Completeness dashboard (missing % by variable / segment / type / source)."""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 4: COMPLETENESS ──────────────────────────────────────
// ═══════════════════════════════════════════════════════════════
function renderCompleteness() {{
  const d   = getQData(CQ);
  const pd_ = getQData(PQ);
  const comp  = d.completeness || {{}};
  const pcomp = pd_.completeness || {{}};
  const qoq   = d.qoq || {{}};
  const ts    = DASH_DATA.time_series;

  const kpis = [
    {{icon:'✅',label:'Overall Completeness',      val:pct(comp.overall_pct,2),   delta:arrow(qoq.completeness_delta,true)}},
    {{icon:'🗂️',label:'Total Records',             val:fmtN(comp.total_records),  delta:''}},
    {{icon:'📊',label:'Columns Analyzed',          val:fmtN(comp.columns_analyzed),delta:''}},
    {{icon:'❓',label:'Columns w/ Missing Data',   val:fmtN(comp.columns_with_missing),delta:''}},
    {{icon:'⚠️',label:'High Missing (>10%)',       val:fmtN(comp.high_missing_count),delta:''}},
    {{icon:'🚨',label:'Critical Missing (>25%)',   val:fmtN(comp.critical_missing_count),delta:''}},
  ];
  const kpiHtml = kpis.map(k=>`<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value">${{k.val}}</div>
    ${{k.delta?`<div class="kpi-delta">${{k.delta}}</div>`:''}}</div>`).join('');

  const sevCounts = comp.severity_counts || {{}};
  const sevLabels = ['Critical','High','Medium','Low','Very Low'];
  const sevColors = ['#dc2626','#ea580c','#d97706','#16a34a','#6b7280'];

  const compRows = (comp.by_column||[]).slice(0,20).map(r=>`<tr>
    <td style="font-family:monospace;font-size:11px">${{r.column}}</td>
    ${{completenessCell(r.missing_pct)}}
    <td>${{badge(r.severity)}}</td>
    <td>${{fmtN(r.missing_n)}}</td>
  </tr>`).join('');

  const segRows = (comp.by_segment||[]).map(s=>`<tr>
    <td>${{s.segment}}</td>
    <td><div style="background:var(--gray-light);border-radius:4px;height:10px;width:100%">
      <div style="background:var(--green);border-radius:4px;height:10px;width:${{s.completeness_pct}}%"></div></div></td>
    <td>${{pct(s.completeness_pct)}}</td>
    <td>${{pct(s.missing_pct)}}</td>
  </tr>`).join('');

  const typeRows = (comp.by_type||[]).map(t=>`<tr>
    <td>${{t.type}}</td>
    <td>${{pct(t.completeness_pct)}}</td>
    <td>${{pct(t.missing_pct)}}</td>
  </tr>`).join('');

  const srcRows = (comp.by_source||[]).map(s=>`<tr>
    <td>${{s.source}}</td>
    <td><div style="background:var(--gray-light);border-radius:4px;height:10px;width:100%">
      <div style="background:var(--green);border-radius:4px;height:10px;width:${{s.completeness_pct}}%"></div></div></td>
    <td>${{pct(s.completeness_pct)}}</td>
    <td>${{pct(s.missing_pct)}}</td>
  </tr>`).join('');

  document.getElementById('tab-completeness').innerHTML = `
    <div class="dash-header">
      <h2>Completeness Dashboard — ${{qLabel(CQ)}}</h2>
      <p>Monitor missing data patterns by variable, segment, source, and data type.</p>
    </div>
    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr)">${{kpiHtml}}</div>
    ${{_modeBar()}}

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Overall Completeness % Over Time</div>
        <div id="comp-chart-trend" class="chart-sm"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Missing Data by Severity (by Columns)</div>
        <div style="display:flex;gap:12px;align-items:center">
          <div id="comp-chart-donut" style="min-width:180px;min-height:180px"></div>
          <table style="flex:1"><thead><tr><th>Severity</th><th>Columns</th><th>%</th></tr></thead><tbody>
            ${{sevLabels.map(s=>`<tr><td>${{badge(s)}}</td><td>${{fmtN(sevCounts[s]||0)}}</td><td>${{pct((sevCounts[s]||0)/(comp.columns_analyzed||1)*100)}}</td></tr>`).join('')}}
            <tr><td style="font-size:10px;color:var(--text-muted)">0% Missing</td><td>${{fmtN(comp.zero_missing_columns||0)}}</td><td>—</td></tr>
          </tbody></table>
        </div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">Missing % by Variable (Top 20) — ${{qLabel(CQ)}}</div>
      <div style="overflow-x:auto"><table>
        <thead><tr><th>Variable</th><th>Missing %</th><th>Severity</th><th>Missing Records</th></tr></thead>
        <tbody>${{compRows}}</tbody>
      </table></div>
    </div>

    <div class="grid-3">
      <div class="section-card">
        <div class="section-title">By Business Segment</div>
        <table><thead><tr><th>Segment</th><th>Completeness</th><th>%</th><th>Missing %</th></tr></thead>
        <tbody>${{segRows}}</tbody></table>
      </div>
      <div class="section-card">
        <div class="section-title">By Data Type</div>
        <table><thead><tr><th>Type</th><th>Completeness %</th><th>Missing %</th></tr></thead>
        <tbody>${{typeRows}}</tbody></table>
      </div>
      <div class="section-card">
        <div class="section-title">By Source System</div>
        <table><thead><tr><th>Source</th><th>Completeness</th><th>%</th><th>Missing %</th></tr></thead>
        <tbody>${{srcRows}}</tbody></table>
      </div>
    </div>
  `;

  Plotly.react('comp-chart-trend', _cmpTraces('completeness_over_time','value'),
    {{..._cmpLayout('%',160), yaxis:{{range:[90,101],gridcolor:'#f1f5f9',tickfont:{{size:9}},title:'%'}}}}, _cmpCfg);

  Plotly.newPlot('comp-chart-donut',[{{
    type:'pie',values:sevLabels.map(s=>sevCounts[s]||0),labels:sevLabels,hole:0.6,
    marker:{{colors:sevColors}},textinfo:'none',
    hovertemplate:'%{{label}}: %{{value}}<extra></extra>',
  }}],{{margin:{{t:5,r:5,b:5,l:5}},height:180,
    paper_bgcolor:'rgba(0,0,0,0)',showlegend:false}},{{responsive:true,displayModeBar:false}});
}}
"""
