"""D2 — Business & Governance dashboard (exec summary, materiality, RCA, recs)."""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 2: GOVERNANCE ────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════
function renderGovernance() {{
  const d   = getQData(CQ);
  const gov = d.governance || {{}};
  const rating = gov.dq_rating || 'GREEN';
  const ratingClass = {{GREEN:'gov-green',MODERATE:'gov-moderate',RED:'gov-red'}}[rating]||'gov-green';

  const issues = gov.issues || [];
  const issueRows = issues.slice(0,10).map((iss,i)=>`<tr>
    <td>${{i+1}}</td>
    <td>${{iss.name}}</td>
    <td>${{badge(iss.severity)}}</td>
    <td>${{fmtN(iss.affected_records)}}</td>
    <td>${{pct(iss.affected_pct)}}</td>
    <td style="font-size:11px;color:var(--text-muted)">${{iss.use_cases}}</td>
  </tr>`).join('');

  const rcaRows = issues.slice(0,8).map(iss=>`<tr>
    <td>${{iss.name}}</td>
    <td style="font-size:11px;color:var(--text-muted)">${{iss.root_cause}}</td>
  </tr>`).join('');

  const impactRows = issues.slice(0,8).map(iss=>`<tr>
    <td>${{iss.name}}</td>
    <td>${{badge(iss.severity)}}</td>
    <td style="font-size:11px;color:var(--text-muted)">${{iss.impact}}</td>
  </tr>`).join('');

  const trackerRows = issues.slice(0,8).map(iss=>`<tr>
    <td>${{iss.name}}</td>
    <td>${{iss.owner}}</td>
    <td>${{badge(iss.status)}}</td>
    <td>${{iss.opened_date}}</td>
    <td>${{iss.target_date}}</td>
    <td>0</td>
  </tr>`).join('');

  const recRows = (gov.recommendations||[]).map(r=>`<tr>
    <td style="font-size:12px">${{r.text}}</td>
    <td>${{badge(r.priority)}}</td>
    <td>${{r.owner}}</td>
    <td>${{r.eta}}</td>
  </tr>`).join('');

  // Materiality grid — bucket issues into 3×3 cells
  const sevColor = {{Critical:'#dc2626',High:'#ea580c',Medium:'#d97706',Low:'#16a34a'}};
  const cellBg = [
    ['#fef9c3','#fef08a','#fde047'],
    ['#fef08a','#fde047','#fdba74'],
    ['#fde047','#fdba74','#fca5a5'],
  ];
  const cellMap = {{}};
  issues.forEach((iss,i)=>{{
    const xMap={{Low:0,Medium:1,High:2}};
    const yMap={{Low:0,Medium:1,High:2}};
    const col = xMap[iss.likelihood]??1;
    const row = yMap[iss.business_impact]??1;
    const key = `${{row}},${{col}}`;
    if(!cellMap[key]) cellMap[key]=[];
    cellMap[key].push({{idx:i+1,sev:iss.severity}});
  }});

  function _matCell(row,col) {{
    const items = (cellMap[`${{row}},${{col}}`]||[]);
    const bg = cellBg[row][col];
    const badges = items.map(it=>
      `<span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:${{sevColor[it.sev]||'#6b7280'}};color:#fff;font-size:10px;font-weight:700;margin:2px">${{it.idx}}</span>`
    ).join('');
    return `<td style="background:${{bg}};vertical-align:middle;text-align:center;padding:8px;border:1px solid #e2e8f0;min-width:80px;min-height:60px">${{badges||''}}</td>`;
  }}

  const matGrid = `
    <div style="display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap">
      <div style="flex:0 0 auto">
        <table style="border-collapse:collapse;font-size:11px">
          <thead>
            <tr>
              <td style="padding:4px 8px;font-weight:700;color:var(--text-muted);font-size:10px;text-align:center;writing-mode:vertical-rl;text-orientation:mixed;transform:rotate(180deg);height:60px" rowspan="4">Business Impact</td>
              <th style="padding:4px 8px;font-weight:700;color:var(--text-muted);border:1px solid #e2e8f0;text-align:center">High</th>
              ${{_matCell(2,0)}}${{_matCell(2,1)}}${{_matCell(2,2)}}
            </tr>
            <tr>
              <th style="padding:4px 8px;font-weight:700;color:var(--text-muted);border:1px solid #e2e8f0;text-align:center">Med</th>
              ${{_matCell(1,0)}}${{_matCell(1,1)}}${{_matCell(1,2)}}
            </tr>
            <tr>
              <th style="padding:4px 8px;font-weight:700;color:var(--text-muted);border:1px solid #e2e8f0;text-align:center">Low</th>
              ${{_matCell(0,0)}}${{_matCell(0,1)}}${{_matCell(0,2)}}
            </tr>
            <tr>
              <td style="border:none"></td>
              <th style="padding:4px 8px;color:var(--text-muted);font-size:10px;text-align:center;border-top:2px solid #cbd5e1">Low</th>
              <th style="padding:4px 8px;color:var(--text-muted);font-size:10px;text-align:center;border-top:2px solid #cbd5e1">Medium</th>
              <th style="padding:4px 8px;color:var(--text-muted);font-size:10px;text-align:center;border-top:2px solid #cbd5e1">High</th>
            </tr>
            <tr>
              <td colspan="4" style="text-align:center;color:var(--text-muted);font-size:10px;padding-top:2px;font-weight:700;letter-spacing:.05em">LIKELIHOOD</td>
            </tr>
          </thead>
        </table>
      </div>
      <div style="flex:1;min-width:180px">
        <table style="font-size:11px;width:100%">
          <thead><tr><th style="width:24px">#</th><th>Issue</th><th>Sev</th></tr></thead>
          <tbody>
            ${{issues.slice(0,10).map((iss,i)=>`<tr>
              <td><span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:${{sevColor[iss.severity]||'#6b7280'}};color:#fff;font-size:9px;font-weight:700">${{i+1}}</span></td>
              <td style="padding:3px 6px;font-size:10px">${{iss.name}}</td>
              <td>${{badge(iss.severity)}}</td>
            </tr>`).join('')}}
          </tbody>
        </table>
      </div>
    </div>`;

  document.getElementById('tab-governance').innerHTML = `
    <div class="dash-header">
      <h2>Business &amp; Governance Dashboard — ${{qLabel(CQ)}}</h2>
      <p>AI-powered interpretation for risk managers, model owners, and senior stakeholders.</p>
    </div>

    <div class="section-card">
      <div style="display:flex;align-items:flex-start;gap:16px">
        <div style="flex:1">
          <div class="section-title">Executive Summary (AI-Generated)</div>
          <div class="summary-text">${{gov.exec_summary||'—'}}</div>
        </div>
        <div style="text-align:center;padding:16px;background:var(--gray-light);border-radius:10px;min-width:120px">
          <div style="font-size:10px;color:var(--text-muted);font-weight:700;text-transform:uppercase;margin-bottom:8px">DQ Rating</div>
          <div class="gov-badge ${{ratingClass}}">${{rating==='GREEN'?'✅':rating==='MODERATE'?'⚠️':'🚨'}} ${{rating}}</div>
          <div style="font-size:10px;color:var(--text-muted);margin-top:8px">vs prior quarter</div>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Top Data Quality Issues (by Severity)</div>
        ${{issues.length?`<table><thead><tr><th>#</th><th>Issue</th><th>Severity</th><th>Affected Records</th><th>%</th><th>Use Cases</th></tr></thead><tbody>${{issueRows}}</tbody></table>`:'<div style="color:var(--green);font-size:12px;padding:8px">✅ No significant issues this quarter</div>'}}
      </div>
      <div class="section-card">
        <div class="section-title">Materiality Heat Map</div>
        ${{matGrid}}
      </div>
    </div>

    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Root Cause Analysis (AI-Assisted)</div>
        ${{issues.length?`<table><thead><tr><th>Issue</th><th>Likely Root Cause</th></tr></thead><tbody>${{rcaRows}}</tbody></table>`:'<div style="color:var(--gray);font-size:12px;padding:8px">No issues to analyze.</div>'}}
      </div>
      <div class="section-card">
        <div class="section-title">Business Impact Assessment</div>
        ${{issues.length?`<table><thead><tr><th>Issue</th><th>Severity</th><th>Potential Impact</th></tr></thead><tbody>${{impactRows}}</tbody></table>`:'<div style="color:var(--green);font-size:12px;padding:8px">✅ No material impacts identified.</div>'}}
      </div>
    </div>

    <div class="section-card">
      <div class="section-title">Issue Tracker</div>
      ${{issues.length?`<table><thead><tr><th>Issue</th><th>Owner</th><th>Status</th><th>Opened</th><th>Target Resolution</th><th>Days Open</th></tr></thead><tbody>${{trackerRows}}</tbody></table>`:'<div style="color:var(--gray);font-size:12px;padding:8px">No open issues.</div>'}}
    </div>

    <div class="section-card">
      <div class="section-title">Recommended Actions (AI-Generated)</div>
      ${{(gov.recommendations||[]).length?`<table><thead><tr><th>Recommendation</th><th>Priority</th><th>Owner</th><th>ETA</th></tr></thead><tbody>${{recRows}}</tbody></table>`:'<div style="color:var(--gray);font-size:12px;padding:8px">No recommendations generated.</div>'}}
    </div>

    <div class="section-card">
      <div class="section-title">Governance Commentary (AI-Draft)</div>
      <div class="summary-text">
        Based on the current snapshot (${{qLabel(CQ)}}), the portfolio data quality is rated <strong>${{rating}}</strong>.
        The primary concerns are rule failures in credit risk and collateral data domains.
        Monitoring frequency: <strong>Quarterly</strong> with ad-hoc review triggered by PSI &gt; 0.20 on any key variable.
        Suggested model owner action: validate LGD and PD inputs against source systems before next ECL run.
      </div>
    </div>
  `;
}}
"""
