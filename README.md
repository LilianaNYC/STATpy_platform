# STATpy Dashboards (multi-dashboard Dash app)

A [Dash](https://dash.plotly.com/) app organised by **dashboard → layered
feature**. Two dashboards are wired up today:

- **Monitoring** – Wholesale Portfolio model monitoring (Overview, **PD**, LGD,
  EAD and Loss Performance). All pages are live and read precomputed metrics
  from the source workbook.
- **SAAS** – a scenario / MEV workspace (MEV time series, projections, monitoring
  bands, Excel/report exports).

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
`/lgd-performance`, `/ead-performance`, `/loss-performance` and `/saas`.

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

Every feature follows the same **layered** structure. Each layer has one
responsibility and only depends on the layers beneath it:

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

  tests/                  # repo-level app/registry/shell + shared-domain tests
  assets/                 # styles.css, js/ subnav scripts, fonts/ (auto-loaded by Dash)
  source_data/            # bundled Excel inputs
```

## Data sources

Source data lives in `source_data/`, bundled with the app. File *locations* are
resolved in `config/settings.py`; data-domain constants (column/sheet names, RAG
bands) live in `shared/domain/constants.py`.

- `portfolio.xlsx` – what was **measured**: the monitoring metric sheets
  (`PD/LGD/EAD/Loss_Performance_Metrics`) and the sensitivity projections
  (`PD/LGD/EAD_Sensitivity_Projections`, carrying the `MM_P0` / `MM_Pm`
  transition margins). There is no longer a `Filters` config sheet — every
  option list is derived from the data.
- `monitoring_rules.xlsx` – PD / CRR-master-scale / RAG-assignment /
  LGD / Loss / scenario-test threshold tables, plus the governance action
  playbook (`monitoring_actions` sheet): one required-action row per stage/RAG,
  surfaced in the Conclusion's Required Actions panel and keyed off the
  review-flow RAGs.
- `dummy_mev_data.xlsx` – what the models **are**: the MEV catalog
  (`model_names` characteristics, `mev_transformed` / `mev_raw` descriptions,
  `scenario` time series), used by the PD MEV Range section and by the whole
  SAAS workspace.

Each dashboard's `data_access.py` reads its source once at import time (through
its `services` layer) and exposes the in-memory payload.

### The Excel → SQL seam

Every read goes through `shared/repositories/tables.py`, where each table is
registered with **both** its workbook coordinates (today) and its production SQL
coordinates. Because all ~17 call sites funnel through `read_table()`, switching
the backend is a change to that one module — uncomment `_read_sql_table`, point
`_read` at it. Never add a `pd.read_excel` to a loader; register the table
instead, or the switch has to go find it.

Production has two shapes:

| Shape | Tables | Address |
|---|---|---|
| Flat | MEV / model configuration | `STAT_Config` · `[dbo].[model_names]`, `[dbo].[mev_raw]`, … |
| Per reporting cycle | scenario time series | `STAT_Inputs_<Run For>_BHC` · `[input].[scenario]` |
| Per reporting cycle | **every portfolio table** | `STAT_Outputs_<Run For>_BHC` · `[output].[pd_performance_metrics]`, … |

The per-cycle tables are split across one database per active `Run For`
(`run_details.Status == "Y"`), while the bundled workbooks keep every cycle in
one sheet. `read_table` fans out and concatenates, so callers above the seam get
the same all-cycles frame either way and never learn which backend is live — and
one cycle's database being unreachable degrades to a warning plus the remaining
cycles, not a blank dashboard. A table is marked per-cycle by the `{run_for}`
placeholder in its `sql_database` (`Table.is_per_cycle`).

Two details that are easy to get wrong:

- **Portfolio object names are lowercase snake_case**, so unlike the MEV tables
  the logical key is *not* the production table name
  (`PD_Performance_Metrics` → `[output].[pd_performance_metrics]`). The real
  spelling lives in `sql_object`; nothing should re-derive it from the key.
- A per-cycle table need not carry `Run For` as a column — the cycle is implied
  by which database the rows came from — but everything above the seam keys on
  it (`normalize_portfolio_columns` turns it into `reporting_cycle`, the join
  key behind every store, figure and export). The fan-out stamps it back on.

The SQL reader is kept **commented and inert**: it cannot run, so it cannot
fail, and the registered coordinates stay plain data until someone deliberately
turns the backend on. `tests/test_tables_source.py` pins the coordinates and
parses the commented block, so it cannot rot unnoticed.

The thresholds in `monitoring_rules.xlsx` have no SQL coordinates: they are
config rather than run output and are expected to stay file-based.

### Where each filter's values come from

No option list is hand-maintained; every one is derived from a workbook. The two
files split along a clean line — `portfolio.xlsx` holds what was *measured*,
`dummy_mev_data.xlsx` holds what the models *are* — which is why a filter about
a model's attributes reads the MEV file even on a monitoring tab.

**Monitoring** (Overview, PD, LGD, EAD, Loss):

| Filter | File | Sheet · column | How |
|---|---|---|---|
| Region | MEV | `model_names` · `Region` | via `mev_catalog`, narrowed to the tab's models |
| Portfolio | MEV | `model_names` · `Portfolio` | same, then narrowed by Region |
| Model Use Case | portfolio | `*_Performance_Metrics` · `Run For` | derived — leading token (`CCAR 2026` → `CCAR`) |
| Reporting Cycle | portfolio | `*_Performance_Metrics` · `Run For` | derived — text after the space (→ `2026`) |
| **Model** | portfolio **+** MEV | `*_Performance_Metrics` · `Model` → `model_names` · `Model Descriptive Name` | the sheet stores the code (`PD_model_a`); the read seam resolves it to `PD Model A` |
| Segment | portfolio | `*_Performance_Metrics` · `Segment` | |
| Monitoring Point | portfolio | `*_Performance_Metrics` · `monitoring_point` (PD) / `Quarter` (others) | PD's `Quarter` is the cohort start, not the as-of |
| Scenario | MEV | `scenario` · `Scenario` | defaults to `intsevere` (`filters_config.default_scenario()`); **not in the bar** on PD/LGD/EAD — it lives in the 2.5 MEV Range section's own display filters, narrowed to the applied cycle; Loss keeps the bar control |
| Model Group *(Overview only)* | **hardcoded** | `overview.MODEL_GROUPS` | the tab taxonomy, `["PD", "LGD", "EAD", "Loss"]` |

**SAAS**:

| Filter | File | Sheet · column | How |
|---|---|---|---|
| Region | MEV | `model_names` · `Region` | |
| Portfolio | MEV | `model_names` · `Portfolio` | |
| Model Use Case | MEV | `scenario` · `Run For` | derived, same helper as monitoring |
| Reporting Cycle | MEV | `scenario` · `Run For` | derived |
| Model Group | MEV | `model_names` · `Model Type` | |
| Model | MEV | `mev_transformed` · `Model Name` → `model_names` · `Model Descriptive Name` | deduplicated by descriptive name |
| Segment | MEV | `model_names` · `Segment Name` | |
| Compare To | MEV | derived from the cycle list | excludes the currently selected cycle |
| Snapshot Period, Reference Lines, MEV Label, Historical Statistics | **hardcoded** | view constants | mode selectors, not data values |

Three consequences worth knowing:

- **SAAS never reads `portfolio.xlsx`.** Every value it offers comes from the MEV
  workbook, which is why its Model list can show models the monitoring tabs do
  not — a different file, not a bug.
- **The two dashboards take cycles from different sheets** —
  `*_Performance_Metrics.Run For` versus `scenario.Run For`. They agree only
  because both workbooks happen to carry the same cycles; SAAS has no CECL data,
  so its Model Use Case filter shows only `CCAR`.
- **Monitoring's Region and Portfolio come from the MEV workbook**, so a model's
  attributes live in a different file from its metrics. That is why trimming the
  PD metrics sheet to two models silently reduced the Region filter to one value:
  the regions are read from `model_names`, then narrowed to the models that
  survive in `portfolio.xlsx`.

The only hardcoded option lists left are the two marked above: Overview's Model
Group (the tab taxonomy, matching the sidebar and the loss-decomposition order)
and SAAS's four mode selectors, whose order carries meaning that sorting would
destroy. No model, cycle, region, portfolio, segment or quarter is hardcoded
anywhere.

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

- **Model Use Case / Reporting Cycle / Monitoring Point** drive which
  precomputed metrics and projection quarters are shown. **Scenario** is not one
  of them on PD/LGD/EAD: it moved into the 2.5 MEV Range section, the only
  section it affected, and so re-renders without Apply. These were once a single
  combined "Model Use Case / Cycle" control; the filter bar's full order, the
  cascade between the filters, and the rule that keeps it free of Dash dependency
  cycles are documented in
  [`features/monitoring/README.md`](features/monitoring/README.md#top-filter-bar).
- **Segment vs Specific Model** are mutually exclusive (single-select); leaving
  the model unselected lets you drill into a segment instead, and leaving both
  unselected defaults PD to the first available model.
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
