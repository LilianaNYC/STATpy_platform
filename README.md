# STATpy Dashboards (multi-dashboard Dash app)

A [Dash](https://dash.plotly.com/) app organised by **dashboard → layered
feature**. Three dashboards are wired up today:

- **Monitoring** – Wholesale Portfolio model monitoring (Overview, **PD**, LGD,
  EAD and Loss Performance). All pages are live and read precomputed metrics
  from the source workbook.
- **SAAS** – a scenario / MEV workspace (MEV time series, projections, monitoring
  bands, Excel/report exports).
- **DQ Wholesale** – a data-quality dashboard (completeness, schema, business
  rules, drift, …). This is the reference implementation of the layered
  architecture below.

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
links navigate between the dashboards' pages: `/` (PD Performance), `/overview`,
`/lgd-performance`, `/ead-performance`, `/loss-performance`, `/saas`, and the DQ
pages under `/dq-*`.

The active environment is selected with `STATPY_ENV` (`dev` by default; see
`config/environments.py`), and the bundled data directory can be overridden with
`STATPY_SOURCE_DATA_DIR`.

## Tests

```bash
pytest STATpy_platform            # full suite (repo-level + every feature's tests)
pytest STATpy_platform/tests      # just the repo-level app/registry/shell tests
```

Each feature keeps its own suite under `features/<name>/tests/` (layout builds,
registration, structural checks); shared analytics/selector tests live under the
repo-level `tests/`.

## Architecture

Every feature follows the same **layered** structure (the `dq_module` is the
reference). Each layer has one responsibility and only depends on the layers
beneath it:

| Layer            | Responsibility | Must **not** contain |
|------------------|----------------|----------------------|
| `ui/`            | Dash page composition: layout, cards, tables, charts, callback IDs. `ui/pages/` are thin registration entrypoints; `ui/views/` build the actual layout. | SQL, file I/O, calculations |
| `callbacks/`     | Glue between UI events and the services/domain layers (one module per page, idempotent `register_callbacks`). | heavy logic, direct queries |
| `services/`      | Application orchestration / use-cases (load+enrich data, build exports/reports). | Dash components, hard-coded UI IDs |
| `domain/`        | Pure, framework-agnostic business logic (metric assembly, RAG scoring, selectors). | Dash imports, DB clients |
| `repositories/`* | Persistence / external-system access (read snapshots, write outputs). | scoring logic, UI mapping |
| `tests/`         | Per-layer confidence (domain / service / callback / structure). | — |

\* Every feature owns its repositories (`features/<name>/repositories/loader.py`).
The one **shared** repository is the `Filters` config-sheet reader in
`shared/repositories/`, because it's read by both `monitoring` and `saas` *and*
the shared `shared/ui` layer. Likewise the shared calculation engine lives in
`shared/domain/`. Shared code is kept shared by the "rule of two"; monitoring-only
logic stays in `features/monitoring/domain/`.

### How the registry wiring works

Each page is a `PageDefinition` (key, label, path, `build_layout`,
`register_callbacks`) in its dashboard's `page_registry.py`. Each dashboard
exposes a `DashboardDefinition` from `dashboard.py`, and `features_registry.py`
lists the dashboards. From there:

- `shell.py` builds the sidebar links, the app-level `dcc.Store`s and the
  `#page-content` router (keyed on `dcc.Location.pathname`) entirely from the
  registry.
- `app.py` loops the registry and calls each dashboard's `register_callbacks`.
- Every `register_callbacks(app)` is idempotent via
  `shared.registration.already_registered(app, key)` (per-app, so building a
  second app instance – e.g. in tests – still registers correctly).
- Each dashboard's `data_access.py` loads its snapshot once at import time (via
  its `services` layer) and exposes it (`PD_PERFORMANCE_DATA`, `SAAS_PAGE_DATA`,
  …), so layouts and callbacks share the same in-memory data without re-reading
  files.

## Project layout

```
STATpy_platform/
  app.py                  # entry point: builds shell, loops registry to register callbacks
  shell.py                # sidebar nav, footer, URL router (all registry-driven)
  features_registry.py    # app-level registry: the list of dashboards

  shared/                 # cross-dashboard shared layers (named for the layer they hold)
    ui/                   #   shared presentational layer (reused by >=2 dashboards)
      charts.py           #     Plotly figure builders (PD + SAAS)
      controls.py         #     global filter bar / sub-nav / range+horizon controls
    domain/               #   shared pure business logic
      calculations.py     #     PD calculation engine (RAG, calibration, discrimination)
      mev_range.py        #     MEV Range helpers (catalog, thresholds, RAG)
      quarter_labels.py   #     YYYY-Qn quarter parse / format / sort utils
      constants.py        #     data-domain constants (columns, sheets, RAG bands)
    repositories/         #   shared persistence
      filters_config.py   #     the Filters config sheet (cycles/scenarios/segments)
    text.py               #   generic text helpers shared by loaders
    types.py              #   DashboardDefinition / PageDefinition registry types
    theme.py              #   app-shell theme constants + element ids
    registration.py       #   per-app idempotent register_callbacks guard

  config/                 # centralised configuration
    settings.py           #   typed Settings (data paths, env, flags), built once
    environments.py       #   dev / uat / prod overrides

  features/
    monitoring/           # README + dashboard.py + page_registry.py + stores.py + data_access.py
      ui/{pages,views}/   #   thin entrypoints + page composition (+ views/cards.py, common.py)
      callbacks/          #   one module per page
      services/           #   data_service.py (load/enrich orchestration)
      domain/             #   lgd / ead / loss / overview (monitoring-only logic)
      repositories/       #   loader.py (reads metric tabs into precomputed stores)
      tests/
    saas/                 # same layout; single Workspace page
      ui/{pages,views}/   #   views/{workspace, components, figures}.py
      callbacks/workspace.py
      services/           #   exports.py (Excel), reports.py (chart export)
      domain/             #   selectors / records / metrics
      repositories/       #   loader.py (reads dummy_mev_data.xlsx)
      tests/
    dq_module/            # reference layered feature (ui/callbacks/services/domain/repositories/tests)

  tests/                  # repo-level app/registry/shell + shared-domain tests
  assets/                 # styles.css, js/ subnav scripts, fonts/ (auto-loaded by Dash)
  source_data/            # bundled Excel inputs
```

## Data sources

Source data lives in `source_data/`, bundled with the app. File *locations* are
resolved in `config/settings.py`; data-domain constants (column/sheet names, RAG
bands) live in `shared/domain/constants.py`.

- `portfolio.xlsx` – the monitoring metric tabs
  (`PD/LGD/EAD/Loss_Performance_Metrics`), the `Filters` config sheet, and
  `PD_Sensitivity_Projections` (with `MM_P0` / `MM_Pm` transition margins).
- `statpy_monitoring_thresholds.xlsm` – PD / CRR-master-scale / RAG-assignment /
  LGD / Loss / scenario-test threshold tables.
- `dummy_mev_data.xlsx` – the MEV catalog (descriptions, time series, model
  characteristics) used by the PD MEV Range section and the SAAS workspace.

Each dashboard's `data_access.py` reads its source once at import time (through
its `services` layer) and exposes the in-memory payload.

## Design notes

- **Shared business logic lives in `shared/domain/`.** The PD calculation engine
  is consumed by the shared `shared/ui` layer *and* by the SAAS dashboard, so by
  the "rule of two" it belongs in a shared location rather than inside one
  feature. Monitoring-only logic lives in `features/monitoring/domain/`.
- **URL paths are declarative** – defined on the page registry, so changing the
  scheme is a one-place edit.
- **The custom registry is the single source of truth for routing.** Dash's
  built-in `use_pages` is intentionally not enabled.

## PD Performance page

The PD Performance page is read-only until the user clicks **Apply filters** (a
getting-started guide is shown first). Once applied it renders two chapters:

- **Chapter 1 – RAG Assignment**
  - 1.1 Overview – the RAG-assignment process-flow diagram (Calibration /
    Discrimination / Balance-Sheet RAGs feeding the overall Performance PD RAG).
  - 1.2 ECL PIT PD – Calibration Conservatism (CI test, notching, default-rate /
    calibration trends).
  - 1.3 ECL PIT PD – Discriminatory Power (Accuracy Ratio, Gini, KS, Kendall's
    Tau, go-live accuracy + discrimination trends).
  - 1.4 Balance Sheet PD – Calibration Conservatism (the same framework on the
    `nco_1y` horizon).
- **Chapter 2 – Post Subjective Review Analysis**
  - 2.1 Overview – a "review scorecard" summarising every Chapter-2 test.
  - 2.2 Transition Matrix – MM_P0 vs MM_Pm migration + RAG-rated delta.
  - 2.3 PSI – population stability trend.
  - 2.4 Scenario Ranking – projected-PD ordering by scenario severity.
  - 2.5 Sensitivity Analysis – baseline vs 2SD-shock PD + relative shock impact.
  - 2.6 MEV Range – per-model MEV development-range monitoring.

### Interaction model

Filter state lives in the global filter controls plus `dcc.Store`s
(`pd-applied-filters-store`, `pd-range-store`, `pd-trend-horizon-store`,
`pd-mev-filter-store`, `pd-scenario-ranking-store`). Clicking **Apply filters**
snapshots the top-bar selections into `pd-applied-filters-store`; a single master
callback then re-runs the content render whenever the applied filters or any
per-chart store changes. Section builders are pure functions of that state.

- **Reporting Cycle / Scenario / Monitoring Point** drive which precomputed
  metrics and projection quarters are shown.
- **Segment vs Specific Model** are mutually exclusive (single-select); leaving
  both at "All" reads the portfolio-level (`All Models`) metrics.
- **Per-chart range controls** (`Window / From / To`) window a chart's history
  via a `range_key` entry in `pd-range-store`; **trend horizon** controls share
  one entry per section in `pd-trend-horizon-store`.
- **MEV Range filters** (`pd-mev-filter-store`) pick which model's MEV panels and
  which MEVs are shown.

## Styling & client-side assets

Files in `assets/` are auto-loaded by Dash.

- `styles.css` – the app stylesheet (cards, RAG tones, flow diagram, fonts).
- `js/monitoring_pd_subnav.js`, `js/saas_workspace_subnav.js` – section
  sub-navigation (smooth-scroll + active-link highlighting) for the PD page
  (`#pd-subnav`) and the SAAS workspace (`#saas-subnav`).
- `js/html2pdf.bundle.min.js` – client-side PDF export of the chart canvas.

These are plain `.js` files (not callbacks) because they are purely
presentational; Dash loads `assets/` (including subfolders) automatically.
