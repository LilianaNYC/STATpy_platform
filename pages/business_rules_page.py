"""D5 — Business Rules dashboard (failures by rule, severity, segment, domain)."""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 5: BUSINESS RULES ─────────────────────────────────────
// ═══════════════════════════════════════════════════════════════
function renderRules() {{
  const d    = getQData(CQ);
  const pd_  = getQData(PQ);
  const rules = d.business_rules || {{}};
  const prul  = pd_.business_rules || {{}};
  const tech  = d.tech_dq || {{}};
  const recon = tech.reconciliation || {{}};
  const ts    = DASH_DATA.time_series;

  // ── Rule Execution KPIs ──
  const kpis = [
    {{icon:'📋',label:'Total Rules Executed', val:fmtN(rules.total_executed),  delta:''}},
    {{icon:'❌',label:'Rules Failed',          val:fmtN(rules.rules_failed),    delta:arrow(-(rules.rules_failed-(prul.rules_failed||0)),true)}},
    {{icon:'🚨',label:'Critical Failures',     val:fmtN(rules.critical_failures),delta:''}},
    {{icon:'🗄️',label:'Records Failed',        val:fmtN(rules.records_failed),  delta:''}},
    {{icon:'📉',label:'Failure Rate %',        val:pct(rules.failure_rate_pct,2),delta:''}},
    {{icon:'✅',label:'Rules Passed',          val:fmtN(rules.rules_passed),    delta:''}},
  ];
  const kpiHtml = kpis.map(k=>`<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value">${{k.val}}</div>
    ${{k.delta?`<div class="kpi-delta">${{k.delta}}</div>`:''}}</div>`).join('');

  // ── Data Anomaly Indicator KPIs (raw counts behind the cross-field rules) ──
  const anomalyKpis = [
    {{icon:'🖊️',label:'MANUAL Balance Source',  val:fmtN(tech.manual_count),              sub:'balance not from system'}},
    {{icon:'📉',label:'Negative ALLL',           val:fmtN(tech.alll_negative_count),       sub:'sign-convention errors (BR_011)'}},
    {{icon:'🚫',label:'RWA Excluded (Flag=N)',   val:fmtN(tech.rwa_exclusion_count),       sub:`${{fmtN(tech.rwa_inclusion_count)}} included`}},
    {{icon:'💰',label:'Capital Charge = 0',      val:fmtN(tech.capital_charge_zero_count), sub:'when RWA flag = Y (CF_002)'}},
  ];
  const anomalyKpiHtml = anomalyKpis.map(k=>`<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value">${{k.val}}</div>
    <div class="kpi-sub">${{k.sub}}</div></div>`).join('');

  const byRule = rules.by_rule || [];
  const sevMap = {{Critical:0,High:0,Medium:0,Low:0}};
  byRule.filter(r=>!r.passed).forEach(r=>{{sevMap[r.severity]=(sevMap[r.severity]||0)+r.failed_records}});

  const topRows = byRule.sort((a,b)=>b.failure_rate_pct-a.failure_rate_pct).slice(0,10).map((r,i)=>`<tr>
    <td style="font-weight:700">${{i+1}}</td>
    <td style="font-family:monospace">${{r.code}}</td>
    <td style="font-size:11px">${{r.description}}</td>
    <td>${{badge(r.severity)}}</td>
    <td style="font-weight:600;color:${{r.passed?'var(--green)':'var(--red)'}}">${{fmtN(r.failed_records)}}</td>
    <td style="color:${{r.passed?'var(--green)':'var(--red)'}}">${{pct(r.failure_rate_pct)}}</td>
    <td>${{badge(r.passed?'Resolved':'Open')}}</td>
  </tr>`).join('');

  const domRows = (rules.by_domain||[]).map(r=>`<tr>
    <td>${{r.domain}}</td>
    <td>${{fmtN(r.failed_records)}}</td>
    <td style="color:${{r.failure_rate_pct>1?'var(--red)':'var(--text)'}}">${{pct(r.failure_rate_pct)}}</td>
  </tr>`).join('');

  const segRows = (rules.by_segment||[]).sort((a,b)=>b.failure_rate_pct-a.failure_rate_pct).map(s=>`<tr>
    <td>${{s.segment}}</td>
    <td><div style="background:var(--gray-light);border-radius:4px;height:10px;width:100%;max-width:120px">
      <div style="background:var(--red);border-radius:4px;height:10px;width:${{Math.min(100,s.failure_rate_pct*10)}}%"></div></div></td>
    <td style="color:var(--red)">${{pct(s.failure_rate_pct)}}</td>
  </tr>`).join('');

  const critRows = (rules.recent_critical||[]).map(r=>`<tr>
    <td style="font-family:monospace">${{r.code}}</td>
    <td style="font-size:11px">${{r.description}}</td>
    <td>${{r.detected_on}}</td>
    <td>${{r.segment}}</td>
    <td>${{fmtN(r.affected_records)}}</td>
    <td>${{badge(r.status)}}</td>
    <td>${{r.assigned_to}}</td>
    <td>${{r.last_updated}}</td>
  </tr>`).join('');

  document.getElementById('tab-rules').innerHTML = `
    <div class="dash-header">
      <h2>Business Rules Dashboard — ${{qLabel(CQ)}}</h2>
      <p>Track business rule validation failures by rule, severity, business segment, and data domain.</p>
    </div>
    <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Rule Execution</div>
    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr);margin-bottom:14px">${{kpiHtml}}</div>

    <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Data Anomaly Indicators</div>
    <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:14px">${{anomalyKpiHtml}}</div>

    ${{_modeBar()}}

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Rule Failure Rate % Over Time</div>
        <div id="rules-chart-trend" class="chart-sm"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Failures by Severity (by Failed Records)</div>
        <div style="display:flex;gap:12px;align-items:center">
          <div id="rules-chart-donut" style="min-width:180px;min-height:180px"></div>
          <table style="flex:1"><thead><tr><th>Severity</th><th>Failed Records</th><th>%</th></tr></thead><tbody>
            ${{['Critical','High','Medium','Low'].map(s=>{{
              const tot=Object.values(sevMap).reduce((a,b)=>a+b,0)||1;
              return `<tr><td>${{badge(s)}}</td><td>${{fmtN(sevMap[s]||0)}}</td><td>${{pct((sevMap[s]||0)/tot*100)}}</td></tr>`;
            }}).join('')}}
          </tbody></table>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Top Failed Business Rules (Top 10)</div>
        ${{topRows?`<table><thead><tr><th>#</th><th>Code</th><th>Rule Description</th><th>Severity</th><th>Failed Records</th><th>Failure Rate %</th><th>Status</th></tr></thead><tbody>${{topRows}}</tbody></table>`:'<div style="color:var(--green);font-size:12px;padding:8px">✅ All rules passed</div>'}}
      </div>
      <div class="section-card">
        <div class="section-title">Failures by Business Segment</div>
        <table><thead><tr><th>Segment</th><th>Failure Rate</th><th>%</th></tr></thead>
        <tbody>${{segRows}}</tbody></table>
        <div style="margin-top:12px">
          <div class="section-title" style="margin-bottom:8px">Failures by Data Domain</div>
          <table><thead><tr><th>Domain</th><th>Failed Records</th><th>Failure Rate %</th></tr></thead>
          <tbody>${{domRows}}</tbody></table>
        </div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">Recent Critical Failures</div>
      ${{critRows ? `<table><thead><tr><th>Code</th><th>Rule</th><th>Detected On</th><th>Segment</th><th>Affected Records</th><th>Status</th><th>Assigned To</th><th>Last Updated</th></tr></thead><tbody>${{critRows}}</tbody></table>` : '<div style="color:var(--green);font-size:12px;padding:8px">✅ No critical failures this quarter</div>'}}
    </div>

    <div class="section-card">
      <div class="section-title">Balance Reconciliation Waterfall (USD Billions)</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">
        Source-system total → adjustments (timing, mapping, manual) → reported DQ total.
        Surfaces integrity issues in the balance figure that downstream metrics rely on.
      </div>
      <div id="rules-recon-waterfall" class="chart-box"></div>
    </div>
  `;

  const ruleTraces = _cmpTraces('failure_rate_over_time','failure_rate_pct','Port 2024','Port 2025','#2563eb','#dc2626');
  const a25fail = _cmpFilter(_cmpTS25('failure_rate_over_time'));
  ruleTraces.push({{ x:_cmpX(a25fail), y:a25fail.map(()=>1.0), name:'Target 1%',
    type:'scatter', mode:'lines', line:{{color:'#6b7280',width:1,dash:'dot'}} }});
  Plotly.react('rules-chart-trend', ruleTraces, _cmpLayout('%',160), _cmpCfg);

  const sevVals = ['Critical','High','Medium','Low'].map(s=>sevMap[s]||0);
  if (sevVals.some(v=>v>0)) {{
    Plotly.newPlot('rules-chart-donut',[{{
      type:'pie',values:sevVals,labels:['Critical','High','Medium','Low'],hole:0.6,
      marker:{{colors:['#dc2626','#ea580c','#d97706','#16a34a']}},textinfo:'none',
      hovertemplate:'%{{label}}: %{{value}}<extra></extra>',
    }}],{{margin:{{t:5,r:5,b:5,l:5}},height:180,
      paper_bgcolor:'rgba(0,0,0,0)',showlegend:false}},{{responsive:true,displayModeBar:false}});
  }}

  // Balance Reconciliation Waterfall
  if (Object.keys(recon).length) {{
    Plotly.newPlot('rules-recon-waterfall',[{{
      type:'waterfall',
      x:['Source System Total','Timing Diff','Mapping Diff','Adjustments','DQ Total'],
      y:[recon.source_total,recon.timing_diff,recon.mapping_diff,recon.adjustment,recon.dq_total],
      measure:['absolute','relative','relative','relative','total'],
      text:[fmtB(recon.source_total),fmtB(recon.timing_diff),fmtB(recon.mapping_diff),fmtB(recon.adjustment),fmtB(recon.dq_total)],
      textposition:'outside',
      connector:{{line:{{color:'#e5e7eb'}}}},
      increasing:{{marker:{{color:'#16a34a'}}}},
      decreasing:{{marker:{{color:'#dc2626'}}}},
      totals:{{marker:{{color:'#2563eb'}}}},
    }}],{{
      margin:{{t:10,r:40,b:60,l:40}},height:240,paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
      yaxis:{{title:'USD Billions',gridcolor:'#f1f5f9'}},showlegend:false
    }},{{responsive:true,displayModeBar:false}});
  }} else {{
    document.getElementById('rules-recon-waterfall').innerHTML='<div style="padding:16px;color:var(--gray);font-size:12px">Reconciliation data not available.</div>';
  }}
}}
"""
