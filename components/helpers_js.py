"""Shared JS helpers (formatters, badges, qLabel, etc.). Module-level constant.

Stored as a raw string so braces are literal — used directly by renderer.py.
"""

JS = r"""
// ── HELPERS ────────────────────────────────────────────────────
const fmt  = (v, d=2) => v == null ? '—' : (+v).toLocaleString('en-US', {minimumFractionDigits:d,maximumFractionDigits:d});
const fmtN = (v)      => v == null ? '—' : (+v).toLocaleString('en-US');
const fmtB = (v)      => v == null ? '—' : '$'+fmt(v,3)+'B';
const pct  = (v, d=1) => v == null ? '—' : fmt(v,d)+'%';
const arrow = (d, good=true) => {
  if (d == null || d === 0) return '<span class="delta-neu">—</span>';
  const cls = (d>0) === good ? 'delta-up' : 'delta-dn';
  return `<span class="${cls}">${d>0?'▲':'▼'} ${Math.abs(d).toLocaleString('en-US',{maximumFractionDigits:2})}</span>`;
};
const badge = (sev) => {
  const m = {Critical:'critical',High:'high',Medium:'medium',Low:'low',
              Open:'open','In Progress':'progress',Resolved:'resolved',
              Stable:'green',Elevated:'amber',Critical_:'red',
              GREEN:'green',MODERATE:'amber',RED:'red',
              'No Drift':'green',Minor:'low',Moderate:'medium',High:'high'};
  const cls = m[sev] || 'gray';
  return `<span class="badge badge-${cls}">${sev}</span>`;
};
const hm = (psi) => {
  if (psi >= 0.50) return `<td class="hm-cell hm-high">${fmt(psi,2)}</td>`;
  if (psi >= 0.20) return `<td class="hm-cell hm-moderate">${fmt(psi,2)}</td>`;
  if (psi >= 0.10) return `<td class="hm-cell hm-minor">${fmt(psi,2)}</td>`;
  return `<td class="hm-cell hm-none">${fmt(psi,2)}</td>`;
};
const completenessCell = (pct) => {
  if (pct === 0) return `<td class="cell-none">0.0%</td>`;
  if (pct >= 25)  return `<td class="cell-critical">${fmt(pct,1)}%</td>`;
  if (pct >= 10)  return `<td class="cell-high">${fmt(pct,1)}%</td>`;
  if (pct >= 5)   return `<td class="cell-medium">${fmt(pct,1)}%</td>`;
  if (pct >= 1)   return `<td class="cell-low">${fmt(pct,1)}%</td>`;
  return `<td>${fmt(pct,1)}%</td>`;
};
const spark = (vals) => {
  if (!vals || !vals.length) return '—';
  const min=Math.min(...vals), max=Math.max(...vals);
  const bars = ['▁','▂','▃','▄','▅','▆','▇','█'];
  return vals.map(v => bars[Math.round((v-min)/(max-min+1e-9)*(bars.length-1))]).join('');
};
const H = (strings, ...vals) => strings.reduce((r,s,i)=>r+s+(vals[i]??''),'');

function qLabel(q) { return q ? q.slice(0,4)+' Q'+q[5] : ''; }
function getQData(q) { return DASH_DATA.by_quarter[q] || {}; }
function getQoQ(q) { return (DASH_DATA.by_quarter[q]||{}).qoq || {}; }
"""
