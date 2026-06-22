# SAAS dashboard

Scenario / MEV workspace for inspecting macroeconomic-variable (MEV) time
series and projections per model.

## Purpose
Let users explore MEV time series, scenario comparisons, monitoring bands and
projections for SAAS models, with Excel/report exports.

## Routes
| Page      | Path     | Status |
|-----------|----------|--------|
| Workspace | `/saas`  | Live   |

## Owned pages
`pages/workspace/` – `page.py` (layout, filters, inline stores) and
`callbacks.py` (filters, charts, exports, theme sync).

## Data sources
- `source_data/dummy_mev_data.xlsx` – transformed/raw MEV descriptions, MEV
  time series, model characteristics.

Loading is in `data/saas/loader.py`; the payload is exposed once via
`data_access.SAAS_PAGE_DATA`. The model-name filter falls back to the
monitoring PD MEV catalog keys when the workbook can't be read (best effort).

## Shared dependencies
- `components/charts.py` – SAAS chart builders (`build_saas_mev_time_series_figure`,
  scenario maps, monitoring-band spec) and `components/filters.py` widgets.
- `data/analytics/` – `format_pd_mev_value`, numeric/range helpers reused here.
- `shared/theme.py` – theme id/options (the workspace syncs its charts to the
  active theme).

## How to add a page
1. Create `pages/<page>/page.py` (no-arg layout builder) and
   `pages/<page>/callbacks.py` with an idempotent
   `register_callbacks(app)` guarded by
   `already_registered(app, "page:saas.<page>")`.
2. Add a `PageDefinition` to `page_registry.py`.
3. Add a smoke test under `tests/features/saas/pages/`.

## How to add exports
Export callbacks live in `pages/workspace/callbacks.py` (Excel / projection /
recon / report downloads). New exports follow the same `dcc.Download` pattern.

## Conventions
- `register_callbacks(app)` is idempotent (see `shared.registration`).
- The workspace keeps its `dcc.Store`s inline in `page.py` (only needed while
  the page is mounted), so `stores.build_stores()` returns `[]`.
