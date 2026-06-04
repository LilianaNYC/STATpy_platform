"""Monitoring Overview page."""

JS = r"""
function getMonitoringOverviewContext() {
  return {
    monitoringPoint: CQ,
    snapshotQuarter: CQ,
  };
}

function calculateMonitoringOverviewKpis(overview, context) {
  const ragScore = {'N/A': 0, Green: 1, Amber: 2, Red: 3};
  const selectedModels = new Set(MONITORING_MODELS);
  const filteredRows = (overview.model_status_rows || []).filter(row => {
    if (row.monitoring_period !== context.snapshotQuarter) return false;
    if (MONITORING_FILTER_MODE === 'models') return selectedModels.has(row.model);
    if (MONITORING_METRIC_SEGMENT !== 'all' && row.model_group.toLowerCase() !== MONITORING_METRIC_SEGMENT) return false;
    return MONITORING_PORTFOLIO_SEGMENT === 'all' || row.segment === MONITORING_PORTFOLIO_SEGMENT;
  });

  const statusByModel = new Map();
  filteredRows.forEach(row => {
    const current = statusByModel.get(row.model);
    if (!current || (ragScore[row.overall_rag] || 0) > (ragScore[current.overall_rag] || 0)) {
      statusByModel.set(row.model, row);
    }
  });

  const modelStatuses = Array.from(statusByModel.values());
  const redModels = modelStatuses.filter(row => row.overall_rag === 'Red').length;
  const amberModels = modelStatuses.filter(row => row.overall_rag === 'Amber').length;
  const greenModels = modelStatuses.filter(row => row.overall_rag === 'Green').length;
  return {
    modelsMonitored: modelStatuses.length,
    redModels,
    amberModels,
    greenModels,
    breaches: redModels + amberModels,
  };
}

function renderOverview() {
  const m = DASH_DATA.monitoring || {};
  const overview = m.overview || {};
  const context = getMonitoringOverviewContext();
  const kpis = calculateMonitoringOverviewKpis(overview, context);

  const cards = [
    {
      title: 'Models Monitored',
      value: fmtN(kpis.modelsMonitored),
      detail: `Snapshot date: ${context.snapshotQuarter}`,
      css: '',
    },
    {
      title: 'Red Models',
      value: fmtN(kpis.redModels),
      detail: 'Worst status retained per model',
      css: 'monitoring-overview-kpi-red',
    },
    {
      title: 'Amber Models',
      value: fmtN(kpis.amberModels),
      detail: 'Worst status retained per model',
      css: 'monitoring-overview-kpi-amber',
    },
    {
      title: 'Green Models',
      value: fmtN(kpis.greenModels),
      detail: 'Worst status retained per model',
      css: 'monitoring-overview-kpi-green',
    },
    {
      title: 'Breaches',
      value: fmtN(kpis.breaches),
      detail: 'Red + Amber models',
      css: 'monitoring-overview-kpi-red',
    },
  ];

  const cardsHtml = cards.map(c => `
    <div class="kpi-card monitoring-overview-kpi ${c.css}">
      <div class="kpi-card-title">${c.title}</div>
      <div class="kpi-card-value">${c.value}</div>
      <div class="kpi-card-subtext">${c.detail}</div>
    </div>`).join('');

  document.getElementById('tab-overview').innerHTML = `
    <div class="dash-header">
      <h2>Monitoring Overview — ${monitoringPointLabel()}</h2>
      <p>${overview.overview_text}</p>
    </div>

    <div class="monitoring-overview-kpi-grid">
      ${cardsHtml}
    </div>
  `;
}

"""
