"""D3 — Schema dashboard.

The portfolio is a single table with a fixed schema, so quarter-over-quarter
or year-over-year views don't apply here — the schema doesn't change within a
portfolio. This tab focuses entirely on comparing the two portfolio files
(Port 2024 vs Port 2025) against each other and against the schema definition.
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 3: SCHEMA (cross-portfolio comparison, no time dim) ──
// ═══════════════════════════════════════════════════════════════
function renderSchema() {{
  const d   = getQData(CQ);
  const s   = d.schema || {{}};
  const sd  = DASH_DATA.schema_diff || {{}};

  const v24 = sd.port24_vs_schema || {{}};
  const v25 = sd.port25_vs_schema || {{}};
  const roster = sd.key_var_roster || [];
  const hygiene = sd.naming_hygiene || [];

  // ── KPIs — entirely portfolio-to-portfolio + schema ──
  const kpis = [
    {{icon:'📐',label:'Schema cols (declared)',val:fmtN((v25.schema_cols)||(v24.schema_cols)||0), sub:'from schema file'}},
    {{icon:'🟢',label:'Port 2025 cols',         val:fmtN(sd.port25_columns),                       sub:`coverage ${{fmt((v25.coverage_pct)||0,1)}}%`}},
    {{icon:'🔵',label:'Port 2024 cols',         val:fmtN(sd.port24_columns),                       sub:`coverage ${{fmt((v24.coverage_pct)||0,1)}}%`}},
    {{icon:'✚',label:'Added in P25',           val:fmtN((sd.added||[]).length),                   sub:'present in P25 only'}},
    {{icon:'✖',label:'Removed from P24',       val:fmtN((sd.removed||[]).length),                 sub:'present in P24 only'}},
    {{icon:'⚠️',label:'P24 ↔ P25 Type Changes', val:fmtN((sd.type_changes||[]).length),           sub:'dtype mismatch across files'}},
  ];
  const kpiHtml = kpis.map(k=>`<div class="kpi-card">
    <div class="kpi-icon">${{k.icon}}</div>
    <div class="kpi-label">${{k.label}}</div>
    <div class="kpi-value">${{k.val}}</div>
    <div class="kpi-sub">${{k.sub}}</div></div>`).join('');

  // ── Column diff content (the P24 vs P25 panel as before) ──
  const sdAdded   = sd.added   || [];
  const sdRemoved = sd.removed || [];
  const sdTypes   = sd.type_changes || [];

  function _tagList(items, color) {{
    if (!items.length) return '<span style="color:#94a3b8;font-size:11px">None</span>';
    return items.map(c=>`<span style="display:inline-block;background:${{color}}18;color:${{color}};border:1px solid ${{color}}44;border-radius:4px;padding:1px 6px;font-family:monospace;font-size:10px;margin:2px">${{c}}</span>`).join('');
  }}

  // ── Per-portfolio schema-vs-data validation (side-by-side) ──
  function _portfolioCard(label, vs, color) {{
    const m = vs.missing_from_data || [];
    const e = vs.extra_in_data     || [];
    const t = vs.type_issues       || [];
    const cov = vs.coverage_pct || 0;
    return `
      <div style="border:1px solid var(--border);border-radius:8px;padding:12px;background:#fff">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${{color}}"></span>
          <strong style="font-size:13px;color:#111827">${{label}}</strong>
          <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">${{fmtN(vs.data_cols)}} cols • ${{fmt(cov,1)}}% schema coverage</span>
        </div>
        <div style="margin-bottom:8px">
          <div style="font-size:10px;font-weight:700;color:#dc2626;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Declared in schema, missing from data (${{m.length}})</div>
          ${{m.length ? `<div>${{_tagList(m,'#dc2626')}}</div>` : '<div style="font-size:11px;color:#16a34a">✅ all declared cols present</div>'}}
        </div>
        <div style="margin-bottom:8px">
          <div style="font-size:10px;font-weight:700;color:#d97706;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">In data but not declared in schema (${{e.length}})</div>
          ${{e.length ? `<div>${{_tagList(e,'#d97706')}}</div>` : '<div style="font-size:11px;color:#16a34a">✅ all data cols are declared</div>'}}
        </div>
        <div>
          <div style="font-size:10px;font-weight:700;color:#ea580c;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Type mismatch vs schema (${{t.length}})</div>
          ${{t.length
            ? `<table style="font-size:10px;width:100%"><thead><tr><th>Column</th><th>Expected</th><th>Actual</th></tr></thead><tbody>
                ${{t.slice(0,8).map(r=>`<tr><td style="font-family:monospace">${{r.column}}</td><td>${{r.expected}}</td><td>${{r.actual}}</td></tr>`).join('')}}
                ${{t.length > 8 ? `<tr><td colspan="3" style="font-style:italic;color:var(--text-muted)">+ ${{t.length-8}} more</td></tr>` : ''}}
              </tbody></table>`
            : '<div style="font-size:11px;color:#16a34a">✅ all types match the schema</div>'}}
        </div>
      </div>`;
  }}

  // ── Key Variables Roster ──
  const rosterRows = roster.map(r => {{
    const okBadge = (ok) => ok
      ? '<span style="display:inline-block;width:18px;height:18px;border-radius:50%;background:#dcfce7;color:#15803d;font-size:11px;text-align:center;line-height:18px;font-weight:700">✓</span>'
      : '<span style="display:inline-block;width:18px;height:18px;border-radius:50%;background:#fee2e2;color:#991b1b;font-size:11px;text-align:center;line-height:18px;font-weight:700">✖</span>';
    const status = (r.in_p24 && r.in_p25) ? 'In both' : (r.in_p25 ? 'P25 only' : (r.in_p24 ? 'P24 only' : 'Missing'));
    const statusColor = (r.in_p24 && r.in_p25) ? '#16a34a' : '#dc2626';
    return `<tr>
      <td style="font-family:monospace">${{r.column}}</td>
      <td style="text-align:center">${{okBadge(r.in_p24)}}</td>
      <td style="text-align:center">${{okBadge(r.in_p25)}}</td>
      <td><span style="font-size:11px;color:${{statusColor}};font-weight:600">${{status}}</span></td>
      <td style="font-size:10px;color:var(--text-muted)">${{r.data_type}}</td>
      <td style="font-size:10px;color:var(--text-muted)">${{r.usage}}</td>
    </tr>`;
  }}).join('');

  // ── Naming hygiene ──
  const hygieneRows = hygiene.map(h => `<tr>
    <td style="font-family:monospace">${{h.column}}</td>
    <td><span style="font-size:11px;color:#d97706">${{h.issue}}</span></td>
  </tr>`).join('');

  // ── Data Types Distribution (per portfolio snapshot) ──
  const typeDist = s.types_distribution || [];
  const typeRows = typeDist.map(t=>`<tr><td>${{t.type}}</td><td>${{fmtN(t.count)}}</td><td>${{pct(t.pct)}}</td></tr>`).join('');

  document.getElementById('tab-schema').innerHTML = `
    <div class="dash-header">
      <h2>Data Schema Dashboard</h2>
      <p>The portfolio is a single table whose structure is fixed by the schema file.
         The interesting comparison is <strong>Port 2024 vs Port 2025</strong> against each other and against the schema definition — quarter or year selectors do not apply here.</p>
    </div>

    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr);margin-bottom:16px">${{kpiHtml}}</div>

    <div class="section-card">
      <div class="section-title">Port 2024 vs Port 2025 — Column Diff</div>
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
          <div style="font-size:18px;font-weight:700;color:${{(sd.net_change||0)>0?'#16a34a':(sd.net_change||0)<0?'#dc2626':'#64748b'}}">${{(sd.net_change||0)>0?'+':''}}${{sd.net_change||0}}</div>
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
    </div>

    <div class="section-card">
      <div class="section-title">Schema-vs-Data Reconciliation — Each Portfolio</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:12px">
        Compares each portfolio file against the declared schema. Surfaces gaps (cols defined in schema but absent from data),
        extras (cols in data but not declared), and type mismatches.
      </div>
      <div class="grid-2">
        ${{_portfolioCard('Port 2024', v24, '#2563eb')}}
        ${{_portfolioCard('Port 2025', v25, '#16a34a')}}
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">🔑 Key Variables Roster</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">
        Columns flagged <code>key_variable=Y</code> in the schema. Must be present in both portfolios.
      </div>
      ${{roster.length ? `<table style="font-size:12px">
        <thead><tr><th>Column</th><th style="text-align:center">In P24</th><th style="text-align:center">In P25</th><th>Status</th><th>Data Type</th><th>Usage</th></tr></thead>
        <tbody>${{rosterRows}}</tbody>
      </table>` : '<div style="color:var(--gray);font-size:12px;padding:8px">No key variables flagged in the schema.</div>'}}
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Data Types Distribution — Port 2025</div>
        <div id="schema-chart-types" style="min-height:200px"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Data Types Summary</div>
        <table><thead><tr><th>Type</th><th>Columns</th><th>%</th></tr></thead>
        <tbody>${{typeRows}}</tbody></table>
        <div style="margin-top:12px;font-size:11px;color:var(--text-muted)">
          <div>📋 Schema declares ${{fmtN(s.expected_columns)}} columns total</div>
          <div>🔑 ${{fmtN(roster.length)}} flagged as key variables</div>
          <div>📊 Single fact table (no joins / dimensions)</div>
        </div>
      </div>
    </div>

    ${{hygiene.length ? `<div class="section-card">
      <div class="section-title">⚠️ Naming Hygiene Findings</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">
        Potential naming issues that can cause silent data joins to fail or duplicate columns.
      </div>
      <table style="font-size:12px">
        <thead><tr><th>Column(s)</th><th>Issue</th></tr></thead>
        <tbody>${{hygieneRows}}</tbody>
      </table>
    </div>` : ''}}
  `;

  // ── Chart ──
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
