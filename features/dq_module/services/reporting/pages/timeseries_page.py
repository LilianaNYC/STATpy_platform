"""D8 — Time Series Analytics.

Cross-cutting trend exploration for the wholesale DQ history. Unlike the
metric-first tabs (Completeness / Drift / Population), this tab is time-first:
the question is *"how is the system evolving across many metrics at once?"*

Seven sections:
  A — Components hero (4 big cards, current + Δ4Q + Δ8Q + sparkline)
  B — Macro sparkline grid (11 series at a glance)
  C — Multi-series overlay (pick 2-4; raw / indexed / z-score; optional smoothing)
  D — Anomaly log (rolling 8Q z-score, configurable severity)
  E — Stability scorecard (sortable: volatility / slope / Δ4Q / Δ8Q)
  F — Correlation matrix + lag-correlation table
  G — Naive 4Q forecast (OLS extrapolation with caveats)

All analyses are client-side over existing DASH_DATA.time_series structures.
No new server-side computation required. Mode bar honored; CMP_MODE defaults
to 'historical' on entry, respects user choice afterward.
"""

JS = f"""
// ═══════════════════════════════════════════════════════════════
// ── TAB 8: TIME SERIES ANALYTICS ──────────────────────────────
// ═══════════════════════════════════════════════════════════════

// ── State ─────────────────────────────────────────────────────
let TS_OVERLAY_SEL = ['completeness_pct', 'avg_psi', 'pop_psi'];
let TS_OVERLAY_MODE = 'zscore';       // 'raw' | 'indexed' | 'zscore'
let TS_OVERLAY_SMOOTH = 0;            // 0 | 4 | 8 (MA window)
let TS_ANOMALY_Z = 2;                 // 2 / 3 / 4 (sigma threshold)
let TS_ANOMALY_SERIES = 'all';        // 'all' | series key
let TS_SCORE_SORT = 'cv_desc';        // sort key for scorecard
let TS_FORECAST_KEY = 'completeness_pct';
let TS_FORECAST_HORIZON = 4;
let TS_LAG_A = 'completeness_pct';
let TS_LAG_B = 'avg_psi';
let _TS_LAST_VISIT = null;            // track previous tab for "auto-default to historical on entry"

// ── Setters ──────────────────────────────────────────────────
function toggleTsOverlay(key) {{
  if (TS_OVERLAY_SEL.includes(key)) {{
    if (TS_OVERLAY_SEL.length > 1) TS_OVERLAY_SEL = TS_OVERLAY_SEL.filter(k => k !== key);
  }} else if (TS_OVERLAY_SEL.length < 4) {{
    TS_OVERLAY_SEL = [...TS_OVERLAY_SEL, key];
  }}
  renderTab('timeseries');
}}
function setTsOverlayMode(m) {{ TS_OVERLAY_MODE = m; renderTab('timeseries'); }}
function setTsOverlaySmooth(s) {{ TS_OVERLAY_SMOOTH = +s; renderTab('timeseries'); }}
function setTsAnomalyZ(z) {{ TS_ANOMALY_Z = +z; renderTab('timeseries'); }}
function setTsAnomalySeries(s) {{ TS_ANOMALY_SERIES = s; renderTab('timeseries'); }}
function setTsScoreSort(s) {{ TS_SCORE_SORT = s; renderTab('timeseries'); }}
function setTsForecastKey(k) {{ TS_FORECAST_KEY = k; renderTab('timeseries'); }}
function setTsForecastHorizon(h) {{ TS_FORECAST_HORIZON = Math.max(1, Math.min(8, +h||4)); renderTab('timeseries'); }}
function setTsLagA(s) {{ TS_LAG_A = s; renderTab('timeseries'); }}
function setTsLagB(s) {{ TS_LAG_B = s; renderTab('timeseries'); }}

// ── Series registry ─────────────────────────────────────────
// `better` describes which direction is good — drives the YoY arrow color
// (green = good move, red = bad move) on the hero cards and sparkline grid.
const TS_SERIES = [
  {{ key:'completeness_pct',  label:'Overall Completeness %',     icon:'✅', better:'high', color:'#16a34a', fmt:v=>fmt(v,2)+'%'  }},
  {{ key:'crit_missing_cols', label:'Critical-missing cols (>25%)',icon:'🔴', better:'low',  color:'#dc2626', fmt:v=>fmtN(v)       }},
  {{ key:'high_missing_cols', label:'High-missing cols (>10%)',    icon:'🟠', better:'low',  color:'#ea580c', fmt:v=>fmtN(v)       }},
  {{ key:'avg_psi',           label:'Avg PSI (drift)',             icon:'📈', better:'low',  color:'#dc2626', fmt:v=>fmt(v,3)      }},
  {{ key:'max_psi',           label:'Max PSI',                     icon:'📉', better:'low',  color:'#7c2d12', fmt:v=>fmt(v,3)      }},
  {{ key:'sig_drift_cols',    label:'Significant-drift cols (>0.20)',icon:'⚠️', better:'low',color:'#ea580c', fmt:v=>fmtN(v)       }},
  {{ key:'pop_psi',           label:'Population PSI',              icon:'👥', better:'low',  color:'#2563eb', fmt:v=>fmt(v,3)      }},
  {{ key:'total_accounts',    label:'Total Accounts',              icon:'📊', better:'neutral',color:'#0369a1',fmt:v=>fmtN(v)      }},
  {{ key:'net_change',        label:'Net Account Change',          icon:'🔀', better:'neutral',color:'#7c3aed',fmt:v=>(v>=0?'+':'')+fmtN(v) }},
  {{ key:'new_accounts',      label:'New Accounts',                icon:'🆕', better:'neutral',color:'#16a34a',fmt:v=>fmtN(v)      }},
  {{ key:'dropped_accounts',  label:'Dropped Accounts',            icon:'⬇️', better:'neutral',color:'#dc2626',fmt:v=>fmtN(v)      }},
];
const _TS_BY_KEY = Object.fromEntries(TS_SERIES.map(s => [s.key, s]));

// ── Math helpers ─────────────────────────────────────────────
function _tsMean(a) {{
  const v = a.filter(x => x != null && Number.isFinite(x));
  return v.length ? v.reduce((s,x)=>s+x, 0) / v.length : null;
}}
function _tsStd(a) {{
  const v = a.filter(x => x != null && Number.isFinite(x));
  if (v.length < 2) return null;
  const m = _tsMean(v);
  return Math.sqrt(v.reduce((s,x)=>s+(x-m)*(x-m), 0) / (v.length - 1));
}}
function _tsOls(ys) {{
  // OLS slope of y on integer index 0..n-1. Returns {{slope, intercept, r2}}.
  const v = ys.map((y,i) => ({{x:i, y}})).filter(p => p.y != null && Number.isFinite(p.y));
  if (v.length < 2) return {{slope:null, intercept:null, r2:null}};
  const n = v.length;
  const mx = v.reduce((s,p)=>s+p.x, 0) / n;
  const my = v.reduce((s,p)=>s+p.y, 0) / n;
  let num = 0, den = 0;
  for (const p of v) {{ num += (p.x-mx)*(p.y-my); den += (p.x-mx)*(p.x-mx); }}
  const slope = den ? num / den : 0;
  const intercept = my - slope * mx;
  let ssRes = 0, ssTot = 0;
  for (const p of v) {{
    const yh = slope * p.x + intercept;
    ssRes += (p.y - yh)*(p.y - yh);
    ssTot += (p.y - my)*(p.y - my);
  }}
  const r2 = ssTot ? 1 - ssRes/ssTot : null;
  return {{slope, intercept, r2, n}};
}}
function _tsPearson(a, b) {{
  const pairs = [];
  for (let i = 0; i < a.length && i < b.length; i++) {{
    if (a[i] != null && b[i] != null && Number.isFinite(a[i]) && Number.isFinite(b[i])) {{
      pairs.push([a[i], b[i]]);
    }}
  }}
  if (pairs.length < 3) return {{r:null, n:pairs.length}};
  const xs = pairs.map(p => p[0]); const ys = pairs.map(p => p[1]);
  const mx = _tsMean(xs); const my = _tsMean(ys);
  let num = 0, dx = 0, dy = 0;
  for (const [x, y] of pairs) {{ num += (x-mx)*(y-my); dx += (x-mx)*(x-mx); dy += (y-my)*(y-my); }}
  const den = Math.sqrt(dx * dy);
  return {{r: den ? num/den : null, n: pairs.length}};
}}
function _tsZscoreSeries(values, window) {{
  // Rolling z-score: at each index i, use values[max(0,i-window):i] for baseline
  const w = window || 8;
  return values.map((v, i) => {{
    if (v == null || !Number.isFinite(v)) return null;
    const start = Math.max(0, i - w);
    const baseline = values.slice(start, i).filter(x => x != null && Number.isFinite(x));
    if (baseline.length < 3) return null;
    const m = _tsMean(baseline);
    const s = _tsStd(baseline);
    if (!s) return null;
    return (v - m) / s;
  }});
}}
function _tsMovingAvg(values, window) {{
  if (!window || window < 2) return values.slice();
  return values.map((v, i) => {{
    if (v == null) return null;
    const start = Math.max(0, i - window + 1);
    const slice = values.slice(start, i+1).filter(x => x != null && Number.isFinite(x));
    if (!slice.length) return null;
    return slice.reduce((s,x)=>s+x, 0) / slice.length;
  }});
}}

// ── Build the per-series quarter-indexed history ───────────────
// Returns: {{ quarters: [...], data: {{ key: [v0, v1, …] aligned to quarters }} }}
function _tsBuildSeries() {{
  const allQ = DASH_DATA.quarters || [];
  const ts = DASH_DATA.time_series || {{}};
  const compOT = ts.completeness_over_time || [];
  const psiOT = ts.psi_over_time || [];
  const popOT = ts.population_over_time || [];
  const psiHm = ts.psi_heatmap || {{}};

  // Index helpers — quarter -> value
  const compByQ = Object.fromEntries(compOT.map(r => [r.quarter, r.value]));
  const psiByQ  = Object.fromEntries(psiOT.map(r => [r.quarter, r.avg_psi]));
  const popByQ  = Object.fromEntries(popOT.map(r => [r.quarter, r]));

  // Per-quarter aggregates derived from psi_heatmap
  const psiCols = Object.keys(psiHm);
  const maxPsiByQ = {{}}, sigDriftCountByQ = {{}};
  for (const q of allQ) {{
    let maxP = null, sigN = 0;
    for (const col of psiCols) {{
      const v = (psiHm[col] || {{}})[q];
      if (v == null) continue;
      if (maxP == null || v > maxP) maxP = v;
      if (v > 0.20) sigN += 1;
    }}
    maxPsiByQ[q] = maxP;
    sigDriftCountByQ[q] = psiCols.length ? sigN : null;
  }}

  // Per-quarter all-columns missing counts (from by_quarter snapshot)
  const critByQ = {{}}, highByQ = {{}};
  for (const q of allQ) {{
    const cols = ((DASH_DATA.by_quarter[q] || {{}}).completeness || {{}}).by_column || [];
    if (!cols.length) {{ critByQ[q] = null; highByQ[q] = null; continue; }}
    let c = 0, h = 0;
    for (const r of cols) {{
      const m = +r.missing_pct;
      if (m > 25) c += 1;
      if (m > 10) h += 1;
    }}
    critByQ[q] = c; highByQ[q] = h;
  }}

  const data = {{
    completeness_pct:  allQ.map(q => compByQ[q] ?? null),
    crit_missing_cols: allQ.map(q => critByQ[q] ?? null),
    high_missing_cols: allQ.map(q => highByQ[q] ?? null),
    avg_psi:           allQ.map(q => psiByQ[q] ?? null),
    max_psi:           allQ.map(q => maxPsiByQ[q] ?? null),
    sig_drift_cols:    allQ.map(q => sigDriftCountByQ[q] ?? null),
    pop_psi:           allQ.map(q => (popByQ[q] || {{}}).psi ?? null),
    total_accounts:    allQ.map(q => (popByQ[q] || {{}}).total ?? null),
    new_accounts:      allQ.map(q => (popByQ[q] || {{}}).new ?? null),
    dropped_accounts:  allQ.map(q => (popByQ[q] || {{}}).dropped ?? null),
  }};
  // Net change: total[q] - total[q-1]
  data.net_change = data.total_accounts.map((v, i) => {{
    if (v == null || i === 0) return null;
    const prev = data.total_accounts[i-1];
    return prev == null ? null : v - prev;
  }});

  return {{ quarters: allQ, data }};
}}

// Apply CMP_MODE to filter the visible quarter window.
function _tsWindowIndexes(allQuarters) {{
  if (CMP_MODE === 'qoq') {{
    const start = Math.max(0, allQuarters.length - 12);
    return allQuarters.map((q,i) => i).slice(start);
  }}
  if (CMP_MODE === 'yoy') {{
    const yr = (typeof YOY_25_YEAR !== 'undefined' && YOY_25_YEAR !== null)
      ? YOY_25_YEAR
      : Math.max(...allQuarters.map(q => +q.slice(0,4)));
    return allQuarters.map((q,i) => i).filter(i => +allQuarters[i].slice(0,4) === yr);
  }}
  // historical: respect HIST_START / HIST_END
  return allQuarters.map((q,i) => i).filter(i => {{
    const q = allQuarters[i];
    if (HIST_START && q < HIST_START) return false;
    if (HIST_END   && q > HIST_END)   return false;
    return true;
  }});
}}

// ═══════════════════════════════════════════════════════════════
// MAIN RENDER
// ═══════════════════════════════════════════════════════════════
function renderTimeseries() {{
  // Auto-default to Historical on first arrival from another tab
  if (_TS_LAST_VISIT !== 'timeseries' && CMP_MODE !== 'historical') {{
    CMP_MODE = 'historical';
  }}
  _TS_LAST_VISIT = 'timeseries';

  const ts = _tsBuildSeries();
  const winIdx = _tsWindowIndexes(ts.quarters);
  const winQ = winIdx.map(i => ts.quarters[i]);
  // Per-series windowed values
  const wd = {{}};
  for (const s of TS_SERIES) wd[s.key] = winIdx.map(i => ts.data[s.key][i]);

  document.getElementById('tab-timeseries').innerHTML = `
    <div class="dash-header">
      <h2>Time Series Analytics — ${{winQ.length}} quarter${{winQ.length===1?'':'s'}} in view</h2>
      <p>Cross-cutting trend exploration. Defaults to Historical mode on entry — pick a window from the mode bar to scope every section below. ${{_lensChip()}}</p>
    </div>

    ${{_modeBar()}}

    <!-- A · Components hero -->
    <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin:6px 0">A · Components</div>
    <div id="ts-hero" style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px"></div>

    <!-- B · Macro sparkline grid -->
    <div class="section-card">
      <div class="section-title">B · Macro trends — all metrics at a glance</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        Every monitored series with its current value, last-8Q sparkline, and YoY arrow.
        Arrow color reflects the metric's direction-of-good: green for an improving move, red for worsening, gray for neutral series.
      </div>
      <div id="ts-spark-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px"></div>
    </div>

    <!-- C · Multi-series overlay -->
    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">
        <div class="section-title" style="margin:0">C · Multi-series overlay <span style="font-size:11px;font-weight:500;color:var(--text-muted)">— pick up to 4</span></div>
        <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">Mode</label>
            <select onchange="setTsOverlayMode(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
              <option value="raw"${{TS_OVERLAY_MODE==='raw'?' selected':''}}>Raw (multi-axis)</option>
              <option value="indexed"${{TS_OVERLAY_MODE==='indexed'?' selected':''}}>Indexed (= 100 at start)</option>
              <option value="zscore"${{TS_OVERLAY_MODE==='zscore'?' selected':''}}>Z-score (mean 0 / std 1)</option>
            </select>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">Smooth</label>
            <select onchange="setTsOverlaySmooth(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
              <option value="0"${{TS_OVERLAY_SMOOTH===0?' selected':''}}>None</option>
              <option value="4"${{TS_OVERLAY_SMOOTH===4?' selected':''}}>4Q MA</option>
              <option value="8"${{TS_OVERLAY_SMOOTH===8?' selected':''}}>8Q MA</option>
            </select>
          </div>
        </div>
      </div>
      <div id="ts-overlay-chips" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px"></div>
      <div id="ts-overlay-chart" style="min-height:340px"></div>
      <div style="margin-top:8px;font-size:10px;color:var(--text-muted);font-style:italic">
        ${{TS_OVERLAY_MODE==='raw' ? 'Raw: each series on its own y-axis. Magnitudes preserved; co-movement harder to read.'
          : TS_OVERLAY_MODE==='indexed' ? 'Indexed: every series rebased to 100 at the first visible quarter. Shows relative growth, not absolute levels.'
          : 'Z-score: each series normalized to mean 0, std 1 over the visible window. Best view for spotting co-movement and lead/lag.'}}
      </div>
    </div>

    <!-- D · Anomaly log -->
    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">
        <div class="section-title" style="margin:0">D · Anomaly log <span style="font-size:11px;font-weight:500;color:var(--text-muted)">— rolling 8Q baseline</span></div>
        <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">Series</label>
            <select onchange="setTsAnomalySeries(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;min-width:200px">
              <option value="all"${{TS_ANOMALY_SERIES==='all'?' selected':''}}>All series</option>
              ${{TS_SERIES.map(s => `<option value="${{s.key}}"${{TS_ANOMALY_SERIES===s.key?' selected':''}}>${{s.label}}</option>`).join('')}}
            </select>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">Min severity</label>
            <select onchange="setTsAnomalyZ(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
              <option value="2"${{TS_ANOMALY_Z===2?' selected':''}}>|z| ≥ 2 (mild)</option>
              <option value="3"${{TS_ANOMALY_Z===3?' selected':''}}>|z| ≥ 3 (moderate)</option>
              <option value="4"${{TS_ANOMALY_Z===4?' selected':''}}>|z| ≥ 4 (strong)</option>
            </select>
          </div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        For each series, compare every quarter's value to the rolling mean ± σ of the prior 8 quarters.
        Quarters that break out beyond the chosen threshold are surfaced here, newest first.
      </div>
      <div id="ts-anomaly-feed" style="max-height:380px;overflow-y:auto"></div>
    </div>

    <!-- E · Stability scorecard -->
    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">
        <div class="section-title" style="margin:0">E · Stability scorecard</div>
        <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">Sort by</label>
            <select onchange="setTsScoreSort(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
              <option value="cv_desc"${{TS_SCORE_SORT==='cv_desc'?' selected':''}}>Volatility (CV) ↓</option>
              <option value="cv_asc"${{TS_SCORE_SORT==='cv_asc'?' selected':''}}>Volatility (CV) ↑</option>
              <option value="slope_abs_desc"${{TS_SCORE_SORT==='slope_abs_desc'?' selected':''}}>|Slope| ↓</option>
              <option value="d8_abs_desc"${{TS_SCORE_SORT==='d8_abs_desc'?' selected':''}}>|Δ 8Q| ↓</option>
              <option value="label_asc"${{TS_SCORE_SORT==='label_asc'?' selected':''}}>Name A→Z</option>
            </select>
          </div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        For every series over the visible window: latest value, change vs 4 / 8 Q ago, coefficient of variation
        (σ / |mean| × 100), OLS trend slope, and the worst / best quarters.
      </div>
      <div id="ts-scorecard"></div>
    </div>

    <!-- F · Correlation matrix + lag table -->
    <div class="section-card">
      <div class="section-title">F · Cross-metric correlation</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
        Pearson correlation across the visible window. Cells use the intersection of available quarters per pair (n shown on hover).
        Correlation is descriptive — it doesn't imply causation, and high noise in either series can mask a real relationship.
      </div>
      <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;align-items:start">
        <div id="ts-corr-matrix"></div>
        <div>
          <div style="font-size:11px;font-weight:700;color:#0f172a;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Lag analysis</div>
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
            Cross-correlation at lags 0–4 quarters. If <code>r</code> peaks at a non-zero lag, one series may lead the other.
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:10px">
            <div style="display:flex;align-items:center;gap:6px">
              <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;width:48px">A</label>
              <select onchange="setTsLagA(this.value)" style="flex:1;font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
                ${{TS_SERIES.map(s => `<option value="${{s.key}}"${{TS_LAG_A===s.key?' selected':''}}>${{s.label}}</option>`).join('')}}
              </select>
            </div>
            <div style="display:flex;align-items:center;gap:6px">
              <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;width:48px">B</label>
              <select onchange="setTsLagB(this.value)" style="flex:1;font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
                ${{TS_SERIES.map(s => `<option value="${{s.key}}"${{TS_LAG_B===s.key?' selected':''}}>${{s.label}}</option>`).join('')}}
              </select>
            </div>
          </div>
          <div id="ts-lag-table"></div>
        </div>
      </div>
    </div>

    <!-- G · Naive forecast -->
    <div class="section-card">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">
        <div class="section-title" style="margin:0">G · Naive forecast</div>
        <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">Series</label>
            <select onchange="setTsForecastKey(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;min-width:200px">
              ${{TS_SERIES.map(s => `<option value="${{s.key}}"${{TS_FORECAST_KEY===s.key?' selected':''}}>${{s.label}}</option>`).join('')}}
            </select>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <label style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">Horizon</label>
            <select onchange="setTsForecastHorizon(this.value)" style="font-size:11px;padding:3px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#fff">
              <option value="2"${{TS_FORECAST_HORIZON===2?' selected':''}}>+2 Q</option>
              <option value="4"${{TS_FORECAST_HORIZON===4?' selected':''}}>+4 Q</option>
              <option value="8"${{TS_FORECAST_HORIZON===8?' selected':''}}>+8 Q</option>
            </select>
          </div>
        </div>
      </div>
      <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;padding:10px 14px;margin-bottom:12px;font-size:11px;color:#92400e">
        ⚠ <strong>Naive extrapolation only.</strong> OLS fit on the last 12 visible quarters projected forward. No exogenous variables,
        no seasonality, no regime-change detection. The shaded band is ±1 residual σ — interpret as <em>uncertainty under the
        assumption that the recent trend continues</em>. For directional guidance, not point estimates.
      </div>
      <div id="ts-forecast-chart" style="min-height:300px"></div>
      <div id="ts-forecast-meta" style="margin-top:8px;font-size:11px;color:var(--text-muted)"></div>
    </div>
  `;

  _tsRenderHero(ts, winIdx);
  _tsRenderSparkGrid(ts);
  _tsRenderOverlayChips(wd);
  _tsRenderOverlay(winQ, wd);
  _tsRenderAnomalies(ts, winIdx);
  _tsRenderScorecard(winQ, wd);
  _tsRenderCorrelation(wd);
  _tsRenderLagTable(wd);
  _tsRenderForecast(winQ, wd);
}}

// ═══════════════════════════════════════════════════════════════
// SECTION A · Components hero strip (4 big cards)
// ═══════════════════════════════════════════════════════════════
function _tsRenderHero(ts, winIdx) {{
  const el = document.getElementById('ts-hero');
  if (!el) return;
  // Pick 4 components to feature: completeness, drift, population, volume
  const featured = ['completeness_pct', 'avg_psi', 'pop_psi', 'total_accounts'];

  const cards = featured.map(key => {{
    const spec = _TS_BY_KEY[key];
    const series = winIdx.map(i => ts.data[key][i]);
    const labels = winIdx.map(i => ts.quarters[i]);
    const last = series.length ? series[series.length-1] : null;
    const i4 = series.length - 1 - 4;
    const i8 = series.length - 1 - 8;
    const v4 = (i4 >= 0) ? series[i4] : null;
    const v8 = (i8 >= 0) ? series[i8] : null;
    const delta = (a, b) => (a == null || b == null) ? null : (a - b);
    const d4 = delta(last, v4);
    const d8 = delta(last, v8);
    // Arrow color logic
    const goodColor = '#16a34a', badColor = '#dc2626', neutralColor = '#64748b';
    function deltaArrow(d) {{
      if (d == null || !Number.isFinite(d)) return `<span style="color:${{neutralColor}}">—</span>`;
      if (Math.abs(d) < 1e-9) return `<span style="color:${{neutralColor}}">—</span>`;
      const dir = d > 0 ? '▲' : '▼';
      const c = spec.better === 'neutral' ? neutralColor
              : spec.better === 'high'
                ? (d > 0 ? goodColor : badColor)
                : (d > 0 ? badColor : goodColor);
      const sign = d > 0 ? '+' : '';
      const num = (Math.abs(d) >= 100) ? fmtN(d) : fmt(d, 3);
      return `<span style="color:${{c}};font-weight:700">${{dir}} ${{sign}}${{num}}</span>`;
    }}
    const sparkVals = series.filter(v => v != null && Number.isFinite(v));
    const spk = sparkVals.length ? spark(sparkVals) : '—';

    return `<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px;border-left:4px solid ${{spec.color}}">
      <div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em">${{spec.icon}} ${{spec.label}}</div>
      <div style="font-size:30px;font-weight:800;color:#0f172a;margin:6px 0 4px;line-height:1">${{last==null?'—':spec.fmt(last)}}</div>
      <div style="display:flex;gap:14px;font-size:11px;color:var(--text-muted);align-items:center">
        <div>Δ 4Q ${{deltaArrow(d4)}}</div>
        <div>Δ 8Q ${{deltaArrow(d8)}}</div>
      </div>
      <div style="margin-top:8px;color:${{spec.color}};font-family:monospace;font-size:14px;letter-spacing:1px">${{spk}}</div>
      <div style="font-size:9px;color:#94a3b8;margin-top:2px">${{labels[0]?qLabel(labels[0]):''}} → ${{labels[labels.length-1]?qLabel(labels[labels.length-1]):''}}</div>
    </div>`;
  }}).join('');
  el.innerHTML = cards;
}}

// ═══════════════════════════════════════════════════════════════
// SECTION B · Macro sparkline grid (all 11 series)
// ═══════════════════════════════════════════════════════════════
function _tsRenderSparkGrid(ts) {{
  const el = document.getElementById('ts-spark-grid');
  if (!el) return;
  const lastN = 8;
  const cards = TS_SERIES.map(spec => {{
    const allVals = ts.data[spec.key];
    const tail = allVals.slice(-lastN).filter(v => v != null && Number.isFinite(v));
    const last = allVals.length ? allVals[allVals.length-1] : null;
    // YoY: compare current vs 4Q ago
    const yIdx = allVals.length - 1 - 4;
    const yoy = (yIdx >= 0 && last != null && allVals[yIdx] != null) ? last - allVals[yIdx] : null;
    const goodColor='#16a34a', badColor='#dc2626', neutralColor='#64748b';
    let arrow = `<span style="color:${{neutralColor}}">—</span>`;
    if (yoy != null && Math.abs(yoy) > 1e-9) {{
      const dir = yoy > 0 ? '▲' : '▼';
      const c = spec.better === 'neutral' ? neutralColor
              : spec.better === 'high'
                ? (yoy > 0 ? goodColor : badColor)
                : (yoy > 0 ? badColor : goodColor);
      arrow = `<span style="color:${{c}};font-weight:700">${{dir}}</span>`;
    }}
    const spk = tail.length ? spark(tail) : '—';

    return `<div style="background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:10px;cursor:pointer;transition:transform .1s,border-color .1s" onmouseover="this.style.borderColor='${{spec.color}}';this.style.transform='translateY(-1px)'" onmouseout="this.style.borderColor='#e2e8f0';this.style.transform='translateY(0)'" onclick="setTsForecastKey('${{spec.key}}');document.getElementById('ts-forecast-chart').scrollIntoView({{behavior:'smooth',block:'start'}})">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px">
        <div style="font-size:10px;font-weight:700;color:#0f172a">${{spec.icon}} ${{spec.label}}</div>
        ${{arrow}}
      </div>
      <div style="font-size:18px;font-weight:800;color:${{spec.color}};margin:6px 0 0;line-height:1">${{last==null?'—':spec.fmt(last)}}</div>
      <div style="color:${{spec.color}};font-family:monospace;font-size:12px;letter-spacing:1px;margin-top:4px">${{spk}}</div>
      <div style="font-size:9px;color:#94a3b8;margin-top:2px">last ${{lastN}}Q · click → forecast</div>
    </div>`;
  }}).join('');
  el.innerHTML = cards;
}}

// ═══════════════════════════════════════════════════════════════
// SECTION C · Multi-series overlay
// ═══════════════════════════════════════════════════════════════
function _tsRenderOverlayChips(wd) {{
  const el = document.getElementById('ts-overlay-chips');
  if (!el) return;
  const sel = new Set(TS_OVERLAY_SEL);
  el.innerHTML = TS_SERIES.map(spec => {{
    const active = sel.has(spec.key);
    const dim = !active && sel.size >= 4;
    return `<button onclick="toggleTsOverlay('${{spec.key}}')" style="font-size:11px;padding:5px 12px;border:1px solid ${{active?spec.color:'#cbd5e1'}};background:${{active?spec.color:'#fff'}};color:${{active?'#fff':(dim?'#cbd5e1':'#475569')}};border-radius:14px;cursor:${{dim?'not-allowed':'pointer'}};font-weight:${{active?'600':'500'}};opacity:${{dim?0.5:1}}">${{spec.icon}} ${{spec.label}}</button>`;
  }}).join('');
}}

function _tsRenderOverlay(winQ, wd) {{
  const el = document.getElementById('ts-overlay-chart');
  if (!el) return;
  const xLabels = winQ.map(q => qLabel(q));
  const traces = [];
  const yAxes = {{}};
  TS_OVERLAY_SEL.forEach((key, idx) => {{
    const spec = _TS_BY_KEY[key];
    if (!spec) return;
    let values = wd[key].slice();
    if (TS_OVERLAY_SMOOTH > 0) values = _tsMovingAvg(values, TS_OVERLAY_SMOOTH);
    if (TS_OVERLAY_MODE === 'indexed') {{
      // First non-null becomes 100
      const i0 = values.findIndex(v => v != null && Number.isFinite(v) && v !== 0);
      const base = i0 >= 0 ? values[i0] : null;
      if (base) values = values.map(v => v == null ? null : (v / base) * 100);
    }} else if (TS_OVERLAY_MODE === 'zscore') {{
      const m = _tsMean(values);
      const s = _tsStd(values);
      if (s) values = values.map(v => v == null ? null : (v - m) / s);
    }}
    const trace = {{
      x: xLabels, y: values,
      name: spec.label,
      type: 'scatter', mode: 'lines+markers',
      line: {{color: spec.color, width: 2}}, marker: {{size: 4}}, connectgaps: true,
    }};
    // In raw mode, give each series its own y-axis on alternating sides
    if (TS_OVERLAY_MODE === 'raw' && idx > 0) {{
      const axisKey = 'y' + (idx + 1);
      trace.yaxis = axisKey;
      yAxes['yaxis' + (idx + 1)] = {{
        overlaying: 'y',
        side: idx % 2 === 1 ? 'right' : 'left',
        position: idx >= 2 ? (idx === 2 ? 0.06 : 0.94) : (idx === 1 ? 1 : 0),
        showgrid: false,
        title: {{ text: spec.label, font: {{size:9, color: spec.color}} }},
        tickfont: {{size: 9, color: spec.color}},
      }};
    }}
    traces.push(trace);
  }});

  const yLabel = TS_OVERLAY_MODE === 'indexed' ? 'Index (= 100 at start)'
              : TS_OVERLAY_MODE === 'zscore' ? 'Z-score (σ units)'
              : (TS_OVERLAY_SEL[0] ? _TS_BY_KEY[TS_OVERLAY_SEL[0]].label : 'Value');

  Plotly.react('ts-overlay-chart', traces, {{
    margin:{{t:30,r:60,b:60,l:60}},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{{tickangle:-45,tickfont:{{size:9}},showgrid:false}},
    yaxis:{{title:yLabel, gridcolor:'#f1f5f9', tickfont:{{size:9}}, zerolinecolor: TS_OVERLAY_MODE==='zscore'?'#94a3b8':undefined, zerolinewidth: TS_OVERLAY_MODE==='zscore'?1:0}},
    legend:{{orientation:'h', y:1.12, font:{{size:10}}}},
    showlegend:true,
    ...yAxes,
  }}, {{responsive:true, displayModeBar:false}});
}}

// ═══════════════════════════════════════════════════════════════
// SECTION D · Anomaly log
// ═══════════════════════════════════════════════════════════════
function _tsRenderAnomalies(ts, winIdx) {{
  const el = document.getElementById('ts-anomaly-feed');
  if (!el) return;
  const sigThresh = TS_ANOMALY_Z;
  const events = [];
  const seriesList = (TS_ANOMALY_SERIES === 'all') ? TS_SERIES : TS_SERIES.filter(s => s.key === TS_ANOMALY_SERIES);

  for (const spec of seriesList) {{
    const values = ts.data[spec.key];
    const z = _tsZscoreSeries(values, 8);
    for (const i of winIdx) {{
      const zi = z[i];
      if (zi == null || !Number.isFinite(zi)) continue;
      if (Math.abs(zi) < sigThresh) continue;
      const baseline = values.slice(Math.max(0, i-8), i).filter(v => v != null && Number.isFinite(v));
      const m = _tsMean(baseline);
      const s = _tsStd(baseline);
      events.push({{
        quarter: ts.quarters[i], qIdx: i,
        key: spec.key, spec,
        value: values[i],
        z: zi, baselineMean: m, baselineStd: s,
      }});
    }}
  }}
  events.sort((a, b) => b.qIdx - a.qIdx);  // newest first

  if (!events.length) {{
    el.innerHTML = `<div style="padding:24px;color:#16a34a;font-size:13px;text-align:center;background:#dcfce7;border-radius:8px">
      ✓ No anomalies in the visible window at |z| ≥ ${{sigThresh}}.
    </div>`;
    return;
  }}

  const sevClass = (z) => {{
    const a = Math.abs(z);
    if (a >= 4) return {{label:'Strong', tone:'#7f1d1d', bg:'#fee2e2', icon:'🔴'}};
    if (a >= 3) return {{label:'Moderate', tone:'#9a3412', bg:'#ffedd5', icon:'🟠'}};
    return {{label:'Mild', tone:'#854d0e', bg:'#fef9c3', icon:'🟡'}};
  }};

  el.innerHTML = events.slice(0, 80).map(ev => {{
    const sv = sevClass(ev.z);
    const dir = ev.z > 0 ? 'spiked' : 'dropped';
    const fmt_ = ev.spec.fmt;
    return `<div style="display:flex;gap:12px;padding:10px 12px;border:1px solid ${{sv.bg}};border-left:3px solid ${{sv.tone}};background:#fff;border-radius:6px;margin-bottom:6px">
      <div style="font-size:20px">${{sv.icon}}</div>
      <div style="flex:1">
        <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap">
          <div><strong style="color:#0f172a;font-family:monospace">${{qLabel(ev.quarter)}}</strong> · <span style="color:${{ev.spec.color}};font-weight:700">${{ev.spec.label}}</span></div>
          <span style="font-size:9px;font-weight:700;color:#fff;background:${{sv.tone}};padding:2px 8px;border-radius:8px;text-transform:uppercase">${{sv.label}} · |z|=${{fmt(Math.abs(ev.z),1)}}</span>
        </div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:3px">
          ${{dir}} to <strong style="color:#0f172a">${{fmt_(ev.value)}}</strong>
          vs rolling baseline <strong>${{fmt_(ev.baselineMean)}}</strong> ± ${{fmt_(ev.baselineStd)}}
          <span style="color:#94a3b8">(last 8Q window)</span>
        </div>
      </div>
    </div>`;
  }}).join('') + (events.length > 80 ? `<div style="text-align:center;font-size:11px;color:var(--text-muted);padding:8px;font-style:italic">… ${{events.length - 80}} more anomalies in the visible window (showing newest 80). Filter by series or raise the threshold to narrow.</div>` : '');
}}

// ═══════════════════════════════════════════════════════════════
// SECTION E · Stability scorecard
// ═══════════════════════════════════════════════════════════════
function _tsRenderScorecard(winQ, wd) {{
  const el = document.getElementById('ts-scorecard');
  if (!el) return;
  const rows = TS_SERIES.map(spec => {{
    const values = wd[spec.key];
    const vClean = values.filter(v => v != null && Number.isFinite(v));
    const last = vClean.length ? vClean[vClean.length-1] : null;
    const mean = _tsMean(vClean);
    const std = _tsStd(vClean);
    const cv = (std != null && mean != null && Math.abs(mean) > 1e-9) ? (std / Math.abs(mean)) * 100 : null;
    const i4 = values.length - 1 - 4;
    const i8 = values.length - 1 - 8;
    const d4 = (i4 >= 0 && last != null && values[i4] != null) ? last - values[i4] : null;
    const d8 = (i8 >= 0 && last != null && values[i8] != null) ? last - values[i8] : null;
    const ols = _tsOls(values);
    // Best / worst — better-direction aware
    let worstIdx = null, bestIdx = null, worstV = null, bestV = null;
    for (let i = 0; i < values.length; i++) {{
      const v = values[i];
      if (v == null || !Number.isFinite(v)) continue;
      // "worst" means farthest from good direction
      if (spec.better === 'high') {{
        if (worstV == null || v < worstV) {{ worstV = v; worstIdx = i; }}
        if (bestV  == null || v > bestV)  {{ bestV  = v; bestIdx  = i; }}
      }} else if (spec.better === 'low') {{
        if (worstV == null || v > worstV) {{ worstV = v; worstIdx = i; }}
        if (bestV  == null || v < bestV)  {{ bestV  = v; bestIdx  = i; }}
      }} else {{
        // neutral — use max as "high" and min as "low" but don't color
        if (worstV == null || v < worstV) {{ worstV = v; worstIdx = i; }}
        if (bestV  == null || v > bestV)  {{ bestV  = v; bestIdx  = i; }}
      }}
    }}
    return {{spec, values, vClean, last, mean, std, cv, d4, d8, slope:ols.slope, r2:ols.r2,
      worstQ: worstIdx != null ? winQ[worstIdx] : null, worstV,
      bestQ:  bestIdx  != null ? winQ[bestIdx]  : null, bestV}};
  }});

  // Sorting
  const cmp = TS_SCORE_SORT;
  const safe = (v, def) => (v == null || !Number.isFinite(v)) ? def : v;
  rows.sort((a, b) => {{
    if (cmp === 'cv_desc')         return safe(b.cv, -Infinity) - safe(a.cv, -Infinity);
    if (cmp === 'cv_asc')          return safe(a.cv,  Infinity) - safe(b.cv,  Infinity);
    if (cmp === 'slope_abs_desc')  return safe(Math.abs(b.slope), -Infinity) - safe(Math.abs(a.slope), -Infinity);
    if (cmp === 'd8_abs_desc')     return safe(Math.abs(b.d8), -Infinity) - safe(Math.abs(a.d8), -Infinity);
    if (cmp === 'label_asc')       return a.spec.label.localeCompare(b.spec.label);
    return 0;
  }});

  const dColor = (spec, d) => {{
    if (d == null || !Number.isFinite(d) || Math.abs(d) < 1e-9) return '#64748b';
    if (spec.better === 'neutral') return '#64748b';
    if (spec.better === 'high') return d > 0 ? '#16a34a' : '#dc2626';
    return d > 0 ? '#dc2626' : '#16a34a';
  }};
  const cvColor = (cv) => cv == null ? '#64748b' : cv > 40 ? '#dc2626' : cv > 20 ? '#d97706' : '#16a34a';

  const bodyRows = rows.map(r => `
    <tr>
      <td style="font-weight:600;color:#0f172a"><span style="color:${{r.spec.color}}">${{r.spec.icon}}</span> ${{r.spec.label}}</td>
      <td style="text-align:right;font-weight:600">${{r.last==null?'—':r.spec.fmt(r.last)}}</td>
      <td style="text-align:right;color:${{dColor(r.spec, r.d4)}};font-weight:600">${{r.d4==null?'—':(r.d4>=0?'+':'')+r.spec.fmt(r.d4)}}</td>
      <td style="text-align:right;color:${{dColor(r.spec, r.d8)}};font-weight:600">${{r.d8==null?'—':(r.d8>=0?'+':'')+r.spec.fmt(r.d8)}}</td>
      <td style="text-align:right;color:${{cvColor(r.cv)}};font-weight:600">${{r.cv==null?'—':fmt(r.cv,1)+'%'}}</td>
      <td style="text-align:right;font-family:monospace;font-size:11px">${{r.slope==null?'—':(r.slope>=0?'+':'')+fmt(r.slope,4)+'/Q'}}</td>
      <td style="font-size:10px;color:var(--text-muted)">${{r.worstQ?qLabel(r.worstQ):'—'}}${{r.worstV==null?'':` <span style="color:#dc2626">(${{r.spec.fmt(r.worstV)}})</span>`}}</td>
      <td style="font-size:10px;color:var(--text-muted)">${{r.bestQ?qLabel(r.bestQ):'—'}}${{r.bestV==null?'':` <span style="color:#16a34a">(${{r.spec.fmt(r.bestV)}})</span>`}}</td>
      <td style="color:${{r.spec.color}};font-family:monospace;font-size:11px;letter-spacing:1px;text-align:center">${{r.vClean.length ? spark(r.vClean) : '—'}}</td>
    </tr>`).join('');

  el.innerHTML = `<div style="overflow-x:auto"><table style="font-size:11px;width:100%">
    <thead><tr>
      <th>Series</th>
      <th style="text-align:right">Latest</th>
      <th style="text-align:right" title="Change vs 4 quarters ago">Δ 4Q</th>
      <th style="text-align:right" title="Change vs 8 quarters ago">Δ 8Q</th>
      <th style="text-align:right" title="Coefficient of variation = σ / |mean| × 100. Higher = more volatile.">CV %</th>
      <th style="text-align:right" title="OLS slope of value vs quarter index across the visible window.">Slope</th>
      <th>Worst Q</th>
      <th>Best Q</th>
      <th style="text-align:center">Sparkline</th>
    </tr></thead>
    <tbody>${{bodyRows}}</tbody>
  </table></div>`;
}}

// ═══════════════════════════════════════════════════════════════
// SECTION F · Correlation matrix + lag table
// ═══════════════════════════════════════════════════════════════
function _tsRenderCorrelation(wd) {{
  const el = document.getElementById('ts-corr-matrix');
  if (!el) return;
  const keys = TS_SERIES.map(s => s.key);
  const labels = TS_SERIES.map(s => s.label);

  // Compute r matrix
  const N = keys.length;
  const z = [];
  const text = [];
  for (let i = 0; i < N; i++) {{
    const row = [], trow = [];
    for (let j = 0; j < N; j++) {{
      if (i === j) {{ row.push(1); trow.push('1.00<br>n=—'); continue; }}
      const a = wd[keys[i]], b = wd[keys[j]];
      const {{r, n}} = _tsPearson(a, b);
      row.push(r);
      trow.push(r == null ? '—' : `${{fmt(r,2)}}<br>n=${{n}}`);
    }}
    z.push(row); text.push(trow);
  }}

  Plotly.react('ts-corr-matrix', [{{
    type:'heatmap',
    z, x: labels, y: labels, text,
    texttemplate: '%{{text}}',
    textfont: {{ size: 9 }},
    colorscale: [[0,'#dc2626'], [0.5,'#ffffff'], [1,'#2563eb']],
    zmin: -1, zmax: 1, zmid: 0,
    showscale: true,
    colorbar: {{title:'r', tickfont:{{size:9}}, len:0.7}},
    hovertemplate: '%{{y}}<br>↔ %{{x}}<br>r = %{{z:.2f}}<extra></extra>',
  }}], {{
    margin:{{t:20,r:20,b:160,l:200}},
    height: 520,
    xaxis:{{tickangle:-45, tickfont:{{size:10}}}},
    yaxis:{{tickfont:{{size:10}}, autorange:'reversed'}},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  }}, {{responsive:true, displayModeBar:false}});
}}

function _tsRenderLagTable(wd) {{
  const el = document.getElementById('ts-lag-table');
  if (!el) return;
  const a = wd[TS_LAG_A], b = wd[TS_LAG_B];
  const labA = _TS_BY_KEY[TS_LAG_A].label;
  const labB = _TS_BY_KEY[TS_LAG_B].label;
  // Compute r at lags 0..4 (positive lag = B follows A by k quarters)
  const lags = [-2, -1, 0, 1, 2, 3, 4];
  const rows = lags.map(k => {{
    let r, n;
    if (k === 0) {{ const res = _tsPearson(a, b); r = res.r; n = res.n; }}
    else if (k > 0) {{ const res = _tsPearson(a.slice(0, a.length-k), b.slice(k)); r = res.r; n = res.n; }}
    else {{ const kk = -k; const res = _tsPearson(a.slice(kk), b.slice(0, b.length-kk)); r = res.r; n = res.n; }}
    return {{k, r, n}};
  }});
  // Find max |r|
  let peakIdx = 0, peakAbs = -1;
  rows.forEach((r, i) => {{ if (r.r != null && Math.abs(r.r) > peakAbs) {{ peakAbs = Math.abs(r.r); peakIdx = i; }} }});

  el.innerHTML = `<table style="width:100%;font-size:11px">
    <thead><tr>
      <th style="text-align:center">Lag (Q)</th>
      <th style="text-align:center">r</th>
      <th style="text-align:center">n</th>
      <th></th>
    </tr></thead>
    <tbody>
      ${{rows.map((r,i) => {{
        const r_ = r.r == null ? '—' : fmt(r.r, 2);
        const c = r.r == null ? '#64748b' : (r.r > 0 ? '#2563eb' : '#dc2626');
        const isPeak = i === peakIdx && r.r != null;
        const interp = r.k === 0 ? 'contemporaneous'
                     : r.k > 0  ? `A leads B by ${{r.k}}Q`
                     : `B leads A by ${{-r.k}}Q`;
        return `<tr${{isPeak?' style="background:#fef9c3"':''}}>
          <td style="text-align:center;font-family:monospace">${{r.k>=0?'+':''}}${{r.k}}</td>
          <td style="text-align:center;color:${{c}};font-weight:700">${{r_}}</td>
          <td style="text-align:center;color:var(--text-muted)">${{r.n}}</td>
          <td style="font-size:10px;color:var(--text-muted)">${{interp}}${{isPeak?' <strong style="color:#854d0e">← peak</strong>':''}}</td>
        </tr>`;
      }}).join('')}}
    </tbody>
  </table>
  <div style="margin-top:8px;font-size:10px;color:var(--text-muted);font-style:italic">
    A = ${{labA}} · B = ${{labB}}. Positive lag k means A predicts B by k quarters; negative means B predicts A.
  </div>`;
}}

// ═══════════════════════════════════════════════════════════════
// SECTION G · Naive forecast (OLS extrapolation)
// ═══════════════════════════════════════════════════════════════
function _tsRenderForecast(winQ, wd) {{
  const el = document.getElementById('ts-forecast-chart');
  const metaEl = document.getElementById('ts-forecast-meta');
  if (!el) return;
  const spec = _TS_BY_KEY[TS_FORECAST_KEY];
  const values = wd[TS_FORECAST_KEY];
  // Fit on last 12 visible quarters (or all if fewer)
  const fitN = Math.min(12, values.length);
  const fitStart = values.length - fitN;
  const fitVals = values.slice(fitStart).map((v,i) => ({{x:i, y:v}}));
  const cleanFit = fitVals.filter(p => p.y != null && Number.isFinite(p.y));
  if (cleanFit.length < 3) {{
    el.innerHTML = `<div style="padding:24px;color:var(--gray);font-size:12px;text-align:center">Not enough data in the fit window for a meaningful projection. Switch to Historical or extend the range.</div>`;
    if (metaEl) metaEl.innerHTML = '';
    return;
  }}
  // OLS fit
  const n = cleanFit.length;
  const mx = cleanFit.reduce((s,p)=>s+p.x, 0) / n;
  const my = cleanFit.reduce((s,p)=>s+p.y, 0) / n;
  let num = 0, den = 0;
  for (const p of cleanFit) {{ num += (p.x-mx)*(p.y-my); den += (p.x-mx)*(p.x-mx); }}
  const slope = den ? num/den : 0;
  const intercept = my - slope*mx;
  // Residual std
  let ssRes = 0;
  for (const p of cleanFit) {{
    const yh = slope*p.x + intercept;
    ssRes += (p.y - yh) * (p.y - yh);
  }}
  const sigma = Math.sqrt(ssRes / Math.max(1, n - 2));

  // Build x/y for historical (full visible) + forecast + uncertainty bands
  const xHist = winQ.map(q => qLabel(q));
  const yHist = values.slice();
  // Forecast quarters: extrapolate quarter labels
  const fcLabels = [];
  const lastQ = winQ[winQ.length - 1] || '2025Q4';
  let [yr, qtr] = [parseInt(lastQ.slice(0,4)), parseInt(lastQ.slice(5))];
  for (let h = 1; h <= TS_FORECAST_HORIZON; h++) {{
    qtr += 1;
    if (qtr > 4) {{ qtr = 1; yr += 1; }}
    fcLabels.push(`${{yr}} Q${{qtr}}`);
  }}
  const yFc = [], yFcUp = [], yFcLo = [];
  for (let h = 1; h <= TS_FORECAST_HORIZON; h++) {{
    const xi = fitN - 1 + h;
    const yh = slope * xi + intercept;
    yFc.push(yh);
    yFcUp.push(yh + sigma);
    yFcLo.push(yh - sigma);
  }}

  const PLcfg = {{responsive:true, displayModeBar:false}};
  Plotly.react('ts-forecast-chart', [
    // Historical line
    {{x: xHist, y: yHist, name: 'Historical', type:'scatter', mode:'lines+markers',
      line:{{color: spec.color, width: 2}}, marker:{{size: 3}}, connectgaps: true}},
    // Forecast confidence band (upper)
    {{x: fcLabels, y: yFcUp, name: '+1σ', type:'scatter', mode:'lines',
      line:{{color: spec.color, width: 0}}, showlegend: false, hoverinfo: 'skip'}},
    // Forecast confidence band (lower) with fill
    {{x: fcLabels, y: yFcLo, name: 'Uncertainty band', type:'scatter', mode:'lines',
      line:{{color: spec.color, width: 0}}, fill: 'tonexty', fillcolor: spec.color + '33',
      hovertemplate: 'σ band: %{{y:.3f}}<extra></extra>'}},
    // Forecast line
    {{x: fcLabels, y: yFc, name: `Forecast +${{TS_FORECAST_HORIZON}}Q`, type:'scatter', mode:'lines+markers',
      line:{{color: spec.color, width: 2, dash: 'dash'}}, marker:{{size: 4, symbol: 'diamond'}}}},
  ], {{
    margin:{{t:20,r:20,b:60,l:60}},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    xaxis:{{tickangle:-45, tickfont:{{size:9}}, showgrid: false}},
    yaxis:{{title: spec.label, gridcolor:'#f1f5f9', tickfont:{{size:9}}}},
    legend:{{orientation:'h', y:1.12, font:{{size:10}}}},
    shapes:[
      // Vertical separator at the boundary
      {{type:'line', x0: xHist[xHist.length-1], x1: xHist[xHist.length-1],
        yref:'paper', y0:0, y1:1, line:{{color:'#cbd5e1', width:1, dash:'dot'}}}}
    ],
    annotations:[
      {{x: xHist[xHist.length-1], yref:'paper', y: 1.02,
        text: '← actual · forecast →', showarrow: false,
        font:{{size: 9, color:'#94a3b8'}}, xanchor: 'center'}}
    ],
  }}, PLcfg);

  if (metaEl) {{
    const fitWindowLabel = winQ.length >= fitN ? `${{qLabel(winQ[winQ.length-fitN])}} → ${{qLabel(winQ[winQ.length-1])}}` : 'visible window';
    metaEl.innerHTML = `Fit: OLS on the last <strong>${{n}}</strong> non-null points (${{fitWindowLabel}}) · slope = ${{fmt(slope, 4)}}/Q · residual σ = ${{fmt(sigma, 4)}}. Forecast next ${{TS_FORECAST_HORIZON}} quarters at constant slope.`;
  }}
}}
"""
