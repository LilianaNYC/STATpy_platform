# SAAS dashboard

Scenario / MEV workspace for inspecting macroeconomic-variable (MEV) time
series and projections per model.

## Purpose
Let users explore MEV time series, scenario comparisons, monitoring bands and
projections for SAAS models, across model use case / cycles, with Excel/report exports.

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

## Top filter bar

Three captioned rows, mirroring the monitoring tabs' Scope/Focus split with a
third row SAAS alone needs:

| Row | Controls |
|---|---|
| **Scope** | Region · Portfolio · Model Use Case · Reporting Cycle |
| **Focus** | Model Group · Model · Segment |
| **View** | Compare To · Snapshot Period · Reference Lines · MEV Label · Historical Statistics · Expand all → **Apply filters** |

Three rows rather than two because SAAS carries 11 controls to a monitoring
tab's 8, and because its presentation controls are neither scope nor focus.
Apply closes the last row, as on the monitoring tabs; it used to sit mid-bar at
the end of row 1.

The Scope row is the same four filters as every monitoring tab, which required
splitting the old combined **Model Use Case / Cycle** control. As there,
`RUN_FOR_ID` keeps its id and its **composite value** (`"CCAR 2026"`) — the
join key behind the applied store, Compare To and every export — and only its
label becomes the bare cycle. Both halves are derived from `model_names`, which
carries `Run For`, `Model Use Case` and `Reporting Cycle`, so the workbook stays
authoritative rather than the composite being split on a space.

**Only the Scope row opens unanswered**, behind `Select …` placeholders, and
Apply is gated on those four alone. Focus and View keep their defaults: an
all-models run is a normal SAAS analysis, and MEV Label is presentation, so
requiring them would be friction with no analytic meaning. `"All"` therefore
survives as a *real* answer on Region/Portfolio, distinct from the unanswered
placeholder — unlike the monitoring tabs, which have no `"All"` at all.

Scope and Focus both cascade left to right (Region → Portfolio → Model Use Case
→ Reporting Cycle, and Model Group → Model → Segment) and carry the cascade
chevrons. The View row does not.

Sizing note: every track is computed against **1032px**, not the 1216px the
monitoring tabs get — the Export panel shares SAAS's line. The row templates are
defined *after* `.saas-secondary-filter-row` on purpose, because the View row
carries that class too and an equally specific rule later in the file wins.

## Where the filter values come from

SAAS reads **only** `dummy_mev_data.xlsx` — it never touches `portfolio.xlsx`.
That is why its Model list can show models the monitoring tabs do not, and why
its Model Use Case filter offers only the cycles present in `scenario`.

| Filter | Sheet · column |
|---|---|
| Region, Portfolio, Segment, Model Group | `model_names` · `Region` / `Portfolio` / `Segment Name` / `Model Type` |
| Model | `mev_transformed` · `Model Name`, resolved to `model_names` · `Model Descriptive Name` and deduplicated by it |
| Model Use Case, Reporting Cycle | `scenario` · `Run For`, derived — see below |
| Compare To | the cycle list, minus the selected cycle |
| Snapshot Period, Reference Lines, MEV Label, Historical Statistics | hardcoded view constants: these are modes, not data |

Both parts of the cycle are derived from `Run For` through
`shared.domain.reporting_cycle.split_run_for`, the same helper the monitoring
tabs use, so the two dashboards cannot disagree about what a cycle is called.

The full cross-dashboard table is in the root `README.md`.

## Filter option ordering

The bar follows the same rule as the monitoring tabs (see
`features/monitoring/README.md`, "Option ordering"): text values A–Z, cycles
most-recent-first, "All"/"None" pinned at the head.

The **mode selectors are exempt** — Snapshot Period, Reference Lines, MEV Label
and Historical Statistics list modes, not data values, and their order is part
of their meaning ("History → Projection → History & Projection", "Off → On").

One behavioural consequence: `DEFAULT_RUN_FOR_VALUE` is `RUN_FOR_OPTIONS[0]`, so
ordering the cycles decides which one the page opens on. It used to be the
workbook's first row, which was the *oldest* cycle; it is now the most recent.
