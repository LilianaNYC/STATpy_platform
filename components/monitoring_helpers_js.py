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

function getMonitoringChartWidth(chart, panelFraction = 1) {
  const rawWidth = (chart && (chart.clientWidth || chart.offsetWidth))
    || window.innerWidth
    || 960;
  const safePanelFraction = Number.isFinite(panelFraction) && panelFraction > 0 && panelFraction <= 1
    ? panelFraction
    : 1;
  return Math.max(rawWidth * safePanelFraction, 240);
}

function getMonitoringTimeSeriesMaxTicks(chartWidth, density = 'normal') {
  let maxTicks;
  if (chartWidth <= 360) maxTicks = 4;
  else if (chartWidth <= 460) maxTicks = 5;
  else if (chartWidth <= 620) maxTicks = 6;
  else if (chartWidth <= 760) maxTicks = 7;
  else if (chartWidth <= 920) maxTicks = 8;
  else if (chartWidth <= 1100) maxTicks = 10;
  else maxTicks = 12;

  if (density === 'compact') return Math.max(4, maxTicks - 2);
  if (density === 'roomy') return Math.max(maxTicks, 10);
  return maxTicks;
}

function buildMonitoringTimeSeriesTickValues(labels, maxTicks) {
  const categories = Array.from(new Set((labels || []).map(value => String(value || '')).filter(Boolean)));
  if (!categories.length || categories.length <= maxTicks) return categories;

  const step = Math.max(2, Math.ceil(categories.length / maxTicks));
  const tickvals = categories.filter((value, index) => (
    index === 0
    || index === categories.length - 1
    || index % step === 0
  ));
  return Array.from(new Set(tickvals));
}

function buildMonitoringTimeSeriesXAxis(labels, baseConfig = {}, options = {}) {
  const categories = Array.from(new Set((labels || []).map(value => String(value || '')).filter(Boolean)));
  const {tickfont: baseTickfont = {}, ...baseAxis} = baseConfig || {};
  const axis = {...baseAxis, type: baseAxis.type || 'category'};
  if (axis.showticklabels === false || options.showticklabels === false || !categories.length) {
    return {...axis, automargin: true};
  }

  const chartWidth = getMonitoringChartWidth(options.chart, options.panelFraction);
  const maxTicks = Number.isFinite(options.maxTicks)
    ? options.maxTicks
    : getMonitoringTimeSeriesMaxTicks(chartWidth, options.density || 'normal');
  const tickvals = buildMonitoringTimeSeriesTickValues(categories, maxTicks);
  const isDense = tickvals.length < categories.length;
  const tickfont = {
    size: isDense ? 10 : 11,
    ...baseTickfont,
  };

  return {
    ...axis,
    tickmode: 'array',
    tickvals,
    ticktext: tickvals,
    tickangle: options.tickangle ?? baseAxis.tickangle ?? (isDense ? -32 : 0),
    automargin: true,
    tickfont,
  };
}
"""
