# Monitoring dashboard

Wholesale Portfolio **Model Monitoring** dashboard (PD / LGD / EAD / Loss
performance).

## Purpose
Surface model-monitoring metrics for the wholesale credit portfolio:
PD/LGD/EAD/Loss calibration, discriminatory power, population stability, and the
post-subjective-review analysis (transition matrix, scenario ranking,
sensitivity, MEV range). Every metric is read **precomputed** from the source
workbook — the app does not recompute from facility data.

## Routes
| Page             | Path                 | Status |
|------------------|----------------------|--------|
| Overview         | `/overview`          | Live   |
| PD Performance   | `/`                  | Live   |
| LGD Performance  | `/lgd-performance`   | Live   |
| EAD Performance  | `/ead-performance`   | Live   |
| Loss Performance | `/loss-performance`  | Live   |

PD Performance is the application's root (`/`) landing page.

## Architecture

The feature follows a layered structure (UI → callbacks → services → domain,
over the shared data layer). Each layer has one responsibility and only depends
on the layers beneath it.

```
features/monitoring/
├── page_registry.py     Page list: maps each page to its layout + callbacks
├── dashboard.py         Dashboard metadata + callback-registration entrypoint
├── data_access.py       Cached in-memory snapshot (PD_PERFORMANCE_DATA) bridge
├── stores.py            Dashboard-level dcc.Store interface (surfaced from PD)
│
├── ui/                  Dash page composition ONLY (no SQL / no calculations)
│   ├── pages/           Thin per-page registration entrypoints (build_layout)
│   │   ├── overview.py · pd_performance.py · lgd_performance.py
│   │   └── ead_performance.py · loss_performance.py
│   ├── views/           Visual structure: cards, tables, charts, section builders
│   │   ├── overview.py · pd_performance.py · lgd_performance.py
│   │   ├── ead_performance.py · loss_performance.py
│   │   └── cards.py     Reusable RAG / test / KPI card builders
│   └── common.py        Shared filter-dropdown shell helpers (single/checkbox)
│
├── callbacks/           Glue between UI events and the data/domain layers
│   ├── overview.py · pd_performance.py · lgd_performance.py
│   └── ead_performance.py · loss_performance.py
│
├── services/            Application orchestration
│   └── data_service.py  Loads + enriches the snapshot (run meta, polars frame)
│
├── domain/              Monitoring-only business logic (framework-agnostic)
│   ├── lgd.py · ead.py · loss.py   Per-product metric assembly + RAG scoring
│   └── overview.py                 Overview RAG roll-up + filter options
│
└── tests/               Layout/registration/structure smoke tests for this feature
```

### What each layer is for
- **`ui/`** — Dash composition only. `ui/pages/<page>.py` is the registration
  boundary the registry imports (just exposes `build_layout` / `page_layout`);
  `ui/views/<page>.py` builds the actual layout (filters, cards, charts, IDs for
  callbacks). No SQL, no calculations.
- **`callbacks/`** — one module per page, each with an idempotent
  `register_callbacks(app)`. Reads user selections, calls the data/domain layers,
  and maps results back into the view. No heavy logic here.
- **`services/`** — orchestration / use-case layer.
  `data_service.load_monitoring_data()` pulls the source snapshot via the shared
  loader, attaches run metadata, and normalizes the portfolio frame;
  `data_access` caches its result.
- **`domain/`** — pure monitoring business logic (LGD/EAD/Loss metric assembly,
  overview RAG roll-up). No Dash imports.
- **`tests/`** — feature-local pytest suite (collected with the rest via `pytest`).

## Shared layer (not owned by this feature)
The **repository** and shared UI/domain code lives outside the feature because
the SAAS dashboard and the `components/` layer reuse parts of it:

- `data/monitoring/loader.py` — reads the workbook tabs into the precomputed
  metric stores (the repository). `data/monitoring/filters_config.py` — the
  `Filters` config sheet (cycles, scenarios, segments, models).
- `data/analytics/` — shared calculation engine: `calculations`, `mev_range`,
  `rank_ordering`, and domain `constants` (RAG colours, threshold helpers).
- `components/charts.py`, `components/filters.py`, `components/kpis.py` — shared
  chart / filter / KPI builders.
- `config/settings.py` — source-data file locations.
- `shared/` — registry types, theme constants, idempotent-registration helper.

## Data sources
- `source_data/portfolio.xlsx` — precomputed metric tabs
  (`PD/LGD/EAD/Loss_Performance_Metrics`), the `Filters` config sheet, and
  `PD_Sensitivity_Projections` (with `MM_P0` / `MM_Pm` margins).
- `source_data/statpy_monitoring_thresholds.xlsm` — PD / CRR-master-scale /
  RAG-assignment / LGD / Loss / scenario-test threshold tables.
- `source_data/dummy_mev_data.xlsx` — the MEV time-series catalog (MEV Range).

Loading happens in `data/monitoring/loader.py`; the enriched payload is exposed
once via `services.data_service` → `data_access.PD_PERFORMANCE_DATA`.

## How to add a page
1. `ui/views/<page>.py` — build the layout (filters, cards, charts, callback IDs).
2. `ui/pages/<page>.py` — thin entrypoint re-exporting `build_layout` /
   `page_layout` from the view.
3. `callbacks/<page>.py` — `def register_callbacks(app): ...`, guarded by
   `already_registered(app, "page:monitoring.<page>")`.
4. Page-only business logic → `domain/`; data orchestration → `services/`.
5. Register the page in `page_registry.py`.
6. Add a smoke test under `tests/`.

## Conventions
- Every `register_callbacks(app)` is **idempotent** via
  `shared.registration.already_registered(app, key)`.
- Dashboard-level stores are surfaced from `stores.py` (currently all owned by
  the PD page) and rendered once in the shell so filter/range state survives
  navigation.
- Shared code lives in `data/` and `components/`; promote feature-local code
  there only once a second page/dashboard needs it ("rule of two").
