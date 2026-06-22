# STATpy Dashboards (multi-dashboard Dash app)

A [Dash](https://dash.plotly.com/) app organised by **dashboard -> page ->
module**. Two dashboards are wired up today:

- **Monitoring** – Wholesale Portfolio model monitoring. The **PD Performance**
  page is fully built out; **LGD** / **EAD Performance** are placeholders ready
  to be filled in following the same per-page structure.
- **SAAS** – a scenario / MEV workspace (MEV time series, projections, bands,
  exports).

Routing and callback registration are **registry-driven**: each dashboard
declares its pages, and the app shell / `app.py` read those registries, so
adding a page or dashboard never requires editing several unrelated central
files. See each dashboard's own README (`features/<name>/README.md`) for its
routes, data sources and conventions.

## Running the app

The app is self-contained – source data is bundled under `source_data/`.

```bash
pip install -r requirements.txt
python -m STATpy_platform.app
```

(run from the directory that *contains* the `STATpy_platform/` folder).

This starts a Dash dev server (default `http://127.0.0.1:8050`). The sidebar
links navigate between `/` (PD Performance), `/lgd-performance`,
`/ead-performance` and `/saas`.

The active environment is selected with `STATPY_ENV` (`dev` by default; see
`config/environments.py`), and the bundled data directory can be overridden with
`STATPY_SOURCE_DATA_DIR`.

## Tests

```bash
pytest STATpy_platform/tests
```

The suite mirrors `features/` one-to-one: a smoke test per page (layout
builds without raising), selector tests for the shared analytics helpers, and a
registry test asserting page paths are unique and reachable.

## Data sources

Source data lives in `source_data/`, bundled with the app. File *locations* are
resolved in `config/settings.py`; data-domain constants (column/sheet names,
RAG bands) live in `data/analytics/constants.py`.

- `portfolio.xlsx` (sheet `Portfolio`) - facility-level portfolio extract
- `statpy_monitoring_thresholds.xlsm` (sheets `PD_Thresholds`,
  `CRR_Master_Scale`, `RAG_Assignment_PD`) - calibration/discrimination
  thresholds, master-scale PDs, and RAG bands
- `mev_dummy_data.json` - macroeconomic-variable scenario catalog
- `facilities_dummy_data.json` - facility-level scenario rank-ordering paths
- `dummy_mev_data.xlsx` - SAAS MEV descriptions, time series and model
  characteristics

Each dashboard's `data_access.py` reads its source files once at import time
and exposes the in-memory payload (e.g. `PD_PERFORMANCE_DATA`, `SAAS_PAGE_DATA`).

## Project layout

```
STATpy_platform/
  app.py                  # entry point: builds shell, loops registry to register callbacks
  shell.py                # sidebar nav, page footer, URL router (all registry-driven)
  features_registry.py    # app-level registry: the list of dashboards

  shared/                 # cross-dashboard shared layer
    types.py              # DashboardDefinition / PageDefinition registry types
    theme.py              # app-shell theme constants + element ids
    registration.py       # per-app idempotent register_callbacks guard

  components/             # shared UI library (reused by >=2 dashboards)
    charts.py             # Plotly figure builders (PD + SAAS)
    filters.py            # global filter bar / sub-nav / range+horizon controls

  config/                 # centralised configuration
    settings.py           # typed Settings (data paths, env, feature flags), built once
    environments.py       # dev / uat / prod overrides

  data/
    common/text.py        # generic helpers shared by loaders (normalize / ordered-unique)
    analytics/            # shared analytics used by components + both dashboards
      calculations.py     #   PD calculation engine (RAG, calibration, discrimination, ...)
      mev_range.py        #   MEV Range helpers (catalog, thresholds, RAG)
      rank_ordering.py    #   Scenario Rank Ordering helpers + YYYY-Qn quarter utils
      constants.py        #   data-domain constants (columns, sheets, RAG bands, palettes)
    monitoring/loader.py  # reads portfolio.xlsx / thresholds / MEV / facilities JSON
    saas/loader.py        # reads dummy_mev_data.xlsx for the SAAS workspace

  features/
    monitoring/           # README, dashboard.py, page_registry.py, stores.py, data_access.py
      pages/pd_performance/  {page.py, callbacks.py, cards.py}
      pages/lgd_performance/ {page.py, callbacks.py}
      pages/ead_performance/ {page.py, callbacks.py}
    saas/                 # README, dashboard.py, page_registry.py, stores.py, data_access.py
      pages/workspace/    {page.py, callbacks.py}

  tests/                  # mirrors features/ 1:1 (registry + per-page smoke + selector tests)
  assets/                 # styles.css, js/ subnav scripts, fonts/ (auto-loaded by Dash)
  source_data/            # bundled Excel/JSON inputs
```

### How the registry wiring works

Each page is described by a `PageDefinition` (key, label, path, `build_layout`,
`register_callbacks`) in its dashboard's `page_registry.py`. Each dashboard exposes a
`DashboardDefinition` from `dashboard.py`, and `features_registry.py` lists the
dashboards. From there:

- `shell.py` builds the sidebar links, the app-level `dcc.Store`s and the
  `#page-content` router (keyed on `dcc.Location.pathname`) entirely from the
  registry. Routes: `/` -> PD Performance, `/lgd-performance`, `/ead-performance`,
  `/saas`.
- `app.py` loops the registry and calls each dashboard's `register_callbacks`.
- Every `register_callbacks(app)` is idempotent via
  `shared.registration.already_registered(app, key)` (per-app, so building a
  second app instance – e.g. in tests – still registers correctly).
- Each dashboard's `data_access.py` loads its source workbook once at import
  time and exposes it (e.g. `PD_PERFORMANCE_DATA`, `SAAS_PAGE_DATA`), so layouts
  and callbacks share the same in-memory data without re-reading files.

### Design notes

- **Shared analytics live in `data/analytics/`.** The PD calculation engine is
  consumed by the shared `components/` layer *and* by the SAAS dashboard, so by
  the "rule of two" it belongs in a shared location rather than inside a single
  dashboard package.
- **URL paths are declarative.** Routes (`/`, `/lgd-performance`, ...) are
  defined on the page registry, so changing the scheme is a one-place edit.
- **The custom registry is the single source of truth for routing.** Dash's
  built-in `use_pages` / `dash.register_page` is intentionally not enabled; if
  adopted later it should be driven from the same registry to avoid two parallel
  routers.

## PD Performance page

The PD Performance page renders both chapters of the ECL PIT / Balance Sheet PD
analysis:

- **Chapter 1 - ECL PIT PD Performance**
  - 1.1 Overview – the "RAG Assignment Overview" 5-stage process-flow diagram
    (Calibration / Discrimination / Balance Sheet RAGs feeding the overall
    Performance PD RAG).
  - 1.2 Calibration Conservatism – CI test, Notching test, default-rate trends,
    calibration trend.
  - 1.3 Discrimination Power – Accuracy Ratio, Gini, KS, Kendall's Tau, and
    discrimination trend charts.
  - 1.4 Performance vs Actuals – EAD-weighted summary, Scenario Rank Ordering,
    and MEV Range charts with model/MEV chart filters.
- **Chapter 2 - Balance Sheet PD Performance**
  - 2.1-2.4 mirror the Chapter 1 sections for the Balance Sheet PD horizon
    (`nco_1y`). Sections without source data render as placeholder cards.

### Interaction model

Filter state lives in the global filter controls plus three `dcc.Store`
components (`pd-range-store`, `pd-trend-horizon-store`, `pd-mev-filter-store`).
A single master callback re-runs `layout.render_pd_performance_content`
whenever any filter or store changes; section builders are pure functions of
that state.

- **Per-chart range controls** – each chart panel with a "Window / From / To"
  control uses one of 13 unique `range_key`s (`calibration_rag`,
  `calibration_ci`, `calibration_notching`, `calibration_default_rate`,
  `discrimination_rag`, `discrimination_accuracy`, `discrimination_trend`,
  `balance_sheet_calibration_rag`, `balance_sheet_ci`, `balance_sheet_notching`,
  `balance_sheet_default_rate`, `rank_ordering`, `mev`), stored as
  `{range_key: {"from": ..., "to": ...}}` in `pd-range-store`. Selecting a
  "From" later than the current "To" (or vice-versa) snaps the other boundary so
  the range stays valid.
- **Trend PD-horizon controls** – every control that affects the same section
  shares one entry in `pd-trend-horizon-store` via `layout.TREND_HORIZON_GROUPS`
  (`calibration_ci`/`calibration_notching`/`calibration_default_rate` ->
  `calibration`, `discrimination_trend` -> `discrimination`), defaulting to
  `{"calibration": "1y", "discrimination": "1y"}`.
- **"Specific Models" checkbox-dropdown** – the Models filter is a collapsed
  `pd-models-toggle` button whose label reflects the current selection
  (`"Select models"` when none are checked, `"All models"` when every model is
  checked, the model name when exactly one is checked, otherwise
  `"N models selected"`, or `"Disabled while Segment is selected"`). It opens a
  `pd-models-menu` dropdown with an "All" toggle and per-model checkboxes; the
  menu stays open while making selections.
- **Segment / model mutual-exclusivity** – selecting a non-"All" Portfolio
  Segment disables the Models checklist (and its "All" toggle); selecting a
  strict subset of models disables the Portfolio Segment dropdown. A help line
  (`pd-filter-help`) explains which filter is active. A disabled control keeps
  its value – reset one filter to "All" before the other becomes selectable.
- **No "Time Horizon" / "PD Input" controls** – `PdFilterContext` carries only
  `quarters` / `models` / `segment` / `monitoring_point`; each section hardcodes
  its own horizon (`1y` / `2y` / `nco_1y`).

### MEV Range chart filters

`pd-mev-filter-store = {"model": "all" | <model_name>, "names": None | [] | [list]}`.

- `"model"` selects which PD model's MEV panel(s) are shown
  (`resolve_pd_mev_chart_model_names`); `"names"` selects which MEVs are shown
  within that scope (`resolve_pd_mev_chart_names`).
- `"names": None` means "no explicit selection yet" and resolves to *all*
  available MEV names for the current model scope. Once the user makes an
  explicit choice, `"names"` becomes a list (which may be empty). An
  explicitly-empty selection shows **zero** MEV charts (an empty-state card is
  rendered).
- "Reset chart filters" restores `pd-mev-filter-store` to
  `{"model": "all", "names": None}` and clears the `"mev"` entry from
  `pd-range-store`.

### Quarter label formats

- Portfolio data and most PD-performance calculations use the `YYYYQn` label
  format (e.g. `2022Q4`).
- Scenario Rank Ordering and MEV data (`facilities_dummy_data.json`,
  `mev_dummy_data.json`) use the `YYYY-Qn` format (e.g. `2022-Q4`), produced from
  ISO dates via `iso_date_to_pd_quarter`. `data/analytics/rank_ordering.py` and
  `data/analytics/mev_range.py` keep this format and provide their own
  `compare_pd_quarter_labels` / `_pd_quarter_sort_key` helpers; it is not
  normalised to `YYYYQn`.

### 1.1 Overview diagram

`build_pd_overview_heatmap`
(`features/monitoring/pages/pd_performance/cards.py`) renders a CSS-grid
process-flow diagram with five stages (Components / Tests / RAG Assignment /
Monitoring Dimension RAG / Performance PD RAG), laid out with
`grid-template-areas`:

- Calibration Conservatism (ECL PIT) 1y/2y notching & confidence-interval test
  nodes feed their RAG-assignment nodes, which feed the calibration dimension
  node.
- Discriminatory Power Accuracy Ratio / Delta Accuracy Ratio test nodes feed the
  discrimination dimension node.
- Calibration Conservatism (Balance Sheet) notching & confidence-interval test
  nodes feed the balance-sheet calibration dimension node.
- All three dimension RAG nodes feed the overall Performance PD RAG gauge
  (`calculate_pd_overview_performance_rag`: weighted 0.25 / 0.25 / 0.50 score,
  rounded to a RAG).

Each dimension RAG node is an in-page anchor link
(`#pd-calibration-rag`, `#pd-discrimination-rag`, `#pd-balance-sheet-calibration`)
that jumps to the corresponding 1.2 / 1.3 / 2.1 section, and RAG-valued nodes
carry an info-chip tooltip (`.pd-info-chip`) with the same explanatory text as
the section cards.

## Styling & client-side assets

Files in `assets/` are auto-loaded by Dash.

- `styles.css` – the app stylesheet (includes the `.pd-overview-flow*` /
  `.pd-flow-*` rules for the 1.1 Overview diagram and the `InterVariable.woff2`
  `@font-face`).
- The PD Performance top bar (`.pd-top-bar`, containing the filter bar and
  section sub-nav) is `position: sticky; top: 0` so it stays visible while the
  page scrolls.
- `js/monitoring_pd_subnav.js` – section sub-navigation for the PD page
  (`#pd-subnav`): it smooth-scrolls to a section on click and highlights
  whichever link/group corresponds to the section currently at the top of the
  viewport.
- `js/saas_workspace_subnav.js` – the equivalent section sub-navigation for the
  SAAS workspace (`#saas-subnav`).

These are plain `.js` files (not callbacks) because they are purely
presentational and don't affect chart data or filter state. They live in
`assets/js/`; Dash loads `assets/` (including subfolders) automatically.

### Layout details

- Trend-detail chart pairs (e.g. default-rate trend + calibration trend) render
  as a horizontal two-column grid (`.pd-trend-detail-grid`,
  `.pd-discrimination-trend-grid`) that collapses to a single column under
  `@media (max-width: 900px)`.
- Chart x-axis tick density is fixed rather than recalculated from container
  width; Plotly's `automargin` / tick-reduction handles overcrowding for the
  data volumes involved.
- The previous monitoring quarter (`get_previous_pd_quarter`) is computed once
  per render and threaded into the calibration/discrimination trend and
  EAD-comparison helpers.
