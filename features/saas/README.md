# SAAS dashboard

Scenario / MEV workspace for inspecting macroeconomic-variable (MEV) time
series and projections per model.

## Purpose
Let users explore MEV time series, scenario comparisons, monitoring bands and
projections for SAAS models, across reporting cycles, with Excel/report exports.

## Routes
| Page      | Path     | Status |
|-----------|----------|--------|
| Workspace | `/saas`  | Live   |

## Architecture

The feature follows the same layered structure as the monitoring dashboard
(UI → callbacks → services → domain, over the shared data layer). The dashboard
has a single page (Workspace), so each layer holds one workspace module.

```
features/saas/
├── page_registry.py     Page list: maps Workspace to its layout + callbacks
├── dashboard.py         Dashboard metadata + callback-registration entrypoint
├── data_access.py       Cached in-memory snapshot (SAAS_PAGE_DATA) bridge
├── stores.py            Dashboard-level dcc.Store hook (returns [] — see below)
│
├── ui/                  Dash page composition ONLY (no calculations / no I/O)
│   ├── pages/
│   │   └── workspace.py     Thin registration entrypoint (page_layout)
│   └── views/
│       ├── workspace.py     Page layout: top-bar filters, inline stores, canvas
│       ├── components.py    Reusable view blocks (model panels, tables, chips)
│       └── figures.py       Plotly figure builders for the on-screen charts
│
├── callbacks/
│   └── workspace.py     Filters, charts, theme sync, and export/download wiring
│
├── services/            Application orchestration (report/export generation)
│   ├── exports.py       Excel workbook builders (historical range, recon, …)
│   └── reports.py       Report figure orchestration for the chart export
│
├── domain/              SAAS business logic (framework-agnostic)
│   ├── selectors.py     Resolve filter selections → scoped model/MEV sets
│   ├── records.py       Shape MEV records (history / projection) for a scope
│   └── metrics.py       History stats, breach tests, projection summaries
│
└── tests/               Workspace layout / selector / metric / export tests
```

### What each layer is for
- **`ui/`** — Dash composition only. `ui/pages/workspace.py` is the registration
  boundary the registry imports; `ui/views/workspace.py` builds the layout and
  delegates reusable blocks to `components.py` and charts to `figures.py`.
- **`callbacks/workspace.py`** — idempotent `register_callbacks(app)`: parses the
  top-bar filters, calls `domain`/`services`, and renders the model panels,
  charts and downloads.
- **`services/`** — orchestration for the heavy outputs: `exports.py` builds the
  Excel workbooks (openpyxl), `reports.py` assembles the chart-export figures.
- **`domain/`** — pure data logic over `SAAS_PAGE_DATA`: `selectors` (scope
  resolution), `records` (record shaping), `metrics` (statistics / breach tests).
  No Dash imports.
- **`tests/`** — feature-local pytest suite.

## Shared layer (not owned by this feature)
This feature owns its repository (`repositories/loader.py`), but reuses shared
UI/domain code:

- `repositories/loader.py` — reads the MEV workbook into `SAAS_PAGE_DATA` (the
  repository); falls back to the monitoring PD MEV catalog keys when the
  workbook can't be read (best effort).
- `shared/ui/charts.py` — shared SAAS chart builders
  (`build_saas_mev_time_series_figure`, scenario maps, monitoring-band spec).
- `shared/domain/` — numeric/range helpers reused here (e.g. `is_finite_number`,
  `format_pd_mev_value`).
- `shared/theme.py` — theme id/options (the workspace syncs its charts to the
  active theme).

## Data sources
- `source_data/dummy_mev_data.xlsx` — transformed/raw MEV descriptions, MEV time
  series, and model characteristics.

Loading happens in `repositories/loader.py`; the payload is exposed once via
`data_access.SAAS_PAGE_DATA`.

## How to add a page
1. `ui/views/<page>.py` (+ optional `components.py` / `figures.py`) for the layout.
2. `ui/pages/<page>.py` — thin entrypoint re-exporting the layout builder.
3. `callbacks/<page>.py` — idempotent `register_callbacks(app)` guarded by
   `already_registered(app, "page:saas.<page>")`.
4. Page-only logic → `domain/`; report/export generation → `services/`.
5. Register the page in `page_registry.py`; add a test under `tests/`.

## Conventions
- `register_callbacks(app)` is idempotent (see `shared.registration`).
- The workspace keeps its `dcc.Store`s inline in `ui/views/workspace.py` (only
  needed while the page is mounted), so `stores.build_stores()` returns `[]`.
- New exports follow the existing `dcc.Download` pattern in
  `callbacks/workspace.py`, delegating the heavy build to `services/`.
