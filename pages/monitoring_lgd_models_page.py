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
  me: 'all',
  rmse: 'all',
  kendall: 'all',
  predicted_actual: 'all',
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

function escapeLgdHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function lgdStatusLabel(rag) {
  if (rag === 'Green') return 'Within threshold';
  if (rag === 'Amber') return 'Monitor closely';
  if (rag === 'Red') return 'Action required';
  return 'Insufficient data';
}

function getLgdSelectedModelLabel() {
  if (!MONITORING_MODELS.length) return 'No LGD models selected';
  if (MONITORING_MODELS.length === 1) return MONITORING_MODELS[0];
  return `${MONITORING_MODELS.length} LGD models`;
}

function getLgdDimensionRags(thresholds, values) {
  const calibration = getWorstLgdRag(['Actual / Expected LGD', 'ME', 'RMSE'].map(metric => (
    calculateLgdMetricRag(thresholds, metric, values[metric])
  )));
  const discriminatory = calculateLgdMetricRag(thresholds, "Kendall's Tau", values["Kendall's Tau"]);
  const recovery = calculateLgdMetricRag(thresholds, 'Recovery Rate', values['Recovery Rate']);
  const performance = getWorstLgdRag([calibration, discriminatory, recovery]);
  return {calibration, discriminatory, recovery, performance};
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
  const chart = document.getElementById('lgd-calibration-trend-chart');
  if (!chart) return;
  Plotly.react('lgd-calibration-trend-chart', [
    {x: quarters, y: trend.map(row => row.actual_lgd), type: 'scatter', mode: 'lines+markers', name: 'Actual LGD', line: {color: '#dc2626', width: 2.5}, hovertemplate: '%{x}<br>Actual LGD: %{y:.2%}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.predicted_lgd), type: 'scatter', mode: 'lines+markers', name: 'Predicted LGD', line: {color: '#2563eb', width: 2.5, dash: 'dash'}, hovertemplate: '%{x}<br>Predicted LGD: %{y:.2%}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.actual_expected_lgd), type: 'scatter', mode: 'lines+markers', name: 'Actual / Expected LGD', yaxis: 'y2', line: {color: '#d97706', width: 2.5}, hovertemplate: '%{x}<br>A / E LGD: %{y:.3f}<extra></extra>'},
  ], {
    height: 390, margin: {t: 18, r: 64, b: 52, l: 62}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified', legend: {orientation: 'h', x: 0, y: 1.14},
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {title: 'Portfolio Quarter', gridcolor: '#e5e7eb'}, {chart}),
    yaxis: {title: 'LGD', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'},
    yaxis2: {title: 'A / E', overlaying: 'y', side: 'right', rangemode: 'tozero'},
  }, {responsive: true, displayModeBar: false});
}

function drawLgdErrorTrend(observations, snapshotQuarter) {
  const trend = filterLgdTrend('error', buildLgdTrend(observations, snapshotQuarter));
  const quarters = trend.map(row => row.quarter);
  const chart = document.getElementById('lgd-error-trend-chart');
  if (!chart) return;
  Plotly.react('lgd-error-trend-chart', [
    {x: quarters, y: trend.map(row => row.mean_error), type: 'scatter', mode: 'lines+markers', name: 'Mean Error', line: {color: '#0891b2', width: 2.5}, hovertemplate: '%{x}<br>Mean Error: %{y:.3f}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.rmse), type: 'scatter', mode: 'lines+markers', name: 'RMSE', line: {color: '#ea580c', width: 2.5, dash: 'dash'}, hovertemplate: '%{x}<br>RMSE: %{y:.3f}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.kendall_tau), type: 'scatter', mode: 'lines+markers', name: "Kendall's Tau", yaxis: 'y2', line: {color: '#7c3aed', width: 2.5, dash: 'dot'}, hovertemplate: "%{x}<br>Kendall's Tau: %{y:.3f}<extra></extra>"},
  ], {
    height: 360, margin: {t: 18, r: 78, b: 52, l: 62}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified', legend: {orientation: 'h', x: 0, y: 1.14},
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {title: 'Portfolio Quarter', gridcolor: '#e5e7eb'}, {chart}),
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

function buildLgdOverviewFlowConnectorSpans(options = {}) {
  return `
    ${options.incoming ? '<span class="pd-overview-flow-connector pd-overview-flow-connector-in" aria-hidden="true"></span>' : ''}
    ${options.outgoing ? '<span class="pd-overview-flow-connector pd-overview-flow-connector-out" aria-hidden="true"></span>' : ''}`;
}

function buildLgdOverviewFlowStage(number, title, subtitle = '') {
  return `
    <div class="pd-overview-flow-stage">
      <span>${escapeLgdHtml([number, title, subtitle].filter(Boolean).join(' '))}</span>
    </div>`;
}

function buildLgdOverviewFlowInput(label, options = {}) {
  return `
    <div class="pd-overview-flow-input ${options.extraClass || ''}">
      <strong>${escapeLgdHtml(label)}</strong>
      ${options.note ? `<span>${escapeLgdHtml(options.note)}</span>` : ''}
    </div>`;
}

function buildLgdOverviewFlowMetric(label, value, format, rag, options = {}) {
  const tone = lgdToneClass(options.ragOverride || rag);
  const valueMarkup = options.isRag
    ? `${lgdRagDot(value)} ${escapeLgdHtml(value)}`
    : escapeLgdHtml(formatLgdMetric(value, format));
  const body = `
      ${buildLgdOverviewFlowConnectorSpans(options)}
      <span class="pd-overview-flow-node-label">
        ${escapeLgdHtml(label)}
        ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapeLgdHtml(options.tooltip)}" title="${escapeLgdHtml(options.tooltip)}">i</span>` : ''}
      </span>
      <span class="pd-overview-flow-node-value ${options.isRag ? 'pd-overview-flow-node-value-rag' : ''}">${valueMarkup}</span>
      ${options.note ? `<span class="pd-overview-flow-node-note">${escapeLgdHtml(options.note)}</span>` : ''}`;
  return `
    <article class="pd-overview-flow-node pd-overview-flow-node-${tone} ${options.extraClass || ''}">
      ${options.href
        ? `<a class="pd-overview-flow-link" href="${options.href}" aria-label="Jump to ${escapeLgdHtml(label)} section">${body}</a>`
        : body}
    </article>`;
}

function buildLgdOverviewFlowTestStack(metrics, options = {}) {
  return `
    <div class="pd-overview-flow-test-stack ${options.extraClass || ''}">
      ${buildLgdOverviewFlowConnectorSpans(options)}
      ${metrics.join('')}
    </div>`;
}

function buildLgdOverviewFlowPerformance(dimensions) {
  const tone = lgdToneClass(dimensions.performance);
  const tooltip = `Performance LGD RAG is the worst available monitoring dimension RAG. Current inputs: Calibration Conservatism = ${dimensions.calibration}, Discriminatory Power = ${dimensions.discriminatory}, Recovery Outcome = ${dimensions.recovery}.`;
  return `
    <article class="pd-overview-flow-performance pd-overview-flow-performance-${tone}">
      <span class="pd-overview-flow-performance-title">
        Performance<br>LGD RAG
        <span class="pd-info-chip" role="img" aria-label="${escapeLgdHtml(tooltip)}" title="${escapeLgdHtml(tooltip)}">i</span>
      </span>
      <strong>${lgdRagDot(dimensions.performance)} ${escapeLgdHtml(dimensions.performance)}</strong>
    </article>`;
}

function buildLgdRagAssignmentOverview(values, thresholds, dimensions) {
  const calibrationRag = dimensions.calibration;
  const discriminatoryRag = dimensions.discriminatory;
  const recoveryRag = dimensions.recovery;
  return `
    <div class="pd-overview-flow-wrap">
      <div class="lgd-overview-flow" aria-label="LGD monitoring overview process flow">
        <div class="lgd-flow-stage-input">${buildLgdOverviewFlowStage('1.', 'Components')}</div>
        <div class="lgd-flow-stage-tests">${buildLgdOverviewFlowStage('2.', 'Tests')}</div>
        <div class="lgd-flow-stage-assignment">${buildLgdOverviewFlowStage('3.', 'RAG Assignment')}</div>
        <div class="lgd-flow-stage-dimension">${buildLgdOverviewFlowStage('4.', 'Monitoring Dimension RAG')}</div>
        <div class="lgd-flow-stage-performance">${buildLgdOverviewFlowStage('5.', 'Performance', 'LGD RAG')}</div>

        <div class="lgd-flow-input">
          ${buildLgdOverviewFlowInput('LGD Model Output', {note: 'Predicted and realized loss severity'})}
        </div>

        ${buildLgdOverviewFlowTestStack([
          buildLgdOverviewFlowMetric('Actual / Expected LGD', values['Actual / Expected LGD'], 'ratio', calculateLgdMetricRag(thresholds, 'Actual / Expected LGD', values['Actual / Expected LGD']), {href: '#lgd-predicted-actual'}),
          buildLgdOverviewFlowMetric('Mean Error', values.ME, 'ratio', calculateLgdMetricRag(thresholds, 'ME', values.ME), {href: '#lgd-threshold-trends'}),
          buildLgdOverviewFlowMetric('RMSE', values.RMSE, 'ratio', calculateLgdMetricRag(thresholds, 'RMSE', values.RMSE), {href: '#lgd-threshold-trends'}),
        ], {incoming: true, extraClass: 'lgd-flow-tests-calibration'})}

        ${buildLgdOverviewFlowMetric('Calibration RAG Assignment', calibrationRag, 'rag', calibrationRag, {
          isRag: true,
          href: '#lgd-threshold-trends',
          tooltip: 'Worst RAG across Actual / Expected LGD, ME, and RMSE.',
          incoming: true,
          outgoing: true,
          extraClass: 'lgd-flow-assignment-calibration',
        })}

        ${buildLgdOverviewFlowMetric('Calibration Conservatism RAG', calibrationRag, 'rag', calibrationRag, {
          isRag: true,
          href: '#lgd-threshold-trends',
          tooltip: 'Monitoring dimension for LGD calibration conservatism.',
          incoming: true,
          outgoing: true,
          extraClass: 'lgd-flow-dimension-calibration',
        })}

        ${buildLgdOverviewFlowTestStack([
          buildLgdOverviewFlowMetric("Kendall's Tau", values["Kendall's Tau"], 'ratio', calculateLgdMetricRag(thresholds, "Kendall's Tau", values["Kendall's Tau"]), {href: '#lgd-threshold-trends'}),
        ], {incoming: true, extraClass: 'lgd-flow-tests-discrimination'})}

        ${buildLgdOverviewFlowMetric('Discriminatory RAG Assignment', discriminatoryRag, 'rag', discriminatoryRag, {
          isRag: true,
          href: '#lgd-threshold-trends',
          tooltip: "Based on Kendall's Tau for LGD rank ordering.",
          incoming: true,
          outgoing: true,
          extraClass: 'lgd-flow-assignment-discrimination',
        })}

        ${buildLgdOverviewFlowMetric('Discriminatory Power RAG', discriminatoryRag, 'rag', discriminatoryRag, {
          isRag: true,
          href: '#lgd-threshold-trends',
          tooltip: 'Monitoring dimension for LGD rank-ordering performance.',
          incoming: true,
          outgoing: true,
          extraClass: 'lgd-flow-dimension-discrimination',
        })}

        ${buildLgdOverviewFlowTestStack([
          buildLgdOverviewFlowMetric('Recovery Rate', values['Recovery Rate'], 'percent', calculateLgdMetricRag(thresholds, 'Recovery Rate', values['Recovery Rate']), {href: '#lgd-rag'}),
        ], {incoming: true, extraClass: 'lgd-flow-tests-recovery'})}

        ${buildLgdOverviewFlowMetric('Recovery RAG Assignment', recoveryRag, 'rag', recoveryRag, {
          isRag: true,
          href: '#lgd-rag',
          tooltip: 'Based on realized recovery rate implied by actual LGD.',
          incoming: true,
          outgoing: true,
          extraClass: 'lgd-flow-assignment-recovery',
        })}

        ${buildLgdOverviewFlowMetric('Recovery Outcome RAG', recoveryRag, 'rag', recoveryRag, {
          isRag: true,
          href: '#lgd-rag',
          tooltip: 'Monitoring dimension for observed recovery outcome.',
          incoming: true,
          outgoing: true,
          extraClass: 'lgd-flow-dimension-recovery',
        })}

        <div class="lgd-flow-performance">
          ${buildLgdOverviewFlowPerformance(dimensions)}
        </div>
      </div>
    </div>`;
}

function buildLgdRagAssignmentSection(thresholds, values, previousValues, context) {
  const dimensions = getLgdDimensionRags(thresholds, values);
  const previousDimensions = getLgdDimensionRags(thresholds, previousValues);
  const metricRows = [
    {metric: 'Actual / Expected LGD', dimension: 'Calibration Conservatism', rag: calculateLgdMetricRag(thresholds, 'Actual / Expected LGD', values['Actual / Expected LGD']), previous: calculateLgdMetricRag(thresholds, 'Actual / Expected LGD', previousValues['Actual / Expected LGD'])},
    {metric: 'ME', dimension: 'Calibration Conservatism', rag: calculateLgdMetricRag(thresholds, 'ME', values.ME), previous: calculateLgdMetricRag(thresholds, 'ME', previousValues.ME)},
    {metric: 'RMSE', dimension: 'Calibration Conservatism', rag: calculateLgdMetricRag(thresholds, 'RMSE', values.RMSE), previous: calculateLgdMetricRag(thresholds, 'RMSE', previousValues.RMSE)},
    {metric: "Kendall's Tau", dimension: 'Discriminatory Power', rag: calculateLgdMetricRag(thresholds, "Kendall's Tau", values["Kendall's Tau"]), previous: calculateLgdMetricRag(thresholds, "Kendall's Tau", previousValues["Kendall's Tau"])},
    {metric: 'Recovery Rate', dimension: 'Recovery Outcome', rag: calculateLgdMetricRag(thresholds, 'Recovery Rate', values['Recovery Rate']), previous: calculateLgdMetricRag(thresholds, 'Recovery Rate', previousValues['Recovery Rate'])},
  ];
  const rows = metricRows.map(row => `<tr>
    <td>${escapeLgdHtml(row.metric)}</td>
    <td>${lgdRagDot(row.rag)} ${escapeLgdHtml(row.rag)}</td>
    <td>${escapeLgdHtml(row.dimension)}</td>
    <td>${lgdRagDot(row.dimension === 'Calibration Conservatism' ? dimensions.calibration : row.dimension === 'Discriminatory Power' ? dimensions.discriminatory : dimensions.recovery)} ${escapeLgdHtml(row.dimension === 'Calibration Conservatism' ? dimensions.calibration : row.dimension === 'Discriminatory Power' ? dimensions.discriminatory : dimensions.recovery)}</td>
    <td>${lgdRagDot(dimensions.performance)} ${escapeLgdHtml(dimensions.performance)}</td>
    <td>${lgdRagDot(row.previous)} ${escapeLgdHtml(row.previous)}</td>
  </tr>`).join('');
  return `<section id="lgd-rag-assignment" class="pd-content-section">
    <div class="pd-content-heading"><div class="pd-content-kicker">RAG Assignment</div><h3>RAG Assignment Overview</h3><p>At-a-glance summary of LGD components, metric tests, RAG assignment, monitoring dimension RAGs, and final Performance LGD RAG.</p></div>
    ${buildLgdRagAssignmentOverview(values, thresholds, dimensions)}
    <div class="pd-content-heading pd-metric-heading"><div class="pd-content-kicker">Dimension Detail</div><h3>Calibration, Discriminatory Power, and Recovery Outcome</h3></div>
    <div class="pd-test-grid pd-test-grid-3">
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Dimension</span><h4>Calibration Conservatism</h4></div><div class="pd-test-status pd-test-status-${lgdToneClass(dimensions.calibration)}">${escapeLgdHtml(dimensions.calibration)}</div></div><div class="pd-test-value">${lgdRagDot(dimensions.calibration)} ${escapeLgdHtml(dimensions.calibration)}</div><div class="pd-test-meta">Inputs: Actual / Expected LGD, ME, and RMSE</div><div class="pd-performance-comparison"><div><span>Previous (${escapeLgdHtml(context.previousQuarter)})</span><strong>${escapeLgdHtml(previousDimensions.calibration)}</strong></div><div><span>Status</span><strong>${escapeLgdHtml(lgdStatusLabel(dimensions.calibration))}</strong></div></div></article>
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Dimension</span><h4>Discriminatory Power</h4></div><div class="pd-test-status pd-test-status-${lgdToneClass(dimensions.discriminatory)}">${escapeLgdHtml(dimensions.discriminatory)}</div></div><div class="pd-test-value">${lgdRagDot(dimensions.discriminatory)} ${escapeLgdHtml(dimensions.discriminatory)}</div><div class="pd-test-meta">Input: Kendall's Tau</div><div class="pd-performance-comparison"><div><span>Previous (${escapeLgdHtml(context.previousQuarter)})</span><strong>${escapeLgdHtml(previousDimensions.discriminatory)}</strong></div><div><span>Status</span><strong>${escapeLgdHtml(lgdStatusLabel(dimensions.discriminatory))}</strong></div></div></article>
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Dimension</span><h4>Recovery Outcome</h4></div><div class="pd-test-status pd-test-status-${lgdToneClass(dimensions.recovery)}">${escapeLgdHtml(dimensions.recovery)}</div></div><div class="pd-test-value">${lgdRagDot(dimensions.recovery)} ${escapeLgdHtml(dimensions.recovery)}</div><div class="pd-test-meta">Input: Recovery Rate</div><div class="pd-performance-comparison"><div><span>Previous (${escapeLgdHtml(context.previousQuarter)})</span><strong>${escapeLgdHtml(previousDimensions.recovery)}</strong></div><div><span>Status</span><strong>${escapeLgdHtml(lgdStatusLabel(dimensions.recovery))}</strong></div></div></article>
    </div>
    <div class="pd-test-grid pd-test-grid-3">
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Final</span><h4>Performance LGD RAG</h4></div><div class="pd-test-status pd-test-status-${lgdToneClass(dimensions.performance)}">${escapeLgdHtml(dimensions.performance)}</div></div><div class="pd-test-value">${lgdRagDot(dimensions.performance)} ${escapeLgdHtml(dimensions.performance)}</div><div class="pd-test-meta">Worst of calibration, discriminatory power, and recovery outcome</div><div class="pd-performance-comparison"><div><span>Previous (${escapeLgdHtml(context.previousQuarter)})</span><strong>${escapeLgdHtml(previousDimensions.performance)}</strong></div><div><span>Snapshot</span><strong>${escapeLgdHtml(context.snapshotQuarter)}</strong></div></div></article>
    </div>
    <div class="section-card pd-rag-section">
      <div class="pd-rag-table-wrap"><table class="pd-rag-table"><thead><tr><th>Metric</th><th>Metric RAG</th><th>Dimension</th><th>Dimension RAG</th><th>Performance RAG</th><th>Previous Metric RAG</th></tr></thead><tbody>${rows}</tbody></table></div>
    </div>
  </section>`;
}

function getLgdMetricSeriesValue(row, metric) {
  return getLgdMetricValues(row)[metric];
}

function getLgdMetricThreshold(thresholds, metric) {
  return thresholds.find(row => row.metric === metric) || null;
}

function getFiniteLgdValues(values) {
  return values.filter(value => value != null && Number.isFinite(value));
}

function buildLgdThresholdShapes(threshold, yValues) {
  const finiteValues = getFiniteLgdValues(yValues);
  if (!threshold || !finiteValues.length) return {shapes: [], range: null};
  const candidates = finiteValues.slice();
  ['green_min', 'green_max', 'amber_min', 'amber_max'].forEach(key => {
    const value = Number(threshold[key]);
    if (Number.isFinite(value)) candidates.push(value);
  });
  if (threshold.red_condition === 'abs above amber_max') {
    candidates.push(-Math.abs(Number(threshold.amber_max) || 0), Math.abs(Number(threshold.amber_max) || 0));
  }
  const low = Math.min(...candidates);
  const high = Math.max(...candidates);
  const pad = Math.max((high - low) * 0.12, Math.abs(high || 1) * 0.05, 0.02);
  const yMin = low - pad;
  const yMax = high + pad;
  const rect = (y0, y1, color) => ({
    type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y',
    y0: Math.max(Math.min(y0, y1), yMin), y1: Math.min(Math.max(y0, y1), yMax),
    fillcolor: color, line: {width: 0}, layer: 'below',
  });
  const line = (y, color, dash = 'solid') => ({
    type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: y, y1: y,
    line: {color, width: 1.5, dash},
  });
  const green = 'rgba(22,163,74,0.14)';
  const amber = 'rgba(217,119,6,0.18)';
  const red = 'rgba(220,38,38,0.12)';
  const shapes = [];
  const greenMin = Number(threshold.green_min);
  const greenMax = Number(threshold.green_max);
  const amberMin = Number(threshold.amber_min);
  const amberMax = Number(threshold.amber_max);
  if (threshold.red_condition === 'abs above amber_max') {
    const g = Math.abs(greenMax);
    const a = Math.abs(amberMax);
    shapes.push(rect(yMin, -a, red), rect(-a, -g, amber), rect(-g, g, green), rect(g, a, amber), rect(a, yMax, red));
    shapes.push(line(-g, 'rgba(22,163,74,.85)'), line(g, 'rgba(22,163,74,.85)'), line(-a, 'rgba(217,119,6,.82)', 'dash'), line(a, 'rgba(217,119,6,.82)', 'dash'));
  } else if (threshold.red_condition === 'below amber_min') {
    shapes.push(rect(yMin, amberMin, red), rect(amberMin, greenMin, amber), rect(greenMin, yMax, green));
    shapes.push(line(amberMin, 'rgba(217,119,6,.82)', 'dash'), line(greenMin, 'rgba(22,163,74,.85)'));
  } else if (threshold.red_condition === 'above amber_max') {
    shapes.push(rect(yMin, greenMax, green), rect(greenMax, amberMax, amber), rect(amberMax, yMax, red));
    shapes.push(line(greenMax, 'rgba(22,163,74,.85)'), line(amberMax, 'rgba(217,119,6,.82)', 'dash'));
  } else {
    shapes.push(rect(yMin, amberMin, red), rect(amberMin, greenMin, amber), rect(greenMin, greenMax, green), rect(greenMax, amberMax, amber), rect(amberMax, yMax, red));
    shapes.push(line(greenMin, 'rgba(22,163,74,.85)'), line(greenMax, 'rgba(22,163,74,.85)'), line(amberMin, 'rgba(217,119,6,.82)', 'dash'), line(amberMax, 'rgba(217,119,6,.82)', 'dash'));
  }
  return {shapes, range: [yMin, yMax]};
}

function drawLgdThresholdMetricChart(chartId, observations, snapshotQuarter, thresholds, metric, rangeKey) {
  const chart = document.getElementById(chartId);
  if (!chart) return;
  const trend = filterLgdTrend(rangeKey, buildLgdTrend(observations, snapshotQuarter));
  const quarters = trend.map(row => row.quarter);
  const values = trend.map(row => getLgdMetricSeriesValue(row, metric));
  const threshold = getLgdMetricThreshold(thresholds, metric);
  const bands = buildLgdThresholdShapes(threshold, values);
  const markerColors = values.map(value => {
    const rag = calculateLgdMetricRag(thresholds, metric, value);
    return rag === 'Green' ? '#16a34a' : rag === 'Amber' ? '#d97706' : rag === 'Red' ? '#dc2626' : '#94a3b8';
  });
  Plotly.react(chartId, [{
    x: quarters,
    y: values,
    type: 'scatter',
    mode: 'lines+markers',
    name: metric,
    line: {color: '#0f1d35', width: 2.4},
    marker: {size: 8, color: markerColors, line: {color: '#ffffff', width: 1.5}},
    hovertemplate: `%{x}<br>${metric}: %{y:.3f}<extra></extra>`,
  }], {
    height: 318,
    margin: {t: 12, r: 18, b: 52, l: 62},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    showlegend: false,
    shapes: bands.shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {title: 'Portfolio Quarter', gridcolor: '#e5e7eb'}, {chart}),
    yaxis: {title: metric, range: bands.range || undefined, gridcolor: '#e5e7eb', zerolinecolor: '#cbd5e1'},
  }, {responsive: true, displayModeBar: false});
}

function drawLgdPredictedActualStandalone(observations, snapshotQuarter) {
  const chart = document.getElementById('lgd-predicted-actual-chart');
  if (!chart) return;
  const trend = filterLgdTrend('predicted_actual', buildLgdTrend(observations, snapshotQuarter));
  const quarters = trend.map(row => row.quarter);
  Plotly.react('lgd-predicted-actual-chart', [
    {x: quarters, y: trend.map(row => row.actual_lgd), type: 'scatter', mode: 'lines+markers', name: 'Actual LGD', line: {color: '#dc2626', width: 2.7}, hovertemplate: '%{x}<br>Actual LGD: %{y:.2%}<extra></extra>'},
    {x: quarters, y: trend.map(row => row.predicted_lgd), type: 'scatter', mode: 'lines+markers', name: 'Predicted LGD', line: {color: '#2563eb', width: 2.7, dash: 'dash'}, hovertemplate: '%{x}<br>Predicted LGD: %{y:.2%}<extra></extra>'},
  ], {
    height: 360,
    margin: {t: 14, r: 24, b: 54, l: 62},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    legend: {orientation: 'h', x: 0, y: 1.14},
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {title: 'Portfolio Quarter', gridcolor: '#e5e7eb'}, {chart}),
    yaxis: {title: 'LGD', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'},
  }, {responsive: true, displayModeBar: false});
}

function getLgdMevData() {
  return [
    {name: 'Unemployment Rate', unit: '%', devMin: 3.5, devMax: 8.6, lower2sd: 1.1, upper2sd: 9.1, values: {'2023Q1': 5.2, '2023Q2': 5.5, '2023Q3': 5.7, '2023Q4': 5.3, '2024Q1': 5.4, '2024Q2': 6.2, '2024Q3': 7.1, '2024Q4': 7.4, '2025Q1': 8.2, '2025Q2': 9.8, '2025Q3': 10.2, '2025Q4': 9.7}},
    {name: 'GDP Growth', unit: '%', devMin: -4.2, devMax: 5.1, lower2sd: -2.5, upper2sd: 6.7, values: {'2023Q1': 2.6, '2023Q2': 2.3, '2023Q3': 2.1, '2023Q4': 2.4, '2024Q1': 1.8, '2024Q2': .6, '2024Q3': -.9, '2024Q4': -1.6, '2025Q1': -2.4, '2025Q2': -3.1, '2025Q3': -1.8, '2025Q4': -.7}},
    {name: 'House Price Index Growth', unit: '%', devMin: -8.5, devMax: 12.2, lower2sd: -6.0, upper2sd: 12.0, values: {'2023Q1': 4.9, '2023Q2': 5.1, '2023Q3': 4.5, '2023Q4': 3.9, '2024Q1': 2.8, '2024Q2': .7, '2024Q3': -1.5, '2024Q4': -3.3, '2025Q1': -5.7, '2025Q2': -4.8, '2025Q3': -2.6, '2025Q4': .4}},
    {name: 'Interest Rate 3M', unit: '%', devMin: .1, devMax: 8.7, lower2sd: -.3, upper2sd: 7.9, values: {'2023Q1': 3.9, '2023Q2': 4.2, '2023Q3': 4.8, '2023Q4': 5.2, '2024Q1': 5.8, '2024Q2': 6.1, '2024Q3': 6.4, '2024Q4': 6.9, '2025Q1': 7.1, '2025Q2': 6.7, '2025Q3': 6.0, '2025Q4': 5.4}},
  ];
}

function getLgdMevRag(mev) {
  const values = Object.values(mev.values).map(Number).filter(Number.isFinite);
  const latest = values[values.length - 1];
  if (latest < mev.lower2sd || latest > mev.upper2sd) return 'Red';
  if (latest < mev.devMin || latest > mev.devMax) return 'Amber';
  return 'Green';
}

function buildLgdMevRangeSection() {
  const mevs = getLgdMevData();
  const rows = mevs.map(mev => {
    const values = Object.values(mev.values).map(Number).filter(Number.isFinite);
    const latest = values[values.length - 1];
    const rag = getLgdMevRag(mev);
    return `<tr><td>${escapeLgdHtml(mev.name)}</td><td>${latest.toFixed(1)}${escapeLgdHtml(mev.unit)}</td><td>${mev.devMin.toFixed(1)}${escapeLgdHtml(mev.unit)} to ${mev.devMax.toFixed(1)}${escapeLgdHtml(mev.unit)}</td><td>${mev.lower2sd.toFixed(1)}${escapeLgdHtml(mev.unit)} to ${mev.upper2sd.toFixed(1)}${escapeLgdHtml(mev.unit)}</td><td>${lgdRagDot(rag)} ${escapeLgdHtml(rag)}</td></tr>`;
  }).join('');
  return `<section id="lgd-mev-range" class="pd-content-section">
    <div class="pd-content-heading"><div class="pd-content-kicker">Post Subjective Review</div><h3>MEV Range Analysis</h3><p>Economic variables are compared with development green ranges and two-standard-deviation amber buffers, mirroring the Modular LGD review workflow.</p></div>
    <div class="pd-primary-analysis-grid">
      <div id="lgd-mev-panel" class="section-card" data-lgd-expand-title="LGD MEV Range Analysis">${buildLgdChartHeader('MEV Range Analysis','Historical and severe-scenario path against development and 2SD bands.','lgd-mev-panel')}<div id="lgd-mev-range-chart" class="pd-mev-chart"></div></div>
    </div>
    <div class="section-card pd-rag-section"><div class="pd-rag-table-wrap"><table class="pd-rag-table"><thead><tr><th>MEV Variable</th><th>Latest</th><th>Development Range</th><th>2SD Range</th><th>RAG</th></tr></thead><tbody>${rows}</tbody></table></div></div>
  </section>`;
}

function drawLgdMevRangeChart() {
  const chart = document.getElementById('lgd-mev-range-chart');
  if (!chart) return;
  const mev = getLgdMevData()[0];
  const points = Object.entries(mev.values).sort(([left], [right]) => left.localeCompare(right));
  const quarters = points.map(([quarter]) => quarter);
  const values = points.map(([, value]) => value);
  const yMin = Math.min(...values, mev.lower2sd, mev.devMin) - .6;
  const yMax = Math.max(...values, mev.upper2sd, mev.devMax) + .6;
  Plotly.react('lgd-mev-range-chart', [{
    x: quarters,
    y: values,
    type: 'scatter',
    mode: 'lines+markers',
    name: mev.name,
    line: {color: '#0f1d35', width: 2.6},
    marker: {size: 7, color: '#ffffff', line: {color: '#0f1d35', width: 2}},
    hovertemplate: `%{x}<br>${mev.name}: %{y:.1f}%<extra></extra>`,
  }], {
    height: 360,
    margin: {t: 18, r: 24, b: 54, l: 62},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    shapes: [
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: yMin, y1: mev.lower2sd, fillcolor: 'rgba(220,38,38,.12)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: mev.lower2sd, y1: mev.devMin, fillcolor: 'rgba(217,119,6,.18)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: mev.devMin, y1: mev.devMax, fillcolor: 'rgba(22,163,74,.14)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: mev.devMax, y1: mev.upper2sd, fillcolor: 'rgba(217,119,6,.18)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: mev.upper2sd, y1: yMax, fillcolor: 'rgba(220,38,38,.12)', line: {width: 0}, layer: 'below'},
    ],
    hovermode: 'x unified',
    showlegend: false,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {title: 'Quarter', gridcolor: '#e5e7eb'}, {chart}),
    yaxis: {title: `${mev.name} (${mev.unit})`, range: [yMin, yMax], gridcolor: '#e5e7eb'},
  }, {responsive: true, displayModeBar: false});
}

function buildLgdScenarioData(current) {
  const base = Number.isFinite(current.predicted_lgd) ? Math.max(current.predicted_lgd, 0.000001) : 0.42;
  const scenarioRows = [
    {scenario: 'Upward', rank: 1, output: base * 0.85},
    {scenario: 'Base', rank: 2, output: base},
    {scenario: 'Severe', rank: 3, output: Math.min(base * 1.35, 1)},
  ];
  const sorted = scenarioRows.slice().sort((a, b) => a.output - b.output);
  scenarioRows.forEach(row => {
    row.observedRank = sorted.findIndex(item => item.scenario === row.scenario) + 1;
    row.pass = row.observedRank === row.rank;
    row.rag = row.pass ? 'Green' : 'Red';
  });
  const sensitivityRows = [
    {shock: '-2SD', output: base * 0.89},
    {shock: 'Base', output: base},
    {shock: '+2SD', output: Math.min(base * 1.12, 1)},
  ].map(row => {
    const diff = (row.output - base) / base;
    return {...row, diff, threshold: 0.15, pass: Math.abs(diff) <= 0.15, rag: Math.abs(diff) <= 0.15 ? 'Green' : 'Red'};
  });
  return {scenarioRows, sensitivityRows};
}

function buildLgdScenarioTestsSection(current) {
  const data = buildLgdScenarioData(current);
  const rankPass = data.scenarioRows.every(row => row.pass);
  const sensitivityPass = data.sensitivityRows.every(row => row.pass);
  const maxSensitivity = Math.max(...data.sensitivityRows.map(row => Math.abs(row.diff)));
  const rankRag = rankPass ? 'Green' : 'Red';
  const sensitivityRag = sensitivityPass ? 'Green' : 'Red';
  const modelLabel = getLgdSelectedModelLabel();
  return `<section id="lgd-scenario-tests" class="pd-content-section">
    <div class="pd-content-heading"><div class="pd-content-kicker">Post Subjective Review</div><h3>Scenario Tests</h3><p>Checks whether LGD outputs increase with scenario severity and remain within the configured sensitivity tolerance.</p></div>
    <div class="pd-test-grid pd-test-grid-4">
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Scenario Rank</span><h4>Rank Ordering Result</h4></div><div class="pd-test-status pd-test-status-${lgdToneClass(rankRag)}">${rankRag}</div></div><div class="pd-test-value">${rankPass ? 'Pass' : 'Fail'}</div><div class="pd-test-meta">Expected: Upward &lt; Base &lt; Severe</div></article>
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Sensitivity</span><h4>+/- 2SD Result</h4></div><div class="pd-test-status pd-test-status-${lgdToneClass(sensitivityRag)}">${sensitivityRag}</div></div><div class="pd-test-value">${sensitivityPass ? 'Pass' : 'Fail'}</div><div class="pd-test-meta">Threshold: 15% from base</div></article>
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Sensitivity</span><h4>Maximum Difference</h4></div><div class="pd-test-status pd-test-status-${lgdToneClass(sensitivityRag)}">${sensitivityRag}</div></div><div class="pd-test-value">${(maxSensitivity * 100).toFixed(1)}%</div><div class="pd-test-meta">Absolute difference vs base</div></article>
      <article class="pd-test-card"><div class="pd-test-card-heading"><div><span>Scope</span><h4>Selected Model</h4></div></div><div class="pd-test-value">${escapeLgdHtml(modelLabel)}</div><div class="pd-test-meta">Model type: LGD</div></article>
    </div>
    <div class="pd-trend-detail-grid">
      <div id="lgd-scenario-rank-panel" class="section-card" data-lgd-expand-title="LGD Scenario Rank Ordering">${buildLgdChartHeader('Scenario Rank Ordering','LGD output should increase as scenario severity increases.','lgd-scenario-rank-panel')}<div id="lgd-scenario-rank-chart" class="pd-rating-default-rate-chart"></div></div>
      <div id="lgd-sensitivity-panel" class="section-card" data-lgd-expand-title="LGD Sensitivity Analysis">${buildLgdChartHeader('Sensitivity Analysis','Base LGD output compared with +/- 2SD shocks.','lgd-sensitivity-panel')}<div id="lgd-sensitivity-chart" class="pd-rating-default-rate-chart"></div></div>
    </div>
  </section>`;
}

function drawLgdScenarioCharts(current) {
  const data = buildLgdScenarioData(current);
  const rankChart = document.getElementById('lgd-scenario-rank-chart');
  if (rankChart) {
    Plotly.react('lgd-scenario-rank-chart', [{
      x: data.scenarioRows.map(row => row.scenario),
      y: data.scenarioRows.map(row => row.output),
      type: 'bar',
      marker: {color: data.scenarioRows.map(row => row.rag === 'Green' ? '#16a34a' : '#dc2626')},
      text: data.scenarioRows.map(row => `${(row.output * 100).toFixed(2)}%`),
      textposition: 'outside',
      hovertemplate: '%{x}<br>Output: %{y:.2%}<extra></extra>',
    }], {
      height: 310, margin: {t: 12, r: 18, b: 48, l: 62}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      xaxis: {title: 'Scenario'}, yaxis: {title: 'LGD Output', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'}, showlegend: false,
    }, {responsive: true, displayModeBar: false});
  }
  const sensChart = document.getElementById('lgd-sensitivity-chart');
  if (sensChart) {
    Plotly.react('lgd-sensitivity-chart', [{
      x: data.sensitivityRows.map(row => row.shock),
      y: data.sensitivityRows.map(row => row.output),
      type: 'bar',
      marker: {color: data.sensitivityRows.map(row => row.rag === 'Green' ? '#16a34a' : '#dc2626')},
      text: data.sensitivityRows.map(row => `${(row.output * 100).toFixed(2)}%`),
      textposition: 'outside',
      hovertemplate: '%{x}<br>Output: %{y:.2%}<br>Diff vs Base: %{customdata:.1%}<extra></extra>',
      customdata: data.sensitivityRows.map(row => row.diff),
    }], {
      height: 310, margin: {t: 12, r: 18, b: 48, l: 62}, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      xaxis: {title: 'Shock'}, yaxis: {title: 'LGD Output', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'}, showlegend: false,
    }, {responsive: true, displayModeBar: false});
  }
}

function buildLgdPostSubjectiveReviewSection(dimensions) {
  const modelLabel = getLgdSelectedModelLabel();
  const scenarioRag = 'Green';
  const mevRag = getWorstLgdRag(getLgdMevData().map(getLgdMevRag));
  const modelPostReview = getWorstLgdRag([dimensions.performance, scenarioRag, mevRag]);
  const rows = [
    ['Performance RAG', `${lgdRagDot(dimensions.performance)} ${escapeLgdHtml(dimensions.performance)}`],
    ['MEV Range Comments', `MEV range review completed for selected LGD scope. Worst MEV status: ${lgdRagDot(mevRag)} ${escapeLgdHtml(mevRag)}.`],
    ['Scenario Tests Comments', `Scenario rank ordering and sensitivity checks completed. Scenario status: ${lgdRagDot(scenarioRag)} ${escapeLgdHtml(scenarioRag)}.`],
    ['Model RAG Post-Subjective Review', `${lgdRagDot(modelPostReview)} ${escapeLgdHtml(modelPostReview)}`],
    ['Pre-Mitigation RAG', `${lgdRagDot(modelPostReview)} ${escapeLgdHtml(modelPostReview)} - aligned to post-subjective review.`],
    ['Compensating Controls Comments', `Controls for ${escapeLgdHtml(modelLabel)} should document overlays, manual adjustments, monitoring governance, and business review outcomes.`],
    ['Post-Mitigation RAG', `${lgdRagDot(modelPostReview)} ${escapeLgdHtml(modelPostReview)}`],
  ].map(([label, value]) => `<tr><td>${escapeLgdHtml(label)}</td><td>${value}</td></tr>`).join('');
  return `<section id="lgd-post-review" class="pd-content-section">
    <div class="pd-content-heading"><div class="pd-content-kicker">Post Subjective Review</div><h3>Review Summary</h3><p>Consolidates quantitative performance, MEV range review, scenario testing, and mitigation status into a model-level outcome.</p></div>
    <div class="section-card pd-rag-section"><div class="pd-rag-table-wrap"><table class="pd-rag-table"><thead><tr><th>Review Area</th><th>Assessment</th></tr></thead><tbody>${rows}</tbody></table></div></div>
  </section>`;
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
  const previousValues = getLgdMetricValues(previous);
  const overallRag = getWorstLgdRag(LGD_RAG_METRICS.map(metric => calculateLgdMetricRag(thresholds, metric, values[metric])));
  const dimensionRags = getLgdDimensionRags(thresholds, values);
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
    <nav class="pd-section-nav" aria-label="LGD performance sections"><a href="#lgd-overview">Overview</a><a href="#lgd-rag-assignment">RAG Assignment</a><a href="#lgd-trends">Trends</a><a href="#lgd-threshold-trends">Threshold Bands</a><a href="#lgd-predicted-actual">Predicted vs Actual</a><a href="#lgd-mev-range">MEV Range</a><a href="#lgd-scenario-tests">Scenario Tests</a><a href="#lgd-post-review">Post Review</a></nav>
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
    ${buildLgdRagAssignmentSection(thresholds, values, previousValues, context)}
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
    <section id="lgd-threshold-trends" class="pd-content-section">
      <div class="pd-content-heading"><div class="pd-content-kicker">Threshold Bands</div><h3>Metric Trends with RAG Backgrounds</h3><p>Replicates the Modular LGD threshold-band view using the monitoring workbook thresholds.</p></div>
      <div class="pd-trend-detail-grid">
        <div id="lgd-me-threshold-panel" class="section-card" data-lgd-expand-title="LGD ME Trend with RAG Threshold Bands">${buildLgdChartHeader('ME Trend with RAG Threshold Bands','Mean Error colored by threshold status.','lgd-me-threshold-panel','me')}<div id="lgd-me-threshold-chart" class="pd-stability-trend-chart"></div></div>
        <div id="lgd-rmse-threshold-panel" class="section-card" data-lgd-expand-title="LGD RMSE Trend with RAG Threshold Bands">${buildLgdChartHeader('RMSE Trend with RAG Threshold Bands','RMSE colored by threshold status.','lgd-rmse-threshold-panel','rmse')}<div id="lgd-rmse-threshold-chart" class="pd-stability-trend-chart"></div></div>
        <div id="lgd-kendall-threshold-panel" class="section-card pd-trend-wide-card" data-lgd-expand-title="LGD Kendall's Tau Trend with RAG Threshold Bands">${buildLgdChartHeader("Kendall's Tau Trend with RAG Threshold Bands","Rank-ordering metric colored by threshold status.",'lgd-kendall-threshold-panel','kendall')}<div id="lgd-kendall-threshold-chart" class="pd-stability-trend-chart"></div></div>
      </div>
    </section>
    <section id="lgd-predicted-actual" class="pd-content-section">
      <div class="pd-content-heading"><div class="pd-content-kicker">Calibration Detail</div><h3>Predicted vs Actual LGD</h3><p>Standalone view of expected and realized loss severity over time.</p></div>
      <div id="lgd-predicted-actual-panel" class="section-card" data-lgd-expand-title="Predicted vs Actual LGD">${buildLgdChartHeader('Predicted vs Actual LGD','Actual realized LGD compared with predicted model output.','lgd-predicted-actual-panel','predicted_actual')}<div id="lgd-predicted-actual-chart" class="pd-default-rate-trend-chart-medium"></div></div>
    </section>
    <section id="lgd-rag" class="pd-content-section"><div class="pd-content-heading"><div class="pd-content-kicker">RAG History</div><h3>Threshold Monitoring by Metric</h3></div>${buildLgdRagHistory(lgd, context)}</section>
    ${buildLgdMevRangeSection()}
    ${buildLgdScenarioTestsSection(current)}
    ${buildLgdPostSubjectiveReviewSection(dimensionRags)}
    <div id="lgd-expanded-modal" class="pd-expanded-modal" aria-hidden="true" onclick="if(event.target===this) closeLgdExpandedPanel()" onkeydown="if(event.key==='Escape') closeLgdExpandedPanel()">
      <div class="pd-expanded-dialog" role="dialog" aria-modal="true" aria-labelledby="lgd-expanded-modal-title"><div class="pd-expanded-modal-header"><div><span>Expanded Analysis</span><strong id="lgd-expanded-modal-title">LGD Analysis</strong></div><button type="button" id="lgd-expanded-modal-close" class="pd-expanded-close" onclick="closeLgdExpandedPanel()">Close</button></div><div id="lgd-expanded-modal-body" class="pd-expanded-modal-body"></div></div>
    </div>`;

  drawLgdCalibrationTrend(observations, context.snapshotQuarter);
  drawLgdErrorTrend(observations, context.snapshotQuarter);
  drawLgdByRating(observations, context.snapshotQuarter);
  drawLgdDistributionShift(observations, context.snapshotQuarter, context.previousQuarter);
  drawLgdThresholdMetricChart('lgd-me-threshold-chart', observations, context.snapshotQuarter, thresholds, 'ME', 'me');
  drawLgdThresholdMetricChart('lgd-rmse-threshold-chart', observations, context.snapshotQuarter, thresholds, 'RMSE', 'rmse');
  drawLgdThresholdMetricChart('lgd-kendall-threshold-chart', observations, context.snapshotQuarter, thresholds, "Kendall's Tau", 'kendall');
  drawLgdPredictedActualStandalone(observations, context.snapshotQuarter);
  drawLgdMevRangeChart();
  drawLgdScenarioCharts(current);
}
"""
