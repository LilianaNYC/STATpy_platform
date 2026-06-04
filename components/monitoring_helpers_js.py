"""JavaScript helpers used only by the model monitoring dashboard."""

JS = r"""
// ── MONITORING HELPERS ─────────────────────────────────────────
const fmtN = (v) => v == null ? '—' : (+v).toLocaleString('en-US');

function qLabel(q) {
  return q ? q.slice(0,4)+' Q'+q[5] : '';
}

function monitoringPointLabel() {
  return CQ || '';
}

function shiftMonitoringQuarterYear(quarter, yearDelta) {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter || '');
  if (!match) return '';
  return `${Number(match[1]) + yearDelta}Q${match[2]}`;
}
"""
