"""Monitoring LGD Performance page."""

JS = r"""
const LGD_RAG_METRICS = [
  'Actual / Expected LGD',
  'ME',
  'RMSE',
  "Kendall's Tau",
  'Recovery Rate',
];
const LGD_TIME_RANGES = {
  calibration: 'all',
  error: 'all',
  rag: 'all',
};
let LGD_EXPANDED_PANEL = null;
let LGD_EXPANDED_PLACEHOLDER = null;

function getPreviousLgdQuarter(quarter) {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter || '');
  if (!match) return '';
  const year = Number(match[1]);
  const quarterNumber = Number(match[2]);
  return quarterNumber === 1 ? `${year - 1}Q4` : `${year}Q${quarterNumber - 1}`;
}

function getLgdPerformanceContext(lgd) {
  const horizonYears = MONITORING_TIME_HORIZON === '2y' ? 2 : 1;
  const horizon = (lgd.performance_horizons || {})[MONITORING_TIME_HORIZON] || {};
  const snapshotQuarter = shiftMonitoringQuarterYear(CQ, -horizonYears);
  return {
    monitoringPoint: CQ,
    horizonLabel: horizon.label || `${horizonYears} year${horizonYears === 1 ? '' : 's'}`,
    snapshotQuarter,
    previousQuarter: getPreviousLgdQuarter(snapshotQuarter),
    predictedColumn: horizon.predicted_column || `LGD_${MONITORING_TIME_HORIZON}_base`,
  };
}

function matchesLgdSelectedPopulation(row, quarter) {
  const selectedModels = new Set(MONITORING_MODELS);
  if (row.quarter !== quarter || !selectedModels.has(row.model)) return false;
  return MONITORING_PORTFOLIO_SEGMENT === 'all' || row.segment === MONITORING_PORTFOLIO_SEGMENT;
}

function filterLgdPerformanceObservations(observations, quarter) {
  return observations.flatMap(row => {
    if (!matchesLgdSelectedPopulation(row, quarter)) return [];
    const horizon = (row.horizons || {})[MONITORING_TIME_HORIZON];
    return horizon ? [{...row, predicted: horizon.predicted}] : [];
  });
}

function calculateLgdKendallTau(rows) {
  if (rows.length < 2) return null;
  let concordant = 0;
  let discordant = 0;
  let predictedTies = 0;
  let realizedTies = 0;
  for (let left = 0; left < rows.length; left += 1) {
    for (let right = left + 1; right < rows.length; right += 1) {
      const predictedDelta = rows[left].predicted - rows[right].predicted;
      const realizedDelta = rows[left].realized - rows[right].realized;
      if (predictedDelta === 0 && realizedDelta === 0) continue;
      if (predictedDelta === 0) predictedTies += 1;
      else if (realizedDelta === 0) realizedTies += 1;
      else if (predictedDelta * realizedDelta > 0) concordant += 1;
      else discordant += 1;
    }
  }
  const denominator = Math.sqrt(
    (concordant + discordant + predictedTies) * (concordant + discordant + realizedTies),
  );
  return denominator ? (concordant - discordant) / denominator : null;
}

function calculateLgdMetrics(rows) {
  if (!rows.length) {
    return {
      actual_lgd: null,
      predicted_lgd: null,
      actual_expected_lgd: null,
      mean_error: null,
      rmse: null,
      kendall_tau: null,
      recovery_rate: null,
    };
  }
  const actual = rows.reduce((sum, row) => sum + row.realized, 0) / rows.length;
  const predicted = rows.reduce((sum, row) => sum + row.predicted, 0) / rows.length;
  const errors = rows.map(row => row.predicted - row.realized);
  return {
    actual_lgd: actual,
    predicted_lgd: predicted,
    actual_expected_lgd: predicted ? actual / predicted : null,
    mean_error: errors.reduce((sum, value) => sum + value, 0) / errors.length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value ** 2, 0) / errors.length),
    kendall_tau: calculateLgdKendallTau(rows),
    recovery_rate: 1 - actual,
  };
}

function getLgdMetricValues(metrics) {
  return {
    'Actual / Expected LGD': metrics.actual_expected_lgd,
    'ME': metrics.mean_error,
    'RMSE': metrics.rmse,
    "Kendall's Tau": metrics.kendall_tau,
    'Recovery Rate': metrics.recovery_rate,
  };
}

function calculateLgdMetricRag(thresholds, metric, value) {
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

function getWorstLgdRag(rags) {
  const scores = {'N/A': 0, Green: 1, Amber: 2, Red: 3};
  return rags.reduce(
    (worst, rag) => (scores[rag] || 0) > (scores[worst] || 0) ? rag : worst,
    'N/A',
  );
}

function lgdToneClass(rag) {
  return rag === 'Green' ? 'green' : rag === 'Amber' ? 'amber' : rag === 'Red' ? 'red' : 'na';
}

function lgdRagDot(rag) {
  const css = (rag || 'N/A').toLowerCase().replace('/', '').replace(' ', '-');
  return `<span class="pd-rag-dot pd-rag-${css}" role="img" aria-label="${rag}" title="${rag}">●</span>`;
}

function formatLgdMetric(value, format = 'ratio') {
  if (value == null || !Number.isFinite(value)) return '—';
  if (format === 'percent') return `${(value * 100).toFixed(2)}%`;
  return value.toFixed(3);
}

function formatLgdChange(current, previous, format = 'ratio') {
  if (current == null || previous == null || !Number.isFinite(current) || !Number.isFinite(previous)) {
    return 'No prior comparison';
  }
  const movement = current - previous;
  if (format === 'percent') return `${movement >= 0 ? '+' : ''}${(movement * 100).toFixed(2)} pp`;
  return `${movement >= 0 ? '+' : ''}${movement.toFixed(3)}`;
}

function buildLgdTrend(observations, snapshotQuarter) {
  return Array.from(new Set(
    (DASH_DATA.quarters || []).filter(quarter => quarter && quarter <= snapshotQuarter),
  )).sort().map(quarter => ({
    quarter,
    ...calculateLgdMetrics(filterLgdPerformanceObservations(observations, quarter)),
  }));
}

function filterLgdTrend(rangeKey, trend) {
  const window = LGD_TIME_RANGES[rangeKey] || 'all';
  if (window === 'all') return trend;
  const count = Number(window.replace('last-', ''));
  return trend.slice(Math.max(0, trend.length - count));
}

function setLgdTrendWindow(rangeKey, value) {
  if (!LGD_TIME_RANGES[rangeKey] || !['all', 'last-4', 'last-8', 'last-12'].includes(value)) return;
  LGD_TIME_RANGES[rangeKey] = value;
  renderLgdModels();
}

function buildLgdWindowControl(rangeKey) {
  const selected = LGD_TIME_RANGES[rangeKey] || 'all';
  return `<label class="lgd-window-control"><span>Window</span>
    <select aria-label="Visible time window" onchange="setLgdTrendWindow('${rangeKey}',this.value)">
      <option value="all"${selected === 'all' ? ' selected' : ''}>All periods</option>
      <option value="last-4"${selected === 'last-4' ? ' selected' : ''}>Last 4 quarters</option>
      <option value="last-8"${selected === 'last-8' ? ' selected' : ''}>Last 8 quarters</option>
      <option value="last-12"${selected === 'last-12' ? ' selected' : ''}>Last 12 quarters</option>
    </select>
  </label>`;
}

function lgdExpandButton(panelId, title) {
  return `<button type="button" class="pd-expand-button" onclick="openLgdExpandedPanel('${panelId}')" aria-label="Enlarge ${title}">
    <span aria-hidden="true">&#x26F6;</span><span>Enlarge</span>
  </button>`;
}

function buildLgdChartHeader(title, subtitle, panelId, rangeKey = '') {
  return `<div class="pd-chart-heading">
    <div class="pd-chart-heading-copy">
      <div class="section-title">${title}</div>
      <div class="pd-section-subtitle">${subtitle}</div>
    </div>
    <div class="pd-chart-actions">
      ${rangeKey ? buildLgdWindowControl(rangeKey) : ''}
      ${lgdExpandButton(panelId, title)}
    </div>
  </div>`;
}

function resizeLgdPanelCharts(panel, expanded) {
  if (!panel || typeof Plotly === 'undefined') return;
  panel.querySelectorAll('.js-plotly-plot').forEach(chart => {
    if (!chart.__lgdBaseHeight) chart.__lgdBaseHeight = (chart.layout && chart.layout.height) || chart.offsetHeight;
    Plotly.relayout(chart, {height: expanded ? Math.max(520, window.innerHeight - 210) : chart.__lgdBaseHeight});
    requestAnimationFrame(() => Plotly.Plots.resize(chart));
  });
}

function openLgdExpandedPanel(panelId) {
  closeLgdExpandedPanel(false);
  const panel = document.getElementById(panelId);
  const modal = document.getElementById('lgd-expanded-modal');
  const body = document.getElementById('lgd-expanded-modal-body');
  if (!panel || !modal || !body) return;
  LGD_EXPANDED_PANEL = panel;
  LGD_EXPANDED_PLACEHOLDER = document.createComment(`Restore ${panelId}`);
  panel.parentNode.insertBefore(LGD_EXPANDED_PLACEHOLDER, panel);
  document.getElementById('lgd-expanded-modal-title').textContent = panel.dataset.lgdExpandTitle || 'LGD Analysis';
  body.appendChild(panel);
  panel.classList.add('pd-expanded-panel');
  modal.classList.add('active');
  modal.setAttribute('aria-hidden', 'false');
  document.getElementById('lgd-expanded-modal-close').focus();
  requestAnimationFrame(() => resizeLgdPanelCharts(panel, true));
}

function closeLgdExpandedPanel(restoreFocus = true) {
  const modal = document.getElementById('lgd-expanded-modal');
  if (!LGD_EXPANDED_PANEL || !LGD_EXPANDED_PLACEHOLDER) return;
  const panelId = LGD_EXPANDED_PANEL.id;
  resizeLgdPanelCharts(LGD_EXPANDED_PANEL, false);
  LGD_EXPANDED_PLACEHOLDER.parentNode.insertBefore(LGD_EXPANDED_PANEL, LGD_EXPANDED_PLACEHOLDER);
  LGD_EXPANDED_PLACEHOLDER.remove();
  LGD_EXPANDED_PANEL.classList.remove('pd-expanded-panel');
  LGD_EXPANDED_PANEL = null;
  LGD_EXPANDED_PLACEHOLDER = null;
  if (modal) {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
  }
  if (restoreFocus) {
    const button = document.querySelector(`[onclick="openLgdExpandedPanel('${panelId}')"]`);
    if (button) button.focus();
  }
}

function drawLgdCalibrationTrend(observations, snapshotQuarter) {
  const trend = filterLgdTrend('calibration', buildLgdTrend(observations, snapshotQuarter));
  const quarters = trend.map(row => row.quarter);
  Plotly.react('lgd-calibration-trend-chart', [
    {x: quarters, y: trend.map(row => row.actual_lgd), type: 'scatter', mode: 'lines+markers', name: 'Actual LGD', line: {color: '#dc2626', width: 2.5}, hovertemplate: '%{x}<br>Actual LGD: %{y:.2%}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.predicted_lgd), type: 'scatter', mode: 'lines+markers', name: 'Predicted LGD', line: {color: '#2563eb', width: 2.5, dash: 'dash'}, hovertemplate: '%{x}<br>Predicted LGD: %{y:.2%}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.actual_expected_lgd), type: 'scatter', mode: 'lines+markers', name: 'Actual / Expected LGD', yaxis: 'y2', line: {color: '#d97706', width: 2.5}, hovertemplate: '%{x}<br>A / E LGD: %{y:.3f}<extra></extra>'},
  ], {
    height: 390, margin: {t: 18, r: 64, b: 52, l: 62}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified', legend: {orientation: 'h', x: 0, y: 1.14},
    xaxis: {title: 'Portfolio Quarter', type: 'category', gridcolor: '#e5e7eb'},
    yaxis: {title: 'LGD', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'},
    yaxis2: {title: 'A / E', overlaying: 'y', side: 'right', rangemode: 'tozero'},
  }, {responsive: true, displayModeBar: false});
}

function drawLgdErrorTrend(observations, snapshotQuarter) {
  const trend = filterLgdTrend('error', buildLgdTrend(observations, snapshotQuarter));
  const quarters = trend.map(row => row.quarter);
  Plotly.react('lgd-error-trend-chart', [
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

function drawLgdByRating(observations, snapshotQuarter) {
  const rows = filterLgdPerformanceObservations(observations, snapshotQuarter);
  const byRating = new Map();
  rows.forEach(row => {
    const rating = row.rating || 'N/A';
    if (!byRating.has(rating)) byRating.set(rating, {actual: 0, predicted: 0, count: 0});
    const item = byRating.get(rating);
    item.actual += row.realized;
    item.predicted += row.predicted;
    item.count += 1;
  });
  const ratings = Array.from(byRating.keys()).sort((a,b) => Number(a) - Number(b));
  const summaries = ratings.map(rating => byRating.get(rating));
  Plotly.react('lgd-rating-chart', [
    {x: ratings, y: summaries.map(row => row.actual / row.count), type: 'bar', name: 'Actual LGD', marker: {color: '#dc2626'}, hovertemplate: 'Rating %{x}<br>Actual LGD: %{y:.2%}<extra></extra>'},
    {x: ratings, y: summaries.map(row => row.predicted / row.count), type: 'bar', name: 'Predicted LGD', marker: {color: '#2563eb'}, hovertemplate: 'Rating %{x}<br>Predicted LGD: %{y:.2%}<extra></extra>'},
  ], {
    height: 310, margin: {t: 12, r: 18, b: 48, l: 62}, barmode: 'group', paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    legend: {orientation: 'h', x: 0, y: 1.16}, xaxis: {title: 'Rating Grade', type: 'category'}, yaxis: {title: 'LGD', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'},
  }, {responsive: true, displayModeBar: false});
}

function drawLgdDistributionShift(observations, snapshotQuarter, previousQuarter) {
  const current = filterLgdPerformanceObservations(observations, snapshotQuarter);
  const previous = filterLgdPerformanceObservations(observations, previousQuarter);
  Plotly.react('lgd-distribution-chart', [
    {x: previous.map(row => row.predicted), type: 'histogram', histnorm: 'probability', nbinsx: 12, name: previousQuarter, opacity: .65, marker: {color: '#64748b'}, hovertemplate: 'Predicted LGD: %{x:.2%}<br>Share: %{y:.1%}<extra></extra>'},
    {x: current.map(row => row.predicted), type: 'histogram', histnorm: 'probability', nbinsx: 12, name: snapshotQuarter, opacity: .65, marker: {color: '#2563eb'}, hovertemplate: 'Predicted LGD: %{x:.2%}<br>Share: %{y:.1%}<extra></extra>'},
  ], {
    height: 310, margin: {t: 12, r: 18, b: 48, l: 62}, barmode: 'overlay', paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    legend: {orientation: 'h', x: 0, y: 1.16}, xaxis: {title: 'Predicted LGD', tickformat: '.1%', gridcolor: '#e5e7eb'}, yaxis: {title: 'Portfolio Share', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'},
  }, {responsive: true, displayModeBar: false});
}

function buildLgdRagHistory(lgd, context) {
  const thresholds = ((DASH_DATA.monitoring_thresholds || {}).lgd_thresholds || []);
  const trend = filterLgdTrend('rag', buildLgdTrend(lgd.performance_observations || [], context.snapshotQuarter));
  const rows = LGD_RAG_METRICS.map(metric => `<tr>
    <td>${metric}</td>
    ${trend.map(item => `<td>${lgdRagDot(calculateLgdMetricRag(thresholds, metric, getLgdMetricValues(item)[metric]))}</td>`).join('')}
  </tr>`).join('');
  return `<div id="lgd-rag-panel" class="section-card pd-rag-section" data-lgd-expand-title="LGD RAG Monitoring History">
    <div class="pd-section-heading">
      <div><div class="section-title">LGD RAG Monitoring History</div><div class="pd-section-subtitle">Threshold status through ${context.snapshotQuarter}.</div></div>
      <div class="pd-section-actions">${buildLgdWindowControl('rag')}${lgdExpandButton('lgd-rag-panel', 'LGD RAG Monitoring History')}</div>
    </div>
    <div class="pd-rag-table-wrap"><table class="pd-rag-table"><thead><tr><th>Metric</th>${trend.map(row => `<th>${row.quarter}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>
    <div class="pd-rag-legend"><span>${lgdRagDot('Green')} Within threshold</span><span>${lgdRagDot('Amber')} Monitor closely</span><span>${lgdRagDot('Red')} Action required</span><span>${lgdRagDot('N/A')} Insufficient data</span></div>
  </div>`;
}

function renderLgdModels() {
  closeLgdExpandedPanel(false);
  const lgd = (DASH_DATA.monitoring || {}).lgd_models || {};
  const observations = lgd.performance_observations || [];
  const context = getLgdPerformanceContext(lgd);
  const currentRows = filterLgdPerformanceObservations(observations, context.snapshotQuarter);
  const previousRows = filterLgdPerformanceObservations(observations, context.previousQuarter);
  const current = calculateLgdMetrics(currentRows);
  const previous = calculateLgdMetrics(previousRows);
  const thresholds = ((DASH_DATA.monitoring_thresholds || {}).lgd_thresholds || []);
  const values = getLgdMetricValues(current);
  const overallRag = getWorstLgdRag(LGD_RAG_METRICS.map(metric => calculateLgdMetricRag(thresholds, metric, values[metric])));
  const segmentLabel = MONITORING_PORTFOLIO_SEGMENT === 'all' ? 'All segments' : MONITORING_PORTFOLIO_SEGMENT;
  const metricCards = [
    ['actual_lgd', 'Actual LGD', 'percent', 'calibration'],
    ['predicted_lgd', 'Predicted LGD', 'percent', 'calibration'],
    ['actual_expected_lgd', 'Actual / Expected LGD', 'ratio', 'calibration'],
    ['mean_error', 'Mean Error', 'ratio', 'performance'],
    ['rmse', 'RMSE', 'ratio', 'performance'],
    ['kendall_tau', "Kendall's Tau", 'ratio', 'rank ordering'],
    ['recovery_rate', 'Recovery Rate', 'percent', 'reference'],
  ].map(([key, title, format, group]) => `<div class="pd-performance-card pd-card-calibration">
    <div class="pd-performance-title">${title}</div>
    <div class="pd-performance-value">${formatLgdMetric(current[key], format)}</div>
    <div class="pd-performance-detail"><span>${group}</span> · Snapshot date: ${context.snapshotQuarter}</div>
    <div class="pd-performance-comparison"><div><span>Previous (${context.previousQuarter})</span><strong>${formatLgdMetric(previous[key], format)}</strong></div><div><span>Change</span><strong>${formatLgdChange(current[key], previous[key], format)}</strong></div></div>
  </div>`).join('');

  document.getElementById('tab-lgd_models').innerHTML = `
    <div class="dash-header pd-page-header">
      <div><h2>LGD Performance Summary — ${monitoringPointLabel()}</h2><p>Monitor realized loss severity, calibration, predictive error, rank ordering, and recovery outcomes.</p></div>
      <div class="pd-overall-status pd-overall-${lgdToneClass(overallRag)}"><span>Overall RAG Status</span><strong>${lgdRagDot(overallRag)} ${overallRag}</strong></div>
    </div>
    <nav class="pd-section-nav" aria-label="LGD performance sections"><a href="#lgd-overview">Overview</a><a href="#lgd-trends">Trends</a><a href="#lgd-rag">RAG History</a></nav>
    <section id="lgd-overview" class="pd-content-section pd-overview-section">
      <div class="pd-content-heading"><div class="pd-content-kicker">Executive Overview</div><h3>LGD Analysis Scope</h3><p>Start with loss severity and error metrics, then inspect trends and threshold history.</p></div>
      <div class="pd-scope-bar">
        <div><span>Monitoring Point</span><strong>${CQ}</strong></div><div><span>Time Horizon</span><strong>${context.horizonLabel}</strong></div>
        <div class="pd-scope-snapshot"><span>Snapshot Date</span><strong>${context.snapshotQuarter}</strong></div><div><span>Previous Quarter</span><strong>${context.previousQuarter}</strong></div><div><span>Segment</span><strong>${segmentLabel}</strong></div>
        <div><span>LGD Models Selected</span><strong>${fmtN(MONITORING_MODELS.length)}</strong></div><div><span>Current Records</span><strong>${fmtN(currentRows.length)}</strong></div>
      </div>
      <div class="pd-filter-application-note"><strong>Applied to this analysis:</strong> monitoring point, time horizon, segment, and selected LGD models.</div>
      <div class="pd-content-heading pd-metric-heading"><div class="pd-content-kicker">Core Metrics</div><h3>Snapshot Date vs. Previous Quarter</h3></div>
      <div class="pd-performance-grid lgd-kpi-grid">${metricCards}</div>
    </section>
    <section id="lgd-trends" class="pd-content-section">
      <div class="pd-content-heading"><div class="pd-content-kicker">Trends</div><h3>Performance Through the Snapshot Date</h3><p>Use trend windows to focus the analysis on the period that matters.</p></div>
      <div class="pd-primary-analysis-grid">
        <div id="lgd-calibration-panel" class="section-card" data-lgd-expand-title="LGD Calibration Trend">${buildLgdChartHeader('LGD Calibration Trend','Actual versus predicted LGD and the Actual / Expected ratio.','lgd-calibration-panel','calibration')}<div id="lgd-calibration-trend-chart" class="pd-default-rate-trend-chart"></div></div>
        <div id="lgd-error-panel" class="section-card" data-lgd-expand-title="LGD Error and Rank-Ordering Trend">${buildLgdChartHeader('Error and Rank-Ordering Trend',"Mean Error, RMSE, and Kendall's Tau through the snapshot date.",'lgd-error-panel','error')}<div id="lgd-error-trend-chart" class="pd-stability-trend-chart"></div></div>
      </div>
      <div class="pd-trend-detail-grid">
        <div id="lgd-rating-panel" class="section-card" data-lgd-expand-title="Actual vs. Predicted LGD by Rating Grade">${buildLgdChartHeader('Actual vs. Predicted LGD by Rating Grade',`Calibration comparison at ${context.snapshotQuarter}.`,'lgd-rating-panel')}<div id="lgd-rating-chart" class="pd-rating-default-rate-chart"></div></div>
        <div id="lgd-distribution-panel" class="section-card" data-lgd-expand-title="Predicted LGD Distribution Shift">${buildLgdChartHeader('Predicted LGD Distribution Shift',`Portfolio comparison for ${context.previousQuarter} and ${context.snapshotQuarter}.`,'lgd-distribution-panel')}<div id="lgd-distribution-chart" class="pd-distribution-shift-chart"></div></div>
      </div>
    </section>
    <section id="lgd-rag" class="pd-content-section"><div class="pd-content-heading"><div class="pd-content-kicker">RAG History</div><h3>Threshold Monitoring by Metric</h3></div>${buildLgdRagHistory(lgd, context)}</section>
    <div id="lgd-expanded-modal" class="pd-expanded-modal" aria-hidden="true" onclick="if(event.target===this) closeLgdExpandedPanel()" onkeydown="if(event.key==='Escape') closeLgdExpandedPanel()">
      <div class="pd-expanded-dialog" role="dialog" aria-modal="true" aria-labelledby="lgd-expanded-modal-title"><div class="pd-expanded-modal-header"><div><span>Expanded Analysis</span><strong id="lgd-expanded-modal-title">LGD Analysis</strong></div><button type="button" id="lgd-expanded-modal-close" class="pd-expanded-close" onclick="closeLgdExpandedPanel()">Close</button></div><div id="lgd-expanded-modal-body" class="pd-expanded-modal-body"></div></div>
    </div>`;

  drawLgdCalibrationTrend(observations, context.snapshotQuarter);
  drawLgdErrorTrend(observations, context.snapshotQuarter);
  drawLgdByRating(observations, context.snapshotQuarter);
  drawLgdDistributionShift(observations, context.snapshotQuarter, context.previousQuarter);
}
"""
