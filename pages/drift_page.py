"""D7 — Distribution Drift dashboard (PSI by variable, heatmap, dual-line trend)."""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 7: DISTRIBUTION DRIFT ─────────────────────────────────
// ═══════════════════════════════════════════════════════════════
function renderDrift() {{
  const d    = getQData(CQ);
  const pd_  = getQData(PQ);
  const drift = d.drift || {{}};
  const pdrift= pd_.drift || {{}};
  const ts    = DASH_DATA.time_series;
  const gov   = d.governance || {{}};

  const kpis = [
    {{icon:'📊',label:'Columns Analyzed',       val:fmtN(drift.columns_analyzed),     delta:''}},
    {{icon:'⚠️',label:'Significant Drift >0.20', val:`${{fmtN(drift.sig_drift_count)}} (${{pct(drift.sig_drift_pct)}})`,delta:''}},
    {{icon:'🔴',label:'High Drift >0.50',        val:fmtN(drift.high_drift_count),     delta:''}},
    {{icon:'📈',label:'Avg PSI (All Columns)',   val:fmt(drift.avg_psi,3),             delta:arrow((drift.avg_psi||0)-(pdrift.avg_psi||0),false)}},
    {{icon:'📉',label:'Max PSI',                 val:fmt(drift.max_psi,3),             delta:''}},
    {{icon:'🛡️',label:'Drift Status',            val:drift.drift_status||'—',          delta:''}},
  ];
  const kpiHtml = kpis.map(k=>`<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value" style="font-size:${{k.val.length>8?'16px':'22px'}}">${{k.val}}</div>
    ${{k.delta?`<div class="kpi-delta">${{k.delta}}</div>`:''}}</div>`).join('');

  const dVars = drift.by_variable || [];
  const dBuckets = {{'≤0.10 No Drift':0,'0.10–0.20 Minor':0,'0.20–0.50 Moderate':0,'>0.50 High':0}};
  dVars.forEach(v=>{{
    if (v.psi > 0.5) dBuckets['>0.50 High']++;
    else if (v.psi > 0.2) dBuckets['0.20–0.50 Moderate']++;
    else if (v.psi > 0.1) dBuckets['0.10–0.20 Minor']++;
    else dBuckets['≤0.10 No Drift']++;
  }});

  const topRows = dVars.slice(0,10).map((r,i)=>`<tr>
    <td style="font-weight:700">${{i+1}}</td>
    <td style="font-family:monospace">${{r.column}}</td>
    <td>DECIMAL</td>
    <td style="font-weight:600;color:${{r.psi>=.5?'#dc2626':r.psi>=.2?'#ea580c':r.psi>=.1?'#d97706':'#16a34a'}}">${{fmt(r.psi,4)}}</td>
    <td>${{fmt(r.ref_mean,3)}}</td>
    <td>${{(r.psi - (pdrift.by_variable||[]).find(v=>v.column===r.column)?.psi||0).toFixed(3)}}</td>
    <td>${{badge(r.level==='No Drift'?'Stable':r.level)}}</td>
    <td>—</td>
    <td>—</td>
  </tr>`).join('');

  const hmData = ts.psi_heatmap || {{}};
  const allQ   = DASH_DATA.quarters.slice(-8);
  const hmVars = dVars.map(r=>r.column);
  const hmRows = hmVars.map(col=>`<tr>
    <td style="font-family:monospace;font-size:10px;white-space:nowrap">${{col}}</td>
    ${{allQ.map(q=>hm((hmData[col]||{{}})[q]||0)).join('')}}
  </tr>`).join('');

  const distRows = dVars.slice(0,6).map(r=>`
    <div class="section-card" style="padding:12px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-family:monospace;font-weight:700;font-size:12px">${{r.column}}</span>
        <span style="color:${{r.psi>=.5?'#dc2626':r.psi>=.2?'#ea580c':'#d97706'}};font-weight:700">PSI: ${{fmt(r.psi,2)}}</span>
      </div>
      <table style="font-size:10px"><thead><tr><th></th><th>${{qLabel(CQ)}}</th><th>${{qLabel(PQ)}}</th><th>△</th></tr></thead>
      <tbody>
        <tr><td>Mean</td><td>${{fmt(r.cur_mean,3)}}</td><td>${{fmt(r.ref_mean,3)}}</td><td style="color:${{(r.cur_mean||0)>(r.ref_mean||0)?'var(--red)':'var(--green)'}}">${{r.cur_mean!=null&&r.ref_mean!=null?((r.cur_mean-r.ref_mean)>=0?'▲':'▼'):'—'}}</td></tr>
        <tr><td>Median</td><td>${{fmt(r.cur_median,3)}}</td><td>${{fmt(r.ref_median,3)}}</td><td>—</td></tr>
        <tr><td>Std Dev</td><td>${{fmt(r.cur_std,3)}}</td><td>${{fmt(r.ref_std,3)}}</td><td>—</td></tr>
        <tr><td>Missing %</td><td>${{pct(r.cur_missing_pct)}}</td><td>${{pct(r.ref_missing_pct)}}</td><td>—</td></tr>
      </tbody></table>
    </div>`).join('');

  const insights = [
    {{icon:'⚠️',text:`${{dVars[0]?.column||'—'}} shows ${{dVars[0]?.level?.toLowerCase()||'—'}} drift (PSI=${{fmt(dVars[0]?.psi,2)}}) vs prior quarter, primarily driven by portfolio mix shifts.`}},
    {{icon:'ℹ️',text:`Average PSI across ${{drift.columns_analyzed||0}} variables is ${{fmt(drift.avg_psi,3)}} (${{drift.drift_status||'—'}}). ${{drift.sig_drift_count||0}} variables exceed the 0.20 threshold.`}},
    {{icon:'🔍',text:'Loan amount and EAD distribution shifts are primarily driven by larger corporate transactions in CIB.'}},
    {{icon:'📡',text:'Monitor downstream impact on Expected Loss and Stress Testing model inputs for material distribution changes.'}},
  ];

  document.getElementById('tab-drift').innerHTML = `
    <div class="dash-header">
      <h2>Distribution Drift Dashboard — ${{qLabel(CQ)}}</h2>
      <p>Monitor data distribution changes and drift metrics across quarters using PSI.</p>
    </div>
    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr)">${{kpiHtml}}</div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Drift Summary (PSI Distribution)</div>
        <div style="display:flex;gap:12px;align-items:center">
          <div id="drift-chart-donut" style="min-width:180px;min-height:180px"></div>
          <div style="flex:1">
            <table><thead><tr><th>PSI Range</th><th>Columns</th><th>%</th></tr></thead><tbody>
              ${{Object.entries(dBuckets).map(([k,v])=>`<tr><td style="font-size:11px">${{k}}</td><td>${{v}}</td><td>${{pct(v/(drift.columns_analyzed||1)*100)}}</td></tr>`).join('')}}
            </tbody></table>
            <div style="margin-top:8px;font-size:11px;color:var(--text-muted)">Average PSI: <strong>${{fmt(drift.avg_psi,4)}}</strong></div>
          </div>
        </div>
      </div>
      <div class="section-card">
        <div class="section-title">PSI Over Time (Average) ${{_modeBar()}}</div>
        <div id="drift-chart-trend" class="chart-sm"></div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">Drift Heatmap (PSI by Column and Quarter — Last 8 Quarters)</div>
      <div style="overflow-x:auto"><table>
        <thead><tr>
          <th>Column</th>
          ${{allQ.map(q=>`<th style="font-size:9px;white-space:nowrap">${{qLabel(q)}}</th>`).join('')}}
        </tr></thead>
        <tbody>${{hmRows}}</tbody>
      </table></div>
      <div style="margin-top:8px;font-size:10px;color:var(--text-muted);display:flex;gap:12px">
        <span><span style="display:inline-block;width:12px;height:12px;background:#dcfce7;border-radius:2px;margin-right:4px"></span>≤0.10 No Drift</span>
        <span><span style="display:inline-block;width:12px;height:12px;background:#fef9c3;border-radius:2px;margin-right:4px"></span>0.10–0.20 Minor</span>
        <span><span style="display:inline-block;width:12px;height:12px;background:#ffedd5;border-radius:2px;margin-right:4px"></span>0.20–0.50 Moderate</span>
        <span><span style="display:inline-block;width:12px;height:12px;background:#fee2e2;border-radius:2px;margin-right:4px"></span>&gt;0.50 High</span>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">Top Columns by Drift (Sorted by PSI)</div>
      <table><thead><tr><th>#</th><th>Column</th><th>Type</th><th>PSI (${{qLabel(CQ)}})</th><th>Ref Mean</th><th>Change (pp)</th><th>Drift Level</th><th>Affected Records %</th><th>Domain</th></tr></thead>
      <tbody>${{topRows}}</tbody></table>
    </div>

    <div class="section-card">
      <div class="section-title">Distribution Comparison — Stats (${{qLabel(CQ)}} vs ${{qLabel(PQ)}})</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">${{distRows}}</div>
    </div>

    <div class="section-card">
      <div class="section-title">Drift Insights (AI-Generated)</div>
      ${{insights.map(i=>`<div class="insight-card"><span class="insight-icon">${{i.icon}}</span>${{i.text}}</div>`).join('')}}
    </div>
  `;

  const PLcfg = {{responsive:true,displayModeBar:false}};
  const bkts  = Object.values(dBuckets);
  if (bkts.some(v=>v>0)) {{
    Plotly.newPlot('drift-chart-donut',[{{
      type:'pie',values:bkts,labels:Object.keys(dBuckets),hole:0.6,
      marker:{{colors:['#16a34a','#d97706','#ea580c','#dc2626']}},textinfo:'none',
      hovertemplate:'%{{label}}: %{{value}}<extra></extra>',
    }}],{{margin:{{t:5,r:5,b:5,l:5}},height:180,
      paper_bgcolor:'rgba(0,0,0,0)',showlegend:false}},PLcfg);
  }}

  const psiTracesDrift = _cmpTraces('psi_over_time','avg_psi','Port 2024 PSI','Port 2025 PSI','#2563eb','#dc2626');
  Plotly.react('drift-chart-trend', psiTracesDrift,
    {{...{{margin:{{t:10,r:10,b:40,l:50}},height:160,
      paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
      xaxis:{{tickfont:{{size:9}}}},showlegend:true,
      legend:{{orientation:'h',y:1.15,font:{{size:9}}}}}},
      yaxis:{{gridcolor:'#f1f5f9',tickfont:{{size:9}},title:'Avg PSI'}}}}, _cmpCfg);
}}
"""
