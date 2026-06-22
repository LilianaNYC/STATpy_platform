# Monitoring dashboard

Wholesale Portfolio **Model Monitoring** dashboard (PD / LGD / EAD performance).

## Purpose
Surface model-monitoring metrics for the wholesale credit portfolio: PD
performance (calibration, discrimination, MEV ranges, scenario rank-ordering)
plus placeholders for the upcoming LGD and EAD performance pages.

## Routes
| Page            | Path                | Status      |
|-----------------|---------------------|-------------|
| PD Performance  | `/`                 | Live        |
| LGD Performance | `/lgd-performance`  | Placeholder |
| EAD Performance | `/ead-performance`  | Placeholder |

The PD Performance page is the application's root (`/`) landing page.

## Owned pages
`pages/pd_performance/`, `pages/lgd_performance/`, `pages/ead_performance/`.
Each page owns its `page.py` (layout) and `callbacks.py` (interactions). The
PD page also has a page-local `cards.py` (KPI/RAG card builders, used only by
this page).

## Data sources
- `source_data/portfolio.xlsx` – portfolio extract (PD performance observations,
  rating migration).
- `source_data/statpy_monitoring_thresholds.xlsm` – PD / CRR-master-scale /
  RAG-assignment threshold tables.
- `source_data/mev_dummy_data.json` – PD MEV time-series catalog.
- `source_data/facilities_dummy_data.json` – facility-level PD paths for the
  scenario rank-ordering section.

Loading is in `data/monitoring/loader.py`; the loaded payload is exposed once
via `data_access.PD_PERFORMANCE_DATA`.

## Shared dependencies
- `data/analytics/` – PD calculation engine (`calculations`, `mev_range`,
  `rank_ordering`) and domain `constants`. Shared because the SAAS dashboard
  and the shared `components/` layer also use parts of it.
- `components/charts.py`, `components/filters.py` – shared chart/filter builders.
- `config/settings.py` – source-data file locations.
- `shared/` – registry types, theme constants, idempotent-registration helper.

## How to add a page
1. Create `pages/<page>/page.py` with a no-arg layout builder (`page_layout()`
   or `build_layout()`).
2. Create `pages/<page>/callbacks.py` with
   `def register_callbacks(app): ...`, guarded by
   `already_registered(app, "page:monitoring.<page>")` (see Conventions).
3. Add a `PageDefinition` to `page_registry.py`.
4. Add at least one smoke test under `tests/features/monitoring/pages/`.

## How to add exports
Export/report generation for a page lives in that page's folder (e.g. an
`exports.py`), invoked from its `callbacks.py`. The SAAS workspace's
download/export callbacks are the current reference implementation.

## Conventions
- Every `register_callbacks(app)` is **idempotent** via
  `shared.registration.already_registered(app, key)` so it is safe to call more
  than once.
- Dashboard-level stores are surfaced from `stores.py` (currently all owned by
  the PD page). They are rendered once in the shell so filter/range state
  survives navigation.
- Prefer page-local ids/constants; promote to `shared/` or `components/` only
  once a second page/dashboard needs them ("rule of two").
