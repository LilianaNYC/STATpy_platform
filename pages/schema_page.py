"""D3 — Schema dashboard (column inventory, diff between port24/port25, quality trend)."""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 3: SCHEMA ────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════
function renderSchema() {{
  const d = getQData(CQ);
  const s = d.schema || {{}};
  const ts = DASH_DATA.time_series;
  const qoq = d.qoq || {{}};

  const kpiHtml = [
    {{label:'Total Columns',    val:fmtN(s.total_columns),                   delta:arrow(qoq.total_records_delta,true)}},
    {{label:'New Columns',      val:fmtN((s.added_vs_prior||[]).length),     delta:''}},
    {{label:'Dropped Columns',  val:fmtN((s.dropped_vs_prior||[]).length),   delta:''}},
    {{label:'Modified Columns', val:fmtN(s.modified_columns),                delta:''}},
    {{label:'Breaking Changes', val:fmtN(s.breaking_changes),                delta:''}},
    {{label:'Quality Score',    val:pct(s.quality_score),                    delta:arrow(qoq.schema_quality_delta,true)}},
  ].map(k=>`<div class="kpi-card">
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value">${{k.val}}</div>
    ${{k.delta?`<div class="kpi-delta">${{k.delta}}</div>`:''}}</div>`).join('');

  const typeDist = s.types_distribution || [];
  const typeRows = typeDist.map(t=>`<tr><td>${{t.type}}</td><td>${{fmtN(t.count)}}</td><td>${{pct(t.pct)}}</td></tr>`).join('');

  document.getElementById('tab-schema').innerHTML = `
    <div class="dash-header">
      <h2>Data Schema Dashboard — ${{qLabel(CQ)}}</h2>
      <p>Monitor schema structure, detect changes, and assess their data quality impact.</p>
    </div>
    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr)">${{kpiHtml}}</div>
    ${{_modeBar()}}

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Port 2024 vs Port 2025 — Column Diff</div>
        <div id="schema-diff-panel"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Schema Quality Score Trend</div>
        <div id="schema-chart-quality" class="chart-sm"></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Data Types Distribution</div>
        <div id="schema-chart-types" style="min-height:200px"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Data Types Summary</div>
        <table><thead><tr><th>Type</th><th>Columns</th><th>%</th></tr></thead>
        <tbody>${{typeRows}}</tbody></table>
        <div style="margin-top:12px;font-size:11px;color:var(--text-muted)">
          <div>🔑 Key columns: ${{fmtN(s.expected_columns)}} defined in schema</div>
          <div>📊 Tables: 1 (fact_portfolio)</div>
          <div>❓ Nullable columns: see completeness dashboard</div>
        </div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">Schema Validation Results — ${{qLabel(CQ)}}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--text-muted);margin-bottom:6px">Missing Columns (${{(s.missing_columns||[]).length}})</div>
          ${{(s.missing_columns||[]).length ? (s.missing_columns||[]).map(c=>`<div class="badge badge-red" style="margin:2px;font-size:10px">${{c}}</div>`).join('') : '<span style="color:var(--green);font-size:12px">✅ None</span>'}}
        </div>
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--text-muted);margin-bottom:6px">New Columns vs Schema (${{(s.new_columns||[]).length}})</div>
          ${{(s.new_columns||[]).length ? (s.new_columns||[]).map(c=>`<div class="badge badge-amber" style="margin:2px;font-size:10px">${{c}}</div>`).join('') : '<span style="color:var(--green);font-size:12px">✅ None</span>'}}
        </div>
      </div>
    </div>
  `;

  // Port 2024 vs Port 2025 column diff panel
  const sd = DASH_DATA.schema_diff || {{}};
  const sdAdded   = sd.added   || [];
  const sdRemoved = sd.removed || [];
  const sdTypes   = sd.type_changes || [];
  const sdNet     = sd.net_change || 0;
  const sdNetStr  = sdNet > 0 ? `+${{sdNet}}` : String(sdNet);
  const sdNetColor= sdNet > 0 ? '#16a34a' : sdNet < 0 ? '#dc2626' : '#64748b';

  function _tagList(items, color) {{
    if (!items.length) return '<span style="color:#94a3b8;font-size:11px">None</span>';
    return items.map(c=>`<span style="display:inline-block;background:${{color}}18;color:${{color}};border:1px solid ${{color}}44;border-radius:4px;padding:1px 6px;font-family:monospace;font-size:10px;margin:2px">${{c}}</span>`).join('');
  }}

  document.getElementById('schema-diff-panel').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">
      <div style="text-align:center;padding:8px;background:#f0fdf4;border-radius:6px">
        <div style="font-size:18px;font-weight:700;color:#16a34a">${{sd.port25_columns||'—'}}</div>
        <div style="font-size:10px;color:#64748b">Port 2025 columns</div>
      </div>
      <div style="text-align:center;padding:8px;background:#f0f9ff;border-radius:6px">
        <div style="font-size:18px;font-weight:700;color:#2563eb">${{sd.port24_columns||'—'}}</div>
        <div style="font-size:10px;color:#64748b">Port 2024 columns</div>
      </div>
      <div style="text-align:center;padding:8px;background:#f8fafc;border-radius:6px">
        <div style="font-size:18px;font-weight:700;color:${{sdNetColor}}">${{sdNetStr}}</div>
        <div style="font-size:10px;color:#64748b">Net column change</div>
      </div>
    </div>
    <div style="margin-bottom:8px">
      <div style="font-size:11px;font-weight:700;color:#16a34a;margin-bottom:4px">✚ Added in Port 2025 (${{sdAdded.length}})</div>
      <div>${{_tagList(sdAdded,'#16a34a')}}</div>
    </div>
    <div style="margin-bottom:8px">
      <div style="font-size:11px;font-weight:700;color:#dc2626;margin-bottom:4px">✖ Removed from Port 2024 (${{sdRemoved.length}})</div>
      <div>${{_tagList(sdRemoved,'#dc2626')}}</div>
    </div>
    <div>
      <div style="font-size:11px;font-weight:700;color:#d97706;margin-bottom:4px">⚠ Type Changes (${{sdTypes.length}})</div>
      ${{sdTypes.length
        ? `<table style="font-size:10px"><thead><tr><th>Column</th><th>Port 2024</th><th>Port 2025</th></tr></thead><tbody>
            ${{sdTypes.map(t=>`<tr><td style="font-family:monospace">${{t.column}}</td><td>${{t.port24_type}}</td><td>${{t.port25_type}}</td></tr>`).join('')}}
          </tbody></table>`
        : '<span style="color:#94a3b8;font-size:11px">No type changes detected</span>'
      }}
    </div>
  `;

  // Local helpers required by the quality-score trend chart
  const _schTotal = r => (r.new_columns||[]).length + (r.dropped_columns||[]).length + (r.modified_columns||0) + (r.breaking_changes||0);
  const sch25 = _cmpFilter(_cmpTS25('schema_changes_over_time'));
  const sch24 = _cmpFilter(_cmpTS24('schema_changes_over_time'));

  // Quality score trend — dual line
  const _qualScore = r => Math.max(80, 100 - _schTotal(r)*5);
  Plotly.newPlot('schema-chart-quality',
    (() => {{
      const t = [];
      if (CMP_MODE !== 'qoq' && sch24.length) t.push({{ x:_cmpX(sch24), y:sch24.map(_qualScore), name:'Port 2024', mode:'lines+markers', line:{{color:'#2563eb',width:2}}, marker:{{size:3}} }});
      t.push({{ x:_cmpX(sch25), y:sch25.map(_qualScore), name:'Port 2025', mode:'lines+markers', line:{{color:'#16a34a',width:2}}, marker:{{size:3}} }});
      return t;
    }})(),
    {{ margin:{{t:10,r:10,b:50,l:50}}, height:160,
      paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
      yaxis:{{range:[75,102],gridcolor:'#f1f5f9',tickfont:{{size:9}},title:'Score'}},
      xaxis:{{tickfont:{{size:9}},tickangle:-45}},
      legend:{{orientation:'h',y:1.18,font:{{size:9}}}},
      showlegend: CMP_MODE !== 'qoq',
    }}, _cmpCfg);

  if (typeDist.length) {{
    Plotly.newPlot('schema-chart-types',[{{
      type:'pie',values:typeDist.map(t=>t.count),labels:typeDist.map(t=>t.type),hole:0.6,
      marker:{{colors:['#2563eb','#16a34a','#d97706','#7c3aed','#6b7280']}},
      textinfo:'percent',textfont:{{size:10}},
    }}],{{margin:{{t:10,r:10,b:10,l:10}},height:200,
      paper_bgcolor:'rgba(0,0,0,0)',legend:{{font:{{size:10}}}}}},{{responsive:true,displayModeBar:false}});
  }}
}}
"""
