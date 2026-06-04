"""Monitoring PD Performance page."""

JS = r"""
function getPreviousPdQuarter(quarter) {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter || '');
  if (!match) return '';
  const year = Number(match[1]);
  const quarterNumber = Number(match[2]);
  return quarterNumber === 1 ? `${year - 1}Q4` : `${year}Q${quarterNumber - 1}`;
}

function getPdPerformanceHorizonKey() {
  return MONITORING_PD_INPUT === 'nco_1y' ? 'nco_1y' : MONITORING_TIME_HORIZON;
}

function getPdPerformanceContextForHorizon(pd, horizonKey) {
  const horizonYears = horizonKey === '2y' ? 2 : 1;
  const horizon = (pd.performance_horizons || {})[horizonKey] || {};
  const snapshotQuarter = shiftMonitoringQuarterYear(CQ, -horizonYears);
  return {
    monitoringPoint: CQ,
    horizonKey,
    inputLabel: MONITORING_PD_INPUT === 'nco_1y' ? 'NCO PD 1 year' : 'Time horizon PD',
    horizonLabel: horizon.label || `${horizonYears} year${horizonYears === 1 ? '' : 's'}`,
    usesNcoInput: MONITORING_PD_INPUT === 'nco_1y',
    snapshotQuarter,
    previousQuarter: getPreviousPdQuarter(snapshotQuarter),
    predictedColumn: horizon.predicted_column || (horizonKey === 'nco_1y' ? 'CPD_NCO_1y' : `CPD_${horizonKey}_base`),
  };
}

function getPdPerformanceContext(pd) {
  return getPdPerformanceContextForHorizon(pd, getPdPerformanceHorizonKey());
}

function matchesPdSelectedPopulation(row, quarter) {
  const selectedModels = new Set(MONITORING_MODELS);
  if (row.quarter !== quarter) return false;
  if (!selectedModels.has(row.model)) return false;
  return MONITORING_PORTFOLIO_SEGMENT === 'all' || row.segment === MONITORING_PORTFOLIO_SEGMENT;
}

function filterPdPerformanceObservationsForHorizon(observations, quarter, horizonKey) {
  return observations.flatMap(row => {
    if (!matchesPdSelectedPopulation(row, quarter)) return [];
    const horizon = (row.horizons || {})[horizonKey];
    return horizon ? [{...row, observed: horizon.observed, predicted: horizon.predicted}] : [];
  });
}

function filterPdPerformanceObservations(observations, quarter) {
  return filterPdPerformanceObservationsForHorizon(observations, quarter, getPdPerformanceHorizonKey());
}

function formatPdCompactAmount(value) {
  if (value == null || !Number.isFinite(value)) return '—';
  const absolute = Math.abs(value);
  if (absolute >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (absolute >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (absolute >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return fmtN(Math.round(value));
}

function calculatePdAuc(rows) {
  const positives = rows.filter(row => row.observed === 1).length;
  const negatives = rows.filter(row => row.observed === 0).length;
  if (!positives || !negatives) return null;

  const sorted = rows.slice().sort((a,b) => a.predicted - b.predicted);
  let positiveRankTotal = 0;
  let index = 0;
  while (index < sorted.length) {
    let end = index + 1;
    while (end < sorted.length && sorted[end].predicted === sorted[index].predicted) end += 1;
    const averageRank = ((index + 1) + end) / 2;
    for (let i = index; i < end; i += 1) {
      if (sorted[i].observed === 1) positiveRankTotal += averageRank;
    }
    index = end;
  }
  return (positiveRankTotal - positives * (positives + 1) / 2) / (positives * negatives);
}

function calculatePdKs(rows) {
  const positives = rows.filter(row => row.observed === 1).length;
  const negatives = rows.filter(row => row.observed === 0).length;
  if (!positives || !negatives) return null;

  const sorted = rows.slice().sort((a,b) => a.predicted - b.predicted);
  let cumulativePositives = 0;
  let cumulativeNegatives = 0;
  let maximumDistance = 0;
  let index = 0;
  while (index < sorted.length) {
    let end = index + 1;
    while (end < sorted.length && sorted[end].predicted === sorted[index].predicted) end += 1;
    for (let i = index; i < end; i += 1) {
      if (sorted[i].observed === 1) cumulativePositives += 1;
      else cumulativeNegatives += 1;
    }
    maximumDistance = Math.max(
      maximumDistance,
      Math.abs(cumulativePositives / positives - cumulativeNegatives / negatives),
    );
    index = end;
  }
  return maximumDistance;
}

function calculatePdPerformanceMetrics(rows) {
  if (!rows.length) {
    return {
      observed_default_rate: null,
      predicted_default_rate: null,
      actual_expected_ratio: null,
      accuracy_ratio: null,
      gini_coefficient: null,
      ks_statistic: null,
    };
  }

  const observedDefaultRate = rows.reduce((sum, row) => sum + row.observed, 0) / rows.length;
  const predictedDefaultRate = rows.reduce((sum, row) => sum + row.predicted, 0) / rows.length;
  const auc = calculatePdAuc(rows);
  const accuracyRatio = auc == null ? null : 2 * auc - 1;
  return {
    observed_default_rate: observedDefaultRate,
    predicted_default_rate: predictedDefaultRate,
    actual_expected_ratio: predictedDefaultRate ? observedDefaultRate / predictedDefaultRate : null,
    accuracy_ratio: accuracyRatio,
    gini_coefficient: accuracyRatio,
    ks_statistic: calculatePdKs(rows),
  };
}

const PD_RAG_GROUPS = {
  calibration: ['Confidence Interval Test', 'Notching Test'],
  discrimination: ['Accuracy Ratio', 'Gini Coefficient', 'KS Statistic', "Kendall's Tau"],
  performance: ['Brier Score', 'Population Stability Index', 'Rating Migration Index'],
};
const PD_THRESHOLD_METRIC_ALIASES = {
  'Confidence Interval Test': 'Confidence Interval',
};

const PD_TIME_RANGES = {
  calibration: {from: '', to: ''},
  calibration_rag: {from: '', to: ''},
  balance_sheet_calibration: {from: '', to: ''},
  balance_sheet_calibration_rag: {from: '', to: ''},
  discrimination_accuracy: {from: '', to: ''},
  discrimination_rag: {from: '', to: ''},
  discrimination: {from: '', to: ''},
  stability: {from: '', to: ''},
};
let PD_CALIBRATION_TREND_HORIZON = '1y';
let PD_DISCRIMINATION_TREND_HORIZON = '1y';
let PD_EXPANDED_PANEL = null;
let PD_EXPANDED_PLACEHOLDER = null;
const PD_GO_LIVE_QUARTER_START = '2019Q2';
const PD_GO_LIVE_QUARTER_END = '2019Q4';

function getPdRangePeriods(maxQuarter) {
  return Array.from(new Set(
    (DASH_DATA.quarters || []).filter(quarter => quarter && quarter <= maxQuarter),
  )).sort();
}

function getPdRangeSelection(rangeKey, periods) {
  const range = PD_TIME_RANGES[rangeKey] || {};
  return {
    from: periods.includes(range.from) ? range.from : '',
    to: periods.includes(range.to) ? range.to : '',
  };
}

function filterPdPeriodsByRange(rangeKey, periods) {
  const range = getPdRangeSelection(rangeKey, periods);
  return periods.filter(period => (!range.from || period >= range.from) && (!range.to || period <= range.to));
}

function getPdRangePreset(rangeKey, periods) {
  const range = getPdRangeSelection(rangeKey, periods);
  if (!range.from && !range.to) return 'all';
  const lastPeriod = periods[periods.length - 1] || '';
  for (const count of [4, 8, 12]) {
    const firstPeriod = periods[Math.max(0, periods.length - count)] || '';
    if (range.from === firstPeriod && range.to === lastPeriod) return `last-${count}`;
  }
  return 'custom';
}

function setPdRangePreset(rangeKey, preset, maxQuarter) {
  if (!PD_TIME_RANGES[rangeKey]) return;
  const periods = getPdRangePeriods(maxQuarter);
  if (preset === 'all') {
    PD_TIME_RANGES[rangeKey] = {from: '', to: ''};
  } else {
    const count = Number((preset || '').replace('last-', ''));
    if (![4, 8, 12].includes(count) || !periods.length) return;
    PD_TIME_RANGES[rangeKey] = {
      from: periods[Math.max(0, periods.length - count)],
      to: periods[periods.length - 1],
    };
  }
  renderPdModels();
}

function setPdRangeBoundary(rangeKey, boundary, value) {
  if (!PD_TIME_RANGES[rangeKey] || !['from', 'to'].includes(boundary)) return;
  const range = {...PD_TIME_RANGES[rangeKey], [boundary]: value};
  if (range.from && range.to && range.from > range.to) {
    if (boundary === 'from') range.to = range.from;
    else range.from = range.to;
  }
  PD_TIME_RANGES[rangeKey] = range;
  renderPdModels();
}

function buildPdPeriodOptions(periods, selected, allLabel) {
  return [
    `<option value=""${selected ? '' : ' selected'}>${allLabel}</option>`,
    ...periods.map(period => `<option value="${period}"${period === selected ? ' selected' : ''}>${period}</option>`),
  ].join('');
}

function buildPdRangeControls(rangeKey, periods, maxQuarter) {
  const range = getPdRangeSelection(rangeKey, periods);
  const preset = getPdRangePreset(rangeKey, periods);
  return `
    <div class="pd-range-controls" aria-label="Visible time range">
      <label>
        <span>Window</span>
        <select aria-label="Time window" onchange="setPdRangePreset('${rangeKey}',this.value,'${maxQuarter}')">
          <option value="all"${preset === 'all' ? ' selected' : ''}>All periods</option>
          <option value="last-4"${preset === 'last-4' ? ' selected' : ''}>Last 4 quarters</option>
          <option value="last-8"${preset === 'last-8' ? ' selected' : ''}>Last 8 quarters</option>
          <option value="last-12"${preset === 'last-12' ? ' selected' : ''}>Last 12 quarters</option>
          <option value="custom"${preset === 'custom' ? ' selected' : ''} disabled>Custom range</option>
        </select>
      </label>
      <label>
        <span>From</span>
        <select aria-label="Start quarter" onchange="setPdRangeBoundary('${rangeKey}','from',this.value)">
          ${buildPdPeriodOptions(periods, range.from, 'Earliest')}
        </select>
      </label>
      <label>
        <span>To</span>
        <select aria-label="End quarter" onchange="setPdRangeBoundary('${rangeKey}','to',this.value)">
          ${buildPdPeriodOptions(periods, range.to, 'Latest')}
        </select>
      </label>
    </div>`;
}

function setPdCalibrationTrendHorizon(horizonKey) {
  if (!['1y', '2y'].includes(horizonKey)) return;
  PD_CALIBRATION_TREND_HORIZON = horizonKey;
  renderPdModels();
}

function buildPdCalibrationTrendHorizonControl() {
  return `
    <div class="pd-range-controls" aria-label="Calibration trend PD horizon">
      <label>
        <span>PD Horizon</span>
        <select aria-label="Calibration trend time horizon" onchange="setPdCalibrationTrendHorizon(this.value)">
          <option value="1y"${PD_CALIBRATION_TREND_HORIZON === '1y' ? ' selected' : ''}>1 year</option>
          <option value="2y"${PD_CALIBRATION_TREND_HORIZON === '2y' ? ' selected' : ''}>2 years</option>
        </select>
      </label>
    </div>`;
}

function setPdDiscriminationTrendHorizon(horizonKey) {
  if (!['1y', '2y'].includes(horizonKey)) return;
  PD_DISCRIMINATION_TREND_HORIZON = horizonKey;
  renderPdModels();
}

function buildPdDiscriminationTrendHorizonControl() {
  return `
    <div class="pd-range-controls" aria-label="Discrimination trend PD horizon">
      <label>
        <span>PD Horizon</span>
        <select aria-label="Discrimination trend time horizon" onchange="setPdDiscriminationTrendHorizon(this.value)">
          <option value="1y"${PD_DISCRIMINATION_TREND_HORIZON === '1y' ? ' selected' : ''}>1 year</option>
          <option value="2y"${PD_DISCRIMINATION_TREND_HORIZON === '2y' ? ' selected' : ''}>2 years</option>
        </select>
      </label>
    </div>`;
}

function buildPdFrozenOneYearHorizonControl(label = 'PD Horizon') {
  return `
    <div class="pd-range-controls" aria-label="${label}">
      <label>
        <span>PD Horizon</span>
        <select aria-label="${label}" disabled>
          <option value="1y" selected>1 year</option>
        </select>
      </label>
    </div>`;
}

function pdExpandButton(panelId, title) {
  return `<button type="button" class="pd-expand-button" onclick="openPdExpandedPanel('${panelId}')" aria-label="Enlarge ${title}" title="Enlarge ${title}">
    <span aria-hidden="true">&#x26F6;</span><span>Enlarge</span>
  </button>`;
}

function buildPdChartHeader(title, subtitle, panelId, rangeKey = '', periods = [], maxQuarter = '', extraControls = '') {
  return `
    <div class="pd-chart-heading">
      <div class="pd-chart-heading-copy">
        <div class="section-title">${title}</div>
        <div class="pd-section-subtitle">${subtitle}</div>
      </div>
      <div class="pd-chart-actions">
        ${extraControls}
        ${rangeKey ? buildPdRangeControls(rangeKey, periods, maxQuarter) : ''}
        ${pdExpandButton(panelId, title)}
      </div>
    </div>`;
}

function resizePdPanelCharts(panel, expanded) {
  if (!panel || typeof Plotly === 'undefined') return;
  panel.querySelectorAll('.js-plotly-plot').forEach(chart => {
    if (!chart.__pdBaseHeight) chart.__pdBaseHeight = (chart.layout && chart.layout.height) || chart.offsetHeight;
    Plotly.relayout(chart, {height: expanded ? Math.max(520, window.innerHeight - 210) : chart.__pdBaseHeight});
    requestAnimationFrame(() => Plotly.Plots.resize(chart));
  });
}

function openPdExpandedPanel(panelId) {
  closePdExpandedPanel(false);
  const panel = document.getElementById(panelId);
  const modal = document.getElementById('pd-expanded-modal');
  const modalBody = document.getElementById('pd-expanded-modal-body');
  const modalTitle = document.getElementById('pd-expanded-modal-title');
  if (!panel || !modal || !modalBody || !modalTitle) return;

  PD_EXPANDED_PANEL = panel;
  PD_EXPANDED_PLACEHOLDER = document.createComment(`Restore ${panelId}`);
  panel.parentNode.insertBefore(PD_EXPANDED_PLACEHOLDER, panel);
  modalTitle.textContent = panel.dataset.pdExpandTitle || 'PD Analysis';
  modalBody.appendChild(panel);
  panel.classList.add('pd-expanded-panel');
  modal.classList.add('active');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('pd-modal-open');
  document.getElementById('pd-expanded-modal-close').focus();
  requestAnimationFrame(() => resizePdPanelCharts(panel, true));
}

function closePdExpandedPanel(restoreFocus = true) {
  const modal = document.getElementById('pd-expanded-modal');
  if (!PD_EXPANDED_PANEL || !PD_EXPANDED_PLACEHOLDER) return;
  const panelId = PD_EXPANDED_PANEL.id;
  resizePdPanelCharts(PD_EXPANDED_PANEL, false);
  PD_EXPANDED_PLACEHOLDER.parentNode.insertBefore(PD_EXPANDED_PANEL, PD_EXPANDED_PLACEHOLDER);
  PD_EXPANDED_PLACEHOLDER.remove();
  PD_EXPANDED_PANEL.classList.remove('pd-expanded-panel');
  PD_EXPANDED_PANEL = null;
  PD_EXPANDED_PLACEHOLDER = null;
  if (modal) {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
  }
  document.body.classList.remove('pd-modal-open');
  if (restoreFocus) {
    const button = document.querySelector(`[onclick="openPdExpandedPanel('${panelId}')"]`);
    if (button) button.focus();
  }
}

function handlePdModalKeydown(event) {
  if (event.key === 'Escape') closePdExpandedPanel();
}

function calculatePdBrierScore(rows) {
  if (!rows.length) return null;
  return rows.reduce((sum, row) => sum + (row.observed - row.predicted) ** 2, 0) / rows.length;
}

const DEFAULT_PD_CRR_MASTER_SCALE = [
  {CRR: 1.0, 'Min PD': 0.0, 'Max PD': 0.0015},
  {CRR: 2.0, 'Min PD': 0.0015, 'Max PD': 0.005},
  {CRR: 3.0, 'Min PD': 0.005, 'Max PD': 0.01},
  {CRR: 4.0, 'Min PD': 0.01, 'Max PD': 0.025},
  {CRR: 5.0, 'Min PD': 0.025, 'Max PD': 0.05},
  {CRR: 6.0, 'Min PD': 0.05, 'Max PD': 0.1},
  {CRR: 7.0, 'Min PD': 0.1, 'Max PD': 0.2},
  {CRR: 8.0, 'Min PD': 0.2, 'Max PD': 0.9999},
  {CRR: 9.0, 'Min PD': 1.0, 'Max PD': 1.0},
];

const DEFAULT_PD_CONFIDENCE_INTERVAL_THRESHOLD = {
  metric: 'Confidence Interval',
  dimension: 'ECL PIT PD - Calibration Conservatism',
  green_rule: 'value >= 0.45',
  amber_rule: '0.35 <= value < 0.45',
  red_rule: 'value < 0.35',
  green_min: 0.45,
  green_max: NaN,
  amber_min: 0.35,
  amber_max: 0.45,
  red_condition: 'below amber_min',
  higher_is_better: true,
  lower_is_better: false,
  target_value: NaN,
  warning_message: null,
  notes: 'Dummy monitoring metric placeholder.',
};

const DEFAULT_PD_RAG_ASSIGNMENT = [
  {'Notching Test': '>2', 'p<5%': 'Amber', '5%<=p<=90%': 'Green', '90%<p<=97.5%': 'Amber', 'p>97.5%': 'Red'},
  {'Notching Test': '+2', 'p<5%': 'Green', '5%<=p<=90%': 'Green', '90%<p<=97.5%': 'Amber', 'p>97.5%': 'Amber'},
  {'Notching Test': '0 to +/-1', 'p<5%': 'Green', '5%<=p<=90%': 'Green', '90%<p<=97.5%': 'Green', 'p>97.5%': 'Amber'},
  {'Notching Test': '-2', 'p<5%': 'Amber', '5%<=p<=90%': 'Amber', '90%<p<=97.5%': 'Amber', 'p>97.5%': 'Amber'},
  {'Notching Test': '<-2', 'p<5%': 'Amber', '5%<=p<=90%': 'Amber', '90%<p<=97.5%': 'Amber', 'p>97.5%': 'Red'},
];

function getPdThresholds() {
  const thresholds = ((DASH_DATA.monitoring_thresholds || {}).pd_thresholds || []).slice();
  if (!thresholds.some(row => row.metric === 'Confidence Interval')) {
    thresholds.push(DEFAULT_PD_CONFIDENCE_INTERVAL_THRESHOLD);
  }
  return thresholds;
}

function getPdThresholdMetricName(metric) {
  return PD_THRESHOLD_METRIC_ALIASES[metric] || metric;
}

function getPdRagAssignment() {
  const rows = ((DASH_DATA.monitoring_thresholds || {}).rag_assignment_pd || DEFAULT_PD_RAG_ASSIGNMENT);
  return rows.map(row => ({
    notchingBucket: String(row.notching_bucket ?? row['Notching Test'] ?? '').trim(),
    pLow: row['p<5%'] ?? row.p_lt_5 ?? row.p_low,
    pMid: row['5%<=p<=90%'] ?? row.p_5_to_90 ?? row.p_mid,
    pHigh: row['90%<p<=97.5%'] ?? row.p_90_to_975 ?? row.p_high,
    pVeryHigh: row['p>97.5%'] ?? row.p_gt_975 ?? row.p_very_high,
  })).filter(row => row.notchingBucket);
}

function getPdCrrMasterScale() {
  const rows = ((DASH_DATA.monitoring_thresholds || {}).crr_master_scale || DEFAULT_PD_CRR_MASTER_SCALE);
  return rows.map(row => ({
    crr: Number(row.crr ?? row.CRR),
    minPd: Number(row.min_pd ?? row['Min PD']),
    maxPd: Number(row.max_pd ?? row['Max PD']),
  })).filter(row => (
    Number.isFinite(row.crr)
    && Number.isFinite(row.minPd)
    && Number.isFinite(row.maxPd)
  )).sort((left, right) => (left.minPd - right.minPd) || (left.crr - right.crr));
}

function mapPdProbabilityToCrr(probability) {
  if (probability == null || !Number.isFinite(probability)) return null;
  const scale = getPdCrrMasterScale();
  if (!scale.length) return null;
  if (probability <= scale[0].minPd) return scale[0].crr;

  for (let index = 0; index < scale.length; index += 1) {
    const row = scale[index];
    const isLast = index === scale.length - 1;
    const nextMin = !isLast ? scale[index + 1].minPd : row.maxPd;
    if (probability >= row.minPd && (probability < nextMin || (isLast && probability <= row.maxPd))) {
      return row.crr;
    }
  }
  return scale[scale.length - 1].crr;
}

function calculatePdNotchingComponents(rows) {
  if (!rows.length) return {actualNotch: null, predictedNotch: null, difference: null};
  const predicted = rows.map(row => row.predicted).filter(Number.isFinite);
  const observed = rows.map(row => row.observed).filter(Number.isFinite);
  if (!predicted.length || !observed.length) return {actualNotch: null, predictedNotch: null, difference: null};

  const averagePredicted = predicted.reduce((sum, value) => sum + value, 0) / predicted.length;
  const averageObserved = observed.reduce((sum, value) => sum + value, 0) / observed.length;
  const predictedNotch = mapPdProbabilityToCrr(averagePredicted);
  const actualNotch = mapPdProbabilityToCrr(averageObserved);
  if (!Number.isFinite(predictedNotch) || !Number.isFinite(actualNotch)) {
    return {actualNotch: null, predictedNotch: null, difference: null};
  }
  return {
    actualNotch,
    predictedNotch,
    signedDifference: predictedNotch - actualNotch,
    difference: Math.abs(predictedNotch - actualNotch),
  };
}

function getPdConfidenceIntervalBucket(value) {
  if (value == null || !Number.isFinite(value)) return '';
  if (value < 0.05) return 'pLow';
  if (value <= 0.90) return 'pMid';
  if (value <= 0.975) return 'pHigh';
  return 'pVeryHigh';
}

function getPdNotchingBucket(value) {
  if (value == null || !Number.isFinite(value)) return '';
  if (value > 2) return '>2';
  if (Math.abs(value - 2) < 1e-9) return '+2';
  if (value < -2) return '<-2';
  if (Math.abs(value + 2) < 1e-9) return '-2';
  return '0 to +/-1';
}

function calculatePdCalibrationAssignmentRag(confidenceInterval, signedNotchingDifference) {
  const confidenceBucket = getPdConfidenceIntervalBucket(confidenceInterval);
  const notchingBucket = getPdNotchingBucket(signedNotchingDifference);
  if (!confidenceBucket || !notchingBucket) return 'N/A';
  const row = getPdRagAssignment().find(entry => entry.notchingBucket === notchingBucket);
  const rag = row ? row[confidenceBucket] : '';
  return rag ? String(rag).trim() : 'N/A';
}

function hashPdSeed(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function calculatePdConfidenceIntervalComponents(rows) {
  if (!rows.length) {
    return {
      actualConfidenceInterval: null,
      predictedConfidenceInterval: null,
      confidenceInterval: null,
      difference: null,
    };
  }

  const predicted = rows.map(row => row.predicted).filter(Number.isFinite);
  const observed = rows.map(row => row.observed).filter(Number.isFinite);
  if (!predicted.length || !observed.length) {
    return {
      actualConfidenceInterval: null,
      predictedConfidenceInterval: null,
      confidenceInterval: null,
      difference: null,
    };
  }

  const averagePredicted = predicted.reduce((sum, value) => sum + value, 0) / predicted.length;
  const averageObserved = observed.reduce((sum, value) => sum + value, 0) / observed.length;
  const predictedStd = predicted.length > 1
    ? Math.sqrt(predicted.reduce((sum, value) => sum + (value - averagePredicted) ** 2, 0) / predicted.length)
    : 0;
  const observedStd = observed.length > 1
    ? Math.sqrt(observed.reduce((sum, value) => sum + (value - averageObserved) ** 2, 0) / observed.length)
    : 0;
  const seed = [
    rows.length,
    averagePredicted.toFixed(6),
    averageObserved.toFixed(6),
    predictedStd.toFixed(6),
    observedStd.toFixed(6),
  ].join('|');
  const normalized = hashPdSeed(seed) / 4294967295;
  const spread = Math.min(0.22, 0.04 + Math.abs(averagePredicted - averageObserved) * 2 + (predictedStd + observedStd) * 0.5);
  const actualConfidenceInterval = Math.min(1, normalized + spread / 2);
  const predictedConfidenceInterval = Math.max(0, normalized - spread / 2);

  return {
    actualConfidenceInterval,
    predictedConfidenceInterval,
    confidenceInterval: normalized,
    difference: Math.abs(actualConfidenceInterval - predictedConfidenceInterval),
  };
}

function calculatePdConfidenceInterval(rows) {
  return calculatePdConfidenceIntervalComponents(rows).confidenceInterval;
}

function calculatePdQuantile(sortedValues, probability) {
  const position = (sortedValues.length - 1) * probability;
  const lowerIndex = Math.floor(position);
  const upperIndex = Math.ceil(position);
  const lower = sortedValues[lowerIndex];
  const upper = sortedValues[upperIndex];
  return lower + (upper - lower) * (position - lowerIndex);
}

function calculatePdPsi(currentRows, previousRows, buckets = 10) {
  const current = currentRows.map(row => row.predicted).filter(Number.isFinite);
  const previous = previousRows.map(row => row.predicted).filter(Number.isFinite);
  if (!current.length || !previous.length) return null;
  if (new Set(previous).size < 3) return 0;

  const sortedPrevious = previous.slice().sort((a,b) => a - b);
  const breaks = [];
  for (let index = 0; index <= buckets; index += 1) {
    const value = calculatePdQuantile(sortedPrevious, index / buckets);
    if (!breaks.length || value !== breaks[breaks.length - 1]) breaks.push(value);
  }
  if (breaks.length < 3) return 0;

  function distribution(values) {
    const counts = breaks.slice(1).map(() => 0);
    let included = 0;
    values.forEach(value => {
      if (value < breaks[0] || value > breaks[breaks.length - 1]) return;
      let bucketIndex = breaks.length - 2;
      for (let index = 1; index < breaks.length; index += 1) {
        if (value <= breaks[index]) {
          bucketIndex = index - 1;
          break;
        }
      }
      counts[bucketIndex] += 1;
      included += 1;
    });
    return included ? counts.map(count => count / included) : [];
  }

  const currentDistribution = distribution(current);
  const previousDistribution = distribution(previous);
  if (!currentDistribution.length || !previousDistribution.length) return null;
  return currentDistribution.reduce((sum, value, index) => {
    const currentShare = value || 0.0001;
    const previousShare = previousDistribution[index] || 0.0001;
    return sum + (currentShare - previousShare) * Math.log(currentShare / previousShare);
  }, 0);
}

function calculatePdRatingMigrationIndex(observations, currentQuarter, previousQuarter) {
  if (!previousQuarter) return null;
  const currentRows = filterPdRatingObservations(observations, currentQuarter);
  const previousRows = filterPdRatingObservations(observations, previousQuarter);
  const currentByAccount = new Map(currentRows.map(row => [row.account, Number(row.rating)]));
  const migrations = previousRows.flatMap(row => {
    const currentRating = currentByAccount.get(row.account);
    const previousRating = Number(row.rating);
    return Number.isFinite(currentRating) && Number.isFinite(previousRating)
      ? [Math.abs(currentRating - previousRating)]
      : [];
  });
  return migrations.length
    ? migrations.reduce((sum, value) => sum + value, 0) / migrations.length
    : null;
}

function calculatePdNotchingTest(rows) {
  return calculatePdNotchingComponents(rows).difference;
}

function calculatePdKendallTau(rows) {
  if (rows.length < 2) return null;
  let concordant = 0;
  let discordant = 0;
  let predictedTies = 0;
  let observedTies = 0;
  for (let left = 0; left < rows.length; left += 1) {
    for (let right = left + 1; right < rows.length; right += 1) {
      const predictedDelta = rows[left].predicted - rows[right].predicted;
      const observedDelta = rows[left].observed - rows[right].observed;
      if (predictedDelta === 0 && observedDelta === 0) continue;
      if (predictedDelta === 0) predictedTies += 1;
      else if (observedDelta === 0) observedTies += 1;
      else if (predictedDelta * observedDelta > 0) concordant += 1;
      else discordant += 1;
    }
  }
  const denominator = Math.sqrt(
    (concordant + discordant + predictedTies) * (concordant + discordant + observedTies),
  );
  return denominator ? (concordant - discordant) / denominator : null;
}

function getPdGoLiveQuarter(performanceObservations, horizonKey) {
  const goLiveQuarters = Array.from(new Set(
    (DASH_DATA.quarters || []).filter(
      quarter => quarter && quarter >= PD_GO_LIVE_QUARTER_START && quarter <= PD_GO_LIVE_QUARTER_END,
    ),
  )).sort().reverse();

  for (const quarter of goLiveQuarters) {
    const rows = filterPdPerformanceObservationsForHorizon(performanceObservations, quarter, horizonKey);
    const accuracyRatio = calculatePdPerformanceMetrics(rows).accuracy_ratio;
    if (Number.isFinite(accuracyRatio)) return quarter;
  }
  return '';
}

function calculatePdRagMetricsForHorizon(performanceObservations, ratingObservations, quarter, horizonKey) {
  const previousQuarter = getPreviousPdQuarter(quarter);
  const currentRows = filterPdPerformanceObservationsForHorizon(performanceObservations, quarter, horizonKey);
  const previousRows = filterPdPerformanceObservationsForHorizon(performanceObservations, previousQuarter, horizonKey);
  const goLiveQuarter = getPdGoLiveQuarter(performanceObservations, horizonKey);
  const goLiveRows = goLiveQuarter
    ? filterPdPerformanceObservationsForHorizon(performanceObservations, goLiveQuarter, horizonKey)
    : [];
  const metrics = calculatePdPerformanceMetrics(currentRows);
  const goLiveMetrics = calculatePdPerformanceMetrics(goLiveRows);
  const goLiveAccuracyRatio = goLiveMetrics.accuracy_ratio;
  const deltaAccuracyRatio = Number.isFinite(goLiveAccuracyRatio) && Number.isFinite(metrics.accuracy_ratio) && goLiveAccuracyRatio !== 0
    ? (goLiveAccuracyRatio - metrics.accuracy_ratio) / goLiveAccuracyRatio
    : null;
  return {
    'Observed Default Rate': metrics.observed_default_rate,
    'Predicted Default Rate': metrics.predicted_default_rate,
    'Actual / Expected Ratio': metrics.actual_expected_ratio,
    'Confidence Interval Test': calculatePdConfidenceInterval(currentRows),
    'Accuracy Ratio': metrics.accuracy_ratio,
    'Go Live Accuracy Ratio': goLiveAccuracyRatio,
    'Go Live Quarter': goLiveQuarter,
    'Delta Accuracy Ratio': deltaAccuracyRatio,
    'Gini Coefficient': metrics.gini_coefficient,
    'KS Statistic': metrics.ks_statistic,
    'Brier Score': calculatePdBrierScore(currentRows),
    'Population Stability Index': calculatePdPsi(currentRows, previousRows),
    'Rating Migration Index': calculatePdRatingMigrationIndex(ratingObservations, quarter, previousQuarter),
    'Notching Test': calculatePdNotchingTest(currentRows),
    "Kendall's Tau": calculatePdKendallTau(currentRows),
  };
}

function calculatePdRagMetrics(performanceObservations, ratingObservations, quarter) {
  return calculatePdRagMetricsForHorizon(
    performanceObservations,
    ratingObservations,
    quarter,
    getPdPerformanceHorizonKey(),
  );
}

function calculatePdMetricRag(thresholds, metric, value) {
  if (value == null || !Number.isFinite(value)) return 'N/A';
  const threshold = thresholds.find(row => row.metric === getPdThresholdMetricName(metric));
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
  if (matchesPdThresholdRule(threshold.green_rule, value)) return 'Green';
  if (matchesPdThresholdRule(threshold.amber_rule, value)) return 'Amber';
  if (matchesPdThresholdRule(threshold.red_rule, value)) return 'Red';
  return 'N/A';
}

function calculatePdDefaultCountForHorizon(performanceObservations, quarter, horizonKey = '1y') {
  if (!quarter) return 0;
  const rows = filterPdPerformanceObservationsForHorizon(performanceObservations, quarter, horizonKey);
  return rows.reduce((sum, row) => sum + (row.observed === 1 ? 1 : 0), 0);
}

function getWorstPdRag(rags) {
  const scores = {'N/A': 0, Green: 1, Amber: 2, Red: 3};
  return rags.reduce(
    (worst, rag) => (scores[rag] || 0) > (scores[worst] || 0) ? rag : worst,
    'N/A',
  );
}

function calculatePdDiscriminationSectionRag(thresholds, values, defaultCount1y = null) {
  if (Number.isFinite(defaultCount1y) && defaultCount1y < 15) return 'Amber';
  const accuracyRag = calculatePdMetricRag(thresholds, 'Accuracy Ratio', values['Accuracy Ratio']);
  const deltaAccuracyRag = calculatePdMetricRag(thresholds, 'Delta Accuracy Ratio', values['Delta Accuracy Ratio']);

  if (deltaAccuracyRag === 'Red' && accuracyRag === 'Green') return 'Amber';
  if (deltaAccuracyRag === 'Red' && accuracyRag === 'Amber') return 'Red';
  if (deltaAccuracyRag === 'Amber' || deltaAccuracyRag === 'Green') return accuracyRag;
  return accuracyRag;
}

function pdRagDot(rag) {
  const css = (rag || 'N/A').toLowerCase().replace('/', '').replace(' ', '-');
  return `<span class="pd-rag-dot pd-rag-${css}" role="img" aria-label="${rag}" title="${rag}">●</span>`;
}

function pdRagColor(rag) {
  return rag === 'Green'
    ? '#16a34a'
    : rag === 'Amber'
      ? '#d97706'
      : rag === 'Red'
        ? '#dc2626'
        : '#94a3b8';
}

function pdRagCell(rag) {
  const tone = pdToneClass(rag);
  const label = rag === 'N/A' ? 'N/A' : rag.slice(0, 1);
  return `<span class="pd-rag-cell pd-rag-cell-${tone}" aria-label="${rag}" title="${rag}">${label}</span>`;
}

function buildPdRagMovement(pd, metrics, rangeKey, snapshotQuarter) {
  const availablePeriods = getPdRangePeriods(snapshotQuarter);
  const periods = filterPdPeriodsByRange(rangeKey, availablePeriods);
  if (!periods.length) {
    return '<div class="pd-performance-note">No RAG movement is available for the selected period.</div>';
  }

  const thresholds = getPdThresholds();
  const observations = pd.performance_observations || [];
  const ratingObservations = pd.rating_migration_observations || [];
  const statusByPeriod = periods.map(period => {
    const values = calculatePdRagMetrics(observations, ratingObservations, period);
    const rags = metrics.map(metric => calculatePdMetricRag(thresholds, metric, values[metric]));
    return {period, rags, groupRag: getWorstPdRag(rags)};
  });
  const rows = [
    {
      metric: 'Section RAG',
      css: 'pd-rag-movement-summary',
      rags: statusByPeriod.map(period => period.groupRag),
    },
    ...metrics.map((metric, index) => ({
      metric,
      css: '',
      rags: statusByPeriod.map(period => period.rags[index]),
    })),
  ];

  return `
    <div class="pd-rag-movement">
      <div class="pd-rag-movement-heading">
        <strong>RAG Movement</strong>
        <span>Quarter-by-quarter threshold status for the trend above.</span>
      </div>
      <div class="pd-rag-movement-wrap">
        <table class="pd-rag-movement-table">
          <thead><tr><th>Test</th>${periods.map(period => `<th>${period}</th>`).join('')}</tr></thead>
          <tbody>
            ${rows.map(row => `<tr class="${row.css}"><td>${escapePdHtml(row.metric)}</td>${row.rags.map(rag => `<td>${pdRagCell(rag)}</td>`).join('')}</tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="pd-rag-legend" aria-label="RAG status legend">
        <span>${pdRagDot('Green')} Within threshold</span>
        <span>${pdRagDot('Amber')} Monitor closely</span>
        <span>${pdRagDot('Red')} Action required</span>
        <span>${pdRagDot('N/A')} Insufficient data</span>
      </div>
      </div>`;
}

function buildPdCalibrationRagTrend(pd, observations, ratingObservations, monitoringQuarter) {
  return Array.from(new Set(
    (DASH_DATA.quarters || []).filter(quarter => quarter && quarter <= monitoringQuarter),
  )).sort().map(quarter => {
    const details = calculatePdCalibrationConservatismDetails(
      pd,
      observations,
      ratingObservations,
      quarter,
    );
    const horizonMap = Object.fromEntries((details.horizons || []).map(horizon => [horizon.key, horizon]));
    return {
      quarter,
      rag: details.rag,
      rag_score: pdRagScore(details.rag),
      weighted_average: details.weightedAverage,
      rounded_score: details.roundedScore,
    };
  });
}

function buildPdDiscriminationRagTrend(observations, ratingObservations, monitoringQuarter) {
  const thresholds = getPdThresholds();
  return Array.from(new Set(
    (DASH_DATA.quarters || []).filter(quarter => quarter && quarter <= monitoringQuarter),
  )).sort().map(quarter => {
    const values = calculatePdRagMetricsForHorizon(
      observations,
      ratingObservations,
      quarter,
      '1y',
    );
    const defaultCount1y = calculatePdDefaultCountForHorizon(observations, quarter, '1y');
    const accuracyRatio = values['Accuracy Ratio'];
    const deltaAccuracyRatio = values['Delta Accuracy Ratio'];
    const accuracyRag = calculatePdMetricRag(thresholds, 'Accuracy Ratio', accuracyRatio);
    const deltaAccuracyRag = calculatePdMetricRag(thresholds, 'Delta Accuracy Ratio', deltaAccuracyRatio);
    const rag = calculatePdDiscriminationSectionRag(thresholds, values, defaultCount1y);
    return {
      quarter,
      rag,
      rag_score: pdRagScore(rag),
      accuracy_ratio: accuracyRatio,
      accuracy_rag: accuracyRag,
      delta_accuracy_ratio: deltaAccuracyRatio,
      delta_accuracy_rag: deltaAccuracyRag,
      default_count_1y: defaultCount1y,
      low_default_override: Number.isFinite(defaultCount1y) && defaultCount1y < 15,
    };
  });
}

function buildPdBalanceSheetCalibrationRagTrend(observations, ratingObservations, monitoringQuarter) {
  const thresholds = getPdThresholds();
  return Array.from(new Set(
    (DASH_DATA.quarters || []).filter(quarter => quarter && quarter <= monitoringQuarter),
  )).sort().map(quarter => {
    const values = calculatePdRagMetricsForHorizon(
      observations,
      ratingObservations,
      quarter,
      'nco_1y',
    );
    const notching = calculatePdNotchingComponents(filterPdPerformanceObservationsForHorizon(
      observations,
      quarter,
      'nco_1y',
    ));
    const assignmentRag = calculatePdCalibrationAssignmentRag(
      values['Confidence Interval Test'],
      notching.signedDifference,
    );
    const rag = assignmentRag === 'N/A'
      ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(
        metric => calculatePdMetricRag(thresholds, metric, values[metric]),
      ))
      : assignmentRag;
    return {
      quarter,
      rag,
      rag_score: pdRagScore(rag),
      confidence_interval: values['Confidence Interval Test'],
      confidence_rag: calculatePdMetricRag(thresholds, 'Confidence Interval Test', values['Confidence Interval Test']),
      notching_difference: notching.signedDifference,
      notching_rag: calculatePdMetricRag(thresholds, 'Notching Test', notching.signedDifference),
      assignment_rag: assignmentRag,
    };
  });
}

function formatPdMetric(value, format) {
  if (value == null || !Number.isFinite(value)) return '—';
  if (format === 'percent') return `${(value * 100).toFixed(2)}%`;
  if (format === 'count') return `${Math.round(value)}`;
  return value.toFixed(3);
}

function formatPdShare(value, total) {
  return total ? `${fmtN(value)} (${(value / total * 100).toFixed(1)}%)` : `${fmtN(value)} (—)`;
}

function pdToneClass(rag) {
  return rag === 'Green' ? 'green' : rag === 'Amber' ? 'amber' : rag === 'Red' ? 'red' : 'na';
}

function pdRagScore(rag) {
  return rag === 'Red' ? 1 : rag === 'Amber' ? 2 : rag === 'Green' ? 3 : null;
}

function pdScoreToRag(score) {
  return score === 1 ? 'Red' : score === 2 ? 'Amber' : score === 3 ? 'Green' : 'N/A';
}

function roundPdHalfDown(value) {
  if (value == null || !Number.isFinite(value)) return null;
  const lower = Math.floor(value);
  return value - lower > 0.5 ? lower + 1 : lower;
}

function calculatePdCalibrationConservatismDetails(pd, observations, ratingObservations, monitoringQuarter) {
  if (!monitoringQuarter) {
    return {rag: 'N/A', weightedAverage: null, roundedScore: null, horizons: [], totalWeight: 0};
  }
  const eadSummaries = calculatePdEadSummaries(observations, monitoringQuarter);
  const horizonConfigs = [{key: '1y', years: 1}, {key: '2y', years: 2}];
  const weightedScores = horizonConfigs.flatMap(horizonConfig => {
    const snapshotQuarter = shiftMonitoringQuarterYear(monitoringQuarter, -horizonConfig.years);
    if (!snapshotQuarter) return [];
    const horizonValues = calculatePdRagMetricsForHorizon(
      observations,
      ratingObservations,
      snapshotQuarter,
      horizonConfig.key,
    );
    const horizonNotching = calculatePdNotchingComponents(filterPdPerformanceObservationsForHorizon(
      observations,
      snapshotQuarter,
      horizonConfig.key,
    ));
    const rag = calculatePdCalibrationAssignmentRag(
      horizonValues['Confidence Interval Test'],
      horizonNotching.signedDifference,
    );
    const score = pdRagScore(rag);
    const weight = eadSummaries[horizonConfig.key]?.share;
    return score != null && Number.isFinite(weight)
      ? [{key: horizonConfig.key, score, weight, rag}]
      : [];
  });
  if (!weightedScores.length) {
    return {rag: 'N/A', weightedAverage: null, roundedScore: null, horizons: [], totalWeight: 0};
  }

  const totalWeight = weightedScores.reduce((sum, entry) => sum + entry.weight, 0);
  const weightedAverage = totalWeight > 0
    ? weightedScores.reduce((sum, entry) => sum + entry.score * entry.weight, 0) / totalWeight
    : weightedScores.reduce((sum, entry) => sum + entry.score, 0) / weightedScores.length;
  const roundedScore = roundPdHalfDown(weightedAverage);
  return {
    rag: pdScoreToRag(roundedScore),
    weightedAverage,
    roundedScore,
    horizons: weightedScores,
    totalWeight,
  };
}

function calculatePdCalibrationConservatismRag(pd, observations, ratingObservations, monitoringQuarter) {
  return calculatePdCalibrationConservatismDetails(
    pd,
    observations,
    ratingObservations,
    monitoringQuarter,
  ).rag;
}

function buildPdCalibrationTooltip(details) {
  if (!details || !details.horizons || !details.horizons.length) {
    return 'Calibration Conservatism is based on weighted RAG Assignment by EAD share.';
  }
  const pieces = details.horizons.map(horizon => (
    `${horizon.key === '1y' ? '1y' : '2y'} ${horizon.rag}= ${horizon.score} x ${(horizon.weight * 100).toFixed(1)}%`
  ));
  const weightedLabel = details.weightedAverage == null || !Number.isFinite(details.weightedAverage)
    ? '—'
    : details.weightedAverage.toFixed(2);
  const roundedLabel = details.roundedScore == null || !Number.isFinite(details.roundedScore)
    ? '—'
    : `${details.roundedScore}`;
  return `Calibration Conservatism = weighted RAG Assignment by EAD share.\n${pieces.join(' + ')} = ${weightedLabel}\nRounded score: ${roundedLabel} -> ${details.rag}`;
}

function buildPdCalibrationNote(details) {
  if (!details || !details.horizons || !details.horizons.length) {
    return 'Weighted RAG Assignment by EAD share is unavailable for the current filtered population.';
  }
  const horizonMap = Object.fromEntries(details.horizons.map(horizon => [horizon.key, horizon]));
  const weightedLabel = details.weightedAverage == null || !Number.isFinite(details.weightedAverage)
    ? '—'
    : details.weightedAverage.toFixed(2);
  const formatPiece = key => {
    const horizon = horizonMap[key];
    if (!horizon) return `EAD ${key} (—) * RAG Assignment ${key} (—=—)`;
    return `EAD ${key} (${(horizon.weight * 100).toFixed(1)}%) * RAG Assignment ${key} (${horizon.rag}=${horizon.score})`;
  };
  return `${formatPiece('1y')} + ${formatPiece('2y')} = ${weightedLabel}`;
}

function pdStatusLabel(rag) {
  return rag === 'Green'
    ? 'Within tolerance'
    : rag === 'Amber'
      ? 'Monitor closely'
      : rag === 'Red'
        ? 'Action required'
        : 'Insufficient data';
}

function escapePdHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatPdTestChange(current, previous, format, threshold = {}) {
  if (current == null || previous == null || !Number.isFinite(current) || !Number.isFinite(previous)) {
    return {text: 'No prior comparison', css: 'pd-change-neutral'};
  }
  const difference = current - previous;
  const displayDifference = format === 'percent' ? difference * 100 : difference;
  const decimals = format === 'count' ? 0 : format === 'percent' ? 2 : 3;
  const suffix = format === 'percent' ? ' pp' : '';
  if (Math.abs(displayDifference) < 10 ** (-decimals) / 2) {
    return {text: `${(0).toFixed(decimals)}${suffix}`, css: 'pd-change-neutral'};
  }
  let improved = null;
  if (threshold.higher_is_better === true) improved = difference > 0;
  else if (threshold.lower_is_better === true) improved = difference < 0;
  else if (Number.isFinite(threshold.target_value)) {
    improved = Math.abs(current - threshold.target_value) < Math.abs(previous - threshold.target_value);
  }
  return {
    text: `${displayDifference > 0 ? '+' : ''}${displayDifference.toFixed(decimals)}${suffix}`,
    css: improved == null ? 'pd-change-neutral' : improved ? 'pd-change-negative' : 'pd-change-positive',
  };
}

function formatPdRagChange(current, previous) {
  const scores = {'N/A': 0, Green: 1, Amber: 2, Red: 3};
  if (!previous || previous === 'N/A') return {text: 'No prior comparison', css: 'pd-change-neutral'};
  if (current === previous) return {text: 'No change', css: 'pd-change-neutral'};
  return (scores[current] || 0) < (scores[previous] || 0)
    ? {text: 'Improved', css: 'pd-change-negative'}
    : {text: 'Deteriorated', css: 'pd-change-positive'};
}

function matchesPdThresholdRule(rule, value) {
  if (!rule || !Number.isFinite(value)) return false;
  return String(rule)
    .split(/\s+OR\s+/i)
    .some(part => {
      const clause = part.trim();
      if (!clause) return false;

      let match = clause.match(/^(-?\d*\.?\d+)\s*(<=|<)\s*value\s*(<=|<)\s*(-?\d*\.?\d+)$/i);
      if (match) {
        const lower = Number(match[1]);
        const lowerOp = match[2];
        const upperOp = match[3];
        const upper = Number(match[4]);
        const lowerPass = lowerOp === '<=' ? value >= lower : value > lower;
        const upperPass = upperOp === '<=' ? value <= upper : value < upper;
        return lowerPass && upperPass;
      }

      match = clause.match(/^value\s*(>=|>|<=|<)\s*(-?\d*\.?\d+)$/i);
      if (match) {
        const op = match[1];
        const threshold = Number(match[2]);
        if (op === '>=') return value >= threshold;
        if (op === '>') return value > threshold;
        if (op === '<=') return value <= threshold;
        if (op === '<') return value < threshold;
      }

      match = clause.match(/^(-?\d*\.?\d+)\s*(>=|>)\s*value$/i);
      if (match) {
        const threshold = Number(match[1]);
        const op = match[2];
        return op === '>=' ? value <= threshold : value < threshold;
      }

      return false;
    });
}

function buildPdTestCard(metric, currentValues, previousValues, thresholds, context, options = {}) {
  const format = options.format || 'ratio';
  const value = currentValues[metric];
  const previousValue = previousValues[metric];
  const rag = calculatePdMetricRag(thresholds, metric, value);
  const threshold = thresholds.find(row => row.metric === metric) || {};
  const movement = formatPdTestChange(value, previousValue, format, threshold);
  return `
    <article class="pd-test-card pd-test-${pdToneClass(rag)} ${options.extraClass || ''}">
      <div class="pd-test-card-heading">
        <div>
          ${options.testLabel ? `<span>${escapePdHtml(options.testLabel)}</span>` : ''}
          <div class="pd-card-title-row">
            <h4>${escapePdHtml(options.cardTitle || metric)}</h4>
            ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapePdHtml(options.tooltip)}" title="${escapePdHtml(options.tooltip)}">i</span>` : ''}
          </div>
        </div>
        <div class="pd-test-status pd-test-status-${pdToneClass(rag)}">${escapePdHtml(rag)}</div>
      </div>
      <div class="pd-test-value">${escapePdHtml(formatPdMetric(value, format))}</div>
      <div class="pd-test-meta">Snapshot date: ${escapePdHtml(context.snapshotQuarter)}</div>
      ${(options.extraMetaRows || []).map(row => `<div class="pd-test-meta">${escapePdHtml(row.label)}: ${escapePdHtml(row.value)}</div>`).join('')}
      <div class="pd-performance-comparison">
        <div><span>Previous (${escapePdHtml(context.previousQuarter || 'No prior quarter')})</span><strong>${escapePdHtml(formatPdMetric(previousValue, format))}</strong></div>
        <div><span>Change</span><strong class="pd-change ${movement.css}">${escapePdHtml(movement.text)}</strong></div>
      </div>
    </article>`;
}

function buildPdSectionRagCard(title, currentRag, previousRag, context, options = {}) {
  const movement = formatPdRagChange(currentRag, previousRag);
  const metaLabel = options.metaLabel || 'Snapshot date';
  const metaValue = options.metaValue || context.snapshotQuarter;
  return `
    <article class="pd-test-card pd-test-${pdToneClass(currentRag)} ${options.extraClass || ''}">
      <div class="pd-test-card-heading">
        <div>
          ${options.testLabel ? `<span>${escapePdHtml(options.testLabel)}</span>` : ''}
          <div class="pd-card-title-row">
            <h4>${escapePdHtml(options.cardTitle || title)}</h4>
            ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapePdHtml(options.tooltip)}" title="${escapePdHtml(options.tooltip)}">i</span>` : ''}
          </div>
        </div>
        ${options.hideStatus ? '' : `<div class="pd-test-status pd-test-status-${pdToneClass(currentRag)}">${escapePdHtml(currentRag)}</div>`}
      </div>
      <div class="pd-test-value">${escapePdHtml(currentRag)}</div>
      <div class="pd-test-meta">${escapePdHtml(metaLabel)}: ${escapePdHtml(metaValue)}</div>
      ${(options.extraMetaRows || []).map(row => `<div class="pd-test-meta">${escapePdHtml(row.label)}: ${escapePdHtml(row.value)}</div>`).join('')}
      ${options.hideComparison ? '' : `<div class="pd-performance-comparison">
        <div><span>Previous (${escapePdHtml(context.previousQuarter || 'No prior quarter')})</span><strong>${escapePdHtml(previousRag)}</strong></div>
        <div><span>Change</span><strong class="pd-change ${movement.css}">${escapePdHtml(movement.text)}</strong></div>
      </div>`}
    </article>`;
}

function calculatePdEadSummaries(observations, quarter) {
  const selectedRows = observations.filter(row => matchesPdSelectedPopulation(row, quarter));
  const empty = {
    '1y': {ead: null, share: null, combinedEad: null},
    '2y': {ead: null, share: null, combinedEad: null},
  };
  if (!selectedRows.length) return empty;

  const sumEadForHorizon = key => selectedRows.reduce((sum, row) => {
    const value = row?.horizons?.[key]?.ead;
    return Number.isFinite(value) ? sum + value : sum;
  }, 0);

  const ead1y = sumEadForHorizon('1y');
  const ead2y = sumEadForHorizon('2y');
  const combinedEad = ead1y + ead2y;
  const summary = (ead) => ({
    ead: Number.isFinite(ead) ? ead : null,
    share: combinedEad > 0 && Number.isFinite(ead) ? ead / combinedEad : null,
    combinedEad: combinedEad > 0 ? combinedEad : null,
  });
  return {
    '1y': summary(ead1y),
    '2y': summary(ead2y),
  };
}

function buildPdEadCard(currentSummary, previousSummary, context, options = {}) {
  const shareLabel = currentSummary.share == null || !Number.isFinite(currentSummary.share)
    ? '—'
    : `${(currentSummary.share * 100).toFixed(1)}%`;
  const previousShareLabel = previousSummary.share == null || !Number.isFinite(previousSummary.share)
    ? '—'
    : `${(previousSummary.share * 100).toFixed(1)}%`;
  const combinedLabel = currentSummary.combinedEad == null || !Number.isFinite(currentSummary.combinedEad)
    ? '—'
    : formatPdCompactAmount(currentSummary.combinedEad);
  const currentLabel = options.currentLabel || context.snapshotQuarter;
  const previousLabel = options.previousLabel || context.previousQuarter || 'No prior quarter';

  return `
    <article class="pd-test-card ${options.extraClass || ''}">
      <div class="pd-test-card-heading">
        <div>
          ${options.testLabel ? `<span>${escapePdHtml(options.testLabel)}</span>` : ''}
          <div class="pd-card-title-row">
            <h4>${escapePdHtml(options.cardTitle || 'EAD')}</h4>
            ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapePdHtml(options.tooltip)}" title="${escapePdHtml(options.tooltip)}">i</span>` : ''}
          </div>
        </div>
      </div>
      <div class="pd-test-value">${escapePdHtml(formatPdCompactAmount(currentSummary.ead))}</div>
      <div class="pd-test-meta">Snapshot date: ${escapePdHtml(currentLabel)}</div>
      <div class="pd-test-meta">% EAD: ${escapePdHtml(shareLabel)} of combined ${escapePdHtml(combinedLabel)}</div>
      <div class="pd-performance-comparison">
        <div><span>Previous (${escapePdHtml(previousLabel)})</span><strong>${escapePdHtml(formatPdCompactAmount(previousSummary.ead))}</strong></div>
        <div><span>Previous % EAD</span><strong>${escapePdHtml(previousShareLabel)}</strong></div>
      </div>
    </article>`;
}

function buildPdSectionHeading(index, title, description, rag, options = {}) {
  return `
    <div class="pd-domain-heading">
      <div>
        <div class="pd-content-kicker">${index}</div>
        <div class="pd-heading-row">
          <h3>${escapePdHtml(title)}</h3>
          ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapePdHtml(options.tooltip)}" title="${escapePdHtml(options.tooltip)}">i</span>` : ''}
        </div>
        <p>${escapePdHtml(description)}</p>
      </div>
      ${options.showRag === false ? '' : `<div class="pd-domain-status pd-domain-${pdToneClass(rag)}">
        <span>${escapePdHtml(options.statusLabel || 'Section RAG')}</span>
        <strong>${pdRagDot(rag)} ${escapePdHtml(rag)}</strong>
        ${options.statusNote ? `<small>${escapePdHtml(options.statusNote)}</small>` : ''}
      </div>`}
    </div>`;
}

function buildPdOverviewMetricCell(label, value, format, rag, options = {}) {
  const tone = pdToneClass(rag);
  const metricBody = `
      <div class="pd-overview-metric-label pd-overview-metric-label-${tone}">${escapePdHtml(label)}</div>
      <div class="pd-overview-metric-value">${escapePdHtml(formatPdMetric(value, format))}</div>`;
  return `
    <td class="pd-overview-metric-cell pd-overview-metric-${tone} ${options.extraClass || ''}">
      ${options.href
        ? `<a class="pd-overview-summary-link" href="${options.href}" aria-label="Jump to ${escapePdHtml(label)} section">${metricBody}</a>`
        : metricBody}
    </td>`;
}

function buildPdOverviewSummaryCell(label, rag, options = {}) {
  const tone = pdToneClass(rag);
  const summaryBody = `
      <div class="pd-overview-metric-label pd-overview-metric-label-${tone}">
        ${escapePdHtml(label)}
        ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapePdHtml(options.tooltip)}" title="${escapePdHtml(options.tooltip)}">i</span>` : ''}
      </div>
      <div class="pd-overview-metric-value">${pdRagDot(rag)} ${escapePdHtml(rag)}</div>`;
  return `
    <td class="pd-overview-metric-cell pd-overview-metric-${tone} pd-overview-summary-cell ${options.extraClass || ''}"${options.rowspan ? ` rowspan="${options.rowspan}"` : ''}>
      ${options.href
        ? `<a class="pd-overview-summary-link" href="${options.href}" aria-label="Jump to ${escapePdHtml(label)} section">${summaryBody}</a>`
        : summaryBody}
    </td>`;
}

function buildPdOverviewEmptyCell() {
  return '<td class="pd-overview-metric-cell pd-overview-metric-empty" aria-hidden="true"></td>';
}

function calculatePdOverviewPerformanceRag(calibrationRag, discriminationRag, balanceSheetRag) {
  const weightedComponents = [
    {rag: calibrationRag, weight: 0.25},
    {rag: discriminationRag, weight: 0.25},
    {rag: balanceSheetRag, weight: 0.50},
  ];
  const scores = weightedComponents.map(component => pdRagScore(component.rag));
  if (scores.some(score => score == null)) {
    return {rag: 'N/A', weightedScore: null, roundedScore: null};
  }
  const weightedScore = weightedComponents.reduce(
    (sum, component, index) => sum + scores[index] * component.weight,
    0,
  );
  const roundedScore = roundPdHalfDown(weightedScore);
  return {
    rag: pdScoreToRag(roundedScore),
    weightedScore,
    roundedScore,
  };
}

function buildPdOverviewPerformanceRagTooltip(calibrationRag, discriminationRag, balanceSheetRag, details) {
  const scoreLabel = rag => {
    const score = pdRagScore(rag);
    return score == null ? '—' : `${score}`;
  };
  const weightedLabel = details.weightedScore == null || !Number.isFinite(details.weightedScore)
    ? '—'
    : details.weightedScore.toFixed(2);
  const roundedLabel = details.roundedScore == null || !Number.isFinite(details.roundedScore)
    ? '—'
    : `${details.roundedScore}`;
  return `Performance PD RAG = ECL PIT PD Calibration Conservatism RAG (${calibrationRag}=${scoreLabel(calibrationRag)}) x 0.25 + ECL PIT PD Discriminatory Power RAG (${discriminationRag}=${scoreLabel(discriminationRag)}) x 0.25 + Balance Sheet PD Calibration Conservatism RAG (${balanceSheetRag}=${scoreLabel(balanceSheetRag)}) x 0.50 = ${weightedLabel}. Rounded score: ${roundedLabel} -> ${details.rag}.`;
}

function buildPdOverviewHeatmap(overview) {
  return `
    <div class="pd-overview-meta" aria-label="PD overview scope">
      <span><strong>Monitoring point:</strong> ${escapePdHtml(overview.monitoringPoint)}</span>
      <span><strong>Segment:</strong> ${escapePdHtml(overview.segmentLabel)}</span>
      <span><strong>PD models selected:</strong> ${escapePdHtml(fmtN(overview.selectedModelCount))}</span>
    </div>
    <div class="pd-overview-heatmap-wrap">
      <table class="pd-overview-heatmap" aria-label="PD monitoring overview">
        <thead>
          <tr>
            <th class="pd-overview-blank"></th>
            <th class="pd-overview-blank"></th>
            <th colspan="3">Tests</th>
            <th>Monitoring Dimension RAG</th>
            <th>PD RAG</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th rowspan="3" class="pd-overview-domain">ECL PIT PD</th>
            <th rowspan="2" class="pd-overview-section-label">Calibration Conservatism</th>
            ${buildPdOverviewMetricCell('Notching Test 1 year', overview.calibration.oneYear.notchingValue, 'count', overview.calibration.oneYear.notchingRag, {href: '#pd-calibration-rag'})}
            ${buildPdOverviewMetricCell('Confidence Interval 1 year', overview.calibration.oneYear.confidenceValue, 'percent', overview.calibration.oneYear.confidenceRag, {href: '#pd-calibration-rag'})}
            ${buildPdOverviewSummaryCell('RAG Assignment 1 year', overview.calibration.oneYear.assignmentRag, {href: '#pd-calibration-rag'})}
            ${buildPdOverviewSummaryCell('Calibration Conservatism RAG', overview.calibration.overallRag, {rowspan: 2, href: '#pd-calibration-rag'})}
            ${buildPdOverviewSummaryCell('Performance PD RAG', overview.performancePd.rag, {
              rowspan: 4,
              extraClass: 'pd-overview-pd-rag-cell',
              tooltip: overview.performancePd.tooltip,
              href: '#pd-performance-rag',
            })}
          </tr>
          <tr>
            ${buildPdOverviewMetricCell('Notching Test 2 year', overview.calibration.twoYear.notchingValue, 'count', overview.calibration.twoYear.notchingRag, {href: '#pd-calibration-rag'})}
            ${buildPdOverviewMetricCell('Confidence Interval 2 year', overview.calibration.twoYear.confidenceValue, 'percent', overview.calibration.twoYear.confidenceRag, {href: '#pd-calibration-rag'})}
            ${buildPdOverviewSummaryCell('RAG Assignment 2 year', overview.calibration.twoYear.assignmentRag, {href: '#pd-calibration-rag'})}
          </tr>
          <tr>
            <th class="pd-overview-section-label">Discriminatory Power</th>
            ${buildPdOverviewMetricCell('Accuracy Ratio 1 year', overview.discrimination.accuracyValue, 'ratio', overview.discrimination.accuracyRag, {href: '#pd-discrimination-rag'})}
            ${buildPdOverviewMetricCell('Delta Accuracy Ratio 1 year', overview.discrimination.deltaValue, 'ratio', overview.discrimination.deltaRag, {href: '#pd-discrimination-rag'})}
            ${buildPdOverviewEmptyCell()}
            ${buildPdOverviewSummaryCell('Discriminatory Power RAG', overview.discrimination.overallRag, {href: '#pd-discrimination-rag'})}
          </tr>
          <tr>
            <th class="pd-overview-domain">Balance Sheet PD</th>
            <th class="pd-overview-section-label">Calibration Conservatism</th>
            ${buildPdOverviewMetricCell('Notching Test 1 year', overview.balanceSheet.notchingValue, 'count', overview.balanceSheet.notchingRag, {href: '#pd-balance-sheet-calibration'})}
            ${buildPdOverviewMetricCell('Confidence Interval 1 year', overview.balanceSheet.confidenceValue, 'percent', overview.balanceSheet.confidenceRag, {href: '#pd-balance-sheet-calibration'})}
            ${buildPdOverviewEmptyCell()}
            ${buildPdOverviewSummaryCell('Calibration Conservatism RAG', overview.balanceSheet.overallRag, {href: '#pd-balance-sheet-calibration'})}
          </tr>
        </tbody>
      </table>
    </div>`;
}

function buildPdExecutiveSignals(pd, ratingMigration, context) {
  const thresholds = getPdThresholds();
  const values = calculatePdRagMetrics(
    pd.performance_observations || [],
    pd.rating_migration_observations || [],
    context.snapshotQuarter
  );
  const previousValues = calculatePdRagMetrics(
    pd.performance_observations || [],
    pd.rating_migration_observations || [],
    context.previousQuarter
  );
  const metricRag = metric => calculatePdMetricRag(thresholds, metric, values[metric]);
  const previousMetricRag = metric => calculatePdMetricRag(thresholds, metric, previousValues[metric]);
  const discriminationDefaultCount = calculatePdDefaultCountForHorizon(
    pd.performance_observations || [],
    context.snapshotQuarter,
    '1y',
  );
  const previousDiscriminationDefaultCount = calculatePdDefaultCountForHorizon(
    pd.performance_observations || [],
    context.previousQuarter,
    '1y',
  );
  const discriminationRag = calculatePdDiscriminationSectionRag(thresholds, values, discriminationDefaultCount);
  const previousDiscriminationRag = calculatePdDiscriminationSectionRag(
    thresholds,
    previousValues,
    previousDiscriminationDefaultCount,
  );
  const retentionCoverage = ratingMigration.currentCount
    ? ratingMigration.retained / ratingMigration.currentCount
    : null;
  const currentCalibrationAssignmentDetails = calculatePdCalibrationConservatismDetails(
    pd,
    pd.performance_observations || [],
    pd.rating_migration_observations || [],
    CQ,
  );
  const previousCalibrationAssignmentDetails = calculatePdCalibrationConservatismDetails(
    pd,
    pd.performance_observations || [],
    pd.rating_migration_observations || [],
    PQ,
  );
  const currentCalibrationRagSummary = currentCalibrationAssignmentDetails.rag === 'N/A'
    ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(metric => metricRag(metric)))
    : currentCalibrationAssignmentDetails.rag;
  const previousCalibrationRagSummary = previousCalibrationAssignmentDetails.rag === 'N/A'
    ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(metric => previousMetricRag(metric)))
    : previousCalibrationAssignmentDetails.rag;
  const performanceRag = getWorstPdRag(PD_RAG_GROUPS.performance.map(metric => metricRag(metric)));
  const previousPerformanceRag = getWorstPdRag(PD_RAG_GROUPS.performance.map(metric => previousMetricRag(metric)));
  const overallRag = getWorstPdRag([currentCalibrationRagSummary, discriminationRag, performanceRag]);
  const previousOverallRag = getWorstPdRag([previousCalibrationRagSummary, previousDiscriminationRag, previousPerformanceRag]);
  const overallMovement = formatPdRagChange(overallRag, previousOverallRag);
  const sectionSummaries = [
    {
      label: 'RAG Assignment',
      rag: currentCalibrationRagSummary,
      previousRag: previousCalibrationRagSummary,
    },
    {
      label: 'Discriminatory Power RAG',
      rag: discriminationRag,
      previousRag: previousDiscriminationRag,
    },
    {
      label: 'Performance RAG',
      rag: performanceRag,
      previousRag: previousPerformanceRag,
    },
  ];
  const signals = [
    {
      label: 'Observed Default Rate',
      value: values['Observed Default Rate'],
      previous: previousValues['Observed Default Rate'],
      format: 'percent',
      reference: true,
      threshold: thresholds.find(row => row.metric === 'Observed Default Rate') || {},
    },
    {
      label: 'Expected Default Rate',
      value: values['Predicted Default Rate'],
      previous: previousValues['Predicted Default Rate'],
      format: 'percent',
      reference: true,
      threshold: thresholds.find(row => row.metric === 'Predicted Default Rate') || {},
    },
    {
      label: 'Actual / Expected Ratio',
      value: values['Actual / Expected Ratio'],
      previous: previousValues['Actual / Expected Ratio'],
      format: 'ratio',
      rag: metricRag('Actual / Expected Ratio'),
      threshold: thresholds.find(row => row.metric === 'Actual / Expected Ratio') || {},
    },
    {
      label: 'Accuracy Ratio',
      value: values['Accuracy Ratio'],
      previous: previousValues['Accuracy Ratio'],
      format: 'ratio',
      rag: metricRag('Accuracy Ratio'),
      threshold: thresholds.find(row => row.metric === 'Accuracy Ratio') || {},
    },
    {
      label: 'Notching Test',
      value: values['Notching Test'],
      previous: previousValues['Notching Test'],
      format: 'count',
      rag: metricRag('Notching Test'),
      threshold: thresholds.find(row => row.metric === 'Notching Test') || {},
    },
    {
      label: 'Population Stability Index',
      value: values['Population Stability Index'],
      previous: previousValues['Population Stability Index'],
      format: 'ratio',
      rag: metricRag('Population Stability Index'),
      threshold: thresholds.find(row => row.metric === 'Population Stability Index') || {},
    },
  ];
  const overviewCards = [
    `
      <article class="pd-signal-card pd-signal-${pdToneClass(overallRag)} pd-overall-signal-card">
        <div class="pd-signal-card-topline">
          <span>Overall RAG Status</span>
          <span class="pd-signal-status">${pdRagDot(overallRag)} ${escapePdHtml(pdStatusLabel(overallRag))}</span>
        </div>
        <strong>${escapePdHtml(overallRag)}</strong>
        <small>Previous (${escapePdHtml(context.previousQuarter || 'No prior quarter')}): <b>${escapePdHtml(previousOverallRag)}</b></small>
        <small>Change: <b class="pd-change ${overallMovement.css}">${escapePdHtml(overallMovement.text)}</b></small>
      </article>
    `,
    ...sectionSummaries.map(section => {
      const movement = formatPdRagChange(section.rag, section.previousRag);
      return `
      <article class="pd-signal-card pd-signal-${pdToneClass(section.rag)} pd-domain-summary-card">
        <div class="pd-signal-card-topline">
          <span>${escapePdHtml(section.label)}</span>
          <span class="pd-signal-status">${pdRagDot(section.rag)} ${escapePdHtml(pdStatusLabel(section.rag))}</span>
        </div>
        <strong>${escapePdHtml(section.rag)}</strong>
        <small>Previous (${escapePdHtml(context.previousQuarter || 'No prior quarter')}): <b>${escapePdHtml(section.previousRag)}</b></small>
        <small>Change: <b class="pd-change ${movement.css}">${escapePdHtml(movement.text)}</b></small>
      </article>
    `}),
    ...signals.map(signal => {
      const movement = formatPdTestChange(signal.value, signal.previous, signal.format, signal.threshold || {});
      return `
      <article class="pd-signal-card ${signal.reference ? 'pd-signal-reference' : `pd-signal-${pdToneClass(signal.rag)}`}">
        <div class="pd-signal-card-topline">
          <span>${escapePdHtml(signal.label)}</span>
          ${signal.reference
            ? '<span class="pd-signal-reference-label">Reference</span>'
            : `<span class="pd-signal-status">${pdRagDot(signal.rag)} ${escapePdHtml(pdStatusLabel(signal.rag))}</span>`}
        </div>
        <strong>${escapePdHtml(formatPdMetric(signal.value, signal.format))}</strong>
        <small>Previous (${escapePdHtml(context.previousQuarter || 'No prior quarter')}): <b>${escapePdHtml(formatPdMetric(signal.previous, signal.format))}</b></small>
        <small>Change: <b class="pd-change ${movement.css}">${escapePdHtml(movement.text)}</b></small>
      </article>
    `}),
    `
      <article class="pd-signal-card pd-retention-card">
        <div class="pd-retention-card-heading">
          <div>
            <h4>Retention Coverage</h4>
            <small>(Facility movement)</small>
          </div>
          <strong>${retentionCoverage === null ? '—' : `${(retentionCoverage * 100).toFixed(1)}%`}</strong>
        </div>
        <div class="pd-retention-grid">
          <div><span>Retained</span><strong>${formatPdShare(ratingMigration.retained, ratingMigration.currentCount)}</strong></div>
          <div><span>Dropped</span><strong>${formatPdShare(ratingMigration.dropped, ratingMigration.previousCount)}</strong></div>
          <div><span>New</span><strong>${formatPdShare(ratingMigration.newFacilities, ratingMigration.currentCount)}</strong></div>
        </div>
      </article>
    `,
  ];
  return {
    overallRag,
    retentionCoverage,
    html: overviewCards.join(''),
  };
}

function filterPdRatingObservations(observations, quarter) {
  return observations.filter(row => matchesPdSelectedPopulation(row, quarter));
}

function buildPdRatingMigrationMatrix(observations, ratings, currentQuarter, previousQuarter) {
  const matrix = ratings.map(() => ratings.map(() => 0));
  const currentRows = filterPdRatingObservations(observations, currentQuarter);
  const currentByAccount = new Map(currentRows.map(row => [row.account, row.rating]));
  if (!previousQuarter) {
    return {matrix, retained: 0, dropped: 0, newFacilities: currentByAccount.size, currentCount: currentByAccount.size, previousCount: 0, stable: 0, migrated: 0, upgrades: 0, downgrades: 0};
  }

  const previousRows = filterPdRatingObservations(observations, previousQuarter);
  const previousByAccount = new Map(previousRows.map(row => [row.account, row.rating]));
  const ratingIndex = new Map(ratings.map((rating, index) => [rating, index]));
  let retained = 0;
  let stable = 0;
  let upgrades = 0;
  let downgrades = 0;

  previousRows.forEach(row => {
    const toRating = currentByAccount.get(row.account);
    if (toRating == null) return;
    const fromIndex = ratingIndex.get(row.rating);
    const toIndex = ratingIndex.get(toRating);
    if (fromIndex == null || toIndex == null) return;
    matrix[fromIndex][toIndex] += 1;
    retained += 1;
    if (row.rating === toRating) stable += 1;
    else if (Number(toRating) < Number(row.rating)) upgrades += 1;
    else if (Number(toRating) > Number(row.rating)) downgrades += 1;
  });

  const dropped = Array.from(previousByAccount.keys()).filter(account => !currentByAccount.has(account)).length;
  const newFacilities = Array.from(currentByAccount.keys()).filter(account => !previousByAccount.has(account)).length;
  return {
    matrix,
    retained,
    dropped,
    newFacilities,
    currentCount: currentByAccount.size,
    previousCount: previousByAccount.size,
    stable,
    migrated: retained - stable,
    upgrades,
    downgrades,
  };
}

function drawPdRatingMigrationMatrix(ratings, matrix, previousLabel, currentLabel, hasPreviousPoint) {
  const chart = document.getElementById('pd-rating-migration-chart');
  if (!chart) return;
  if (!hasPreviousPoint) {
    chart.innerHTML = '<div class="pd-performance-note">No previous monitoring point is available for a rating migration comparison.</div>';
    return;
  }
  if (!ratings.length) {
    chart.innerHTML = '<div class="pd-performance-note">No rating migration data is available.</div>';
    return;
  }

  const trace = {
    x: ratings,
    y: ratings,
    z: matrix,
    type: 'heatmap',
    colorscale: [
      [0, '#eff6ff'],
      [0.35, '#bfdbfe'],
      [0.7, '#60a5fa'],
      [1, '#1d4ed8'],
    ],
    colorbar: {title: 'Count'},
    text: matrix.map(row => row.map(value => String(value))),
    texttemplate: '%{text}',
    hovertemplate: 'From rating %{y}<br>To rating %{x}<br>Facilities %{z}<extra></extra>',
  };
  const layout = {
    height: 390,
    margin: {t: 20, r: 80, b: 60, l: 75},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    xaxis: {title: `Rating To (${currentLabel})`, type: 'category'},
    yaxis: {title: `Rating From (${previousLabel})`, type: 'category', autorange: 'reversed'},
  };
  Plotly.react('pd-rating-migration-chart', [trace], layout, {responsive: true, displayModeBar: false});
}

function drawPdRatingMigrationDirection(ratingMigration) {
  const chart = document.getElementById('pd-rating-direction-chart');
  if (!chart) return;
  const labels = ['Upgrades', 'Stable', 'Downgrades'];
  const values = [ratingMigration.upgrades, ratingMigration.stable, ratingMigration.downgrades];
  Plotly.react('pd-rating-direction-chart', [{
    x: values,
    y: labels,
    type: 'bar',
    orientation: 'h',
    marker: {color: ['#16a34a', '#64748b', '#dc2626']},
    text: values.map(value => fmtN(value)),
    textposition: 'auto',
    hovertemplate: '%{y}: %{x:,}<extra></extra>',
  }], {
    height: 230,
    margin: {t: 8, r: 24, b: 36, l: 92},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    xaxis: {title: 'Retained Facilities', rangemode: 'tozero', gridcolor: '#e5e7eb'},
    yaxis: {autorange: 'reversed'},
  }, {responsive: true, displayModeBar: false});
}

function buildPdPerformanceTrendForHorizon(observations, ratingObservations, snapshotQuarter, horizonKey) {
  return Array.from(new Set(
    (DASH_DATA.quarters || []).filter(quarter => quarter && quarter <= snapshotQuarter),
  )).sort().map(quarter => {
    const currentRows = filterPdPerformanceObservationsForHorizon(observations, quarter, horizonKey);
    const ragMetrics = calculatePdRagMetricsForHorizon(observations, ratingObservations, quarter, horizonKey);
    const notching = calculatePdNotchingComponents(currentRows);
    return {
      quarter,
      ...calculatePdPerformanceMetrics(currentRows),
      brier_score: ragMetrics['Brier Score'],
      population_stability_index: ragMetrics['Population Stability Index'],
      rating_migration_index: ragMetrics['Rating Migration Index'],
      notching_test: ragMetrics['Notching Test'],
      actual_notch: notching.actualNotch,
      predicted_notch: notching.predictedNotch,
      notching_difference: notching.difference,
      confidence_interval: ragMetrics['Confidence Interval Test'],
      go_live_accuracy_ratio: ragMetrics['Go Live Accuracy Ratio'],
      go_live_quarter: ragMetrics['Go Live Quarter'],
      delta_accuracy_ratio: ragMetrics['Delta Accuracy Ratio'],
      kendall_tau: ragMetrics["Kendall's Tau"],
    };
  });
}

function buildPdPerformanceTrend(observations, ratingObservations, snapshotQuarter) {
  return buildPdPerformanceTrendForHorizon(
    observations,
    ratingObservations,
    snapshotQuarter,
    getPdPerformanceHorizonKey(),
  );
}

function buildPdAeRatioBands(threshold, ratios) {
  const greenMin = Number.isFinite(threshold.green_min) ? threshold.green_min : 0.75;
  const greenMax = Number.isFinite(threshold.green_max) ? threshold.green_max : 1.25;
  const amberMin = Number.isFinite(threshold.amber_min) ? threshold.amber_min : greenMin;
  const amberMax = Number.isFinite(threshold.amber_max) ? threshold.amber_max : greenMax;
  const finiteRatios = ratios.filter(Number.isFinite);
  const maxRatio = finiteRatios.length ? Math.max(...finiteRatios) : amberMax;
  const axisMax = Math.max(amberMax * 1.12, maxRatio * 1.12, 1.6);
  const band = (y0, y1, fillcolor) => ({
    type: 'rect',
    xref: 'paper',
    x0: 0,
    x1: 1,
    yref: 'y2',
    y0,
    y1,
    fillcolor,
    line: {width: 0},
    layer: 'below',
  });
  return {
    axisRange: [0, axisMax],
    shapes: [
      band(0, amberMin, 'rgba(220,38,38,.08)'),
      band(amberMin, greenMin, 'rgba(217,119,6,.18)'),
      band(greenMin, greenMax, 'rgba(22,163,74,.10)'),
      band(greenMax, amberMax, 'rgba(217,119,6,.18)'),
      band(amberMax, axisMax, 'rgba(220,38,38,.08)'),
      {
        type: 'line',
        xref: 'paper',
        x0: 0,
        x1: 1,
        yref: 'y2',
        y0: 1,
        y1: 1,
        line: {color: '#16a34a', width: 1.5, dash: 'dash'},
      },
    ],
  };
}

function extractPdRuleUpperBound(rule) {
  if (!rule) return null;
  const text = String(rule).trim();
  let match = text.match(/value\s*(?:<=|<)\s*(-?\d*\.?\d+)/i);
  if (match) return Number(match[1]);
  match = text.match(/(-?\d*\.?\d+)\s*(?:<=|<)\s*value\s*(?:<=|<)\s*(-?\d*\.?\d+)/i);
  if (match) return Number(match[2]);
  return null;
}

function extractPdRuleLowerBound(rule) {
  if (!rule) return null;
  const text = String(rule).trim();
  let match = text.match(/value\s*(?:>=|>)\s*(-?\d*\.?\d+)/i);
  if (match) return Number(match[1]);
  match = text.match(/(-?\d*\.?\d+)\s*(?:<=|<)\s*value\s*(?:<=|<)\s*(-?\d*\.?\d+)/i);
  if (match) return Number(match[1]);
  return null;
}

function buildPdThresholdBands(threshold, values, options = {}) {
  const finiteValues = values.filter(Number.isFinite);
  const minValue = finiteValues.length ? Math.min(...finiteValues) : 0;
  const maxValue = finiteValues.length ? Math.max(...finiteValues) : 1;
  const minAxisMax = Number.isFinite(options.minAxisMax) ? options.minAxisMax : 1;
  const red = 'rgba(220,38,38,.08)';
  const amber = 'rgba(217,119,6,.18)';
  const green = 'rgba(22,163,74,.10)';
  const band = (y0, y1, fillcolor) => ({
    type: 'rect',
    xref: 'paper',
    x0: 0,
    x1: 1,
    yref: 'y',
    y0,
    y1,
    fillcolor,
    line: {width: 0},
    layer: 'below',
  });
  const positiveAxis = upperBound => [
    Math.min(0, minValue < 0 ? minValue * 1.12 : 0),
    Math.max(upperBound, maxValue * 1.12, minAxisMax),
  ];

  const redCondition = threshold?.red_condition;
  const inferredGreenMax = extractPdRuleUpperBound(threshold?.green_rule);
  const inferredAmberMax = extractPdRuleUpperBound(threshold?.amber_rule);
  const inferredGreenMin = extractPdRuleLowerBound(threshold?.green_rule);
  const inferredAmberMin = extractPdRuleLowerBound(threshold?.amber_rule);

  if (!threshold || redCondition === 'no_rag') {
    return {axisRange: positiveAxis(maxValue), shapes: []};
  }
  if (redCondition === 'below amber_min') {
    const greenMin = Number.isFinite(threshold.green_min) ? threshold.green_min : maxValue;
    const amberMin = Number.isFinite(threshold.amber_min) ? threshold.amber_min : greenMin;
    const axisRange = positiveAxis(greenMin * 1.2);
    return {
      axisRange,
      shapes: [
        band(axisRange[0], amberMin, red),
        band(amberMin, greenMin, amber),
        band(greenMin, axisRange[1], green),
      ],
    };
  }
  if (redCondition === 'above amber_max') {
    const greenMax = Number.isFinite(threshold.green_max) ? threshold.green_max : maxValue;
    const amberMax = Number.isFinite(threshold.amber_max) ? threshold.amber_max : greenMax;
    const axisRange = positiveAxis(amberMax * 1.12);
    return {
      axisRange,
      shapes: [
        band(axisRange[0], greenMax, green),
        band(greenMax, amberMax, amber),
        band(amberMax, axisRange[1], red),
      ],
    };
  }
  if (redCondition === 'outside amber range') {
    const greenMin = Number.isFinite(threshold.green_min) ? threshold.green_min : minValue;
    const greenMax = Number.isFinite(threshold.green_max) ? threshold.green_max : maxValue;
    const amberMin = Number.isFinite(threshold.amber_min) ? threshold.amber_min : greenMin;
    const amberMax = Number.isFinite(threshold.amber_max) ? threshold.amber_max : greenMax;
    const axisRange = positiveAxis(amberMax * 1.12);
    return {
      axisRange,
      shapes: [
        band(axisRange[0], amberMin, red),
        band(amberMin, greenMin, amber),
        band(greenMin, greenMax, green),
        band(greenMax, amberMax, amber),
        band(amberMax, axisRange[1], red),
      ],
    };
  }
  if (redCondition === 'abs above amber_max') {
    const greenMax = Math.abs(Number.isFinite(threshold.green_max) ? threshold.green_max : maxValue);
    const amberMax = Math.abs(Number.isFinite(threshold.amber_max) ? threshold.amber_max : greenMax);
    const axisMax = Math.max(amberMax * 1.12, Math.abs(minValue) * 1.12, Math.abs(maxValue) * 1.12, minAxisMax);
    const axisRange = [-axisMax, axisMax];
    return {
      axisRange,
      shapes: [
        band(axisRange[0], -amberMax, red),
        band(-amberMax, -greenMax, amber),
        band(-greenMax, greenMax, green),
        band(greenMax, amberMax, amber),
        band(amberMax, axisRange[1], red),
      ],
    };
  }
  if (threshold?.lower_is_better === true && Number.isFinite(inferredGreenMax) && Number.isFinite(inferredAmberMax)) {
    const axisRange = positiveAxis(inferredAmberMax * 1.12);
    return {
      axisRange,
      shapes: [
        band(axisRange[0], inferredGreenMax, green),
        band(inferredGreenMax, inferredAmberMax, amber),
        band(inferredAmberMax, axisRange[1], red),
      ],
    };
  }
  if (threshold?.higher_is_better === true && Number.isFinite(inferredGreenMin) && Number.isFinite(inferredAmberMin)) {
    const axisRange = positiveAxis(Math.max(maxValue, inferredGreenMin * 1.2));
    return {
      axisRange,
      shapes: [
        band(axisRange[0], inferredAmberMin, red),
        band(inferredAmberMin, inferredGreenMin, amber),
        band(inferredGreenMin, axisRange[1], green),
      ],
    };
  }
  return {axisRange: positiveAxis(maxValue), shapes: []};
}

function drawPdDefaultRateTrend(observations, ratingObservations, snapshotQuarter, horizonKey = '1y', options = {}) {
  const chartId = options.chartId || 'pd-default-rate-trend-chart';
  const rangeKey = options.rangeKey || 'calibration';
  const chart = document.getElementById(chartId);
  if (!chart) return;
  const performanceTrend = buildPdPerformanceTrendForHorizon(observations, ratingObservations, snapshotQuarter, horizonKey);
  const periods = filterPdPeriodsByRange(rangeKey, performanceTrend.map(row => row.quarter));
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No portfolio periods are available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const aeThreshold = getPdThresholds()
    .find(row => row.metric === 'Actual / Expected Ratio') || {};
  const ratios = trend.map(row => row.actual_expected_ratio);
  const ratioRags = trend.map(row => calculatePdMetricRag([aeThreshold], 'Actual / Expected Ratio', row.actual_expected_ratio));
  const ratioBands = buildPdAeRatioBands(aeThreshold, ratios);
  const shapes = ratioBands.shapes.slice();
  if (quarters.includes(snapshotQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x2',
      x0: snapshotQuarter,
      x1: snapshotQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  }
  const traces = [
    {
      x: quarters,
      y: trend.map(row => row.observed_default_rate),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Actual Default Rate',
      line: {color: '#dc2626', width: 2.5},
      marker: {size: 6},
      hovertemplate: '%{x}<br>Actual Default Rate: %{y:.2%}<extra></extra>',
    },
    {
      x: quarters,
      y: trend.map(row => row.predicted_default_rate),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Predicted Default Rate',
      line: {color: '#2563eb', width: 2.5, dash: 'dash'},
      marker: {size: 6},
      hovertemplate: '%{x}<br>Predicted Default Rate: %{y:.2%}<extra></extra>',
    },
    {
      x: quarters,
      y: ratios,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'A/E Ratio',
      xaxis: 'x2',
      yaxis: 'y2',
      line: {color: '#d97706', width: 2.5},
      marker: {size: 8, color: ratioRags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: ratioRags,
      hovertemplate: '%{x}<br>A/E Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>',
    },
  ];
  const layout = {
    height: 420,
    margin: {t: 18, r: 30, b: 52, l: 68},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    legend: {orientation: 'h', x: 0, y: 1.08},
    shapes,
    xaxis: {
      domain: [0, 1],
      anchor: 'y',
      showticklabels: false,
      gridcolor: '#e5e7eb',
    },
    yaxis: {
      domain: [0.42, 1],
      title: 'Default Rate',
      tickformat: '.1%',
      rangemode: 'tozero',
      gridcolor: '#e5e7eb',
    },
    xaxis2: {
      domain: [0, 1],
      anchor: 'y2',
      title: 'Portfolio Quarter',
      type: 'category',
      gridcolor: '#e5e7eb',
    },
    yaxis2: {
      domain: [0, 0.28],
      title: 'A/E Ratio',
      range: ratioBands.axisRange,
      gridcolor: '#e5e7eb',
    },
  };
  Plotly.react(chartId, traces, layout, {responsive: true, displayModeBar: false});
}

function drawPdCalibrationRagTrend(pd, observations, ratingObservations, monitoringQuarter, options = {}) {
  const chartId = options.chartId || 'pd-calibration-rag-trend-chart';
  const rangeKey = options.rangeKey || 'calibration_rag';
  const chart = document.getElementById(chartId);
  if (!chart) return;

  const ragTrend = buildPdCalibrationRagTrend(pd, observations, ratingObservations, monitoringQuarter);
  const periods = filterPdPeriodsByRange(rangeKey, ragTrend.map(row => row.quarter));
  const trend = ragTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No calibration-conservatism RAG periods are available for the selected monitoring point.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const ragScores = trend.map(row => row.rag_score);
  const ragLabels = trend.map(row => row.rag);
  const customData = trend.map(row => [
    row.rag,
    row.weighted_average == null || !Number.isFinite(row.weighted_average) ? '—' : row.weighted_average.toFixed(2),
    row.rounded_score == null || !Number.isFinite(row.rounded_score) ? '—' : `${row.rounded_score}`,
  ]);
  const shapes = [
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 0.5, y1: 1.5, fillcolor: 'rgba(220,38,38,0.08)', line: {width: 0}},
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 1.5, y1: 2.5, fillcolor: 'rgba(217,119,6,0.08)', line: {width: 0}},
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 2.5, y1: 3.5, fillcolor: 'rgba(22,163,74,0.08)', line: {width: 0}},
  ];
  if (quarters.includes(monitoringQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: monitoringQuarter,
      x1: monitoringQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  }

  const traces = [
    {
      x: quarters,
      y: ragScores,
      type: 'scatter',
      mode: 'markers',
      name: 'Final RAG',
      marker: {
        color: ragLabels.map(pdRagColor),
        size: 16,
        opacity: 0.95,
        line: {color: '#ffffff', width: 1},
      },
      customdata: customData,
      hovertemplate: '%{x}<br>Calibration Conservatism RAG: %{customdata[0]}<br>Weighted score: %{customdata[1]}<br>Rounded score: %{customdata[2]}<extra></extra>',
    },
  ];

  Plotly.react(chartId, traces, {
    height: 250,
    margin: {t: 18, r: 28, b: 54, l: 78},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'closest',
    showlegend: false,
    shapes,
    xaxis: {
      title: 'Monitoring Point',
      type: 'category',
      gridcolor: '#e5e7eb',
    },
    yaxis: {
      title: 'Calibration Conservatism Score',
      range: [0.5, 3.5],
      tickvals: [1, 2, 3],
      ticktext: ['Red (1)', 'Amber (2)', 'Green (3)'],
      zeroline: false,
      gridcolor: '#e5e7eb',
    },
  }, {responsive: true, displayModeBar: false});
}

function drawPdDiscriminationRagTrend(observations, ratingObservations, monitoringQuarter, options = {}) {
  const chartId = options.chartId || 'pd-discrimination-rag-trend-chart';
  const rangeKey = options.rangeKey || 'discrimination_rag';
  const chart = document.getElementById(chartId);
  if (!chart) return;

  const ragTrend = buildPdDiscriminationRagTrend(observations, ratingObservations, monitoringQuarter);
  const periods = filterPdPeriodsByRange(rangeKey, ragTrend.map(row => row.quarter));
  const trend = ragTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No discriminatory-power RAG periods are available for the selected monitoring point.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const ragScores = trend.map(row => row.rag_score);
  const ragLabels = trend.map(row => row.rag);
  const customData = trend.map(row => ([
    row.rag,
    row.accuracy_ratio == null || !Number.isFinite(row.accuracy_ratio) ? '—' : row.accuracy_ratio.toFixed(3),
    row.accuracy_rag || 'N/A',
    row.delta_accuracy_ratio == null || !Number.isFinite(row.delta_accuracy_ratio) ? '—' : row.delta_accuracy_ratio.toFixed(3),
    row.delta_accuracy_rag || 'N/A',
    Number.isFinite(row.default_count_1y) ? `${row.default_count_1y}` : '—',
    row.low_default_override ? 'Yes' : 'No',
  ]));
  const shapes = [
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 0.5, y1: 1.5, fillcolor: 'rgba(220,38,38,0.08)', line: {width: 0}},
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 1.5, y1: 2.5, fillcolor: 'rgba(217,119,6,0.08)', line: {width: 0}},
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 2.5, y1: 3.5, fillcolor: 'rgba(22,163,74,0.08)', line: {width: 0}},
  ];
  if (quarters.includes(monitoringQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: monitoringQuarter,
      x1: monitoringQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  }

  const traces = [
    {
      x: quarters,
      y: ragScores,
      type: 'scatter',
      mode: 'markers',
      name: 'Final RAG',
      marker: {
        color: ragLabels.map(pdRagColor),
        size: 16,
        opacity: 0.95,
        line: {color: '#ffffff', width: 1},
      },
      customdata: customData,
      hovertemplate: '%{x}<br>Discriminatory Power RAG: %{customdata[0]}<br>Accuracy Ratio 1 year: %{customdata[1]} (%{customdata[2]})<br>Delta Accuracy Ratio 1 year: %{customdata[3]} (%{customdata[4]})<br>Default 1 year count: %{customdata[5]}<br>Low-default override: %{customdata[6]}<extra></extra>',
    },
  ];

  Plotly.react(chartId, traces, {
    height: 250,
    margin: {t: 18, r: 28, b: 54, l: 78},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'closest',
    showlegend: false,
    shapes,
    xaxis: {
      title: 'Monitoring Point',
      type: 'category',
      gridcolor: '#e5e7eb',
    },
    yaxis: {
      title: 'Discriminatory Power Score',
      range: [0.5, 3.5],
      tickvals: [1, 2, 3],
      ticktext: ['Red (1)', 'Amber (2)', 'Green (3)'],
      zeroline: false,
      gridcolor: '#e5e7eb',
    },
  }, {responsive: true, displayModeBar: false});
}

function drawPdBalanceSheetCalibrationRagTrend(observations, ratingObservations, monitoringQuarter, options = {}) {
  const chartId = options.chartId || 'pd-balance-sheet-calibration-rag-trend-chart';
  const rangeKey = options.rangeKey || 'balance_sheet_calibration_rag';
  const chart = document.getElementById(chartId);
  if (!chart) return;

  const ragTrend = buildPdBalanceSheetCalibrationRagTrend(observations, ratingObservations, monitoringQuarter);
  const periods = filterPdPeriodsByRange(rangeKey, ragTrend.map(row => row.quarter));
  const trend = ragTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No balance sheet calibration-conservatism RAG periods are available for the selected monitoring point.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const ragScores = trend.map(row => row.rag_score);
  const ragLabels = trend.map(row => row.rag);
  const customData = trend.map(row => ([
    row.rag,
    row.assignment_rag || 'N/A',
    row.confidence_interval == null || !Number.isFinite(row.confidence_interval) ? '—' : `${(row.confidence_interval * 100).toFixed(2)}%`,
    row.confidence_rag || 'N/A',
    row.notching_difference == null || !Number.isFinite(row.notching_difference) ? '—' : `${Math.round(row.notching_difference)}`,
    row.notching_rag || 'N/A',
  ]));
  const shapes = [
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 0.5, y1: 1.5, fillcolor: 'rgba(220,38,38,0.08)', line: {width: 0}},
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 1.5, y1: 2.5, fillcolor: 'rgba(217,119,6,0.08)', line: {width: 0}},
    {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 2.5, y1: 3.5, fillcolor: 'rgba(22,163,74,0.08)', line: {width: 0}},
  ];
  if (quarters.includes(monitoringQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: monitoringQuarter,
      x1: monitoringQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  }

  const traces = [
    {
      x: quarters,
      y: ragScores,
      type: 'scatter',
      mode: 'markers',
      name: 'Final RAG',
      marker: {
        color: ragLabels.map(pdRagColor),
        size: 16,
        opacity: 0.95,
        line: {color: '#ffffff', width: 1},
      },
      customdata: customData,
      hovertemplate: '%{x}<br>Calibration Conservatism RAG: %{customdata[0]}<br>RAG Assignment: %{customdata[1]}<br>Confidence Interval: %{customdata[2]} (%{customdata[3]})<br>Notching Test: %{customdata[4]} (%{customdata[5]})<extra></extra>',
    },
  ];

  Plotly.react(chartId, traces, {
    height: 250,
    margin: {t: 18, r: 28, b: 54, l: 78},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'closest',
    showlegend: false,
    shapes,
    xaxis: {
      title: 'Monitoring Point',
      type: 'category',
      gridcolor: '#e5e7eb',
    },
    yaxis: {
      title: 'Calibration Conservatism Score',
      range: [0.5, 3.5],
      tickvals: [1, 2, 3],
      ticktext: ['Red (1)', 'Amber (2)', 'Green (3)'],
      zeroline: false,
      gridcolor: '#e5e7eb',
    },
  }, {responsive: true, displayModeBar: false});
}

function drawPdNotchingTrend(observations, ratingObservations, snapshotQuarter, horizonKey = '1y', options = {}) {
  const chartId = options.chartId || 'pd-notching-trend-chart';
  const rangeKey = options.rangeKey || 'calibration';
  const chart = document.getElementById(chartId);
  if (!chart) return;
  const performanceTrend = buildPdPerformanceTrendForHorizon(observations, ratingObservations, snapshotQuarter, horizonKey);
  const periods = filterPdPeriodsByRange(rangeKey, performanceTrend.map(row => row.quarter));
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No notching periods are available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const thresholds = getPdThresholds();
  const threshold = thresholds.find(row => row.metric === 'Notching Test') || {};
  const differences = trend.map(row => row.notching_difference);
  const differenceRags = trend.map(row => calculatePdMetricRag(thresholds, 'Notching Test', row.notching_difference));
  const differenceBands = buildPdThresholdBands(threshold, differences, {minAxisMax: 2});
  const shapes = differenceBands.shapes.map(shape => ({...shape, yref: 'y2'}));
  if (quarters.includes(snapshotQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x2',
      x0: snapshotQuarter,
      x1: snapshotQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  }

  const traces = [
    {
      x: quarters,
      y: trend.map(row => row.actual_notch),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Actual Notch',
      line: {color: '#dc2626', width: 2.5},
      marker: {size: 6},
      hovertemplate: '%{x}<br>Actual Notch: %{y:.0f}<extra></extra>',
    },
    {
      x: quarters,
      y: trend.map(row => row.predicted_notch),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Predicted Notch',
      line: {color: '#2563eb', width: 2.5, dash: 'dash'},
      marker: {size: 6},
      hovertemplate: '%{x}<br>Predicted Notch: %{y:.0f}<extra></extra>',
    },
    {
      x: quarters,
      y: differences,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Notching Difference',
      xaxis: 'x2',
      yaxis: 'y2',
      line: {color: '#d97706', width: 2.5},
      marker: {size: 8, color: differenceRags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: differenceRags,
      hovertemplate: '%{x}<br>Notching Difference: %{y:.0f}<br>RAG: %{customdata}<extra></extra>',
    },
  ];
  const layout = {
    height: 420,
    margin: {t: 18, r: 30, b: 52, l: 68},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    legend: {orientation: 'h', x: 0, y: 1.08},
    shapes,
    xaxis: {
      domain: [0, 1],
      anchor: 'y',
      showticklabels: false,
      gridcolor: '#e5e7eb',
    },
    yaxis: {
      domain: [0.42, 1],
      title: 'CRR Notch',
      tickmode: 'linear',
      dtick: 1,
      range: [0.5, 9.5],
      gridcolor: '#e5e7eb',
    },
    xaxis2: {
      domain: [0, 1],
      anchor: 'y2',
      title: 'Portfolio Quarter',
      type: 'category',
      gridcolor: '#e5e7eb',
    },
    yaxis2: {
      domain: [0, 0.28],
      title: 'Notching Difference',
      range: differenceBands.axisRange,
      tickmode: 'linear',
      dtick: 1,
      gridcolor: '#e5e7eb',
    },
  };
  Plotly.react(chartId, traces, layout, {responsive: true, displayModeBar: false});
}

function drawPdConfidenceIntervalTrend(observations, ratingObservations, snapshotQuarter, horizonKey = '1y', options = {}) {
  const chartId = options.chartId || 'pd-confidence-interval-trend-chart';
  const rangeKey = options.rangeKey || 'calibration';
  const chart = document.getElementById(chartId);
  if (!chart) return;
  const performanceTrend = buildPdPerformanceTrendForHorizon(observations, ratingObservations, snapshotQuarter, horizonKey);
  const periods = filterPdPeriodsByRange(rangeKey, performanceTrend.map(row => row.quarter));
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No confidence-interval periods are available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const thresholds = getPdThresholds();
  const threshold = thresholds.find(row => row.metric === getPdThresholdMetricName('Confidence Interval Test')) || DEFAULT_PD_CONFIDENCE_INTERVAL_THRESHOLD;
  const confidenceValues = trend.map(row => row.confidence_interval);
  const confidenceRags = trend.map(row => calculatePdMetricRag(thresholds, 'Confidence Interval Test', row.confidence_interval));
  const confidenceBands = buildPdThresholdBands(threshold, confidenceValues, {minAxisMax: 1});
  const shapes = confidenceBands.shapes.slice();
  if (quarters.includes(snapshotQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: snapshotQuarter,
      x1: snapshotQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  }

  const traces = [{
    x: quarters,
    y: confidenceValues,
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Confidence Interval Test',
    line: {color: '#16a34a', width: 2.5},
    marker: {size: 8, color: confidenceRags.map(pdRagColor), line: {color: '#fff', width: 1}},
    customdata: confidenceRags,
    hovertemplate: '%{x}<br>Confidence Interval Test: %{y:.1%}<br>RAG: %{customdata}<extra></extra>',
  }];
  const layout = {
    height: 300,
    margin: {t: 18, r: 30, b: 52, l: 68},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    legend: {orientation: 'h', x: 0, y: 1.08},
    shapes,
    xaxis: {
      title: 'Portfolio Quarter',
      type: 'category',
      gridcolor: '#e5e7eb',
    },
    yaxis: {
      title: 'Confidence Interval Test',
      tickformat: '.0%',
      range: confidenceBands.axisRange,
      gridcolor: '#e5e7eb',
    },
  };
  Plotly.react(chartId, traces, layout, {responsive: true, displayModeBar: false});
}

function drawPdDiscriminationTrend(observations, ratingObservations, snapshotQuarter, horizonKey = '1y') {
  const grid = document.getElementById('pd-discrimination-trend-grid');
  if (!grid) return;
  const performanceTrend = buildPdPerformanceTrendForHorizon(
    observations,
    ratingObservations,
    snapshotQuarter,
    horizonKey,
  );
  const periods = filterPdPeriodsByRange('discrimination', performanceTrend.map(row => row.quarter));
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    grid.innerHTML = '<div class="pd-performance-note pd-discrimination-trend-note">No portfolio periods are available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const thresholds = getPdThresholds();
  const metricConfig = [
    {key: 'gini_coefficient', name: 'Gini Coefficient', chartId: 'pd-discrimination-trend-gini-coefficient', color: '#7c3aed', dash: 'dash'},
    {key: 'ks_statistic', name: 'KS Statistic', chartId: 'pd-discrimination-trend-ks-statistic', color: '#d97706', dash: 'dot'},
    {key: 'kendall_tau', name: "Kendall's Tau", chartId: 'pd-discrimination-trend-kendall-tau', color: '#0891b2', dash: 'dashdot'},
  ];
  metricConfig.forEach(metric => {
    const chart = document.getElementById(metric.chartId);
    if (!chart) return;
    const values = trend.map(row => row[metric.key]);
    const rags = trend.map(row => calculatePdMetricRag(thresholds, metric.name, row[metric.key]));
    const threshold = thresholds.find(row => row.metric === metric.name) || {};
    const bands = buildPdThresholdBands(threshold, values);
    const shapes = bands.shapes.slice();
    if (quarters.includes(snapshotQuarter)) {
      shapes.push({
        type: 'line',
        xref: 'x',
        x0: snapshotQuarter,
        x1: snapshotQuarter,
        yref: 'paper',
        y0: 0,
        y1: 1,
        line: {color: '#64748b', width: 1.5, dash: 'dot'},
      });
    }
    Plotly.react(metric.chartId, [{
      x: quarters,
      y: values,
      type: 'scatter',
      mode: 'lines+markers',
      name: metric.name,
      connectgaps: false,
      line: {color: metric.color, width: 2.5, dash: metric.dash},
      marker: {size: 8, color: rags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: rags,
      hovertemplate: `%{x}<br>${metric.name}: %{y:.3f}<br>RAG: %{customdata}<extra></extra>`,
    }], {
      height: 270,
      margin: {t: 34, r: 20, b: 42, l: 52},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      hovermode: 'x unified',
      showlegend: false,
      shapes,
      title: {text: metric.name, x: 0, y: 1, xanchor: 'left', yanchor: 'top', font: {size: 12, color: '#0f172a'}},
      xaxis: {title: 'Portfolio Quarter', type: 'category', gridcolor: '#e5e7eb'},
      yaxis: {title: metric.name, range: bands.axisRange, gridcolor: '#e5e7eb', zerolinecolor: '#cbd5e1'},
    }, {responsive: true, displayModeBar: false});
  });
}

function drawPdGoLiveAccuracyTrend(observations, ratingObservations, snapshotQuarter) {
  const chart = document.getElementById('pd-go-live-accuracy-trend-chart');
  if (!chart) return;

  const horizonKey = '1y';
  const performanceTrend = buildPdPerformanceTrendForHorizon(
    observations,
    ratingObservations,
    snapshotQuarter,
    horizonKey,
  );
  const goLiveQuarter = getPdGoLiveQuarter(observations, horizonKey);
  if (!goLiveQuarter) {
    chart.innerHTML = '<div class="pd-performance-note">No go-live quarter between 2019Q2 and 2019Q4 is available for the selected population.</div>';
    return;
  }

  const goLivePeriods = performanceTrend
    .map(row => row.quarter)
    .filter(quarter => quarter && quarter >= goLiveQuarter);
  const periods = filterPdPeriodsByRange('discrimination_accuracy', goLivePeriods);
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No discriminatory-power accuracy periods are available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const thresholds = getPdThresholds();
  const deltaThreshold = thresholds.find(row => row.metric === 'Delta Accuracy Ratio') || {};
  const deltaValues = trend.map(row => row.delta_accuracy_ratio);
  const deltaRags = trend.map(row => calculatePdMetricRag(thresholds, 'Delta Accuracy Ratio', row.delta_accuracy_ratio));
  const deltaBands = buildPdThresholdBands(deltaThreshold, deltaValues, {minAxisMax: 0.3});
  const shapes = deltaBands.shapes.map(shape => ({...shape, yref: 'y2'}));

  if (quarters.includes(snapshotQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x2',
      x0: snapshotQuarter,
      x1: snapshotQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  }

  const traces = [
    {
      x: quarters,
      y: trend.map(row => row.accuracy_ratio),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Accuracy Ratio',
      line: {color: '#2563eb', width: 2.5},
      marker: {size: 6},
      hovertemplate: '%{x}<br>Accuracy Ratio: %{y:.3f}<extra></extra>',
    },
    {
      x: quarters,
      y: trend.map(row => row.go_live_accuracy_ratio),
      type: 'scatter',
      mode: 'lines',
      name: 'Go Live Accuracy Ratio',
      line: {color: '#0f766e', width: 2, dash: 'dash'},
      hovertemplate: `%{x}<br>Go Live Accuracy Ratio: %{y:.3f}<br>Go-live quarter: ${goLiveQuarter}<extra></extra>`,
    },
    {
      x: quarters,
      y: deltaValues,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Delta Accuracy Ratio',
      xaxis: 'x2',
      yaxis: 'y2',
      line: {color: '#d97706', width: 2.5},
      marker: {size: 8, color: deltaRags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: deltaRags,
      hovertemplate: '%{x}<br>Delta Accuracy Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>',
    },
  ];

  const layout = {
    height: 420,
    margin: {t: 18, r: 30, b: 52, l: 68},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    legend: {orientation: 'h', x: 0, y: 1.08},
    shapes,
    xaxis: {
      domain: [0, 1],
      anchor: 'y',
      showticklabels: false,
      gridcolor: '#e5e7eb',
    },
    yaxis: {
      domain: [0.42, 1],
      title: 'Accuracy Ratio',
      gridcolor: '#e5e7eb',
      zerolinecolor: '#cbd5e1',
    },
    xaxis2: {
      domain: [0, 1],
      anchor: 'y2',
      title: `Portfolio Quarter (from ${goLiveQuarter})`,
      type: 'category',
      gridcolor: '#e5e7eb',
    },
    yaxis2: {
      domain: [0, 0.28],
      title: 'Delta Accuracy Ratio',
      range: deltaBands.axisRange,
      gridcolor: '#e5e7eb',
      zerolinecolor: '#cbd5e1',
    },
  };

  Plotly.react('pd-go-live-accuracy-trend-chart', traces, layout, {responsive: true, displayModeBar: false});
}

function drawPdStabilityTrend(observations, ratingObservations, snapshotQuarter) {
  const grid = document.getElementById('pd-stability-trend-grid');
  if (!grid) return;
  const performanceTrend = buildPdPerformanceTrend(observations, ratingObservations, snapshotQuarter);
  const periods = filterPdPeriodsByRange('stability', performanceTrend.map(row => row.quarter));
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    grid.innerHTML = '<div class="pd-performance-note pd-stability-trend-note">No stability data is available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const thresholds = getPdThresholds();
  const metricConfig = [
    {key: 'population_stability_index', name: 'Population Stability Index', chartId: 'pd-stability-trend-psi', yTitle: 'PSI', color: '#0891b2', dash: 'solid'},
    {key: 'brier_score', name: 'Brier Score', chartId: 'pd-stability-trend-brier-score', yTitle: 'Brier Score', color: '#ea580c', dash: 'dash'},
  ];
  metricConfig.forEach(metric => {
    const chart = document.getElementById(metric.chartId);
    if (!chart) return;
    const values = trend.map(row => row[metric.key]);
    const rags = trend.map(row => calculatePdMetricRag(thresholds, metric.name, row[metric.key]));
    const threshold = thresholds.find(row => row.metric === metric.name) || {};
    const bands = buildPdThresholdBands(threshold, values, {minAxisMax: 0});
    const shapes = bands.shapes.slice();
    if (quarters.includes(snapshotQuarter)) {
      shapes.push({
        type: 'line',
        xref: 'x',
        x0: snapshotQuarter,
        x1: snapshotQuarter,
        yref: 'paper',
        y0: 0,
        y1: 1,
        line: {color: '#64748b', width: 1.5, dash: 'dot'},
      });
    }
    Plotly.react(metric.chartId, [{
      x: quarters,
      y: values,
      type: 'scatter',
      mode: 'lines+markers',
      name: metric.name,
      connectgaps: false,
      line: {color: metric.color, width: 2.5, dash: metric.dash},
      marker: {size: 8, color: rags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: rags,
      hovertemplate: `%{x}<br>${metric.name}: %{y:.3f}<br>RAG: %{customdata}<extra></extra>`,
    }], {
      height: 280,
      margin: {t: 34, r: 20, b: 42, l: 52},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      hovermode: 'x unified',
      showlegend: false,
      shapes,
      title: {text: metric.name, x: 0, y: 1, xanchor: 'left', yanchor: 'top', font: {size: 12, color: '#0f172a'}},
      xaxis: {title: 'Portfolio Quarter', type: 'category', gridcolor: '#e5e7eb'},
      yaxis: {title: metric.yTitle, range: bands.axisRange, gridcolor: '#e5e7eb', zerolinecolor: '#cbd5e1'},
    }, {responsive: true, displayModeBar: false});
  });
}

function drawPdDistributionShift(observations, snapshotQuarter, previousQuarter) {
  const chart = document.getElementById('pd-distribution-shift-chart');
  if (!chart) return;
  const currentRows = filterPdPerformanceObservations(observations, snapshotQuarter);
  const previousRows = filterPdPerformanceObservations(observations, previousQuarter);
  if (!currentRows.length && !previousRows.length) {
    chart.innerHTML = '<div class="pd-performance-note">No predicted-PD distribution data is available for the selected comparison.</div>';
    return;
  }

  Plotly.react('pd-distribution-shift-chart', [
    {
      x: previousRows.map(row => row.predicted),
      type: 'histogram',
      histnorm: 'probability',
      nbinsx: 12,
      name: previousQuarter || 'Previous Quarter',
      opacity: 0.65,
      marker: {color: '#64748b'},
      hovertemplate: 'Predicted PD: %{x:.2%}<br>Share: %{y:.1%}<extra></extra>',
    },
    {
      x: currentRows.map(row => row.predicted),
      type: 'histogram',
      histnorm: 'probability',
      nbinsx: 12,
      name: snapshotQuarter,
      opacity: 0.65,
      marker: {color: '#2563eb'},
      hovertemplate: 'Predicted PD: %{x:.2%}<br>Share: %{y:.1%}<extra></extra>',
    },
  ], {
    height: 310,
    margin: {t: 12, r: 18, b: 48, l: 62},
    barmode: 'overlay',
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    legend: {orientation: 'h', x: 0, y: 1.16},
    xaxis: {title: 'Predicted PD', tickformat: '.1%', gridcolor: '#e5e7eb'},
    yaxis: {title: 'Portfolio Share', tickformat: '.1%', rangemode: 'tozero', gridcolor: '#e5e7eb'},
  }, {responsive: true, displayModeBar: false});
}

function renderPdModels() {
  closePdExpandedPanel(false);
  const pd = (DASH_DATA.monitoring || {}).pd_models || {};
  const observations = pd.performance_observations || [];
  const ratingObservations = pd.rating_migration_observations || [];
  const thresholds = getPdThresholds();
  const context = getPdPerformanceContext(pd);
  const trendPeriods = getPdRangePeriods(context.snapshotQuarter);
  const currentRows = filterPdPerformanceObservations(observations, context.snapshotQuarter);
  const analysisScopeCurrentRecordCount = (
    filterPdPerformanceObservationsForHorizon(observations, shiftMonitoringQuarterYear(CQ, -1), '1y').length
    + filterPdPerformanceObservationsForHorizon(observations, shiftMonitoringQuarterYear(CQ, -2), '2y').length
  );
  const previousLabel = context.previousQuarter || 'No prior quarter';
  const selectedModelCount = MONITORING_MODELS.length;
  const segmentLabel = MONITORING_PORTFOLIO_SEGMENT === 'all' ? 'All segments' : MONITORING_PORTFOLIO_SEGMENT;
  const ratingValues = pd.rating_values || [];
  const ratingMigration = buildPdRatingMigrationMatrix(
    ratingObservations,
    ratingValues,
    context.snapshotQuarter,
    context.previousQuarter,
  );
  const executiveSignals = buildPdExecutiveSignals(
    pd,
    ratingMigration,
    context,
  );
  const retentionWarning = executiveSignals.retentionCoverage !== null && executiveSignals.retentionCoverage < 0.5
    ? `<div class="pd-retention-warning" role="status">
        <strong>Interpret migration patterns cautiously.</strong>
        Only ${fmtN(ratingMigration.retained)} of ${fmtN(ratingMigration.currentCount)} snapshot-quarter facilities are also present in ${previousLabel}.
      </div>`
    : '';
  const availabilityNote = currentRows.length
    ? ''
    : `<div class="pd-performance-note pd-data-note">
        No PD observations are available for snapshot date ${context.snapshotQuarter} using ${context.predictedColumn}.
      </div>`;
  const currentRagValues = calculatePdRagMetrics(observations, ratingObservations, context.snapshotQuarter);
  const previousRagValues = calculatePdRagMetrics(observations, ratingObservations, context.previousQuarter);
  const calibrationTrendHorizonKey = PD_CALIBRATION_TREND_HORIZON === '2y' ? '2y' : '1y';
  const calibrationTrendContext = getPdPerformanceContextForHorizon(pd, calibrationTrendHorizonKey);
  const calibrationTrendPeriods = getPdRangePeriods(calibrationTrendContext.snapshotQuarter);
  const goLiveDiscriminationHorizonKey = '1y';
  const goLiveDiscriminationContext = getPdPerformanceContextForHorizon(pd, goLiveDiscriminationHorizonKey);
  const goLiveDiscriminationStartQuarter = getPdGoLiveQuarter(observations, goLiveDiscriminationHorizonKey);
  const goLiveDiscriminationPeriods = getPdRangePeriods(goLiveDiscriminationContext.snapshotQuarter)
    .filter(period => !goLiveDiscriminationStartQuarter || period >= goLiveDiscriminationStartQuarter);
  const discriminationTrendHorizonKey = PD_DISCRIMINATION_TREND_HORIZON === '2y' ? '2y' : '1y';
  const discriminationTrendContext = getPdPerformanceContextForHorizon(pd, discriminationTrendHorizonKey);
  const discriminationTrendPeriods = getPdRangePeriods(discriminationTrendContext.snapshotQuarter);
  const balanceSheetCalibrationContext = getPdPerformanceContextForHorizon(pd, 'nco_1y');
  const balanceSheetCalibrationPeriods = getPdRangePeriods(balanceSheetCalibrationContext.snapshotQuarter);
  const balanceSheetCalibrationValues = calculatePdRagMetricsForHorizon(
    observations,
    ratingObservations,
    balanceSheetCalibrationContext.snapshotQuarter,
    'nco_1y',
  );
  const previousBalanceSheetCalibrationValues = calculatePdRagMetricsForHorizon(
    observations,
    ratingObservations,
    balanceSheetCalibrationContext.previousQuarter,
    'nco_1y',
  );
  const balanceSheetCalibrationNotching = calculatePdNotchingComponents(filterPdPerformanceObservationsForHorizon(
    observations,
    balanceSheetCalibrationContext.snapshotQuarter,
    'nco_1y',
  ));
  const previousBalanceSheetCalibrationNotching = calculatePdNotchingComponents(filterPdPerformanceObservationsForHorizon(
    observations,
    balanceSheetCalibrationContext.previousQuarter,
    'nco_1y',
  ));
  const balanceSheetCalibrationAssignmentRag = calculatePdCalibrationAssignmentRag(
    balanceSheetCalibrationValues['Confidence Interval Test'],
    balanceSheetCalibrationNotching.signedDifference,
  );
  const previousBalanceSheetCalibrationAssignmentRag = calculatePdCalibrationAssignmentRag(
    previousBalanceSheetCalibrationValues['Confidence Interval Test'],
    previousBalanceSheetCalibrationNotching.signedDifference,
  );
  const balanceSheetCalibrationRag = balanceSheetCalibrationAssignmentRag === 'N/A'
    ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(
      metric => calculatePdMetricRag(thresholds, metric, balanceSheetCalibrationValues[metric]),
    ))
    : balanceSheetCalibrationAssignmentRag;
  const previousBalanceSheetCalibrationRag = previousBalanceSheetCalibrationAssignmentRag === 'N/A'
    ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(
      metric => calculatePdMetricRag(thresholds, metric, previousBalanceSheetCalibrationValues[metric]),
    ))
    : previousBalanceSheetCalibrationAssignmentRag;
  const balanceSheetAvailabilityNote = filterPdPerformanceObservationsForHorizon(
    observations,
    balanceSheetCalibrationContext.snapshotQuarter,
    'nco_1y',
  ).length
    ? ''
    : `<div class="pd-performance-note pd-data-note">
        No PD observations are available for snapshot date ${balanceSheetCalibrationContext.snapshotQuarter} using ${balanceSheetCalibrationContext.predictedColumn}.
      </div>`;
  const currentMonitoringEad = calculatePdEadSummaries(observations, CQ);
  const previousMonitoringEad = calculatePdEadSummaries(observations, PQ);
  const previousCalibrationAssignmentDetails = calculatePdCalibrationConservatismDetails(
    pd,
    observations,
    ratingObservations,
    PQ,
  );
  const groupRag = group => getWorstPdRag(
    PD_RAG_GROUPS[group].map(metric => calculatePdMetricRag(thresholds, metric, currentRagValues[metric])),
  );
  const calibrationAssignmentDetails = calculatePdCalibrationConservatismDetails(
    pd,
    observations,
    ratingObservations,
    CQ,
  );
  const calibrationAssignmentRag = calibrationAssignmentDetails.rag;
  const calibrationRag = calibrationAssignmentRag === 'N/A' ? groupRag('calibration') : calibrationAssignmentRag;
  const previousCalibrationRag = previousCalibrationAssignmentDetails.rag === 'N/A'
    ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(metric => calculatePdMetricRag(thresholds, metric, previousRagValues[metric])))
    : previousCalibrationAssignmentDetails.rag;
  const discriminationDefaultCount = calculatePdDefaultCountForHorizon(
    observations,
    context.snapshotQuarter,
    '1y',
  );
  const previousDiscriminationDefaultCount = calculatePdDefaultCountForHorizon(
    observations,
    context.previousQuarter,
    '1y',
  );
  const discriminationRag = calculatePdDiscriminationSectionRag(
    thresholds,
    currentRagValues,
    discriminationDefaultCount,
  );
  const previousDiscriminationRag = calculatePdDiscriminationSectionRag(
    thresholds,
    previousRagValues,
    previousDiscriminationDefaultCount,
  );
  const performanceRag = groupRag('performance');
  const testCards = (group, definitions) => definitions.map(([metric, testLabel, format]) => (
    buildPdTestCard(metric, currentRagValues, previousRagValues, thresholds, context, {testLabel, format})
  )).join('');
  const calibrationHorizonCards = [];
  const calibrationOverview = {};
  calibrationHorizonCards.push(
    buildPdSectionRagCard(
      'Calibration Conservatism RAG',
      calibrationRag,
      previousCalibrationRag,
      context,
      {
        cardTitle: 'Calibration Conservatism RAG',
        extraClass: 'pd-calibration-summary-card',
        tooltip: buildPdCalibrationNote(calibrationAssignmentDetails),
        hideStatus: true,
        metaLabel: 'Monitoring point',
        metaValue: context.monitoringPoint,
        hideComparison: true,
      },
    ),
  );
  [
    {key: '1y', label: '1 Year Time Horizon', suffix: '1 year'},
    {key: '2y', label: '2 Year Time Horizon', suffix: '2 year'},
  ].forEach(horizonConfig => {
    const horizonContext = getPdPerformanceContextForHorizon(pd, horizonConfig.key);
    const horizonValues = calculatePdRagMetricsForHorizon(
      observations,
      ratingObservations,
      horizonContext.snapshotQuarter,
      horizonConfig.key,
    );
    const previousHorizonValues = calculatePdRagMetricsForHorizon(
      observations,
      ratingObservations,
      horizonContext.previousQuarter,
      horizonConfig.key,
    );
    const horizonNotching = calculatePdNotchingComponents(filterPdPerformanceObservationsForHorizon(
      observations,
      horizonContext.snapshotQuarter,
      horizonConfig.key,
    ));
    const previousHorizonNotching = calculatePdNotchingComponents(filterPdPerformanceObservationsForHorizon(
      observations,
      horizonContext.previousQuarter,
      horizonConfig.key,
    ));
    const horizonCalibrationAssignmentRag = calculatePdCalibrationAssignmentRag(
      horizonValues['Confidence Interval Test'],
      horizonNotching.signedDifference,
    );
    const previousHorizonCalibrationAssignmentRag = calculatePdCalibrationAssignmentRag(
      previousHorizonValues['Confidence Interval Test'],
      previousHorizonNotching.signedDifference,
    );
    const horizonCalibrationRag = horizonCalibrationAssignmentRag === 'N/A'
      ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(metric => calculatePdMetricRag(thresholds, metric, horizonValues[metric])))
      : horizonCalibrationAssignmentRag;
    const previousHorizonCalibrationRag = previousHorizonCalibrationAssignmentRag === 'N/A'
      ? getWorstPdRag(PD_RAG_GROUPS.calibration.map(metric => calculatePdMetricRag(thresholds, metric, previousHorizonValues[metric])))
      : previousHorizonCalibrationAssignmentRag;
    const currentHorizonEad = currentMonitoringEad[horizonConfig.key] || {ead: null, share: null, combinedEad: null};
    const previousHorizonEad = previousMonitoringEad[horizonConfig.key] || {ead: null, share: null, combinedEad: null};
    calibrationOverview[horizonConfig.key] = {
      notchingValue: horizonValues['Notching Test'],
      notchingRag: calculatePdMetricRag(thresholds, 'Notching Test', horizonValues['Notching Test']),
      confidenceValue: horizonValues['Confidence Interval Test'],
      confidenceRag: calculatePdMetricRag(thresholds, 'Confidence Interval Test', horizonValues['Confidence Interval Test']),
      assignmentRag: horizonCalibrationRag,
    };
    calibrationHorizonCards.push(
      buildPdEadCard(
        currentHorizonEad,
        previousHorizonEad,
        horizonContext,
        {
          cardTitle: `EAD ${horizonConfig.suffix}`,
          currentLabel: horizonContext.snapshotQuarter,
          previousLabel: horizonContext.previousQuarter || 'No prior quarter',
        },
      ),
      buildPdSectionRagCard(
        'RAG Assignment',
        horizonCalibrationRag,
        previousHorizonCalibrationRag,
        horizonContext,
        {cardTitle: `RAG Assignment ${horizonConfig.suffix}`, hideStatus: true},
      ),
      buildPdTestCard(
        'Notching Test',
        horizonValues,
        previousHorizonValues,
        thresholds,
        horizonContext,
        {cardTitle: `Notching Test ${horizonConfig.suffix}`, format: 'count'},
      ),
      buildPdTestCard(
        'Confidence Interval Test',
        horizonValues,
        previousHorizonValues,
        thresholds,
        horizonContext,
        {cardTitle: `Confidence Interval ${horizonConfig.suffix}`, format: 'percent'},
      ),
    );
  });
  const performancePdOverview = calculatePdOverviewPerformanceRag(
    calibrationRag,
    discriminationRag,
    balanceSheetCalibrationRag,
  );
  performancePdOverview.tooltip = buildPdOverviewPerformanceRagTooltip(
    calibrationRag,
    discriminationRag,
    balanceSheetCalibrationRag,
    performancePdOverview,
  );
  const overviewHeatmap = buildPdOverviewHeatmap({
    monitoringPoint: CQ,
    segmentLabel,
    selectedModelCount,
    calibration: {
      oneYear: calibrationOverview['1y'] || {},
      twoYear: calibrationOverview['2y'] || {},
      overallRag: calibrationRag,
    },
    discrimination: {
      accuracyValue: currentRagValues['Accuracy Ratio'],
      accuracyRag: calculatePdMetricRag(thresholds, 'Accuracy Ratio', currentRagValues['Accuracy Ratio']),
      deltaValue: currentRagValues['Delta Accuracy Ratio'],
      deltaRag: calculatePdMetricRag(thresholds, 'Delta Accuracy Ratio', currentRagValues['Delta Accuracy Ratio']),
      overallRag: discriminationRag,
    },
    balanceSheet: {
      notchingValue: balanceSheetCalibrationValues['Notching Test'],
      notchingRag: calculatePdMetricRag(thresholds, 'Notching Test', balanceSheetCalibrationValues['Notching Test']),
      confidenceValue: balanceSheetCalibrationValues['Confidence Interval Test'],
      confidenceRag: calculatePdMetricRag(thresholds, 'Confidence Interval Test', balanceSheetCalibrationValues['Confidence Interval Test']),
      overallRag: balanceSheetCalibrationRag,
    },
    performancePd: performancePdOverview,
  });

  document.getElementById('tab-pd_models').innerHTML = `
    <nav class="pd-section-nav" aria-label="PD performance sections">
      <a href="#pd-analysis-scope">Overview</a>
      <a href="#pd-calibration-rag">ECL PIT PD - Calibration Conservatism</a>
      <a href="#pd-discrimination-rag">ECL PIT PD - Discriminatory Power</a>
      <a href="#pd-balance-sheet-calibration">Balance Sheet PD - Calibration Conservatism</a>
      <a href="#pd-performance-rag">Performance</a>
    </nav>

    <section id="pd-analysis-scope" class="pd-content-section pd-overview-section">
      <div class="pd-content-heading">
        <div class="pd-content-kicker">1. Overview</div>
        <h3>PD Monitoring Overview</h3>
        <p>At-a-glance summary of the current ECL PIT PD and Balance Sheet PD calibration and discriminatory power diagnostics.</p>
      </div>
      ${overviewHeatmap}
      ${availabilityNote}
    </section>

    <section id="pd-calibration-rag" class="pd-content-section">
      ${buildPdSectionHeading(
        '2. ECL PIT PD - Calibration Conservatism',
        'ECL PIT PD - Calibration Conservatism',
        'Compare observed defaults with predicted PIT PD, and review monotonicity across rating grades for the ECL monitoring population.',
        calibrationRag,
        {
          showRag: false,
        },
      )}
      <div class="pd-test-grid pd-calibration-test-grid">
        ${calibrationHorizonCards.join('')}
      </div>
      <div id="pd-calibration-rag-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Calibration Conservatism RAG Trend">
        ${buildPdChartHeader(
          'Calibration Conservatism RAG Trend',
          'Quarter-by-quarter Calibration Conservatism RAG shown as a simple color-coded dot timeline.',
          'pd-calibration-rag-trend-panel',
          'calibration_rag',
          getPdRangePeriods(CQ),
          CQ,
        )}
        <div id="pd-calibration-rag-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-notching-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Notching Trend">
        ${buildPdChartHeader(
          'Notching Trend',
          `Actual notch, predicted notch, and notching difference using the ${calibrationTrendContext.horizonLabel} time horizon.`,
          'pd-notching-trend-panel',
          'calibration',
          calibrationTrendPeriods,
          calibrationTrendContext.snapshotQuarter,
          buildPdCalibrationTrendHorizonControl(),
        )}
        <div id="pd-notching-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-confidence-interval-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Confidence Interval Test Trend">
        ${buildPdChartHeader(
          'Confidence Interval Test Trend',
          `Confidence interval test trend using the ${calibrationTrendContext.horizonLabel} time horizon. Markers use RAG colors.`,
          'pd-confidence-interval-trend-panel',
          'calibration',
          calibrationTrendPeriods,
          calibrationTrendContext.snapshotQuarter,
          buildPdCalibrationTrendHorizonControl(),
        )}
        <div id="pd-confidence-interval-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-calibration-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Calibration Trend">
        ${buildPdChartHeader(
          'Calibration Trend',
          `Actual vs. predicted default rates and their ratio using the ${calibrationTrendContext.horizonLabel} time horizon. Ratio trend markers use RAG colors.`,
          'pd-calibration-trend-panel',
          'calibration',
          calibrationTrendPeriods,
          calibrationTrendContext.snapshotQuarter,
          buildPdCalibrationTrendHorizonControl(),
        )}
        <div id="pd-default-rate-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
    </section>

    <section id="pd-discrimination-rag" class="pd-content-section">
      ${buildPdSectionHeading(
        '3. ECL PIT PD - Discriminatory Power',
        'ECL PIT PD - Discriminatory Power',
        'Assess how effectively PIT PD separates higher-risk and lower-risk observations within the monitored ECL population.',
        discriminationRag,
        {showRag: false},
      )}
      <div class="pd-test-grid pd-discrimination-test-grid">
        ${buildPdSectionRagCard(
          'Discriminatory Power RAG',
          discriminationRag,
          previousDiscriminationRag,
          context,
          {
            cardTitle: 'Discriminatory Power RAG',
            tooltip: 'If the 1-year default count is below 15, the RAG is forced to Amber. Otherwise: if Delta Accuracy Ratio is Red and Accuracy Ratio is Green, the RAG is Amber. If Delta Accuracy Ratio is Red and Accuracy Ratio is Amber, the RAG is Red. Otherwise the Accuracy Ratio RAG is used.',
            hideStatus: true,
            metaLabel: 'Monitoring point',
            metaValue: context.monitoringPoint,
            extraMetaRows: [{
              label: 'Default 1 year count',
              value: fmtN(discriminationDefaultCount),
            }],
            hideComparison: true,
          },
        )}
        ${testCards('discrimination', [
          ['Accuracy Ratio', 'Accuracy Ratio 1 year', 'ratio'],
        ])}
        ${buildPdTestCard(
          'Delta Accuracy Ratio',
          currentRagValues,
          previousRagValues,
          thresholds,
          context,
          {
            cardTitle: 'Delta Accuracy Ratio 1 year',
            format: 'ratio',
            extraMetaRows: [{
              label: 'Go-live date',
              value: currentRagValues['Go Live Quarter'] || '—',
            }],
            tooltip: currentRagValues['Go Live Quarter']
              ? `Reference go-live quarter: ${currentRagValues['Go Live Quarter']}`
              : 'No go-live quarter between 2019Q2 and 2019Q4 is available for the selected filters.',
          },
        )}
      </div>
      <div id="pd-discrimination-rag-trend-panel" class="section-card pd-discrimination-trend-section" data-pd-expand-title="Discriminatory Power RAG Trend">
        ${buildPdChartHeader(
          'Discriminatory Power RAG Trend',
          'Quarter-by-quarter Discriminatory Power RAG shown as a simple color-coded dot timeline.',
          'pd-discrimination-rag-trend-panel',
          'discrimination_rag',
          getPdRangePeriods(CQ),
          CQ,
        )}
        <div id="pd-discrimination-rag-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-go-live-accuracy-trend-panel" class="section-card pd-discrimination-trend-section" data-pd-expand-title="Accuracy Ratio and Go-Live Delta Trend">
        ${buildPdChartHeader(
          'Accuracy Ratio and Go-Live Delta Trend',
          `Accuracy Ratio, Go Live Accuracy Ratio, and Delta Accuracy Ratio from ${goLiveDiscriminationStartQuarter || 'the configured go-live period'} onward. PD horizon is fixed to the ${goLiveDiscriminationContext.horizonLabel} time horizon and delta markers use threshold shading.`,
          'pd-go-live-accuracy-trend-panel',
          'discrimination_accuracy',
          goLiveDiscriminationPeriods,
          goLiveDiscriminationContext.snapshotQuarter,
          buildPdFrozenOneYearHorizonControl('Accuracy trend PD horizon'),
        )}
        <div id="pd-go-live-accuracy-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-discrimination-trend-panel" class="section-card pd-discrimination-trend-section" data-pd-expand-title="Discriminatory Power Trend Other Metrics Trend">
        ${buildPdChartHeader(
          'Discriminatory Power Trend Other Metrics Trend',
          `Gini Coefficient, KS Statistic, and Kendall's Tau through ${discriminationTrendContext.snapshotQuarter} using the ${discriminationTrendContext.horizonLabel} time horizon. Markers use RAG colors.`,
          'pd-discrimination-trend-panel',
          'discrimination',
          discriminationTrendPeriods,
          discriminationTrendContext.snapshotQuarter,
          buildPdDiscriminationTrendHorizonControl(),
        )}
        <div id="pd-discrimination-trend-grid" class="pd-discrimination-trend-grid">
          <div id="pd-discrimination-trend-gini-coefficient" class="pd-discrimination-trend-chart"></div>
          <div id="pd-discrimination-trend-ks-statistic" class="pd-discrimination-trend-chart"></div>
          <div id="pd-discrimination-trend-kendall-tau" class="pd-discrimination-trend-chart"></div>
        </div>
      </div>
    </section>

    <section id="pd-balance-sheet-calibration" class="pd-content-section">
      ${buildPdSectionHeading(
        '4. Balance Sheet PD - Calibration Conservatism',
        'Balance Sheet PD - Calibration Conservatism',
        'Assess balance sheet PD calibration with the same framework, using CPD NCO as the predicted PD input for the 1-year horizon.',
        'N/A',
        {showRag: false},
      )}
      <div class="pd-performance-note">
        Balance sheet calibration uses the same card logic as ECL PIT calibration, but evaluates the 1-year population with <strong>${escapePdHtml(balanceSheetCalibrationContext.predictedColumn)}</strong> as the predicted PD source.
      </div>
      ${balanceSheetAvailabilityNote}
      <div class="pd-test-grid pd-test-grid-3">
        ${buildPdSectionRagCard(
          'RAG Assignment',
          balanceSheetCalibrationRag,
          previousBalanceSheetCalibrationRag,
          balanceSheetCalibrationContext,
          {cardTitle: 'Calibration Conservatism RAG', hideStatus: true},
        )}
        ${buildPdTestCard(
          'Notching Test',
          balanceSheetCalibrationValues,
          previousBalanceSheetCalibrationValues,
          thresholds,
          balanceSheetCalibrationContext,
          {cardTitle: 'Notching Test 1 year', format: 'count'},
        )}
        ${buildPdTestCard(
          'Confidence Interval Test',
          balanceSheetCalibrationValues,
          previousBalanceSheetCalibrationValues,
          thresholds,
          balanceSheetCalibrationContext,
          {cardTitle: 'Confidence Interval 1 year', format: 'percent'},
        )}
      </div>
      <div id="pd-balance-sheet-calibration-rag-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Balance Sheet Calibration Conservatism RAG Trend">
        ${buildPdChartHeader(
          'Balance Sheet Calibration Conservatism RAG Trend',
          'Quarter-by-quarter Calibration Conservatism RAG shown as a simple color-coded dot timeline.',
          'pd-balance-sheet-calibration-rag-trend-panel',
          'balance_sheet_calibration_rag',
          balanceSheetCalibrationPeriods,
          balanceSheetCalibrationContext.snapshotQuarter,
          buildPdFrozenOneYearHorizonControl('Balance sheet calibration RAG PD horizon'),
        )}
        <div id="pd-balance-sheet-calibration-rag-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-balance-sheet-notching-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Balance Sheet Notching Trend">
        ${buildPdChartHeader(
          'Balance Sheet Notching Trend',
          `Actual notch, predicted notch, and notching difference using ${balanceSheetCalibrationContext.predictedColumn} for the fixed ${balanceSheetCalibrationContext.horizonLabel} horizon.`,
          'pd-balance-sheet-notching-trend-panel',
          'balance_sheet_calibration',
          balanceSheetCalibrationPeriods,
          balanceSheetCalibrationContext.snapshotQuarter,
          buildPdFrozenOneYearHorizonControl('Balance sheet calibration PD horizon'),
        )}
        <div id="pd-balance-sheet-notching-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-balance-sheet-confidence-interval-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Balance Sheet Confidence Interval Test Trend">
        ${buildPdChartHeader(
          'Balance Sheet Confidence Interval Test Trend',
          `Confidence interval test trend using ${balanceSheetCalibrationContext.predictedColumn} for the fixed ${balanceSheetCalibrationContext.horizonLabel} horizon. Markers use RAG colors.`,
          'pd-balance-sheet-confidence-interval-trend-panel',
          'balance_sheet_calibration',
          balanceSheetCalibrationPeriods,
          balanceSheetCalibrationContext.snapshotQuarter,
          buildPdFrozenOneYearHorizonControl('Balance sheet calibration PD horizon'),
        )}
        <div id="pd-balance-sheet-confidence-interval-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
      <div id="pd-balance-sheet-calibration-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Balance Sheet Calibration Trend">
        ${buildPdChartHeader(
          'Balance Sheet Calibration Trend',
          `Actual vs. predicted default rates and their ratio using ${balanceSheetCalibrationContext.predictedColumn} for the fixed ${balanceSheetCalibrationContext.horizonLabel} horizon. Ratio trend markers use RAG colors.`,
          'pd-balance-sheet-calibration-trend-panel',
          'balance_sheet_calibration',
          balanceSheetCalibrationPeriods,
          balanceSheetCalibrationContext.snapshotQuarter,
          buildPdFrozenOneYearHorizonControl('Balance sheet calibration PD horizon'),
        )}
        <div id="pd-balance-sheet-default-rate-trend-chart" class="pd-default-rate-trend-chart"></div>
      </div>
    </section>

    <section id="pd-performance-rag" class="pd-content-section">
      ${buildPdSectionHeading(
        '5. Performance',
        'Performance',
        'Monitor predictive error, population stability, and rating movement through time.',
        performanceRag,
        {showRag: false},
      )}
      <div class="pd-test-grid pd-performance-test-grid">
        <div class="pd-domain-status pd-domain-status-top pd-domain-${pdToneClass(performanceRag)} pd-performance-domain-status">
          <span>Performance RAG</span>
          <strong>${pdRagDot(performanceRag)} ${escapePdHtml(performanceRag)}</strong>
        </div>
        ${testCards('performance', [
          ['Brier Score', '', 'ratio'],
          ['Population Stability Index', '', 'ratio'],
          ['Rating Migration Index', '', 'ratio'],
        ])}
      </div>
      <div id="pd-stability-trend-panel" class="section-card" data-pd-expand-title="Performance Trend">
        ${buildPdChartHeader(
          'Performance Trend',
          'Population Stability Index and Brier Score trend markers use RAG colors.',
          'pd-stability-trend-panel',
          'stability',
          trendPeriods,
          context.snapshotQuarter,
        )}
        <div id="pd-stability-trend-grid" class="pd-stability-trend-grid">
          <div id="pd-stability-trend-psi" class="pd-stability-trend-chart"></div>
          <div id="pd-stability-trend-brier-score" class="pd-stability-trend-chart"></div>
        </div>
      </div>
      <div id="pd-distribution-shift-panel" class="section-card" data-pd-expand-title="Predicted PD Distribution Shift">
        ${buildPdChartHeader(
          'Predicted PD Distribution Shift',
          `Portfolio distribution comparison for ${previousLabel} and ${context.snapshotQuarter}.`,
          'pd-distribution-shift-panel',
        )}
        <div id="pd-distribution-shift-chart" class="pd-distribution-shift-chart"></div>
      </div>
      <div id="pd-migration-analysis-panel" class="section-card pd-migration-section" data-pd-expand-title="Rating Migration Analysis">
        ${buildPdChartHeader(
          'Rating Migration Analysis',
          `Counts of retained facilities moving from ${previousLabel} ratings (rows) to ${context.snapshotQuarter} ratings (columns).
          The matrix uses the selected PD models and segment; the active monitoring setup determines these comparison quarters.`,
          'pd-migration-analysis-panel',
        )}
        ${retentionWarning}
        <div class="pd-migration-summary">
          <span><strong>${fmtN(ratingMigration.retained)}</strong> Retained facilities</span>
          <span><strong>${formatPdShare(ratingMigration.stable, ratingMigration.retained)}</strong> Stable ratings</span>
          <span><strong>${formatPdShare(ratingMigration.upgrades, ratingMigration.retained)}</strong> Upgrades</span>
          <span><strong>${formatPdShare(ratingMigration.downgrades, ratingMigration.retained)}</strong> Downgrades</span>
          <span><strong>${formatPdShare(ratingMigration.migrated, ratingMigration.retained)}</strong> Migrated ratings</span>
        </div>
        <div class="pd-migration-grid">
          <div class="pd-subchart-panel">
            <div class="pd-subchart-title">Migration Direction</div>
            <div id="pd-rating-direction-chart" class="pd-rating-direction-chart"></div>
          </div>
          <div class="pd-subchart-panel">
            <div class="pd-subchart-title">Rating Migration Matrix</div>
            <div id="pd-rating-migration-chart" class="pd-migration-chart"></div>
          </div>
        </div>
      </div>
    </section>

    <div id="pd-expanded-modal" class="pd-expanded-modal" aria-hidden="true" onclick="if(event.target===this) closePdExpandedPanel()" onkeydown="handlePdModalKeydown(event)">
      <div class="pd-expanded-dialog" role="dialog" aria-modal="true" aria-labelledby="pd-expanded-modal-title">
        <div class="pd-expanded-modal-header">
          <div>
            <span>Expanded Analysis</span>
            <strong id="pd-expanded-modal-title">PD Analysis</strong>
          </div>
          <button type="button" id="pd-expanded-modal-close" class="pd-expanded-close" onclick="closePdExpandedPanel()" aria-label="Close enlarged chart">Close</button>
        </div>
        <div id="pd-expanded-modal-body" class="pd-expanded-modal-body"></div>
      </div>
    </div>
  `;

  drawPdRatingMigrationMatrix(
    ratingValues,
    ratingMigration.matrix,
    previousLabel,
    context.snapshotQuarter,
    Boolean(context.previousQuarter),
  );
  drawPdRatingMigrationDirection(ratingMigration);
  drawPdCalibrationRagTrend(
    pd,
    observations,
    ratingObservations,
    CQ,
  );
  drawPdNotchingTrend(
    observations,
    ratingObservations,
    calibrationTrendContext.snapshotQuarter,
    calibrationTrendHorizonKey,
  );
  drawPdConfidenceIntervalTrend(
    observations,
    ratingObservations,
    calibrationTrendContext.snapshotQuarter,
    calibrationTrendHorizonKey,
  );
  drawPdDefaultRateTrend(
    observations,
    ratingObservations,
    calibrationTrendContext.snapshotQuarter,
    calibrationTrendHorizonKey,
  );
  drawPdDiscriminationRagTrend(
    observations,
    ratingObservations,
    CQ,
  );
  drawPdDiscriminationTrend(
    observations,
    ratingObservations,
    discriminationTrendContext.snapshotQuarter,
    discriminationTrendHorizonKey,
  );
  drawPdGoLiveAccuracyTrend(
    observations,
    ratingObservations,
    goLiveDiscriminationContext.snapshotQuarter,
  );
  drawPdBalanceSheetCalibrationRagTrend(
    observations,
    ratingObservations,
    balanceSheetCalibrationContext.snapshotQuarter,
  );
  drawPdNotchingTrend(
    observations,
    ratingObservations,
    balanceSheetCalibrationContext.snapshotQuarter,
    'nco_1y',
    {chartId: 'pd-balance-sheet-notching-trend-chart', rangeKey: 'balance_sheet_calibration'},
  );
  drawPdConfidenceIntervalTrend(
    observations,
    ratingObservations,
    balanceSheetCalibrationContext.snapshotQuarter,
    'nco_1y',
    {chartId: 'pd-balance-sheet-confidence-interval-trend-chart', rangeKey: 'balance_sheet_calibration'},
  );
  drawPdDefaultRateTrend(
    observations,
    ratingObservations,
    balanceSheetCalibrationContext.snapshotQuarter,
    'nco_1y',
    {chartId: 'pd-balance-sheet-default-rate-trend-chart', rangeKey: 'balance_sheet_calibration'},
  );
  drawPdDistributionShift(observations, context.snapshotQuarter, context.previousQuarter);
  drawPdStabilityTrend(observations, ratingObservations, context.snapshotQuarter);
}

"""
