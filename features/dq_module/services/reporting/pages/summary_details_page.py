"""D9 — Summary Details.

CCAR-style "Balance Check" view modelled directly on the user's Excel sheet.
Eight segmentation tables, one per dimension:

  Business Unit · Model 14A Line · Facility Type Description · SCR Code ·
  Blackrock Bus FCL · Committed Ind · Direct / Contingent · RWA Calc Flag

Each row shows: segment | records | latest year-end balance | prior
year-end balance | balance ratio (%). Period is fixed YoY (latest year-end
quarter vs prior year-end quarter) regardless of the global Comparison Mode
— this matches the CCAR shape literally and keeps the page focused on the
year-over-year balance check.

All data is precomputed server-side in processor.py → DASH_DATA.summary_segments.
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 9: SUMMARY DETAILS (CCAR-style balance breakdowns) ────
// ═══════════════════════════════════════════════════════════════

// Selected comparison pair. Default to the latest YE-vs-prior-YE pair
// (the same fixed pair the backend precomputes for summary_segments).
let SUMMARY_PRIOR_Q = null;
let SUMMARY_CURRENT_Q = null;
function setSummaryPriorQ(q) {{ SUMMARY_PRIOR_Q = q; renderTab('summary_details'); }}
function setSummaryCurrentQ(q) {{ SUMMARY_CURRENT_Q = q; renderTab('summary_details'); }}
function resetSummaryPeriod() {{
  const def = _summaryDefaultPair();
  SUMMARY_PRIOR_Q = def.prior;
  SUMMARY_CURRENT_Q = def.current;
  renderTab('summary_details');
}}

// Default YE/prior-YE pair, pulled from the precomputed payload so the
// JS doesn't have to re-derive the year boundaries.
function _summaryDefaultPair() {{
  const baseSegs = DASH_DATA.summary_segments || {{}};
  const first = Object.values(baseSegs)[0] || {{}};
  return {{prior: first.prior_q || '', current: first.current_q || ''}};
}}

// Resolve the segment payload for an arbitrary (prior, current) pair from the
// per-quarter aggregates — same shape as DASH_DATA.summary_segments.
function _segmentsForPair(priorQ, currentQ) {{
  const baseSegs = DASH_DATA.summary_segments || {{}};
  const byQ = DASH_DATA.summary_by_quarter || {{}};
  const prv = byQ[priorQ] || {{}};
  const cur = byQ[currentQ] || {{}};
  const out = {{}};
  for (const dimKey of Object.keys(baseSegs)) {{
    const base = baseSegs[dimKey];
    const prvSegs = (prv[dimKey] || {{}}).segments || {{}};
    const curSegs = (cur[dimKey] || {{}}).segments || {{}};
    const segSet = new Set([...Object.keys(prvSegs), ...Object.keys(curSegs)]);
    const rows = [...segSet].sort().map(s => {{
      const p = prvSegs[s] || {{count: 0, balance: 0}};
      const c = curSegs[s] || {{count: 0, balance: 0}};
      const ratio = Math.abs(p.balance) > 1e-9 ? (c.balance / p.balance * 100) : null;
      return {{
        segment: s,
        records: c.count,
        prior_records: p.count,
        record_change: c.count - p.count,
        current_balance: round2(c.balance),
        prior_balance: round2(p.balance),
        ratio_pct: ratio == null ? null : Math.round(ratio * 10) / 10,
      }};
    }});
    out[dimKey] = {{
      label: base.label,
      column: base.column,
      current_q: currentQ,
      prior_q: priorQ,
      rows,
    }};
  }}
  return out;
}}
function round2(v) {{ return Math.round((+v || 0) * 100) / 100; }}

// Re-run the anomaly detector client-side so it stays in sync with whatever
// pair the user picked. Mirrors callbacks/segment_breakdowns.detect_count_anomalies.
function _detectCountAnomaliesJS(segs, ratioThreshold, absMin) {{
  ratioThreshold = ratioThreshold || 2.0;
  absMin = absMin || 10;
  const alerts = [];
  for (const dimKey of Object.keys(segs)) {{
    const entry = segs[dimKey];
    for (const row of entry.rows) {{
      const p = +row.prior_records || 0;
      const c = +row.records || 0;
      const base = {{
        dim_key: dimKey, dim_label: entry.label, dim_column: entry.column,
        segment: row.segment, prior: p, current: c, change: c - p,
      }};
      if (p === 0 && c > 0) {{
        alerts.push({{...base, kind: 'appeared', severity: c >= absMin ? 'high' : 'low'}});
      }} else if (p > 0 && c === 0) {{
        alerts.push({{...base, kind: 'disappeared', severity: p >= absMin ? 'high' : 'low'}});
      }} else if (p > 0 && c > 0) {{
        const r = c / p;
        if (r >= ratioThreshold && (c - p) >= absMin) {{
          alerts.push({{...base, kind: 'drastic_growth', severity: 'high'}});
        }} else if (r <= 1.0/ratioThreshold && (p - c) >= absMin) {{
          alerts.push({{...base, kind: 'drastic_drop', severity: 'high'}});
        }}
      }}
    }}
  }}
  alerts.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
  return alerts;
}}

// ────────────────────────────────────────────────────────────────
// Period selector — two quarter dropdowns + reset to default pair
// ────────────────────────────────────────────────────────────────
function _periodSelector(priorQ, currentQ) {{
  const allQ = DASH_DATA.quarters || [];
  const optsHtml = (sel) => [...allQ].reverse()
    .map(q => `<option value="${{q}}"${{q===sel?' selected':''}}>${{qLabel(q)}}</option>`).join('');
  const def = _summaryDefaultPair();
  const isDefault = priorQ === def.prior && currentQ === def.current;
  return `<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:14px">
    <span style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em">Comparison Period</span>
    <div style="display:flex;align-items:center;gap:6px">
      <label style="font-size:11px;color:#64748b">Prior</label>
      <select onchange="setSummaryPriorQ(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;min-width:120px">${{optsHtml(priorQ)}}</select>
    </div>
    <span style="font-size:13px;color:#94a3b8">→</span>
    <div style="display:flex;align-items:center;gap:6px">
      <label style="font-size:11px;color:#64748b">Current</label>
      <select onchange="setSummaryCurrentQ(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;min-width:120px">${{optsHtml(currentQ)}}</select>
    </div>
    ${{!isDefault ? `<button onclick="resetSummaryPeriod()" style="font-size:10px;padding:4px 12px;border:1px solid #cbd5e1;background:#fff;color:#475569;border-radius:4px;cursor:pointer">↺ Reset to default YE pair</button>` : `<span style="font-size:10px;color:#64748b;font-style:italic">default year-end pair</span>`}}
    <span style="margin-left:auto;font-size:11px;color:#475569;font-family:monospace"><strong>${{qLabel(priorQ)}}</strong> → <strong>${{qLabel(currentQ)}}</strong></span>
  </div>`;
}}

function renderSummaryDetails() {{
  // Initialise the selected pair on first entry
  if (SUMMARY_PRIOR_Q == null || SUMMARY_CURRENT_Q == null) {{
    const def = _summaryDefaultPair();
    SUMMARY_PRIOR_Q = def.prior;
    SUMMARY_CURRENT_Q = def.current;
  }}

  // Compute segments + anomalies for the active pair
  const segs = _segmentsForPair(SUMMARY_PRIOR_Q, SUMMARY_CURRENT_Q);
  const dims = Object.keys(segs);
  const curLabel = SUMMARY_CURRENT_Q ? qLabel(SUMMARY_CURRENT_Q) : '—';
  const prvLabel = SUMMARY_PRIOR_Q ? qLabel(SUMMARY_PRIOR_Q) : '—';
  const anomalies = _detectCountAnomaliesJS(segs);

  document.getElementById('tab-summary_details').innerHTML = `
    <div class="dash-header">
      <h2>Summary Details — Balance Check</h2>
      <p>Portfolio balance breakdown by each segmentation dimension. Current pair: <strong>${{prvLabel}}</strong> → <strong>${{curLabel}}</strong>. Pick any other pair from the selector below.</p>
    </div>

    ${{_periodSelector(SUMMARY_PRIOR_Q, SUMMARY_CURRENT_Q)}}

    <!-- Count anomaly alerts -->
    ${{_renderCountAnomalies(anomalies, curLabel, prvLabel)}}

    <!-- Portfolio totals strip -->
    ${{_renderSummaryTotals(segs, curLabel, prvLabel)}}

    <!-- One card per dimension -->
    <div class="grid-2" style="margin-top:14px">
      ${{dims.map(k => _renderSummaryCard(segs[k], curLabel, prvLabel)).join('')}}
    </div>
  `;
}}

// ────────────────────────────────────────────────────────────────
// Count anomaly alerts — flag segments with drastic record-count
// changes between the two periods. Renders a collapsible panel at
// the top when there's anything to report; renders nothing otherwise.
// ────────────────────────────────────────────────────────────────
function _renderCountAnomalies(anomalies, curLabel, prvLabel) {{
  if (!anomalies || !anomalies.length) {{
    return `<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 14px;margin-bottom:14px;display:flex;align-items:center;gap:10px">
      <span style="font-size:18px">✓</span>
      <div>
        <div style="font-size:12px;font-weight:700;color:#15803d">No drastic record-count swings detected</div>
        <div style="font-size:11px;color:#166534">All segments retain comparable record counts between ${{prvLabel}} and ${{curLabel}}. Thresholds: 2× ratio or ≥10 records appeared/disappeared.</div>
      </div>
    </div>`;
  }}

  const kindMeta = {{
    appeared:       {{icon:'🆕', tone:'#15803d', bg:'#dcfce7', border:'#bbf7d0', label:'Appeared'}},
    disappeared:    {{icon:'⬇️', tone:'#991b1b', bg:'#fee2e2', border:'#fecaca', label:'Disappeared'}},
    drastic_growth: {{icon:'📈', tone:'#15803d', bg:'#dcfce7', border:'#bbf7d0', label:'Drastic growth'}},
    drastic_drop:   {{icon:'📉', tone:'#991b1b', bg:'#fee2e2', border:'#fecaca', label:'Drastic drop'}},
  }};

  // Group by dimension so the panel reads "per dimension, here are the swings"
  const byDim = {{}};
  for (const a of anomalies) {{
    byDim[a.dim_key] = byDim[a.dim_key] || {{label: a.dim_label, column: a.dim_column, rows: []}};
    byDim[a.dim_key].rows.push(a);
  }}

  const dimBlocks = Object.entries(byDim).map(([k, group]) => {{
    const rowsHtml = group.rows.map(a => {{
      const meta = kindMeta[a.kind] || kindMeta.disappeared;
      const change = a.change;
      const sign = change > 0 ? '+' : '';
      const ratio = (a.prior > 0 && a.current > 0)
        ? `${{fmt((a.current / a.prior) * 100, 0)}}%`
        : (a.prior === 0 ? '∞' : '0');
      return `<div style="display:flex;align-items:center;gap:10px;padding:6px 10px;background:${{meta.bg}};border-left:3px solid ${{meta.tone}};border-radius:0 4px 4px 0">
        <span style="font-size:14px">${{meta.icon}}</span>
        <div style="flex:1;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
          <span style="font-family:monospace;font-weight:700;color:#0f172a">${{a.segment}}</span>
          <span style="font-size:11px;color:${{meta.tone}};font-weight:600">${{meta.label}}</span>
          <span style="font-size:11px;color:#475569;font-family:monospace">${{prvLabel}}: <strong>${{fmtN(a.prior)}}</strong> → ${{curLabel}}: <strong>${{fmtN(a.current)}}</strong></span>
        </div>
        <span style="font-size:11px;font-weight:700;color:${{meta.tone}};font-family:monospace">${{sign}}${{fmtN(change)}} · ratio ${{ratio}}</span>
      </div>`;
    }}).join('');
    return `<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px">
      <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:8px">
        <div style="font-size:12px;font-weight:700;color:#0f172a">${{group.label}}</div>
        <div style="font-size:10px;color:var(--text-muted);font-family:monospace">${{group.rows.length}} flagged · grouped by ${{group.column}}</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">${{rowsHtml}}</div>
    </div>`;
  }}).join('');

  const total = anomalies.length;
  return `<div style="background:#fffbeb;border:1px solid #fcd34d;border-left:4px solid #d97706;border-radius:8px;padding:14px 16px;margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
      <span style="font-size:20px">⚠</span>
      <div style="flex:1">
        <div style="font-size:13px;font-weight:700;color:#92400e">Record-count anomalies between ${{prvLabel}} and ${{curLabel}}</div>
        <div style="font-size:11px;color:#92400e;margin-top:2px">
          <strong>${{total}}</strong> segment${{total===1?'':'s'}} flagged. Thresholds: 2× ratio (≥10 records) or any segment that appeared / disappeared. Investigate before trusting the balances for those buckets.
        </div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr;gap:8px">${{dimBlocks}}</div>
  </div>`;
}}

// ────────────────────────────────────────────────────────────────
// Portfolio totals: read from the first dimension card (Business Unit
// usually) — sum of current balance and sum of prior balance across
// all segments give the overall portfolio total for each year-end.
// ────────────────────────────────────────────────────────────────
function _renderSummaryTotals(segs, curLabel, prvLabel) {{
  const keys = Object.keys(segs);
  if (!keys.length) return '';
  // Sum across rows of the first dim (any dim works; they partition the same data)
  const firstRows = (segs[keys[0]] || {{}}).rows || [];
  let curTotal = 0, prvTotal = 0, curCount = 0, prvCount = 0;
  for (const r of firstRows) {{
    curTotal += +(r.current_balance || 0);
    prvTotal += +(r.prior_balance || 0);
    curCount += +(r.records || 0);
    prvCount += +(r.prior_records || 0);
  }}
  const change = Math.abs(prvTotal) > 1e-9 ? ((curTotal - prvTotal) / prvTotal * 100) : null;
  const rColor = _changeColor(change);
  const cntChange = prvCount > 0 ? ((curCount - prvCount) / prvCount * 100) : null;
  const cntColor = _changeColor(cntChange);
  return `<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">
    <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid #2563eb;border-radius:8px;padding:14px">
      <div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">Count · ${{prvLabel}}</div>
      <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1;margin-top:6px">${{fmtN(prvCount)}}</div>
      <div style="font-size:10px;color:#64748b;margin-top:4px">facilities · prior year-end</div>
    </div>
    <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid ${{cntColor}};border-radius:8px;padding:14px">
      <div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">Count · ${{curLabel}}</div>
      <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1;margin-top:6px">${{fmtN(curCount)}}</div>
      <div style="font-size:10px;color:${{cntColor}};margin-top:4px">${{_fmtChange(cntChange)}} vs ${{prvLabel}}</div>
    </div>
    <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid #2563eb;border-radius:8px;padding:14px">
      <div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">Portfolio Balance · ${{prvLabel}}</div>
      <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1;margin-top:6px">${{_fmtBalance(prvTotal)}}</div>
      <div style="font-size:10px;color:#64748b;margin-top:4px">prior year-end reference</div>
    </div>
    <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid #16a34a;border-radius:8px;padding:14px">
      <div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">Portfolio Balance · ${{curLabel}}</div>
      <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1;margin-top:6px">${{_fmtBalance(curTotal)}}</div>
      <div style="font-size:10px;color:#64748b;margin-top:4px">sum of Balance column · current year-end</div>
    </div>
    <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid ${{rColor}};border-radius:8px;padding:14px">
      <div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em">Overall Balance Change</div>
      <div style="font-size:24px;font-weight:800;color:${{rColor}};line-height:1;margin-top:6px">${{_fmtChange(change)}}</div>
      <div style="font-size:10px;color:#64748b;margin-top:4px">portfolio-wide change vs ${{prvLabel}}</div>
    </div>
  </div>`;
}}

// ────────────────────────────────────────────────────────────────
// Per-dimension card: title, optional column note, balance-check
// table with a portfolio TOTAL row at the bottom.
// ────────────────────────────────────────────────────────────────
function _renderSummaryCard(entry, curLabel, prvLabel) {{
  const rows = entry.rows || [];
  if (!rows.length) {{
    return `<div class="section-card">
      <div class="section-title">${{entry.label}}</div>
      <div style="padding:24px;color:#94a3b8;font-size:12px;text-align:center">No segments for this dimension.</div>
    </div>`;
  }}

  let totC = 0, totP = 0, totRC = 0, totRP = 0;
  for (const r of rows) {{
    totC += +(r.current_balance || 0);
    totP += +(r.prior_balance || 0);
    totRC += +(r.records || 0);
    totRP += +(r.prior_records || 0);
  }}
  const totChange = Math.abs(totP) > 1e-9 ? ((totC - totP) / totP * 100) : null;
  const totCntChange = totRP > 0 ? ((totRC - totRP) / totRP * 100) : null;

  // Highlight rows that are themselves count anomalies (matches the alert
  // panel thresholds in segment_breakdowns.detect_count_anomalies)
  function _countCellColor(r) {{
    const p = +r.prior_records || 0, c = +r.records || 0;
    if (p === 0 && c >= 10)            return '#15803d';   // appeared
    if (c === 0 && p >= 10)            return '#991b1b';   // disappeared
    if (p > 0 && c > 0) {{
      const ratio = c / p;
      if (ratio >= 2.0 && (c - p) >= 10) return '#15803d';
      if (ratio <= 0.5 && (p - c) >= 10) return '#991b1b';
    }}
    return '#475569';
  }}

  const bodyRows = rows.map(r => {{
    const cntColor = _countCellColor(r);
    const isAnom = cntColor !== '#475569';
    const balChange = (r.ratio_pct != null) ? (r.ratio_pct - 100) : null;
    return `<tr${{isAnom ? ' style="background:#fffbeb"' : ''}}>
      <td style="font-weight:600;color:#0f172a">${{r.segment}}${{isAnom?' <span title="Flagged in the count-anomaly panel above" style="color:#d97706">⚠</span>':''}}</td>
      <td style="text-align:right;font-family:monospace;color:#475569">${{fmtN(r.prior_records || 0)}}</td>
      <td style="text-align:right;font-family:monospace;font-weight:${{isAnom?'700':'500'}};color:${{cntColor}}">${{fmtN(r.records || 0)}}</td>
      <td style="text-align:right;font-family:monospace;color:${{r.prior_balance<0?'#dc2626':'#475569'}}">${{_fmtBalance(r.prior_balance)}}</td>
      <td style="text-align:right;font-family:monospace;color:${{r.current_balance<0?'#dc2626':'#0f172a'}}">${{_fmtBalance(r.current_balance)}}</td>
      <td style="text-align:right;font-weight:600;color:${{_changeColor(balChange)}}">${{_fmtChange(balChange)}}</td>
    </tr>`;
  }}).join('');

  const totalRow = `<tr style="font-weight:700;background:#f8fafc;border-top:2px solid #0f1d35">
    <td style="color:#0f1d35">TOTAL</td>
    <td style="text-align:right;font-family:monospace">${{fmtN(totRP)}}</td>
    <td style="text-align:right;font-family:monospace">${{fmtN(totRC)}}${{totCntChange==null?'':` <span style="font-size:9px;font-weight:500;color:${{_changeColor(totCntChange)}}">${{_fmtChange(totCntChange)}}</span>`}}</td>
    <td style="text-align:right;font-family:monospace">${{_fmtBalance(totP)}}</td>
    <td style="text-align:right;font-family:monospace">${{_fmtBalance(totC)}}</td>
    <td style="text-align:right;color:${{_changeColor(totChange)}}">${{_fmtChange(totChange)}}</td>
  </tr>`;

  // Only the Balance Change % header keeps a tooltip — its formula is the
  // most likely to be unclear at a glance.
  const tipChange = `Balance Change % = (${{curLabel}} Balance − ${{prvLabel}} Balance) ÷ ${{prvLabel}} Balance × 100. Positive = the segment's balance grew; negative = it shrank. "—" when the prior balance is zero (no baseline to compare against).`;

  return `<div class="section-card">
    <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:10px">
      <div class="section-title" style="margin:0">${{entry.label}}</div>
    </div>
    <div style="overflow-x:auto"><table style="font-size:11px;width:100%;border-collapse:collapse">
      <thead>
        <tr>
          <th style="text-align:left;padding:6px 8px;background:#0f1d35;color:#fff;font-weight:700;border:1px solid #1e293b">${{entry.label}}</th>
          <th style="text-align:right;padding:6px 8px;background:#1e293b;color:#fff;font-weight:600;border:1px solid #1e293b">Count · ${{prvLabel}}</th>
          <th style="text-align:right;padding:6px 8px;background:#1e293b;color:#fff;font-weight:600;border:1px solid #1e293b">Count · ${{curLabel}}</th>
          <th style="text-align:right;padding:6px 8px;background:#1e293b;color:#fff;font-weight:600;border:1px solid #1e293b">${{prvLabel}}<br><span style="font-size:9px;font-weight:500;opacity:.7">Portfolio Balance</span></th>
          <th style="text-align:right;padding:6px 8px;background:#1e293b;color:#fff;font-weight:600;border:1px solid #1e293b">${{curLabel}}<br><span style="font-size:9px;font-weight:500;opacity:.7">Portfolio Balance</span></th>
          <th style="text-align:right;padding:6px 8px;background:#1e293b;color:#fff;font-weight:600;border:1px solid #1e293b">Balance Change % ${{_tooltip(tipChange)}}</th>
        </tr>
      </thead>
      <tbody>${{bodyRows}}${{totalRow}}</tbody>
    </table></div>
  </div>`;
}}

// Balance formatting — compact $ amount with full digits + sign for negatives
function _fmtBalance(v) {{
  if (v == null || !Number.isFinite(v)) return '—';
  if (Math.abs(v) < 1e-9) return '$0';
  const sign = v < 0 ? '-' : '';
  const abs = Math.abs(v);
  return `${{sign}}$${{fmtN(Math.round(abs))}}`;
}}

// Signed change formatter — always shows + or - sign with 1 decimal %.
function _fmtChange(change) {{
  if (change == null || !Number.isFinite(change)) return '—';
  const sign = change > 0 ? '+' : (change < 0 ? '-' : '');
  return `${{sign}}${{fmt(Math.abs(change), 1)}}%`;
}}

// Change-% color: stronger accents for large swings.
//   > +100 % strong green · > +10 % green · -10..+10 % gray ·
//   < -10 % red · < -50 % strong red
function _changeColor(change) {{
  if (change == null || !Number.isFinite(change)) return '#94a3b8';
  if (change > 100)  return '#15803d';
  if (change >= 10)  return '#16a34a';
  if (change <= -50) return '#7f1d1d';
  if (change <= -10) return '#dc2626';
  return '#475569';
}}

// Small "?" pill used in column headers; the native `title` attribute drives
// the hover tooltip with the explanation passed in. White on the dark navy
// header cells, so it stays readable.
function _tooltip(text) {{
  const safe = (text || '').replace(/"/g, '&quot;');
  return `<span title="${{safe}}" style="display:inline-flex;align-items:center;justify-content:center;width:13px;height:13px;border:1px solid currentColor;border-radius:50%;font-size:9px;font-weight:700;cursor:help;opacity:0.75;margin-left:4px;font-style:normal;line-height:1;vertical-align:middle">?</span>`;
}}
"""
