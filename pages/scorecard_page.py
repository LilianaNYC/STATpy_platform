"""D8 — Port 2024 vs Port 2025 scorecard tab."""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// D8 — PORT 2024 vs PORT 2025 SCORECARD
// ═══════════════════════════════════════════════════════════════
function renderScorecard() {{
  const sc   = DASH_DATA.scorecard || {{}};
  const rows = Array.isArray(sc) ? sc : (sc.rows || []);
  const q24  = sc.quarter_24 || 'Q4 2024';
  const q25  = sc.quarter_25 || 'Q4 2025';

  function _ragN(r) {{ return (r||'').toLowerCase(); }}
  function ragBg(r)  {{ const n=_ragN(r); return n==='red'?'#fee2e2':n==='amber'?'#fef9c3':n==='green'?'#dcfce7':'#f8fafc'; }}
  function ragCol(r) {{ const n=_ragN(r); return n==='red'?'#991b1b':n==='amber'?'#92400e':n==='green'?'#166534':'#475569'; }}
  function ragLabel(r) {{ const n=_ragN(r); return n?n.charAt(0).toUpperCase()+n.slice(1):'—'; }}
  function ragBadge(r) {{
    if (!r||r==='GRAY'||r==='gray') return '<span style="color:#94a3b8">—</span>';
    return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;background:${{ragBg(r)}};color:${{ragCol(r)}}">${{ragLabel(r)}}</span>`;
  }}
  function scFmt(v) {{
    if (v===null||v===undefined) return '—';
    if (typeof v==='number') return Number.isInteger(v)?v.toLocaleString():v.toFixed(3);
    return String(v);
  }}
  function deltaColor(d, rag) {{
    const n = _ragN(rag);
    return n==='red'?'#dc2626':n==='amber'?'#d97706':n==='green'?'#16a34a':'inherit';
  }}

  const scRows = rows.map(r => `<tr style="background:${{ragBg(r.rag)}}">
    <td style="font-weight:600">${{r.metric}}</td>
    <td style="text-align:right">${{scFmt(r.v24)}}</td>
    <td style="text-align:right">${{scFmt(r.v25)}}</td>
    <td style="text-align:right;font-weight:600;color:${{deltaColor(r.delta,r.rag)}}">${{r.delta||'—'}}</td>
    <td style="text-align:center">${{ragBadge(r.rag)}}</td>
    <td style="font-size:11px;color:#64748b">${{r.red_flag||''}}</td>
  </tr>`).join('');

  const summaryGreen = rows.filter(r=>_ragN(r.rag)==='green').length;
  const summaryAmber = rows.filter(r=>_ragN(r.rag)==='amber').length;
  const summaryRed   = rows.filter(r=>_ragN(r.rag)==='red').length;

  document.getElementById('tab-scorecard').innerHTML = `
    <div class="dash-header">
      <h2>Portfolio Scorecard — ${{q24}} vs ${{q25}}</h2>
      <p>Side-by-side comparison of key DQ metrics across the 2024 and 2025 portfolios. RAG status highlights material changes.</p>
    </div>

    <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:16px">
      <div class="kpi-card">
        <div class="kpi-icon">🟢</div>
        <div class="kpi-label">Green</div>
        <div class="kpi-value" style="color:#166534">${{summaryGreen}}</div>
        <div class="kpi-sub">metrics improved / stable</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">🟡</div>
        <div class="kpi-label">Amber</div>
        <div class="kpi-value" style="color:#92400e">${{summaryAmber}}</div>
        <div class="kpi-sub">metrics need monitoring</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">🔴</div>
        <div class="kpi-label">Red</div>
        <div class="kpi-value" style="color:#991b1b">${{summaryRed}}</div>
        <div class="kpi-sub">metrics require action</div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">DQ Metric Comparison — ${{q24}} vs ${{q25}}</div>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th style="text-align:right">${{q24}}</th>
            <th style="text-align:right">${{q25}}</th>
            <th style="text-align:right">Change</th>
            <th style="text-align:center">RAG</th>
            <th>Alert Condition</th>
          </tr>
        </thead>
        <tbody>
          ${{scRows.length ? scRows : '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:24px">Scorecard data not available — run pipeline with both portfolio files</td></tr>'}}
        </tbody>
      </table>
    </div>

    <div class="section-card" style="margin-top:16px">
      <div class="section-title">RAG Status Distribution</div>
      <div id="scorecard-chart-rag" style="height:160px"></div>
    </div>
  `;

  Plotly.react('scorecard-chart-rag',[{{
    type:'bar', orientation:'h',
    y:['Green','Amber','Red'],
    x:[summaryGreen,summaryAmber,summaryRed],
    marker:{{color:['#16a34a','#d97706','#dc2626']}},
    text:[summaryGreen,summaryAmber,summaryRed],
    textposition:'outside',
  }}],{{margin:{{t:5,r:40,b:30,l:60}},height:160,
    paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{{gridcolor:'#f1f5f9',tickfont:{{size:9}}}},
    yaxis:{{tickfont:{{size:10}}}},showlegend:false}},
    {{responsive:true,displayModeBar:false}});
}}
"""
