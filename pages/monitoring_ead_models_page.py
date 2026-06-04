"""Monitoring EAD Performance page."""

JS = r"""
const EAD_RAG_METRICS = [
  'Actual / Expected EAD',
  'ME',
  'RMSE',
  "Kendall's Tau",
  'CCF',
  'Utilization Rate',
];
const EAD_TIME_RANGES = {
  calibration: 'all',
  error: 'all',
  rag: 'all',
};
let EAD_EXPANDED_PANEL = null;
let EAD_EXPANDED_PLACEHOLDER = null;

function getPreviousEadQuarter(quarter) {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter || '');
  if (!match) return '';
  const year = Number(match[1]);
  const quarterNumber = Number(match[2]);
  return quarterNumber === 1 ? `${year - 1}Q4` : `${year}Q${quarterNumber - 1}`;
}

function getEadPerformanceContext(ead) {
  const horizonYears = MONITORING_TIME_HORIZON === '2y' ? 2 : 1;
  const horizon = (ead.performance_horizons || {})[MONITORING_TIME_HORIZON] || {};
  const snapshotQuarter = shiftMonitoringQuarterYear(CQ, -horizonYears);
  return {
    monitoringPoint: CQ,
    horizonLabel: horizon.label || `${horizonYears} year${horizonYears === 1 ? '' : 's'}`,
    snapshotQuarter,
    previousQuarter: getPreviousEadQuarter(snapshotQuarter),
    predictedColumn: horizon.predicted_column || `EAD_${MONITORING_TIME_HORIZON}_base`,
  };
}

function matchesEadSelectedPopulation(row, quarter) {
  const selectedModels = new Set(MONITORING_MODELS);
  if (row.quarter !== quarter || !selectedModels.has(row.model)) return false;
  return MONITORING_PORTFOLIO_SEGMENT === 'all' || row.segment === MONITORING_PORTFOLIO_SEGMENT;
}

function filterEadPerformanceObservations(observations, quarter) {
  return observations.flatMap(row => {
    if (!matchesEadSelectedPopulation(row, quarter)) return [];
    const horizon = (row.horizons || {})[MONITORING_TIME_HORIZON];
    return horizon ? [{...row, predicted: horizon.predicted}] : [];
  });
}

function calculateEadKendallTau(rows) {
  if (rows.length < 2) return null;
  let concordant = 0;
  let discordant = 0;
  let predictedTies = 0;
  let realizedTies = 0;
  for (let left = 0; left < rows.length; left += 1) {
    for (let right = left + 1; right < rows.length; right += 1) {
      const predictedDelta = rows[left].predicted - rows[right].predicted;
      const observedDelta = rows[left].observed - rows[right].observed;
      if (predictedDelta === 0 && observedDelta === 0) continue;
      if (predictedDelta === 0) predictedTies += 1;
      else if (observedDelta === 0) realizedTies += 1;
      else if (predictedDelta * observedDelta > 0) concordant += 1;
      else discordant += 1;
    }
  }
  const denominator = Math.sqrt(
    (concordant + discordant + predictedTies) * (concordant + discordant + realizedTies),
  );
  return denominator ? (concordant - discordant) / denominator : null;
}

function calculateEadMetrics(rows) {
  if (!rows.length) {
    return {
      observed_ead: null,
      predicted_ead: null,
      actual_expected_ead: null,
      mean_error: null,
      rmse: null,
      kendall_tau: null,
      ccf: null,
      utilization_rate: null,
    };
  }
  const observed = rows.reduce((sum, row) => sum + row.observed, 0);
  const predicted = rows.reduce((sum, row) => sum + row.predicted, 0);
  const errors = rows.map(row => (row.predicted - row.observed) / row.limit);
  const ccfValues = rows
    .filter(row => row.undrawn > 0)
    .map(row => (row.predicted - row.observed) / row.undrawn);
  const utilizationRates = rows.map(row => row.observed / row.limit);
  return {
    observed_ead: observed,
    predicted_ead: predicted,
    actual_expected_ead: predicted ? observed / predicted : null,
    mean_error: errors.reduce((sum, value) => sum + value, 0) / errors.length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value ** 2, 0) / errors.length),
    kendall_tau: calculateEadKendallTau(rows),
    ccf: ccfValues.length ? ccfValues.reduce((sum, value) => sum + value, 0) / ccfValues.length : null,
    utilization_rate: utilizationRates.reduce((sum, value) => sum + value, 0) / utilizationRates.length,
  };
}

function getEadMetricValues(metrics) {
  return {
    'Actual / Expected EAD': metrics.actual_expected_ead,
    'ME': metrics.mean_error,
    'RMSE': metrics.rmse,
    "Kendall's Tau": metrics.kendall_tau,
    'CCF': metrics.ccf,
    'Utilization Rate': metrics.utilization_rate,
  };
}

function calculateEadMetricRag(thresholds, metric, value) {
  if (value == null || !Number.isFinite(value)) return 'N/A';
  const threshold = thresholds.find(row => row.metric === metric);
  if (!threshold) return 'N/A';
  if (threshold.red_condition === 'no_rag') return 'Green';
  if (threshold.red_condition === 'outside amber range') {
    if (value >= threshold.green_min && value <= threshold.green_max) return 'Green';
    if (value >= threshold.amber_min && value <= threshold.amber_max) return 'Amber';
    return 'Red';
  }
  if (threshold.red_condition === 'below amber_min') {
    if (value >= threshold.green_min) return 'Green';
    if (value >= threshold.amber_min) return 'Amber';
    return 'Red';
  }
  if (threshold.red_condition === 'above amber_max') {
    if (value <= threshold.green_max) return 'Green';
    if (value <= threshold.amber_max) return 'Amber';
    return 'Red';
  }
  if (threshold.red_condition === 'abs above amber_max') {
    if (Math.abs(value) <= Math.abs(threshold.green_max)) return 'Green';
    if (Math.abs(value) <= Math.abs(threshold.amber_max)) return 'Amber';
    return 'Red';
  }
  return 'N/A';
}

function getWorstEadRag(rags) {
  const scores = {'N/A': 0, Green: 1, Amber: 2, Red: 3};
  return rags.reduce(
    (worst, rag) => (scores[rag] || 0) > (scores[worst] || 0) ? rag : worst,
    'N/A',
  );
}

function eadToneClass(rag) {
  return rag === 'Green' ? 'green' : rag === 'Amber' ? 'amber' : rag === 'Red' ? 'red' : 'na';
}

function eadRagDot(rag) {
  const css = (rag || 'N/A').toLowerCase().replace('/', '').replace(' ', '-');
  return `<span class="pd-rag-dot pd-rag-${css}" role="img" aria-label="${rag}" title="${rag}">●</span>`;
}

function formatEadMetric(value, format = 'ratio') {
  if (value == null || !Number.isFinite(value)) return '—';
  if (format === 'money') return `$${(value / 1000000).toFixed(1)}m`;
  if (format === 'percent') return `${(value * 100).toFixed(2)}%`;
  return value.toFixed(3);
}

function formatEadChange(current, previous, format = 'ratio') {
  if (current == null || previous == null || !Number.isFinite(current) || !Number.isFinite(previous)) {
    return 'No prior comparison';
  }
  const movement = current - previous;
  if (format === 'money') return `${movement >= 0 ? '+' : '-'}$${(Math.abs(movement) / 1000000).toFixed(1)}m`;
  if (format === 'percent') return `${movement >= 0 ? '+' : ''}${(movement * 100).toFixed(2)} pp`;
  return `${movement >= 0 ? '+' : ''}${movement.toFixed(3)}`;
}

function buildEadTrend(observations, snapshotQuarter) {
  return Array.from(new Set(
    (DASH_DATA.quarters || []).filter(quarter => quarter && quarter <= snapshotQuarter),
  )).sort().map(quarter => ({
    quarter,
    ...calculateEadMetrics(filterEadPerformanceObservations(observations, quarter)),
  }));
}

function filterEadTrend(rangeKey, trend) {
  const window = EAD_TIME_RANGES[rangeKey] || 'all';
  if (window === 'all') return trend;
  const count = Number(window.replace('last-', ''));
  return trend.slice(Math.max(0, trend.length - count));
}

function setEadTrendWindow(rangeKey, value) {
  if (!EAD_TIME_RANGES[rangeKey] || !['all', 'last-4', 'last-8', 'last-12'].includes(value)) return;
  EAD_TIME_RANGES[rangeKey] = value;
  renderEadModels();
}

function buildEadWindowControl(rangeKey) {
  const selected = EAD_TIME_RANGES[rangeKey] || 'all';
  return `<label class="ead-window-control"><span>Window</span>
    <select aria-label="Visible time window" onchange="setEadTrendWindow('${rangeKey}',this.value)">
      <option value="all"${selected === 'all' ? ' selected' : ''}>All periods</option>
      <option value="last-4"${selected === 'last-4' ? ' selected' : ''}>Last 4 quarters</option>
      <option value="last-8"${selected === 'last-8' ? ' selected' : ''}>Last 8 quarters</option>
      <option value="last-12"${selected === 'last-12' ? ' selected' : ''}>Last 12 quarters</option>
    </select>
  </label>`;
}

function eadExpandButton(panelId, title) {
  return `<button type="button" class="pd-expand-button" onclick="openEadExpandedPanel('${panelId}')" aria-label="Enlarge ${title}">
    <span aria-hidden="true">&#x26F6;</span><span>Enlarge</span>
  </button>`;
}

function buildEadChartHeader(title, subtitle, panelId, rangeKey = '') {
  return `<div class="pd-chart-heading">
    <div class="pd-chart-heading-copy">
      <div class="section-title">${title}</div>
      <div class="pd-section-subtitle">${subtitle}</div>
    </div>
    <div class="pd-chart-actions">
      ${rangeKey ? buildEadWindowControl(rangeKey) : ''}
      ${eadExpandButton(panelId, title)}
    </div>
  </div>`;
}

function resizeEadPanelCharts(panel, expanded) {
  if (!panel || typeof Plotly === 'undefined') return;
  panel.querySelectorAll('.js-plotly-plot').forEach(chart => {
    if (!chart.__eadBaseHeight) chart.__eadBaseHeight = (chart.layout && chart.layout.height) || chart.offsetHeight;
    Plotly.relayout(chart, {height: expanded ? Math.max(520, window.innerHeight - 210) : chart.__eadBaseHeight});
    requestAnimationFrame(() => Plotly.Plots.resize(chart));
  });
}

function openEadExpandedPanel(panelId) {
  closeEadExpandedPanel(false);
  const panel = document.getElementById(panelId);
  const modal = document.getElementById('ead-expanded-modal');
  const body = document.getElementById('ead-expanded-modal-body');
  if (!panel || !modal || !body) return;
  EAD_EXPANDED_PANEL = panel;
  EAD_EXPANDED_PLACEHOLDER = document.createComment(`Restore ${panelId}`);
  panel.parentNode.insertBefore(EAD_EXPANDED_PLACEHOLDER, panel);
  document.getElementById('ead-expanded-modal-title').textContent = panel.dataset.eadExpandTitle || 'EAD Analysis';
  body.appendChild(panel);
  panel.classList.add('pd-expanded-panel');
  modal.classList.add('active');
  modal.setAttribute('aria-hidden', 'false');
  document.getElementById('ead-expanded-modal-close').focus();
  requestAnimationFrame(() => resizeEadPanelCharts(panel, true));
}

function closeEadExpandedPanel(restoreFocus = true) {
  const modal = document.getElementById('ead-expanded-modal');
  if (!EAD_EXPANDED_PANEL || !EAD_EXPANDED_PLACEHOLDER) return;
  const panelId = EAD_EXPANDED_PANEL.id;
  resizeEadPanelCharts(EAD_EXPANDED_PANEL, false);
  EAD_EXPANDED_PLACEHOLDER.parentNode.insertBefore(EAD_EXPANDED_PANEL, EAD_EXPANDED_PLACEHOLDER);
  EAD_EXPANDED_PLACEHOLDER.remove();
  EAD_EXPANDED_PANEL.classList.remove('pd-expanded-panel');
  EAD_EXPANDED_PANEL = null;
  EAD_EXPANDED_PLACEHOLDER = null;
  if (modal) {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
  }
  if (restoreFocus) {
    const button = document.querySelector(`[onclick="openEadExpandedPanel('${panelId}')"]`);
    if (button) button.focus();
  }
}

function drawEadCalibrationTrend(observations, snapshotQuarter) {
  const trend = filterEadTrend('calibration', buildEadTrend(observations, snapshotQuarter));
  const quarters = trend.map(row => row.quarter);
  Plotly.react('ead-calibration-trend-chart', [
    {x: quarters, y: trend.map(row => row.observed_ead), type: 'scatter', mode: 'lines+markers', name: 'Observed Balance', line: {color: '#dc2626', width: 2.5}, hovertemplate: '%{x}<br>Observed Balance: $%{y:,.0f}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.predicted_ead), type: 'scatter', mode: 'lines+markers', name: 'Predicted EAD', line: {color: '#2563eb', width: 2.5, dash: 'dash'}, hovertemplate: '%{x}<br>Predicted EAD: $%{y:,.0f}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.actual_expected_ead), type: 'scatter', mode: 'lines+markers', name: 'Actual / Expected EAD', yaxis: 'y2', line: {color: '#d97706', width: 2.5}, hovertemplate: '%{x}<br>A / E EAD: %{y:.3f}<extra></extra>'},
  ], {
    height: 390, margin: {t: 18, r: 64, b: 52, l: 62}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified', legend: {orientation: 'h', x: 0, y: 1.14},
    xaxis: {title: 'Portfolio Quarter', type: 'category', gridcolor: '#e5e7eb'},
    yaxis: {title: 'Exposure Amount', tickprefix: '$', tickformat: '~s', rangemode: 'tozero', gridcolor: '#e5e7eb'},
    yaxis2: {title: 'A / E', overlaying: 'y', side: 'right', rangemode: 'tozero'},
  }, {responsive: true, displayModeBar: false});
}

function drawEadErrorTrend(observations, snapshotQuarter) {
  const trend = filterEadTrend('error', buildEadTrend(observations, snapshotQuarter));
  const quarters = trend.map(row => row.quarter);
  Plotly.react('ead-error-trend-chart', [
    {x: quarters, y: trend.map(row => row.mean_error), type: 'scatter', mode: 'lines+markers', name: 'Mean Error', line: {color: '#0891b2', width: 2.5}, hovertemplate: '%{x}<br>Mean Error: %{y:.3f}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.rmse), type: 'scatter', mode: 'lines+markers', name: 'RMSE', line: {color: '#ea580c', width: 2.5, dash: 'dash'}, hovertemplate: '%{x}<br>RMSE: %{y:.3f}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.kendall_tau), type: 'scatter', mode: 'lines+markers', name: "Kendall's Tau", yaxis: 'y2', line: {color: '#7c3aed', width: 2.5, dash: 'dot'}, hovertemplate: "%{x}<br>Kendall's Tau: %{y:.3f}<extra></extra>"},
  ], {
    height: 360, margin: {t: 18, r: 78, b: 52, l: 62}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified', legend: {orientation: 'h', x: 0, y: 1.14},
    xaxis: {title: 'Portfolio Quarter', type: 'category', gridcolor: '#e5e7eb'},
    yaxis: {title: 'Error', gridcolor: '#e5e7eb'},
    yaxis2: {title: "Kendall's Tau", overlaying: 'y', side: 'right'},
  }, {responsive: true, displayModeBar: false});
}

function drawEadByRating(observations, snapshotQuarter) {
  const rows = filterEadPerformanceObservations(observations, snapshotQuarter);
  const byRating = new Map();
  rows.forEach(row => {
    const rating = row.rating || 'N/A';
    if (!byRating.has(rating)) byRating.set(rating, {actual: 0, predicted: 0, count: 0});
    const item = byRating.get(rating);
    item.actual += row.observed;
    item.predicted += row.predicted;
    item.count += 1;
  });
  const ratings = Array.from(byRating.keys()).sort((a,b) => Number(a) - Number(b));
  const summaries = ratings.map(rating => byRating.get(rating));
  Plotly.react('ead-rating-chart', [
    {x: ratings, y: summaries.map(row => row.actual), type: 'bar', name: 'Observed Balance', marker: {color: '#dc2626'}, hovertemplate: 'Rating %{x}<br>Observed Balance: $%{y:,.0f}<extra></extra>'},
    {x: ratings, y: summaries.map(row => row.predicted), type: 'bar', name: 'Predicted EAD', marker: {color: '#2563eb'}, hovertemplate: 'Rating %{x}<br>Predicted EAD: $%{y:,.0f}<extra></extra>'},
  ], {
    height: 310, margin: {t: 12, r: 18, b: 48, l: 62}, barmode: 'group', paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    legend: {orientation: 'h', x: 0, y: 1.16}, xaxis: {title: 'Rating Grade', type: 'category'}, yaxis: {title: 'Exposure Amount', tickprefix: '$', tickformat: '~s', rangemode: 'tozero', gridcolor: '#e5e7eb'},
  }, {responsive: true, displayModeBar: false});
}

function drawEadDistributionShift(observations, snapshotQuarter, previousQuarter) {
  const current = filterEadPerformanceObservations(observations, snapshotQuarter);
  const previous = filterEadPerformanceObservations(observations, previousQuarter);
  Plotly.react('ead-distribution-chart', [
    {x: previous.map(row => row.predicted), type: 'histogram', histnorm: 'probability', nbinsx: 12, name: previousQuarter, opacity: .65, marker: {color: '#64748b'}, hovertemplate: 'Predicted EAD: $%{x:,.0f}<br>Share: %{y:.1%}<extra></extra>'},
    {x: current.map(row => row.predicted), type: 'histogram', histnorm: 'probability', nbinsx: 12, name: snapshotQuarter, opacity: .65, marker: {color: '#2563eb'}, hovertemplate: 'Predicted EAD: $%{x:,.0f}<br>Share: %{y:.1%}<extra></extra>'},
  ], {
    height: 310, margin: {t: 12, r: 18, b: 48, l: 62}, barmode: 'overlay', paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    legend: {orientation: 'h', x: 0, y: 1.16}, xaxis: {title: 'Predicted EAD', tickprefix: '$', tickformat: '~s', gridcolor: '#e5e7eb'}, yaxis: {title: 'Portfolio Share', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'},
  }, {responsive: true, displayModeBar: false});
}

function buildEadRagHistory(ead, context) {
  const thresholds = ((DASH_DATA.monitoring_thresholds || {}).ead_thresholds || []);
  const trend = filterEadTrend('rag', buildEadTrend(ead.performance_observations || [], context.snapshotQuarter));
  const rows = EAD_RAG_METRICS.map(metric => `<tr>
    <td>${metric}</td>
    ${trend.map(item => `<td>${eadRagDot(calculateEadMetricRag(thresholds, metric, getEadMetricValues(item)[metric]))}</td>`).join('')}
  </tr>`).join('');
  return `<div id="ead-rag-panel" class="section-card pd-rag-section" data-ead-expand-title="EAD RAG Monitoring History">
    <div class="pd-section-heading">
      <div><div class="section-title">EAD RAG Monitoring History</div><div class="pd-section-subtitle">Threshold status through ${context.snapshotQuarter}.</div></div>
      <div class="pd-section-actions">${buildEadWindowControl('rag')}${eadExpandButton('ead-rag-panel', 'EAD RAG Monitoring History')}</div>
    </div>
    <div class="pd-rag-table-wrap"><table class="pd-rag-table"><thead><tr><th>Metric</th>${trend.map(row => `<th>${row.quarter}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>
    <div class="pd-rag-legend"><span>${eadRagDot('Green')} Within threshold</span><span>${eadRagDot('Amber')} Monitor closely</span><span>${eadRagDot('Red')} Action required</span><span>${eadRagDot('N/A')} Insufficient data</span></div>
  </div>`;
}

function renderEadModels() {
  closeEadExpandedPanel(false);
  const ead = (DASH_DATA.monitoring || {}).ead_models || {};
  const observations = ead.performance_observations || [];
  const context = getEadPerformanceContext(ead);
  const currentRows = filterEadPerformanceObservations(observations, context.snapshotQuarter);
  const previousRows = filterEadPerformanceObservations(observations, context.previousQuarter);
  const current = calculateEadMetrics(currentRows);
  const previous = calculateEadMetrics(previousRows);
  const thresholds = ((DASH_DATA.monitoring_thresholds || {}).ead_thresholds || []);
  const values = getEadMetricValues(current);
  const overallRag = getWorstEadRag(EAD_RAG_METRICS.map(metric => calculateEadMetricRag(thresholds, metric, values[metric])));
  const segmentLabel = MONITORING_PORTFOLIO_SEGMENT === 'all' ? 'All segments' : MONITORING_PORTFOLIO_SEGMENT;
  const metricCards = [
    ['observed_ead', 'Observed Balance', 'money', 'calibration'],
    ['predicted_ead', 'Predicted EAD', 'money', 'calibration'],
    ['actual_expected_ead', 'Actual / Expected EAD', 'ratio', 'calibration'],
    ['mean_error', 'Mean Error', 'ratio', 'performance'],
    ['rmse', 'RMSE', 'ratio', 'performance'],
    ['kendall_tau', "Kendall's Tau", 'ratio', 'rank ordering'],
    ['ccf', 'CCF', 'percent', 'reference'],
    ['utilization_rate', 'Utilization Rate', 'percent', 'reference'],
  ].map(([key, title, format, group]) => `<div class="pd-performance-card pd-card-calibration">
    <div class="pd-performance-title">${title}</div>
    <div class="pd-performance-value">${formatEadMetric(current[key], format)}</div>
    <div class="pd-performance-detail"><span>${group}</span> · Snapshot date: ${context.snapshotQuarter}</div>
    <div class="pd-performance-comparison"><div><span>Previous (${context.previousQuarter})</span><strong>${formatEadMetric(previous[key], format)}</strong></div><div><span>Change</span><strong>${formatEadChange(current[key], previous[key], format)}</strong></div></div>
  </div>`).join('');

  document.getElementById('tab-ead_models').innerHTML = `
    <div class="dash-header pd-page-header">
      <div><h2>EAD Performance Summary — ${monitoringPointLabel()}</h2><p>Monitor exposure projections, calibration, normalized forecast error, rank ordering, CCF, and utilization.</p></div>
      <div class="pd-overall-status pd-overall-${eadToneClass(overallRag)}"><span>Overall RAG Status</span><strong>${eadRagDot(overallRag)} ${overallRag}</strong></div>
    </div>
    <nav class="pd-section-nav" aria-label="EAD performance sections"><a href="#ead-overview">Overview</a><a href="#ead-trends">Trends</a><a href="#ead-rag">RAG History</a></nav>
    <section id="ead-overview" class="pd-content-section pd-overview-section">
      <div class="pd-content-heading"><div class="pd-content-kicker">Executive Overview</div><h3>EAD Analysis Scope</h3><p>Start with exposure calibration and normalized error metrics, then inspect trends and threshold history.</p></div>
      <div class="pd-scope-bar">
        <div><span>Monitoring Point</span><strong>${CQ}</strong></div><div><span>Time Horizon</span><strong>${context.horizonLabel}</strong></div>
        <div class="pd-scope-snapshot"><span>Snapshot Date</span><strong>${context.snapshotQuarter}</strong></div><div><span>Previous Quarter</span><strong>${context.previousQuarter}</strong></div><div><span>Segment</span><strong>${segmentLabel}</strong></div>
        <div><span>EAD Models Selected</span><strong>${fmtN(MONITORING_MODELS.length)}</strong></div><div><span>Current Records</span><strong>${fmtN(currentRows.length)}</strong></div>
      </div>
      <div class="pd-filter-application-note"><strong>Applied to this analysis:</strong> monitoring point, time horizon, segment, and selected EAD models.</div>
      <div class="pd-performance-note pd-data-note"><strong>Observed exposure assumption:</strong> ${ead.observation_basis || 'Balance (current drawn exposure proxy)'}. ME and RMSE are normalized by facility limit so they can be evaluated against the configured EAD thresholds.</div>
      <div class="pd-content-heading pd-metric-heading"><div class="pd-content-kicker">Core Metrics</div><h3>Snapshot Date vs. Previous Quarter</h3></div>
      <div class="pd-performance-grid ead-kpi-grid">${metricCards}</div>
    </section>
    <section id="ead-trends" class="pd-content-section">
      <div class="pd-content-heading"><div class="pd-content-kicker">Trends</div><h3>Performance Through the Snapshot Date</h3><p>Use trend windows to focus the analysis on the period that matters.</p></div>
      <div class="pd-primary-analysis-grid">
        <div id="ead-calibration-panel" class="section-card" data-ead-expand-title="EAD Calibration Trend">${buildEadChartHeader('EAD Calibration Trend','Observed balance proxy versus predicted EAD and the Actual / Expected ratio.','ead-calibration-panel','calibration')}<div id="ead-calibration-trend-chart" class="pd-default-rate-trend-chart"></div></div>
        <div id="ead-error-panel" class="section-card" data-ead-expand-title="EAD Error and Rank-Ordering Trend">${buildEadChartHeader('Error and Rank-Ordering Trend',"Mean Error, RMSE, and Kendall's Tau through the snapshot date.",'ead-error-panel','error')}<div id="ead-error-trend-chart" class="pd-stability-trend-chart"></div></div>
      </div>
      <div class="pd-trend-detail-grid">
        <div id="ead-rating-panel" class="section-card" data-ead-expand-title="Observed vs. Predicted EAD by Rating Grade">${buildEadChartHeader('Observed vs. Predicted EAD by Rating Grade',`Calibration comparison at ${context.snapshotQuarter}.`,'ead-rating-panel')}<div id="ead-rating-chart" class="pd-rating-default-rate-chart"></div></div>
        <div id="ead-distribution-panel" class="section-card" data-ead-expand-title="Predicted EAD Distribution Shift">${buildEadChartHeader('Predicted EAD Distribution Shift',`Portfolio comparison for ${context.previousQuarter} and ${context.snapshotQuarter}.`,'ead-distribution-panel')}<div id="ead-distribution-chart" class="pd-distribution-shift-chart"></div></div>
      </div>
    </section>
    <section id="ead-rag" class="pd-content-section"><div class="pd-content-heading"><div class="pd-content-kicker">RAG History</div><h3>Threshold Monitoring by Metric</h3></div>${buildEadRagHistory(ead, context)}</section>
    <div id="ead-expanded-modal" class="pd-expanded-modal" aria-hidden="true" onclick="if(event.target===this) closeEadExpandedPanel()" onkeydown="if(event.key==='Escape') closeEadExpandedPanel()">
      <div class="pd-expanded-dialog" role="dialog" aria-modal="true" aria-labelledby="ead-expanded-modal-title"><div class="pd-expanded-modal-header"><div><span>Expanded Analysis</span><strong id="ead-expanded-modal-title">EAD Analysis</strong></div><button type="button" id="ead-expanded-modal-close" class="pd-expanded-close" onclick="closeEadExpandedPanel()">Close</button></div><div id="ead-expanded-modal-body" class="pd-expanded-modal-body"></div></div>
    </div>`;

  drawEadCalibrationTrend(observations, context.snapshotQuarter);
  drawEadErrorTrend(observations, context.snapshotQuarter);
  drawEadByRating(observations, context.snapshotQuarter);
  drawEadDistributionShift(observations, context.snapshotQuarter, context.previousQuarter);
}
"""
