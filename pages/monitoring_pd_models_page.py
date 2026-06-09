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
  mev: {from: '', to: ''},
  stability: {from: '', to: ''},
};
const PD_RANGE_PERIOD_OVERRIDES = {};
let PD_CALIBRATION_TREND_HORIZON = '1y';
let PD_DISCRIMINATION_TREND_HORIZON = '1y';
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

function getPdRangeSourcePeriods(rangeKey, maxQuarter) {
  const overridePeriods = PD_RANGE_PERIOD_OVERRIDES[rangeKey] || [];
  if (overridePeriods.length) return overridePeriods.slice();
  return getPdRangePeriods(maxQuarter);
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
  const periods = getPdRangeSourcePeriods(rangeKey, maxQuarter);
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
  PD_RANGE_PERIOD_OVERRIDES[rangeKey] = periods.slice();
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
      </div>
    </div>`;
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
    return 'Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. The required inputs are unavailable for the current filtered population.';
  }
  const pieces = details.horizons.map(horizon => (
    `${horizon.key === '1y' ? '1-year RAG Assignment' : '2-year RAG Assignment'}: ${horizon.rag} (${horizon.score}) x ${(horizon.weight * 100).toFixed(1)}%`
  )).join('; ');
  const weightedLabel = details.weightedAverage == null || !Number.isFinite(details.weightedAverage)
    ? '—'
    : details.weightedAverage.toFixed(2);
  const roundedLabel = details.roundedScore == null || !Number.isFinite(details.roundedScore)
    ? '—'
    : `${details.roundedScore}`;
  if (details.weightedAverage == null || !Number.isFinite(details.weightedAverage) || details.roundedScore == null || !Number.isFinite(details.roundedScore)) {
    return `Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: ${pieces}. One or more inputs are unavailable, so the final Calibration Conservatism RAG is ${details.rag}.`;
  }
  return `Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: ${pieces}. Weighted average score = ${weightedLabel}. Rounded score = ${roundedLabel}, so the final Calibration Conservatism RAG is ${details.rag}.`;
}

function formatPdConfidenceBucketLabel(bucket) {
  if (bucket === 'pLow') return 'p < 5%';
  if (bucket === 'pMid') return '5% <= p <= 90%';
  if (bucket === 'pHigh') return '90% < p <= 97.5%';
  if (bucket === 'pVeryHigh') return 'p > 97.5%';
  return '—';
}

function formatPdSignedNotchingLabel(value) {
  if (value == null || !Number.isFinite(value)) return '—';
  const rounded = Math.round(value);
  return rounded > 0 ? `+${rounded}` : `${rounded}`;
}

function buildPdCalibrationAssignmentTooltip(label, confidenceInterval, signedNotchingDifference, lookupRag, displayedRag, confidenceRag, notchingRag) {
  const confidenceBucket = getPdConfidenceIntervalBucket(confidenceInterval);
  const notchingBucket = getPdNotchingBucket(signedNotchingDifference);
  const lookupLabel = lookupRag || 'N/A';
  const fallbackActive = lookupLabel === 'N/A' && displayedRag && displayedRag !== 'N/A';
  const fallbackText = fallbackActive
    ? ` The lookup result is unavailable, so the card falls back to the worse of Confidence Interval Test (${confidenceRag || 'N/A'}) and Notching Test (${notchingRag || 'N/A'}): ${displayedRag}.`
    : ` Final displayed RAG = ${displayedRag || 'N/A'}.`;

  if (!confidenceBucket || !notchingBucket) {
    return `RAG Assignment ${label} is determined from a lookup table using the Confidence Interval Test bucket and the signed notch difference bucket (predicted notch minus actual notch). The signed notch difference is not the same as the absolute Notching Test shown in the KPI card. One or more current inputs are unavailable, so the direct lookup result is ${lookupLabel}.${fallbackText}`;
  }

  return `RAG Assignment ${label} is determined from a lookup table using the Confidence Interval Test bucket and the signed notch difference bucket (predicted notch minus actual notch). The signed notch difference is not the same as the absolute Notching Test shown in the KPI card. Current inputs: Confidence Interval = ${formatPdMetric(confidenceInterval, 'percent')} (${formatPdConfidenceBucketLabel(confidenceBucket)}); signed notch difference = ${formatPdSignedNotchingLabel(signedNotchingDifference)} (${notchingBucket}). Direct lookup result = ${lookupLabel}.${fallbackText}`;
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

function buildPdStaticInfoCard(title, value, metaRows = [], options = {}) {
  return `
    <article class="pd-test-card ${options.extraClass || ''}">
      <div class="pd-test-card-heading">
        <div>
          ${options.testLabel ? `<span>${escapePdHtml(options.testLabel)}</span>` : ''}
          <div class="pd-card-title-row">
            <h4>${escapePdHtml(title)}</h4>
            ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapePdHtml(options.tooltip)}" title="${escapePdHtml(options.tooltip)}">i</span>` : ''}
          </div>
        </div>
      </div>
      <div class="pd-test-value">${escapePdHtml(value)}</div>
      ${metaRows.map(row => `<div class="pd-test-meta">${escapePdHtml(row.label)}: ${escapePdHtml(row.value)}</div>`).join('')}
      ${options.footnote ? `<div class="pd-test-footnote">${escapePdHtml(options.footnote)}</div>` : ''}
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

function buildPdChapterHeading(index, title, description, options = {}) {
  return `
    <div class="pd-chapter-heading ${options.extraClass || ''}">
      <div class="pd-chapter-heading-copy">
        <div class="pd-chapter-kicker">${escapePdHtml(index)}</div>
        <h2>${escapePdHtml(title)}</h2>
        <p>${escapePdHtml(description)}</p>
      </div>
      ${options.note
        ? `<div class="pd-chapter-note">${escapePdHtml(options.note)}</div>`
        : ''}
    </div>`;
}

function buildPdPlaceholderCard(title, message, tags = []) {
  return `
    <div class="section-card pd-placeholder-card">
      <div class="pd-placeholder-badge">Placeholder module</div>
      <div class="pd-placeholder-title">${escapePdHtml(title)}</div>
      <p>${escapePdHtml(message)}</p>
      ${tags.length
        ? `<div class="pd-placeholder-tags">${tags.map(tag => `<span>${escapePdHtml(tag)}</span>`).join('')}</div>`
        : ''}
    </div>`;
}

function buildPdOverviewFlowConnectorSpans(options = {}) {
  return `
    ${options.incoming ? '<span class="pd-overview-flow-connector pd-overview-flow-connector-in" aria-hidden="true"></span>' : ''}
    ${options.outgoing ? '<span class="pd-overview-flow-connector pd-overview-flow-connector-out" aria-hidden="true"></span>' : ''}`;
}

function buildPdOverviewFlowStage(number, title, subtitle = '') {
  const label = [number, title, subtitle].filter(Boolean).join(' ');
  return `
    <div class="pd-overview-flow-stage">
      <span>${escapePdHtml(label)}</span>
    </div>`;
}

function buildPdOverviewFlowInput(label, options = {}) {
  return `
    <div class="pd-overview-flow-input ${options.extraClass || ''}">
      <strong>${escapePdHtml(label)}</strong>
      ${options.note ? `<span>${escapePdHtml(options.note)}</span>` : ''}
    </div>`;
}

function buildPdOverviewFlowMetric(label, value, format, rag, options = {}) {
  const tone = pdToneClass(options.ragOverride || rag);
  const valueMarkup = options.isRag
    ? `${pdRagDot(value)} ${escapePdHtml(value)}`
    : escapePdHtml(formatPdMetric(value, format));
  const body = `
      ${buildPdOverviewFlowConnectorSpans(options)}
      <span class="pd-overview-flow-node-label">
        ${escapePdHtml(label)}
        ${options.tooltip ? `<span class="pd-info-chip" role="img" aria-label="${escapePdHtml(options.tooltip)}" title="${escapePdHtml(options.tooltip)}">i</span>` : ''}
      </span>
      <span class="pd-overview-flow-node-value ${options.isRag ? 'pd-overview-flow-node-value-rag' : ''}">${valueMarkup}</span>
      ${options.note ? `<span class="pd-overview-flow-node-note">${escapePdHtml(options.note)}</span>` : ''}`;
  return `
    <article class="pd-overview-flow-node pd-overview-flow-node-${tone} ${options.extraClass || ''}">
      ${options.href
        ? `<a class="pd-overview-flow-link" href="${options.href}" aria-label="Jump to ${escapePdHtml(label)} section">${body}</a>`
        : body}
    </article>`;
}

function buildPdOverviewFlowTestStack(metrics, options = {}) {
  return `
    <div class="pd-overview-flow-test-stack ${options.extraClass || ''}">
      ${buildPdOverviewFlowConnectorSpans(options)}
      ${metrics.join('')}
    </div>`;
}

function buildPdOverviewFlowPassThrough(options = {}) {
  return `
    <div class="pd-overview-flow-pass-through ${options.extraClass || ''}" aria-hidden="true">
      ${buildPdOverviewFlowConnectorSpans({incoming: true, outgoing: true})}
    </div>`;
}

function buildPdOverviewFlowPerformance(overview) {
  const tone = pdToneClass(overview.performancePd.rag);
  return `
    <article class="pd-overview-flow-performance pd-overview-flow-performance-${tone}">
      <span class="pd-overview-flow-performance-title">
        Performance<br>PD RAG
        <span class="pd-info-chip" role="img" aria-label="${escapePdHtml(overview.performancePd.tooltip)}" title="${escapePdHtml(overview.performancePd.tooltip)}">i</span>
      </span>
      <strong>${pdRagDot(overview.performancePd.rag)} ${escapePdHtml(overview.performancePd.rag)}</strong>
    </article>`;
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
  const componentSummary = [
    `ECL PIT Calibration: ${calibrationRag} (${scoreLabel(calibrationRag)}) x 25%`,
    `ECL PIT Discriminatory Power: ${discriminationRag} (${scoreLabel(discriminationRag)}) x 25%`,
    `Balance Sheet Calibration: ${balanceSheetRag} (${scoreLabel(balanceSheetRag)}) x 50%`,
  ].join('; ');
  const weightedLabel = details.weightedScore == null || !Number.isFinite(details.weightedScore)
    ? '—'
    : details.weightedScore.toFixed(2);
  const roundedLabel = details.roundedScore == null || !Number.isFinite(details.roundedScore)
    ? '—'
    : `${details.roundedScore}`;
  if (details.weightedScore == null || !Number.isFinite(details.weightedScore) || details.roundedScore == null || !Number.isFinite(details.roundedScore)) {
    return `Performance PD RAG combines three inputs with weights of 25%, 25%, and 50%. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: ${componentSummary}. One or more inputs are unavailable, so the final Performance PD RAG is ${details.rag}.`;
  }
  return `Performance PD RAG combines three inputs with weights of 25%, 25%, and 50%. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: ${componentSummary}. Weighted average score = ${weightedLabel}. Rounded score = ${roundedLabel}, so the final Performance PD RAG is ${details.rag}.`;
}

function buildPdOverviewHeatmap(overview) {
  const eclPitCalibrationSummary = buildPdOverviewFlowMetric(
    'Calibration Conservatism RAG (ECL PIT)',
    overview.calibration.overallRag,
    'rag',
    overview.calibration.overallRag,
    {
      isRag: true,
      href: '#pd-calibration-rag',
      tooltip: overview.calibration.tooltip,
      outgoing: true,
      extraClass: 'pd-flow-dimension-calibration',
    },
  );
  const discriminationSummary = buildPdOverviewFlowMetric(
    'Discriminatory Power RAG',
    overview.discrimination.overallRag,
    'rag',
    overview.discrimination.overallRag,
    {
      isRag: true,
      href: '#pd-discrimination-rag',
      tooltip: overview.discrimination.tooltip,
      incoming: true,
      outgoing: true,
      extraClass: 'pd-flow-dimension-discrimination',
    },
  );
  const balanceSheetSummary = buildPdOverviewFlowMetric(
    'Calibration Conservatism RAG (Balance Sheet)',
    overview.balanceSheet.overallRag,
    'rag',
    overview.balanceSheet.overallRag,
    {
      isRag: true,
      href: '#pd-balance-sheet-calibration',
      tooltip: overview.balanceSheet.assignmentTooltip,
      incoming: true,
      outgoing: true,
      extraClass: 'pd-flow-dimension-balance',
    },
  );
  return `
    <div class="pd-overview-flow-wrap">
      <div class="pd-overview-flow" aria-label="PD monitoring overview process flow">
        <div class="pd-flow-stage-input">${buildPdOverviewFlowStage('1.', 'Components')}</div>
        <div class="pd-flow-stage-tests">${buildPdOverviewFlowStage('2.', 'Tests')}</div>
        <div class="pd-flow-stage-assignment">${buildPdOverviewFlowStage('3.', 'RAG Assignment')}</div>
        <div class="pd-flow-stage-dimension">${buildPdOverviewFlowStage('4.', 'Monitoring Dimension RAG')}</div>
        <div class="pd-flow-stage-performance">${buildPdOverviewFlowStage('5.', 'Performance', 'PD RAG')}</div>

        <div class="pd-flow-input-ecl">
          ${buildPdOverviewFlowInput('ECL PIT PD', {extraClass: 'pd-overview-flow-input-ecl'})}
        </div>
        <div class="pd-flow-input-balance">
          ${buildPdOverviewFlowInput('Balance Sheet PD', {extraClass: 'pd-overview-flow-input-balance'})}
        </div>

        ${buildPdOverviewFlowTestStack([
          buildPdOverviewFlowMetric('Notching Test 1 year', overview.calibration.oneYear.notchingValue, 'count', overview.calibration.oneYear.notchingRag, {href: '#pd-calibration-rag'}),
          buildPdOverviewFlowMetric('Confidence Interval 1 year', overview.calibration.oneYear.confidenceValue, 'percent', overview.calibration.oneYear.confidenceRag, {href: '#pd-calibration-rag'}),
        ], {incoming: true, extraClass: 'pd-flow-tests-calibration-1'})}

        ${buildPdOverviewFlowMetric('RAG Assignment 1 year', overview.calibration.oneYear.assignmentRag, 'rag', overview.calibration.oneYear.assignmentRag, {
          isRag: true,
          href: '#pd-calibration-rag',
          tooltip: overview.calibration.oneYear.assignmentTooltip,
          incoming: true,
          outgoing: true,
          extraClass: 'pd-flow-assignment-1',
        })}

        ${buildPdOverviewFlowTestStack([
          buildPdOverviewFlowMetric('Notching Test 2 year', overview.calibration.twoYear.notchingValue, 'count', overview.calibration.twoYear.notchingRag, {href: '#pd-calibration-rag'}),
          buildPdOverviewFlowMetric('Confidence Interval 2 year', overview.calibration.twoYear.confidenceValue, 'percent', overview.calibration.twoYear.confidenceRag, {href: '#pd-calibration-rag'}),
        ], {incoming: true, extraClass: 'pd-flow-tests-calibration-2'})}

        ${buildPdOverviewFlowMetric('RAG Assignment 2 year', overview.calibration.twoYear.assignmentRag, 'rag', overview.calibration.twoYear.assignmentRag, {
          isRag: true,
          href: '#pd-calibration-rag',
          tooltip: overview.calibration.twoYear.assignmentTooltip,
          incoming: true,
          outgoing: true,
          extraClass: 'pd-flow-assignment-2',
        })}

        ${buildPdOverviewFlowTestStack([
          buildPdOverviewFlowMetric('Accuracy Ratio 1 year', overview.discrimination.accuracyValue, 'ratio', overview.discrimination.accuracyRag, {href: '#pd-discrimination-rag'}),
          buildPdOverviewFlowMetric('Delta Accuracy Ratio 1 year', overview.discrimination.deltaValue, 'ratio', overview.discrimination.deltaRag, {href: '#pd-discrimination-rag'}),
        ], {incoming: true, extraClass: 'pd-flow-tests-discrimination'})}

        ${buildPdOverviewFlowPassThrough({extraClass: 'pd-flow-pass-discrimination'})}

        ${buildPdOverviewFlowTestStack([
          buildPdOverviewFlowMetric('Notching Test 1 year', overview.balanceSheet.notchingValue, 'count', overview.balanceSheet.notchingRag, {href: '#pd-balance-sheet-calibration'}),
          buildPdOverviewFlowMetric('Confidence Interval 1 year', overview.balanceSheet.confidenceValue, 'percent', overview.balanceSheet.confidenceRag, {href: '#pd-balance-sheet-calibration'}),
        ], {incoming: true, extraClass: 'pd-flow-tests-balance'})}

        ${buildPdOverviewFlowPassThrough({extraClass: 'pd-flow-pass-balance'})}

        ${eclPitCalibrationSummary}
        ${discriminationSummary}
        ${balanceSheetSummary}

        <div class="pd-flow-performance">
          ${buildPdOverviewFlowPerformance(overview)}
        </div>
      </div>
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
  const useHorizontalLayout = (options.horizontalSubplots ?? (chartId === 'pd-default-rate-trend-chart'))
    && (chart.clientWidth || chart.offsetWidth || window.innerWidth || 0) >= 960;
  const performanceTrend = buildPdPerformanceTrendForHorizon(observations, ratingObservations, snapshotQuarter, horizonKey);
  const periods = filterPdPeriodsByRange(rangeKey, performanceTrend.map(row => row.quarter));
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No portfolio periods are available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const lastQuarter = quarters[quarters.length - 1];
  const aeThreshold = getPdThresholds()
    .find(row => row.metric === 'Actual / Expected Ratio') || {};
  const ratios = trend.map(row => row.actual_expected_ratio);
  const ratioRags = trend.map(row => calculatePdMetricRag([aeThreshold], 'Actual / Expected Ratio', row.actual_expected_ratio));
  const ratioBands = buildPdAeRatioBands(aeThreshold, ratios);
  const shapes = ratioBands.shapes.map(shape => (
    useHorizontalLayout ? {...shape, xref: 'x2 domain', yref: 'y2'} : shape
  ));
  if (useHorizontalLayout) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: lastQuarter,
      x1: lastQuarter,
      yref: 'y domain',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
    shapes.push({
      type: 'line',
      xref: 'x2',
      x0: lastQuarter,
      x1: lastQuarter,
      yref: 'y2 domain',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  } else if (quarters.includes(snapshotQuarter)) {
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
      showlegend: !useHorizontalLayout,
      xaxis: 'x2',
      yaxis: 'y2',
      line: {color: '#d97706', width: 2.5},
      marker: {size: 8, color: ratioRags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: ratioRags,
      hovertemplate: '%{x}<br>A/E Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>',
    },
  ];
  const mainXAxisDomain = useHorizontalLayout ? [0, 0.45] : [0, 1];
  const secondaryXAxisDomain = useHorizontalLayout ? [0.56, 1] : [0, 1];
  const mainYAxisDomain = useHorizontalLayout ? [0, 1] : [0.42, 1];
  const secondaryYAxisDomain = useHorizontalLayout ? [0, 1] : [0, 0.28];
  const axisLineColor = '#cbd5e1';
  const annotations = [];
  if (useHorizontalLayout) {
    const legendLineStart = secondaryXAxisDomain[0] + 0.02;
    const legendLineEnd = secondaryXAxisDomain[0] + 0.075;
    const legendMarkerCenter = secondaryXAxisDomain[0] + 0.0475;
    const legendY = 1.09;
    shapes.push({
      type: 'line',
      xref: 'paper',
      yref: 'paper',
      x0: legendLineStart,
      x1: legendLineEnd,
      y0: legendY,
      y1: legendY,
      line: {color: '#d97706', width: 2.5},
    });
    shapes.push({
      type: 'circle',
      xref: 'paper',
      yref: 'paper',
      x0: legendMarkerCenter - 0.006,
      x1: legendMarkerCenter + 0.006,
      y0: legendY - 0.012,
      y1: legendY + 0.012,
      fillcolor: '#d97706',
      line: {color: '#ffffff', width: 1},
    });
    annotations.push({
      xref: 'paper',
      yref: 'paper',
      x: legendLineEnd + 0.01,
      y: legendY,
      text: 'A/E Ratio',
      showarrow: false,
      xanchor: 'left',
      yanchor: 'middle',
      font: {size: 12, color: '#475569'},
    });
  }
  const layout = {
    height: useHorizontalLayout ? 330 : 470,
    margin: {t: useHorizontalLayout ? 34 : 18, r: 48, b: useHorizontalLayout ? 82 : 52, l: 72},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: useHorizontalLayout ? 'closest' : 'x unified',
    legend: {orientation: 'h', x: 0, y: useHorizontalLayout ? 1.22 : 1.08},
    annotations,
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      domain: mainXAxisDomain,
      anchor: 'y',
      title: useHorizontalLayout ? 'Portfolio Quarter' : undefined,
      showticklabels: useHorizontalLayout,
      showline: true,
      linecolor: axisLineColor,
      mirror: false,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
      panelFraction: useHorizontalLayout ? (mainXAxisDomain[1] - mainXAxisDomain[0]) : 1,
    }),
    yaxis: {
      domain: mainYAxisDomain,
      title: 'Default Rate',
      tickformat: '.1%',
      rangemode: 'tozero',
      side: 'left',
      automargin: true,
      showline: true,
      linecolor: axisLineColor,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    },
    xaxis2: buildMonitoringTimeSeriesXAxis(quarters, {
      domain: secondaryXAxisDomain,
      anchor: 'y2',
      title: 'Portfolio Quarter',
      showline: true,
      linecolor: axisLineColor,
      mirror: false,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
      panelFraction: useHorizontalLayout ? (secondaryXAxisDomain[1] - secondaryXAxisDomain[0]) : 1,
    }),
    yaxis2: {
      anchor: 'x2',
      domain: secondaryYAxisDomain,
      title: {text: 'A/E Ratio', standoff: 8},
      range: ratioBands.axisRange,
      side: 'left',
      automargin: true,
      showline: true,
      linecolor: axisLineColor,
      ticks: 'outside',
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
      hovertemplate: '%{x}<br>Calibration Conservatism RAG (ECL PIT): %{customdata[0]}<br>Weighted score: %{customdata[1]}<br>Rounded score: %{customdata[2]}<extra></extra>',
    },
  ];

  Plotly.react(chartId, traces, {
    height: 290,
    margin: {t: 18, r: 28, b: 54, l: 78},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'closest',
    showlegend: false,
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      title: 'Monitoring Point',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
    }),
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
    height: 290,
    margin: {t: 18, r: 28, b: 54, l: 78},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'closest',
    showlegend: false,
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      title: 'Monitoring Point',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
    }),
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
      hovertemplate: '%{x}<br>Calibration Conservatism RAG (ECL PIT): %{customdata[0]}<br>RAG Assignment: %{customdata[1]}<br>Confidence Interval: %{customdata[2]} (%{customdata[3]})<br>Notching Test: %{customdata[4]} (%{customdata[5]})<extra></extra>',
    },
  ];

  Plotly.react(chartId, traces, {
    height: 290,
    margin: {t: 18, r: 28, b: 54, l: 78},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'closest',
    showlegend: false,
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      title: 'Monitoring Point',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
    }),
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
  const useHorizontalLayout = (chart.clientWidth || chart.offsetWidth || window.innerWidth || 0) >= 960;
  const performanceTrend = buildPdPerformanceTrendForHorizon(observations, ratingObservations, snapshotQuarter, horizonKey);
  const periods = filterPdPeriodsByRange(rangeKey, performanceTrend.map(row => row.quarter));
  const trend = performanceTrend.filter(row => periods.includes(row.quarter));
  if (!trend.length) {
    chart.innerHTML = '<div class="pd-performance-note">No notching periods are available for the selected snapshot date.</div>';
    return;
  }

  const quarters = trend.map(row => row.quarter);
  const lastQuarter = quarters[quarters.length - 1];
  const thresholds = getPdThresholds();
  const threshold = thresholds.find(row => row.metric === 'Notching Test') || {};
  const differences = trend.map(row => row.notching_difference);
  const differenceRags = trend.map(row => calculatePdMetricRag(thresholds, 'Notching Test', row.notching_difference));
  const differenceBands = buildPdThresholdBands(threshold, differences, {minAxisMax: 2});
  const shapes = differenceBands.shapes.map(shape => ({...shape, xref: 'x2 domain', yref: 'y2'}));
  shapes.push({
    type: 'line',
    xref: 'x',
    x0: lastQuarter,
    x1: lastQuarter,
    yref: 'y domain',
    y0: 0,
    y1: 1,
    line: {color: '#64748b', width: 1.5, dash: 'dot'},
  });
  shapes.push({
    type: 'line',
    xref: 'x2',
    x0: lastQuarter,
    x1: lastQuarter,
    yref: 'y2 domain',
    y0: 0,
    y1: 1,
    line: {color: '#64748b', width: 1.5, dash: 'dot'},
  });

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
      showlegend: !useHorizontalLayout,
      xaxis: 'x2',
      yaxis: 'y2',
      line: {color: '#d97706', width: 2.5},
      marker: {size: 8, color: differenceRags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: differenceRags,
      hovertemplate: '%{x}<br>Notching Difference: %{y:.0f}<br>RAG: %{customdata}<extra></extra>',
    },
  ];
  const mainXAxisDomain = useHorizontalLayout ? [0, 0.45] : [0, 1];
  const secondaryXAxisDomain = useHorizontalLayout ? [0.56, 1] : [0, 1];
  const mainYAxisDomain = useHorizontalLayout ? [0, 1] : [0.42, 1];
  const secondaryYAxisDomain = useHorizontalLayout ? [0, 1] : [0, 0.28];
  const axisLineColor = '#cbd5e1';
  const annotations = [];
  if (useHorizontalLayout) {
    const legendLineStart = secondaryXAxisDomain[0] + 0.02;
    const legendLineEnd = secondaryXAxisDomain[0] + 0.075;
    const legendMarkerCenter = secondaryXAxisDomain[0] + 0.0475;
    const legendY = 1.09;
    shapes.push({
      type: 'line',
      xref: 'paper',
      yref: 'paper',
      x0: legendLineStart,
      x1: legendLineEnd,
      y0: legendY,
      y1: legendY,
      line: {color: '#d97706', width: 2.5},
    });
    shapes.push({
      type: 'circle',
      xref: 'paper',
      yref: 'paper',
      x0: legendMarkerCenter - 0.006,
      x1: legendMarkerCenter + 0.006,
      y0: legendY - 0.012,
      y1: legendY + 0.012,
      fillcolor: '#d97706',
      line: {color: '#ffffff', width: 1},
    });
    annotations.push({
      xref: 'paper',
      yref: 'paper',
      x: legendLineEnd + 0.01,
      y: legendY,
      text: 'Notching Difference',
      showarrow: false,
      xanchor: 'left',
      yanchor: 'middle',
      font: {size: 12, color: '#475569'},
    });
  }
  const layout = {
    height: useHorizontalLayout ? 330 : 470,
    margin: {t: useHorizontalLayout ? 34 : 18, r: 48, b: useHorizontalLayout ? 82 : 52, l: 72},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: useHorizontalLayout ? 'closest' : 'x unified',
    legend: {orientation: 'h', x: 0, y: useHorizontalLayout ? 1.22 : 1.08},
    annotations,
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      domain: mainXAxisDomain,
      anchor: 'y',
      title: useHorizontalLayout ? 'Portfolio Quarter' : undefined,
      showticklabels: useHorizontalLayout,
      showline: true,
      linecolor: axisLineColor,
      mirror: false,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
      panelFraction: useHorizontalLayout ? (mainXAxisDomain[1] - mainXAxisDomain[0]) : 1,
    }),
    yaxis: {
      domain: mainYAxisDomain,
      title: 'CRR Notch',
      tickmode: 'linear',
      dtick: 1,
      range: [0.5, 9.5],
      side: 'left',
      automargin: true,
      showline: true,
      linecolor: axisLineColor,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    },
    xaxis2: buildMonitoringTimeSeriesXAxis(quarters, {
      domain: secondaryXAxisDomain,
      anchor: 'y2',
      title: 'Portfolio Quarter',
      showline: true,
      linecolor: axisLineColor,
      mirror: false,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
      panelFraction: useHorizontalLayout ? (secondaryXAxisDomain[1] - secondaryXAxisDomain[0]) : 1,
    }),
    yaxis2: {
      anchor: 'x2',
      domain: secondaryYAxisDomain,
      title: {text: 'Notching Difference', standoff: 8},
      range: differenceBands.axisRange,
      tickmode: 'linear',
      dtick: 1,
      side: 'left',
      automargin: true,
      showline: true,
      linecolor: axisLineColor,
      ticks: 'outside',
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
    height: 340,
    margin: {t: 18, r: 30, b: 52, l: 68},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    legend: {orientation: 'h', x: 0, y: 1.08},
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      title: 'Portfolio Quarter',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
    }),
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
      height: 296,
      margin: {t: 18, r: 20, b: 42, l: 52},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      hovermode: 'x unified',
      showlegend: false,
      shapes,
      xaxis: buildMonitoringTimeSeriesXAxis(quarters, {title: 'Portfolio Quarter', gridcolor: '#e5e7eb'}, {
        chart,
        density: 'compact',
      }),
      yaxis: {title: metric.name, range: bands.axisRange, gridcolor: '#e5e7eb', zerolinecolor: '#cbd5e1'},
    }, {responsive: true, displayModeBar: false});
  });
}

function drawPdGoLiveAccuracyTrend(observations, ratingObservations, snapshotQuarter) {
  const chart = document.getElementById('pd-go-live-accuracy-trend-chart');
  if (!chart) return;
  const useHorizontalLayout = (chart.clientWidth || chart.offsetWidth || window.innerWidth || 0) >= 960;

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
  const lastQuarter = quarters[quarters.length - 1];
  const thresholds = getPdThresholds();
  const deltaThreshold = thresholds.find(row => row.metric === 'Delta Accuracy Ratio') || {};
  const deltaValues = trend.map(row => row.delta_accuracy_ratio);
  const deltaRags = trend.map(row => calculatePdMetricRag(thresholds, 'Delta Accuracy Ratio', row.delta_accuracy_ratio));
  const deltaBands = buildPdThresholdBands(deltaThreshold, deltaValues, {minAxisMax: 0.3});
  const shapes = deltaBands.shapes.map(shape => (
    useHorizontalLayout ? {...shape, xref: 'x2 domain', yref: 'y2'} : {...shape, yref: 'y2'}
  ));

  if (useHorizontalLayout) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: lastQuarter,
      x1: lastQuarter,
      yref: 'y domain',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
    shapes.push({
      type: 'line',
      xref: 'x2',
      x0: lastQuarter,
      x1: lastQuarter,
      yref: 'y2 domain',
      y0: 0,
      y1: 1,
      line: {color: '#64748b', width: 1.5, dash: 'dot'},
    });
  } else if (quarters.includes(snapshotQuarter)) {
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
      showlegend: !useHorizontalLayout,
      xaxis: 'x2',
      yaxis: 'y2',
      line: {color: '#d97706', width: 2.5},
      marker: {size: 8, color: deltaRags.map(pdRagColor), line: {color: '#fff', width: 1}},
      customdata: deltaRags,
      hovertemplate: '%{x}<br>Delta Accuracy Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>',
    },
  ];
  const mainXAxisDomain = useHorizontalLayout ? [0, 0.45] : [0, 1];
  const secondaryXAxisDomain = useHorizontalLayout ? [0.56, 1] : [0, 1];
  const mainYAxisDomain = useHorizontalLayout ? [0, 1] : [0.42, 1];
  const secondaryYAxisDomain = useHorizontalLayout ? [0, 1] : [0, 0.28];
  const axisLineColor = '#cbd5e1';
  const annotations = [];
  if (useHorizontalLayout) {
    const legendLineStart = secondaryXAxisDomain[0] + 0.02;
    const legendLineEnd = secondaryXAxisDomain[0] + 0.075;
    const legendMarkerCenter = secondaryXAxisDomain[0] + 0.0475;
    const legendY = 1.09;
    shapes.push({
      type: 'line',
      xref: 'paper',
      yref: 'paper',
      x0: legendLineStart,
      x1: legendLineEnd,
      y0: legendY,
      y1: legendY,
      line: {color: '#d97706', width: 2.5},
    });
    shapes.push({
      type: 'circle',
      xref: 'paper',
      yref: 'paper',
      x0: legendMarkerCenter - 0.006,
      x1: legendMarkerCenter + 0.006,
      y0: legendY - 0.012,
      y1: legendY + 0.012,
      fillcolor: '#d97706',
      line: {color: '#ffffff', width: 1},
    });
    annotations.push({
      xref: 'paper',
      yref: 'paper',
      x: legendLineEnd + 0.01,
      y: legendY,
      text: 'Delta Accuracy Ratio',
      showarrow: false,
      xanchor: 'left',
      yanchor: 'middle',
      font: {size: 12, color: '#475569'},
    });
  }

  const layout = {
    height: useHorizontalLayout ? 330 : 470,
    margin: {t: useHorizontalLayout ? 34 : 18, r: 48, b: useHorizontalLayout ? 82 : 52, l: 72},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: useHorizontalLayout ? 'closest' : 'x unified',
    legend: {orientation: 'h', x: 0, y: useHorizontalLayout ? 1.22 : 1.08},
    annotations,
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      domain: mainXAxisDomain,
      anchor: 'y',
      title: useHorizontalLayout ? 'Portfolio Quarter' : undefined,
      showticklabels: useHorizontalLayout,
      showline: true,
      linecolor: axisLineColor,
      mirror: false,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
      panelFraction: useHorizontalLayout ? (mainXAxisDomain[1] - mainXAxisDomain[0]) : 1,
    }),
    yaxis: {
      domain: mainYAxisDomain,
      title: 'Accuracy Ratio',
      side: 'left',
      automargin: true,
      showline: true,
      linecolor: axisLineColor,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
      zerolinecolor: '#cbd5e1',
    },
    xaxis2: buildMonitoringTimeSeriesXAxis(quarters, {
      domain: secondaryXAxisDomain,
      anchor: 'y2',
      title: `Portfolio Quarter (from ${goLiveQuarter})`,
      showline: true,
      linecolor: axisLineColor,
      mirror: false,
      ticks: 'outside',
      gridcolor: '#e5e7eb',
    }, {
      chart,
      density: 'compact',
      panelFraction: useHorizontalLayout ? (secondaryXAxisDomain[1] - secondaryXAxisDomain[0]) : 1,
    }),
    yaxis2: {
      anchor: 'x2',
      domain: secondaryYAxisDomain,
      title: {text: 'Delta Accuracy Ratio', standoff: 8},
      range: deltaBands.axisRange,
      side: 'left',
      automargin: true,
      showline: true,
      linecolor: axisLineColor,
      ticks: 'outside',
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
      height: 288,
      margin: {t: 34, r: 20, b: 42, l: 52},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      hovermode: 'x unified',
      showlegend: false,
      shapes,
      title: {text: metric.name, x: 0, y: 1, xanchor: 'left', yanchor: 'top', font: {size: 12, color: '#0f172a'}},
      xaxis: buildMonitoringTimeSeriesXAxis(quarters, {title: 'Portfolio Quarter', gridcolor: '#e5e7eb'}, {
        chart,
        density: 'compact',
      }),
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

const PD_MEV_PALETTE = ['#0f766e', '#2563eb', '#7c3aed', '#ea580c', '#0891b2', '#be123c', '#a16207', '#334155'];
let PD_MEV_FILTER_MODELS = [];
let PD_MEV_FILTER_NAMES = [];
let PD_MEV_FILTER_NAMES_EMPTY = false;
let PD_MEV_FILTER_EVENTS_BOUND = false;
let PD_MEV_FILTER_STATE_RESTORED = false;
let PD_MEV_FILTER_REOPEN_MENU_ID = '';
let PD_MEV_FILTER_REOPEN_MENU_SCROLL_TOP = 0;

function getPdMevFilterStorageKey() {
  const runId = (DASH_DATA && DASH_DATA.run_id) ? DASH_DATA.run_id : 'default';
  return `monitoring:pd:mev-filters:${runId}`;
}

function getPdMevFilterStores() {
  const stores = [];
  try {
    if (window.localStorage) stores.push(window.localStorage);
  } catch (error) {
    // Storage can be unavailable for local files or privacy-restricted sessions.
  }
  try {
    if (window.sessionStorage) stores.push(window.sessionStorage);
  } catch (error) {
    // Storage can be unavailable for local files or privacy-restricted sessions.
  }
  return stores;
}

function readPdMevFilterStorage() {
  const key = getPdMevFilterStorageKey();
  for (const store of getPdMevFilterStores()) {
    try {
      const raw = store.getItem(key);
      if (raw) return raw;
    } catch (error) {
      continue;
    }
  }
  return '';
}

function writePdMevFilterStorage(payload) {
  const serialized = JSON.stringify(payload);
  const key = getPdMevFilterStorageKey();
  getPdMevFilterStores().forEach(store => {
    try {
      store.setItem(key, serialized);
    } catch (error) {
      // Ignore browser storage restrictions and keep the in-memory state.
    }
  });
}

function restorePdMevFilterState() {
  if (PD_MEV_FILTER_STATE_RESTORED) return;
  PD_MEV_FILTER_STATE_RESTORED = true;
  const raw = readPdMevFilterStorage();
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed.models)) {
      PD_MEV_FILTER_MODELS = parsed.models
        .map(value => String(value || '').trim())
        .filter(Boolean);
    }
    if (Array.isArray(parsed.names)) {
      PD_MEV_FILTER_NAMES = parsed.names
        .map(value => String(value || '').trim())
        .filter(Boolean);
    }
  } catch (error) {
    PD_MEV_FILTER_MODELS = [];
    PD_MEV_FILTER_NAMES = [];
    PD_MEV_FILTER_NAMES_EMPTY = false;
  }
}

function persistPdMevFilterState() {
  writePdMevFilterStorage({
    models: PD_MEV_FILTER_MODELS.slice(),
    names: PD_MEV_FILTER_NAMES.slice(),
  });
}

function slugifyPdToken(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function formatPdShortDate(value) {
  if (!value) return '—';
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-US', {year: 'numeric', month: 'short', day: 'numeric'});
}

function formatPdMevValue(value) {
  if (value == null || !Number.isFinite(value)) return '—';
  return value.toLocaleString('en-US', {maximumFractionDigits: 2});
}

function formatPdDateSummary(dates) {
  const uniqueDates = Array.from(new Set((dates || []).filter(Boolean)));
  if (!uniqueDates.length) return '—';
  if (uniqueDates.length <= 2) return uniqueDates.map(formatPdShortDate).join(' / ');
  return `${uniqueDates.length} dates`;
}

function isoDateToPdQuarter(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
  if (!match) return '';
  const quarter = Math.floor((Number(match[2]) - 1) / 3) + 1;
  return `${match[1]}-Q${quarter}`;
}

function comparePdQuarterLabels(left, right) {
  const pattern = /^(\d{4})-Q([1-4])$/;
  const leftMatch = pattern.exec(left || '');
  const rightMatch = pattern.exec(right || '');
  if (!leftMatch || !rightMatch) return String(left || '').localeCompare(String(right || ''));
  const leftSort = Number(leftMatch[1]) * 10 + Number(leftMatch[2]);
  const rightSort = Number(rightMatch[1]) * 10 + Number(rightMatch[2]);
  return leftSort - rightSort;
}

function getPdMevCatalog(pd) {
  return pd.mev_catalog || {};
}

function getPdMevSelectedModels(pd) {
  const catalog = getPdMevCatalog(pd);
  const availableModels = Object.keys(catalog);
  let modelNames = MONITORING_MODELS.length
    ? availableModels.filter(name => MONITORING_MODELS.includes(name))
    : availableModels.slice();

  if (MONITORING_PORTFOLIO_SEGMENT !== 'all') {
    modelNames = modelNames.filter(name => (catalog[name].segments || []).includes(MONITORING_PORTFOLIO_SEGMENT));
  }
  return modelNames;
}

function getPdMevAvailableNamesForModels(pd, modelNames) {
  const catalog = getPdMevCatalog(pd);
  return Array.from(new Set(
    modelNames.flatMap(modelName => Object.keys(catalog[modelName]?.mevs || {})),
  )).sort((left, right) => left.localeCompare(right));
}

function getPdMevVisiblePeriods(catalog, modelNames, mevNames) {
  return Array.from(new Set(
    modelNames.flatMap(modelName => Object.entries(catalog[modelName]?.mevs || {})
      .filter(([mevName]) => mevNames.includes(mevName))
      .flatMap(([, mevData]) => Object.keys(mevData?.time_series || {}))),
  )).sort(comparePdQuarterLabels);
}

function getPdMevChartModelNames(pd) {
  const availableModels = getPdMevSelectedModels(pd);
  if (!availableModels.length) {
    PD_MEV_FILTER_MODELS = [];
    return [];
  }
  const preserved = PD_MEV_FILTER_MODELS.filter(modelName => availableModels.includes(modelName));
  if (!preserved.length || preserved.length === availableModels.length) {
    PD_MEV_FILTER_MODELS = availableModels.slice();
  } else {
    PD_MEV_FILTER_MODELS = [preserved[0]];
  }
  return PD_MEV_FILTER_MODELS.slice();
}

function getPdMevChartNames(pd) {
  const availableNames = getPdMevAvailableNamesForModels(pd, getPdMevChartModelNames(pd));
  if (!availableNames.length) {
    PD_MEV_FILTER_NAMES = [];
    PD_MEV_FILTER_NAMES_EMPTY = false;
    return [];
  }
  const preserved = PD_MEV_FILTER_NAMES.filter(mevName => availableNames.includes(mevName));
  if (preserved.length) {
    PD_MEV_FILTER_NAMES = preserved;
    PD_MEV_FILTER_NAMES_EMPTY = false;
  } else if (PD_MEV_FILTER_NAMES_EMPTY) {
    PD_MEV_FILTER_NAMES = [];
  } else {
    PD_MEV_FILTER_NAMES = availableNames.slice();
  }
  return PD_MEV_FILTER_NAMES.slice();
}

function getPdMevChartId(modelName, mevName) {
  return `pd-mev-chart-${slugifyPdToken(modelName)}-${slugifyPdToken(mevName)}`;
}

function getPdMevChartColor(index) {
  return PD_MEV_PALETTE[index % PD_MEV_PALETTE.length];
}

function colorToRgba(hexColor, alpha) {
  const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hexColor || '');
  if (!match) return `rgba(37,99,235,${alpha})`;
  return `rgba(${parseInt(match[1], 16)},${parseInt(match[2], 16)},${parseInt(match[3], 16)},${alpha})`;
}

function calculatePdMevThresholds(devRange = {}) {
  const greenMin = Number(devRange.min);
  const greenMax = Number(devRange.max);
  const mean = Number(devRange.mean);
  const twoStdLower = Number(devRange['2std_lower']);
  const twoStdUpper = Number(devRange['2std_upper']);
  if (!Number.isFinite(greenMin) || !Number.isFinite(greenMax) || !Number.isFinite(mean)) return null;

  const lowerStd = Number.isFinite(twoStdLower) ? Math.max((mean - twoStdLower) / 2, 0) : 0;
  const upperStd = Number.isFinite(twoStdUpper) ? Math.max((twoStdUpper - mean) / 2, 0) : 0;
  return {
    greenMin,
    greenMax,
    amberLower: Math.min(greenMin, greenMin - 2 * lowerStd),
    amberUpper: Math.max(greenMax, greenMax + 2 * upperStd),
    developmentDate: devRange.development_date || '',
  };
}

function buildPdMevThresholdChip(label, value, tone) {
  return `<span class="pd-mev-threshold-chip pd-mev-threshold-chip-${tone}"><strong>${escapePdHtml(label)}</strong>${escapePdHtml(value)}</span>`;
}

function buildPdMevThresholdChipRow(thresholds) {
  if (!thresholds) return '';
  return `
    <div class="pd-mev-threshold-chip-row">
      ${buildPdMevThresholdChip('Green', `${formatPdMevValue(thresholds.greenMin)} to ${formatPdMevValue(thresholds.greenMax)}`, 'green')}
      ${buildPdMevThresholdChip('Amber low', `${formatPdMevValue(thresholds.amberLower)} to ${formatPdMevValue(thresholds.greenMin)}`, 'amber')}
      ${buildPdMevThresholdChip('Amber high', `${formatPdMevValue(thresholds.greenMax)} to ${formatPdMevValue(thresholds.amberUpper)}`, 'amber')}
      ${buildPdMevThresholdChip('Red', `< ${formatPdMevValue(thresholds.amberLower)} or > ${formatPdMevValue(thresholds.amberUpper)}`, 'red')}
    </div>`;
}

function buildPdMevMarkerLegendItem(label, dateValue, tone) {
  return `
    <div class="pd-mev-marker-legend-item pd-mev-marker-legend-item-${tone}">
      <span class="pd-mev-marker-legend-line pd-mev-marker-legend-line-${tone}" aria-hidden="true"></span>
      <span class="pd-mev-marker-legend-copy">
        <span class="pd-mev-marker-legend-label">${escapePdHtml(label)}</span>
        <span class="pd-mev-marker-legend-date">${escapePdHtml(formatPdShortDate(dateValue))}</span>
      </span>
    </div>`;
}

function buildPdMevMarkerLegendRow(modelData, mevData) {
  const items = [];
  if (mevData?.dev_range?.development_date) {
    items.push(buildPdMevMarkerLegendItem('Development', mevData.dev_range.development_date, 'development'));
  }
  if (modelData?.severe_scenario_date) {
    items.push(buildPdMevMarkerLegendItem('Severe scenario', modelData.severe_scenario_date, 'scenario'));
  }
  if (!items.length) return '';
  return `<div class="pd-mev-marker-legend-row" aria-label="Reference date markers">${items.join('')}</div>`;
}

function closePdMevFilterMenus() {
  document.querySelectorAll('.pd-mev-filter-row .checkbox-dropdown-menu').forEach(menu => {
    menu.classList.remove('open');
  });
  PD_MEV_FILTER_REOPEN_MENU_ID = '';
  PD_MEV_FILTER_REOPEN_MENU_SCROLL_TOP = 0;
}

function initPdMevFilterEvents() {
  if (PD_MEV_FILTER_EVENTS_BOUND) return;
  document.addEventListener('click', function(evt) {
    if (!evt.target.closest('.pd-mev-filter-row .checkbox-dropdown')) {
      closePdMevFilterMenus();
    }
  });
  PD_MEV_FILTER_EVENTS_BOUND = true;
}

function togglePdMevFilterMenu(event, menuId) {
  event.stopPropagation();
  const menu = document.getElementById(menuId);
  if (!menu) return;
  const shouldOpen = !menu.classList.contains('open');
  closePdMevFilterMenus();
  menu.classList.toggle('open', shouldOpen);
  if (shouldOpen) {
    PD_MEV_FILTER_REOPEN_MENU_ID = menuId;
    PD_MEV_FILTER_REOPEN_MENU_SCROLL_TOP = menu.scrollTop || 0;
  }
}

function queuePdMevMenuRestore(menuId, scrollTop = 0) {
  PD_MEV_FILTER_REOPEN_MENU_ID = menuId || '';
  PD_MEV_FILTER_REOPEN_MENU_SCROLL_TOP = Number.isFinite(scrollTop) ? scrollTop : 0;
}

function restorePdMevMenuState() {
  if (!PD_MEV_FILTER_REOPEN_MENU_ID) return;
  const menu = document.getElementById(PD_MEV_FILTER_REOPEN_MENU_ID);
  if (!menu) {
    PD_MEV_FILTER_REOPEN_MENU_ID = '';
    PD_MEV_FILTER_REOPEN_MENU_SCROLL_TOP = 0;
    return;
  }
  menu.classList.add('open');
  menu.scrollTop = PD_MEV_FILTER_REOPEN_MENU_SCROLL_TOP;
}

function getPdMevQuarterKey(quarter) {
  const match = /^(\d{4})Q([1-4])$/.exec(quarter || '');
  return match ? `${match[1]}-Q${match[2]}` : '';
}

function calculatePdMevRag(value, thresholds) {
  if (!Number.isFinite(value) || !thresholds) return 'N/A';
  if (value < thresholds.amberLower || value > thresholds.amberUpper) return 'Red';
  if (value < thresholds.greenMin || value > thresholds.greenMax) return 'Amber';
  return 'Green';
}

function calculatePdMevWorstRagAfterQuarter(mevData, startQuarter) {
  const thresholds = calculatePdMevThresholds(mevData?.dev_range || {});
  if (!thresholds) return 'N/A';
  const postScenarioValues = Object.entries(mevData?.time_series || {})
    .filter(([quarter, rawValue]) => (
      (!startQuarter || comparePdQuarterLabels(quarter, startQuarter) >= 0)
      && Number.isFinite(Number(rawValue))
    ))
    .map(([, rawValue]) => Number(rawValue));
  if (!postScenarioValues.length) return 'N/A';

  let worstRag = 'Green';
  for (const value of postScenarioValues) {
    const rag = calculatePdMevRag(value, thresholds);
    if (rag === 'Red') return 'Red';
    if (rag === 'Amber') worstRag = 'Amber';
  }
  return worstRag;
}

function buildPdMevRagTagRow(label, names, tone) {
  return `
    <div class="pd-mev-rag-tag-row">
      <span class="pd-mev-rag-tag-label pd-mev-rag-tag-label-${tone}">${escapePdHtml(label)}</span>
      <div class="pd-mev-rag-tags">
        ${names.length
          ? names.map(name => `<span class="pd-mev-rag-tag pd-mev-rag-tag-${tone}">${escapePdHtml(name)}</span>`).join('')
          : `<span class="pd-mev-rag-tag pd-mev-rag-tag-neutral">None</span>`}
      </div>
    </div>`;
}

function buildPdMevDropdownMenu(menuId, options, selectedValues, onChangeFn, allAttribute) {
  const safeAllAttribute = allAttribute ? ` ${allAttribute}` : '';
  return `
    <div class="checkbox-dropdown-menu" id="${menuId}">
      <label><input type="checkbox" value="All"${safeAllAttribute} onchange="${onChangeFn}(this)"${options.length && selectedValues.length === options.length ? ' checked' : ''}>All</label>
      ${options.map(option => `
        <label>
          <input type="checkbox" value="${escapePdHtml(option)}" onchange="${onChangeFn}(this)"${selectedValues.includes(option) ? ' checked' : ''}>
          ${escapePdHtml(option)}
        </label>
      `).join('')}
    </div>`;
}

function buildPdMevSelectOptions(options, selectedValue, allLabel) {
  return [
    `<option value="all"${selectedValue === 'all' ? ' selected' : ''}>${escapePdHtml(allLabel)}</option>`,
    ...options.map(option => (
      `<option value="${escapePdHtml(option)}"${selectedValue === option ? ' selected' : ''}>${escapePdHtml(option)}</option>`
    )),
  ].join('');
}

function formatPdMevFilterToggle(selectedValues, totalCount, singularLabel, pluralLabel) {
  if (!totalCount || !selectedValues.length) return `Select ${pluralLabel}`;
  if (selectedValues.length === totalCount) return `All ${pluralLabel}`;
  if (selectedValues.length === 1) return selectedValues[0];
  return `${selectedValues.length} ${pluralLabel} selected`;
}

function resetPdMevFilters() {
  PD_MEV_FILTER_MODELS = [];
  PD_MEV_FILTER_NAMES = [];
  PD_MEV_FILTER_NAMES_EMPTY = false;
  PD_TIME_RANGES.mev = {from: '', to: ''};
  persistPdMevFilterState();
  closePdMevFilterMenus();
  renderPdModels();
}

function buildPdMevFilterRow(pd, mevPeriods) {
  const availableModelNames = getPdMevSelectedModels(pd);
  const selectedModelNames = getPdMevChartModelNames(pd);
  const availableMevNames = getPdMevAvailableNamesForModels(pd, selectedModelNames);
  const selectedMevNames = getPdMevChartNames(pd);
  const selectedModelValue = selectedModelNames.length === availableModelNames.length
    ? 'all'
    : (selectedModelNames[0] || 'all');
  const mevRangeSelection = getPdRangeSelection('mev', mevPeriods);
  const hasMevRangeSelection = !!mevRangeSelection.from || !!mevRangeSelection.to;
  const hasModelSelection = selectedModelNames.length !== availableModelNames.length;
  const hasMevSelection = selectedMevNames.length !== availableMevNames.length;
  const canResetFilters = hasModelSelection || hasMevSelection || hasMevRangeSelection;
  return `
    <div class="pd-mev-filter-row">
      <div class="pd-mev-filter-copy">
        <div class="pd-content-kicker">Chart Filters</div>
        <p>Refine the MEV charts below by PD model or by individual macroeconomic variable.</p>
      </div>
      <div class="pd-mev-filter-controls">
        <div class="pd-mev-filter-group">
          <label>PD Model</label>
          <select
            id="pd-mev-model-filter-select"
            class="pd-mev-filter-select"
            aria-label="PD model chart filter"
            onchange="setPdMevModelFilter(this.value)"
            ${availableModelNames.length ? '' : 'disabled'}
          >${buildPdMevSelectOptions(availableModelNames, selectedModelValue, 'All')}</select>
        </div>
        <div class="pd-mev-filter-group">
          <label>MEV</label>
          <div class="checkbox-dropdown pd-mev-filter-dropdown">
            <button
              type="button"
              class="checkbox-dropdown-toggle"
              id="pd-mev-name-filter-toggle"
              onclick="togglePdMevFilterMenu(event,'pd-mev-name-filter-menu')"
              ${availableMevNames.length ? '' : 'disabled'}
            >${escapePdHtml(formatPdMevFilterToggle(selectedMevNames, availableMevNames.length, 'MEV', 'MEVs'))}</button>
            ${buildPdMevDropdownMenu(
              'pd-mev-name-filter-menu',
              availableMevNames,
              selectedMevNames,
              'setPdMevNameFilters',
              'data-pd-mev-name-all',
            )}
          </div>
        </div>
        ${mevPeriods.length ? buildPdRangeControls('mev', mevPeriods, mevPeriods[mevPeriods.length - 1]) : ''}
        <div class="pd-mev-filter-actions">
          <button
            type="button"
            class="btn pd-mev-filter-reset"
            onclick="resetPdMevFilters()"
            ${canResetFilters ? '' : 'disabled'}
          >Reset chart filters</button>
        </div>
      </div>
    </div>`;
}

function setPdMevModelFilter(value) {
  const pd = (DASH_DATA.monitoring || {}).pd_models || {};
  const availableModelNames = getPdMevSelectedModels(pd);
  if (!availableModelNames.length) {
    PD_MEV_FILTER_MODELS = [];
  } else if (!value || value === 'all' || !availableModelNames.includes(value)) {
    PD_MEV_FILTER_MODELS = availableModelNames.slice();
  } else {
    PD_MEV_FILTER_MODELS = [value];
  }
  persistPdMevFilterState();
  closePdMevFilterMenus();
  renderPdModels();
}

function setPdMevNameFilters(changedInput) {
  const inputs = Array.from(document.querySelectorAll('#pd-mev-name-filter-menu input[type="checkbox"]'));
  const allInput = inputs.find(input => input.hasAttribute('data-pd-mev-name-all'));
  const mevInputs = inputs.filter(input => !input.hasAttribute('data-pd-mev-name-all'));
  const toggle = document.getElementById('pd-mev-name-filter-toggle');
  const menu = document.getElementById('pd-mev-name-filter-menu');
  if (changedInput && changedInput.hasAttribute('data-pd-mev-name-all')) {
    mevInputs.forEach(input => { input.checked = changedInput.checked; });
  } else if (allInput) {
    allInput.checked = mevInputs.length > 0 && mevInputs.every(input => input.checked);
  }
  const selectedNames = mevInputs.filter(input => input.checked).map(input => input.value);
  if (!selectedNames.length) {
    PD_MEV_FILTER_NAMES_EMPTY = false;
    if (toggle) toggle.textContent = 'Select MEVs';
    return;
  }
  PD_MEV_FILTER_NAMES = selectedNames;
  PD_MEV_FILTER_NAMES_EMPTY = false;
  if (menu && menu.classList.contains('open')) {
    queuePdMevMenuRestore('pd-mev-name-filter-menu', menu.scrollTop || 0);
  }
  persistPdMevFilterState();
  renderPdModels();
}

function buildPdMevRagSummaryCard(selectedModels, catalog) {
  const severeScenarioDates = selectedModels
    .map(modelName => catalog[modelName]?.severe_scenario_date)
    .filter(Boolean);
  const modelSummaries = selectedModels.map(modelName => {
    const mevEntries = Object.entries(catalog[modelName]?.mevs || {});
    const severeQuarter = isoDateToPdQuarter(catalog[modelName]?.severe_scenario_date);
    const summary = {
      modelName,
      severeQuarter,
      red: [],
      amber: [],
      unavailable: [],
    };
    mevEntries.forEach(([mevName, mevData]) => {
      const rag = calculatePdMevWorstRagAfterQuarter(mevData, severeQuarter);
      if (rag === 'Red') summary.red.push(mevName);
      else if (rag === 'Amber') summary.amber.push(mevName);
      else if (rag === 'N/A') summary.unavailable.push(mevName);
    });
    return summary;
  });

  return `
    <article class="pd-test-card pd-mev-rag-summary-card">
      <div class="pd-test-card-heading">
        <div>
          <span>Post-scenario RAG</span>
          <div class="pd-card-title-row">
            <h4>Worst amber / red MEV counts</h4>
          </div>
        </div>
      </div>
      <div class="pd-test-value">${escapePdHtml(formatPdDateSummary(severeScenarioDates))}</div>
      <div class="pd-test-meta">Evaluation window: each model severe scenario date onward</div>
      <div class="pd-test-meta">Method: worst RAG observed across all post-scenario MEV values</div>
      <div class="pd-mev-rag-summary-list">
        ${modelSummaries.length
          ? modelSummaries.map(summary => `
            <div class="pd-mev-rag-model">
              <div class="pd-mev-rag-model-header">
                <strong>${escapePdHtml(summary.modelName)}</strong>
                <div class="pd-mev-rag-counts">
                  <span class="pd-mev-rag-count pd-mev-rag-count-red">${summary.red.length} red</span>
                  <span class="pd-mev-rag-count pd-mev-rag-count-amber">${summary.amber.length} amber</span>
                </div>
              </div>
              <div class="pd-test-meta">Window start: ${escapePdHtml(summary.severeQuarter || 'Unavailable')}</div>
              ${buildPdMevRagTagRow('Red', summary.red, 'red')}
              ${buildPdMevRagTagRow('Amber', summary.amber, 'amber')}
            </div>
          `).join('')
          : `<div class="pd-test-meta">No PD models are currently in scope for MEV evaluation.</div>`}
      </div>
    </article>`;
}

function buildPdMevDevelopmentDatesCard(selectedModels, catalog) {
  const modelDates = selectedModels.map(modelName => {
    const dates = Array.from(new Set(
      Object.values(catalog[modelName]?.mevs || {})
        .map(mev => mev?.dev_range?.development_date)
        .filter(Boolean),
    )).sort();
    return {modelName, dates};
  });
  const distinctCheckpointCount = new Set(modelDates.flatMap(item => item.dates)).size;

  return `
    <article class="pd-test-card pd-mev-development-card">
      <div class="pd-test-card-heading">
        <div>
          <span>Reference</span>
          <div class="pd-card-title-row">
            <h4>Development dates</h4>
          </div>
        </div>
      </div>
      <div class="pd-mev-development-list">
        ${modelDates.length
          ? modelDates.map(item => {
            const dateLabel = item.dates.length
              ? item.dates.map(formatPdShortDate).join(' / ')
              : '—';
            return `
              <div class="pd-mev-development-row">
                <strong>${escapePdHtml(item.modelName)}</strong>
                <span>${escapePdHtml(dateLabel)}</span>
              </div>`;
          }).join('')
          : '<div class="pd-test-meta">No development dates in scope.</div>'}
      </div>
      <div class="pd-test-meta">Distinct checkpoints: ${escapePdHtml(`${distinctCheckpointCount}`)}</div>
      <div class="pd-test-meta">Purpose: Green range reference</div>
    </article>`;
}

function buildPdMevRangeSection(pd) {
  const catalog = getPdMevCatalog(pd);
  const selectedModels = getPdMevSelectedModels(pd);
  const chartModelNames = getPdMevChartModelNames(pd);
  const chartMevNames = getPdMevChartNames(pd);
  const mevPeriods = getPdMevVisiblePeriods(catalog, chartModelNames, chartMevNames);
  const totalMevs = selectedModels.reduce(
    (sum, modelName) => sum + Object.keys(catalog[modelName]?.mevs || {}).length,
    0,
  );
  const developmentDates = selectedModels.flatMap(modelName => (
    Object.values(catalog[modelName]?.mevs || {})
      .map(mev => mev?.dev_range?.development_date)
      .filter(Boolean)
  ));
  const severeScenarioDates = selectedModels
    .map(modelName => catalog[modelName]?.severe_scenario_date)
    .filter(Boolean);
  const modelScopeLabel = selectedModels.length
    ? selectedModels.join(', ')
    : 'No models matched the current filters';
  const modelPanels = chartModelNames.map((modelName, modelIndex) => {
    const modelData = catalog[modelName] || {};
    const mevEntries = Object.entries(modelData.mevs || {})
      .filter(([mevName]) => chartMevNames.includes(mevName))
      .sort(([left], [right]) => left.localeCompare(right));
    if (!mevEntries.length) return '';
    return `
      <div class="section-card pd-mev-model-panel">
        <div class="pd-mev-model-heading">
          <div class="pd-mev-model-copy">
            <div class="pd-content-kicker">Model Scope</div>
            <h4>${escapePdHtml(modelName)}</h4>
            <p>Segments covered: ${escapePdHtml((modelData.segments || []).join(', ') || '—')}</p>
          </div>
          <div class="pd-mev-model-badges">
            <span class="pd-mev-model-badge">${escapePdHtml(mevEntries.length)} MEVs</span>
            <span class="pd-mev-model-badge">Severe scenario: ${escapePdHtml(formatPdShortDate(modelData.severe_scenario_date))}</span>
          </div>
        </div>
        <div class="pd-mev-chart-grid">
          ${mevEntries.map(([mevName, mevData], mevIndex) => {
            const thresholds = calculatePdMevThresholds(mevData.dev_range || {});
            const chartId = getPdMevChartId(modelName, mevName);
            return `
              <article class="pd-mev-chart-card">
                <div class="pd-mev-chart-header">
                  <div>
                    <div class="pd-mev-chart-title">${escapePdHtml(mevName)}</div>
                    <div class="pd-mev-chart-meta">Reference dates and threshold ranges for ${escapePdHtml(mevName)}.</div>
                  </div>
                </div>
                ${buildPdMevThresholdChipRow(thresholds)}
                ${buildPdMevMarkerLegendRow(modelData, mevData)}
                <div id="${chartId}" class="pd-mev-chart" data-mev-color="${escapePdHtml(getPdMevChartColor(modelIndex * 8 + mevIndex))}"></div>
              </article>`;
          }).join('')}
        </div>
      </div>`;
  }).filter(Boolean).join('');

  const emptyState = `
    <div class="section-card pd-mev-empty-state">
      <div class="pd-mev-chart-title">No MEV charts match the current chart filters</div>
      <p class="pd-section-subtitle">
        Adjust the PD model selector or MEV checkboxes below the summary cards, or broaden the dashboard filters above.
      </p>
    </div>`;

  return `
    <section id="pd-mev-range" class="pd-content-section pd-live-section">
      ${buildPdSectionHeading(
        '2.6 MEV Range',
        'MEV Range',
        'Plot the selected PD models against their development green range, amber two-standard-deviation buffers, and red out-of-range zones.',
        'N/A',
        {showRag: false},
      )}
      <div class="pd-performance-note">
        Each chart uses the model-specific development min/max as the green band, extends amber by two standard deviations beyond that development range, and marks the model development date and severe scenario date directly on the timeline. Source: <strong>${escapePdHtml(pd.mev_source_file || 'mev_dummy_data.json')}</strong>.
      </div>
      <div class="pd-test-grid pd-mev-summary-grid">
        ${buildPdMevRagSummaryCard(selectedModels, catalog)}
        ${buildPdStaticInfoCard(
          'Models in scope',
          `${selectedModels.length}`,
          [
            {label: 'Segment filter', value: MONITORING_PORTFOLIO_SEGMENT === 'all' ? 'All segments' : MONITORING_PORTFOLIO_SEGMENT},
            {label: 'Model scope', value: modelScopeLabel},
          ],
          {testLabel: 'Filters'},
        )}
        ${buildPdStaticInfoCard(
          'MEV charts',
          `${totalMevs}`,
          [
            {label: 'Rendered panels', value: totalMevs ? `${totalMevs} charts` : 'No charts in scope'},
            {label: 'Catalog models', value: `${Object.keys(catalog).length}`},
          ],
          {testLabel: 'Coverage'},
        )}
        ${buildPdMevDevelopmentDatesCard(selectedModels, catalog)}
        ${buildPdStaticInfoCard(
          'Severe scenario',
          formatPdDateSummary(severeScenarioDates),
          [
            {label: 'Distinct checkpoints', value: `${new Set(severeScenarioDates).size}`},
            {label: 'Purpose', value: 'Scenario marker'},
          ],
          {testLabel: 'Scenario'},
        )}
      </div>
      ${buildPdMevFilterRow(pd, mevPeriods)}
      ${chartModelNames.length && chartMevNames.length && modelPanels ? modelPanels : emptyState}
    </section>`;
}

function drawPdMevRangeChart(chartId, modelData, mevName, mevData, color) {
  const chart = document.getElementById(chartId);
  if (!chart) return;

  const allPoints = Object.entries(mevData.time_series || {})
    .map(([quarter, value]) => [quarter, Number(value)])
    .filter(([, value]) => Number.isFinite(value))
    .sort(([left], [right]) => comparePdQuarterLabels(left, right));
  const visibleQuarters = filterPdPeriodsByRange('mev', allPoints.map(([quarter]) => quarter));
  const points = allPoints.filter(([quarter]) => visibleQuarters.includes(quarter));
  if (!points.length) {
    chart.innerHTML = '<div class="pd-performance-note">No MEV time-series data is available for the selected time window.</div>';
    return;
  }

  const thresholds = calculatePdMevThresholds(mevData.dev_range || {});
  const quarters = points.map(([quarter]) => quarter);
  const values = points.map(([, value]) => value);
  const developmentQuarter = isoDateToPdQuarter(mevData?.dev_range?.development_date);
  const severeQuarter = isoDateToPdQuarter(modelData?.severe_scenario_date);
  const allYValues = values.slice();
  if (thresholds) {
    allYValues.push(thresholds.greenMin, thresholds.greenMax, thresholds.amberLower, thresholds.amberUpper);
  }
  const minValue = Math.min(...allYValues);
  const maxValue = Math.max(...allYValues);
  const padding = Math.max((maxValue - minValue) * 0.08, Math.abs(maxValue || 1) * 0.05, 0.25);
  const yMin = minValue - padding;
  const yMax = maxValue + padding;
  const shapes = [];

  if (thresholds) {
    shapes.push(
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: yMin, y1: thresholds.amberLower, fillcolor: 'rgba(220,38,38,0.14)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.amberLower, y1: thresholds.greenMin, fillcolor: 'rgba(217,119,6,0.20)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.greenMin, y1: thresholds.greenMax, fillcolor: 'rgba(22,163,74,0.16)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.greenMax, y1: thresholds.amberUpper, fillcolor: 'rgba(217,119,6,0.20)', line: {width: 0}, layer: 'below'},
      {type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.amberUpper, y1: yMax, fillcolor: 'rgba(220,38,38,0.14)', line: {width: 0}, layer: 'below'},
      {type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.greenMin, y1: thresholds.greenMin, line: {color: 'rgba(22,163,74,0.9)', width: 1.8}},
      {type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.greenMax, y1: thresholds.greenMax, line: {color: 'rgba(22,163,74,0.9)', width: 1.8}},
      {type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.amberLower, y1: thresholds.amberLower, line: {color: 'rgba(217,119,6,0.82)', width: 1.4, dash: 'dash'}},
      {type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: thresholds.amberUpper, y1: thresholds.amberUpper, line: {color: 'rgba(217,119,6,0.82)', width: 1.4, dash: 'dash'}},
    );
  }

  if (developmentQuarter && quarters.includes(developmentQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: developmentQuarter,
      x1: developmentQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#0f172a', width: 1.5, dash: 'dot'},
    });
  }

  if (severeQuarter && quarters.includes(severeQuarter)) {
    shapes.push({
      type: 'line',
      xref: 'x',
      x0: severeQuarter,
      x1: severeQuarter,
      yref: 'paper',
      y0: 0,
      y1: 1,
      line: {color: '#9a3412', width: 1.5, dash: 'dash'},
    });
  }

  Plotly.react(chartId, [{
    x: quarters,
    y: values,
    type: 'scatter',
    mode: 'lines+markers',
    connectgaps: false,
    line: {
      color,
      width: 2.6,
      shape: 'spline',
      smoothing: 0.45,
    },
    marker: {
      size: 6,
      color: '#ffffff',
      line: {color, width: 2},
    },
    hovertemplate: `%{x}<br>${escapePdHtml(mevName)}: %{y:,.2f}<extra></extra>`,
  }], {
    height: 292,
    margin: {t: 16, r: 18, b: 54, l: 58},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    hovermode: 'x unified',
    showlegend: false,
    shapes,
    xaxis: buildMonitoringTimeSeriesXAxis(quarters, {
      title: 'Quarter',
      gridcolor: '#e2e8f0',
      showline: true,
      linecolor: '#cbd5e1',
      ticks: 'outside',
    }, {
      chart,
      density: 'compact',
    }),
    yaxis: {
      title: mevName,
      range: [yMin, yMax],
      automargin: true,
      gridcolor: '#e2e8f0',
      zerolinecolor: '#cbd5e1',
      showline: true,
      linecolor: '#cbd5e1',
      ticks: 'outside',
    },
  }, {responsive: true, displayModeBar: false});
}

function drawPdMevCharts(pd) {
  const catalog = getPdMevCatalog(pd);
  const selectedModels = getPdMevChartModelNames(pd);
  const selectedMevNames = getPdMevChartNames(pd);
  selectedModels.forEach((modelName, modelIndex) => {
    const modelData = catalog[modelName] || {};
    Object.entries(modelData.mevs || {})
      .filter(([mevName]) => selectedMevNames.includes(mevName))
      .sort(([left], [right]) => left.localeCompare(right))
      .forEach(([mevName, mevData], mevIndex) => {
        drawPdMevRangeChart(
          getPdMevChartId(modelName, mevName),
          modelData,
          mevName,
          mevData,
          getPdMevChartColor(modelIndex * 8 + mevIndex),
        );
      });
  });
}

function renderPdModels() {
  restorePdMevFilterState();
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
  const balanceSheetConfidenceRag = calculatePdMetricRag(
    thresholds,
    'Confidence Interval Test',
    balanceSheetCalibrationValues['Confidence Interval Test'],
  );
  const balanceSheetNotchingRag = calculatePdMetricRag(
    thresholds,
    'Notching Test',
    balanceSheetCalibrationValues['Notching Test'],
  );
  const balanceSheetAssignmentTooltip = buildPdCalibrationAssignmentTooltip(
    'Balance Sheet 1 year',
    balanceSheetCalibrationValues['Confidence Interval Test'],
    balanceSheetCalibrationNotching.signedDifference,
    balanceSheetCalibrationAssignmentRag,
    balanceSheetCalibrationRag,
    balanceSheetConfidenceRag,
    balanceSheetNotchingRag,
  );
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
      'Calibration Conservatism RAG (ECL PIT)',
      calibrationRag,
      previousCalibrationRag,
      context,
      {
        cardTitle: 'Calibration Conservatism RAG (ECL PIT)',
        extraClass: 'pd-calibration-summary-card',
        tooltip: buildPdCalibrationTooltip(calibrationAssignmentDetails),
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
    const horizonConfidenceRag = calculatePdMetricRag(
      thresholds,
      'Confidence Interval Test',
      horizonValues['Confidence Interval Test'],
    );
    const horizonNotchingRag = calculatePdMetricRag(
      thresholds,
      'Notching Test',
      horizonValues['Notching Test'],
    );
    const horizonAssignmentTooltip = buildPdCalibrationAssignmentTooltip(
      horizonConfig.suffix,
      horizonValues['Confidence Interval Test'],
      horizonNotching.signedDifference,
      horizonCalibrationAssignmentRag,
      horizonCalibrationRag,
      horizonConfidenceRag,
      horizonNotchingRag,
    );
    const currentHorizonEad = currentMonitoringEad[horizonConfig.key] || {ead: null, share: null, combinedEad: null};
    const previousHorizonEad = previousMonitoringEad[horizonConfig.key] || {ead: null, share: null, combinedEad: null};
    calibrationOverview[horizonConfig.key] = {
      notchingValue: horizonValues['Notching Test'],
      notchingRag: horizonNotchingRag,
      confidenceValue: horizonValues['Confidence Interval Test'],
      confidenceRag: horizonConfidenceRag,
      assignmentRag: horizonCalibrationRag,
      assignmentTooltip: horizonAssignmentTooltip,
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
        {cardTitle: `RAG Assignment ${horizonConfig.suffix}`, tooltip: horizonAssignmentTooltip, hideStatus: true},
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
      tooltip: buildPdCalibrationTooltip(calibrationAssignmentDetails),
    },
    discrimination: {
      accuracyValue: currentRagValues['Accuracy Ratio'],
      accuracyRag: calculatePdMetricRag(thresholds, 'Accuracy Ratio', currentRagValues['Accuracy Ratio']),
      deltaValue: currentRagValues['Delta Accuracy Ratio'],
      deltaRag: calculatePdMetricRag(thresholds, 'Delta Accuracy Ratio', currentRagValues['Delta Accuracy Ratio']),
      overallRag: discriminationRag,
      tooltip: 'If the 1-year default count is below 15, the RAG is forced to Amber. Otherwise: if Delta Accuracy Ratio is Red and Accuracy Ratio is Green, the RAG is Amber. If Delta Accuracy Ratio is Red and Accuracy Ratio is Amber, the RAG is Red. Otherwise the Accuracy Ratio RAG is used.',
    },
    balanceSheet: {
      notchingValue: balanceSheetCalibrationValues['Notching Test'],
      notchingRag: balanceSheetNotchingRag,
      confidenceValue: balanceSheetCalibrationValues['Confidence Interval Test'],
      confidenceRag: balanceSheetConfidenceRag,
      overallRag: balanceSheetCalibrationRag,
      assignmentTooltip: balanceSheetAssignmentTooltip,
    },
    performancePd: performancePdOverview,
  });

  document.getElementById('tab-pd_models').innerHTML = `
    <section id="pd-rag-assignment" class="pd-content-section pd-chapter-section">
      ${buildPdChapterHeading(
        '1.',
        'RAG Assignment',
        'Core monitoring view for PD model health, combining the current overview with ECL PIT PD and Balance Sheet PD calibration and discriminatory-power diagnostics.',
        {
          note: `Monitoring point ${CQ}`,
        },
      )}
    </section>

    <div class="pd-chapter-body pd-chapter-body-primary">
    <section id="pd-analysis-scope" class="pd-content-section pd-overview-section pd-live-section">
      <div class="pd-content-heading">
        <div class="pd-content-kicker">1.1 Overview</div>
        <h3>RAG Assignment Overview</h3>
        <p>At-a-glance summary of the current ECL PIT PD and Balance Sheet PD calibration and discriminatory power diagnostics.</p>
      </div>
      ${overviewHeatmap}
      ${availabilityNote}
    </section>

    <section id="pd-calibration-rag" class="pd-content-section pd-live-section">
      ${buildPdSectionHeading(
        '1.2 ECL PIT PD - Calibration Conservatism',
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
      <div class="pd-trend-detail-grid">
      <div id="pd-calibration-rag-trend-panel" class="section-card pd-default-rate-trend-section" data-pd-expand-title="Calibration Conservatism RAG (ECL PIT) Trend">
        ${buildPdChartHeader(
          'Calibration Conservatism RAG (ECL PIT) Trend',
          'Quarter-by-quarter Calibration Conservatism RAG (ECL PIT) shown as a simple color-coded dot timeline.',
          'pd-calibration-rag-trend-panel',
          'calibration_rag',
          getPdRangePeriods(CQ),
          CQ,
        )}
        <div id="pd-calibration-rag-trend-chart" class="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact"></div>
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
        <div id="pd-confidence-interval-trend-chart" class="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium"></div>
      </div>
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
        <div id="pd-notching-trend-chart" class="pd-default-rate-trend-chart pd-notching-trend-chart"></div>
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
        <div id="pd-default-rate-trend-chart" class="pd-default-rate-trend-chart pd-calibration-trend-chart"></div>
      </div>
    </section>

    <section id="pd-discrimination-rag" class="pd-content-section pd-live-section">
      ${buildPdSectionHeading(
        '1.3 ECL PIT PD - Discriminatory Power',
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
        <div id="pd-discrimination-rag-trend-chart" class="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact"></div>
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
        <div id="pd-go-live-accuracy-trend-chart" class="pd-default-rate-trend-chart pd-go-live-accuracy-trend-chart"></div>
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

    <section id="pd-balance-sheet-calibration" class="pd-content-section pd-live-section">
      ${buildPdSectionHeading(
        '1.4 Balance Sheet PD - Calibration Conservatism',
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
          {cardTitle: 'Calibration Conservatism RAG', tooltip: balanceSheetAssignmentTooltip, hideStatus: true},
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
      <div class="pd-trend-detail-grid">
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
        <div id="pd-balance-sheet-calibration-rag-trend-chart" class="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact"></div>
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
        <div id="pd-balance-sheet-confidence-interval-trend-chart" class="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium"></div>
      </div>
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
        <div id="pd-balance-sheet-notching-trend-chart" class="pd-default-rate-trend-chart pd-notching-trend-chart"></div>
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
        <div id="pd-balance-sheet-default-rate-trend-chart" class="pd-default-rate-trend-chart pd-calibration-trend-chart"></div>
      </div>
    </section>
    </div>

    <section id="pd-post-subjective-review-analysis" class="pd-content-section pd-chapter-section">
      ${buildPdChapterHeading(
        '2.',
        'Post Subjective Review Analysis',
        'This is a qualitative analysis with a binary outcome: whether rank ordering holds or not. There is no direct RAG assignment for this process; however, any significant concerns identified through the deep-dive analysis will be highlighted in the monitoring report and reflected in the overall Model RAG.',
        {
          note: 'Scaffold aligned to requested subsections',
        },
      )}
    </section>

    <div class="pd-chapter-body pd-chapter-body-secondary">
    <section id="pd-post-subjective-overview" class="pd-content-section pd-placeholder-section">
      ${buildPdSectionHeading(
        '2.1 Overview',
        'Overview',
        'High-level landing area for the future post subjective review analysis package.',
        'N/A',
        {showRag: false},
      )}
      ${buildPdPlaceholderCard(
        'Post Subjective Review Overview',
        'This placeholder section is ready for the future summary narrative, key flags, and cross-check metrics that will frame the post subjective review analysis.',
        ['Summary KPIs', 'Narrative insights', 'Reviewer actions'],
      )}
    </section>

    <section id="pd-transition-matrix-distance" class="pd-content-section pd-placeholder-section">
      ${buildPdSectionHeading(
        '2.2 Transition Matrix',
        'Transition Matrix',
        'Future section for comparing post-review transition behavior against the reference migration structure.',
        'N/A',
        {showRag: false},
      )}
      ${buildPdPlaceholderCard(
        'Transition Matrix',
        'A compact placeholder is in place for the transition matrix views, distance metrics, and interpretation rules that will be added later.',
        ['Transition view', 'Distance metric', 'Threshold guidance'],
      )}
    </section>

    <section id="pd-population-stability-index" class="pd-content-section pd-placeholder-section">
      ${buildPdSectionHeading(
        '2.3 PSI',
        'PSI',
        'Future section for population stability diagnostics after subjective review adjustments.',
        'N/A',
        {showRag: false},
      )}
      ${buildPdPlaceholderCard(
        'Population Stability Index (PSI)',
        'This placeholder reserves space for PSI trends, distribution shift diagnostics, and any future threshold-based alerts.',
        ['PSI trend', 'Shift diagnostics', 'Threshold alerts'],
      )}
    </section>

    <section id="pd-rank-ordering" class="pd-content-section pd-placeholder-section">
      ${buildPdSectionHeading(
        '2.4 Scenario Rank Ordering',
        'Scenario Rank Ordering',
        'Future section for rank-order consistency diagnostics across scenarios after subjective review adjustments.',
        'N/A',
        {showRag: false},
      )}
      ${buildPdPlaceholderCard(
        'Scenario Rank Ordering',
        'This placeholder will later host scenario rank-order checks, supporting visuals, and exception commentary for post-review performance review.',
        ['Ordering stability', 'Scenario comparison', 'Supporting evidence'],
      )}
    </section>

    <section id="pd-sensitivity-analysis" class="pd-content-section pd-placeholder-section">
      ${buildPdSectionHeading(
        '2.5 Sensitivity Analysis',
        'Sensitivity Analysis',
        'Future section for showing how model outputs react to selected drivers and review overlays.',
        'N/A',
        {showRag: false},
      )}
      ${buildPdPlaceholderCard(
        'Sensitivity Analysis',
        'A lightweight placeholder is ready for future parameter sensitivities, comparative views, and documented interpretation logic.',
        ['Driver impact', 'Scenario comparison', 'Review commentary'],
      )}
    </section>

    ${buildPdMevRangeSection(pd)}
    </div>

  `;

  initPdMevFilterEvents();
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
    {chartId: 'pd-balance-sheet-default-rate-trend-chart', rangeKey: 'balance_sheet_calibration', horizontalSubplots: true},
  );
  drawPdMevCharts(pd);
  restorePdMevMenuState();
}

"""
