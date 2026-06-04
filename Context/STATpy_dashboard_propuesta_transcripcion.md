# STATpy — Propuesta: What to Build Next (Dashboard)

## Recommended Approach: Extend the Existing Dash App

The cleanest integration is to add a new page + callbacks inside the existing STATpy structure, rather than building a separate application. STATpy already uses `use_pages=True`, so adding a page is zero-friction.

### Why not a separate app?

- The LocalDB (`(LocalDB)\STAT_UAT`) is a **local single-user instance** — concurrent connections from a second process are unreliable.
- MLflow is already connected; reusing the same process avoids double-initialization.
- The sidebar is already the navigation pattern — adding a new section is trivial.

---

## Stack

| Concern | Choice | Reason |
|---|---|---|
| Charting | **Plotly Express + Graph Objects** | Already in the project via Dash; no new dependencies |
| Data grid / tables | `dash_ag_grid` | Best-in-class for large tabular SQL results; sorting, filtering, export to CSV built-in |
| Multi-select filters | `dcc.Dropdown` (multi=True) | Already used everywhere in the app |
| Date/period selectors | `dcc.Dropdown` against `run_for` from `STAT_Config` | Consistent with existing UI pattern |
| Caching | `flask_caching` with `FileSystemCache` | Queries against LocalDB can be slow for aggregates; cache by `(run_for, scenario)` key |
| Export | `dcc.Download` + `pandas.to_excel()` | Already pattern-matched elsewhere in the app |
| Layout | `dash_bootstrap_components` (already present) | No new dependency |

---

## Architecture

```
sidebar.py                      ← add "Dashboard" section with new links
pages/
    dashboard_loss_page.py       ← new page: /dashboard-loss
    dashboard_pd_page.py         ← new page: /dashboard-pd (optional)
callbacks/
    dashboard_callbacks.py       ← all dashboard callbacks
config/
    dashboard_config.py          ← chart definitions, color maps per segment
```

---

## Dashboard Page Structure

### Filters (top bar — stateless dropdowns)

```
Run For | Scenario (dynamic) | Portfolio | Loss Model (NCO/ACL) | Segment (multi)
```

All driven by the exact same callback pattern as `update_loss_scenario_options` already in `loss_calculations_callbacks.py`.

### Charts (driven by SQL queries on `results.*` tables)

| Chart | SQL Source | Chart Type |
|---|---|---|
| Loss over projection quarters | `results.loss` grouped by quarter | Line (one line per segment) |
| PD term structure | `results.pd` / `results.pd_crr` | Line with ribbon (base ± stress) |
| EAD balance run-off | `results.ead` | Stacked area |
| LGD heatmap by CRR grade | `results.lgd` JOIN `input.Jumpoff_ALLL` | Heatmap |
| Loss by segment (waterfall) | `results.loss` | Horizontal bar / waterfall |
| ACL vs NCO comparison | both result tables | Grouped bar |

### Data grid

A full `dash_ag_grid` table at the bottom showing facility-level results, filterable and exportable.

---

## Caching Strategy

```python
from flask_caching import Cache

cache = Cache(app.server, config={
    'CACHE_TYPE': 'FileSystemCache',
    'CACHE_DIR': 'cache',
    'CACHE_DEFAULT_TIMEOUT': 300
})

@cache.memoize()
def get_loss_results(run_for, scenario, portfolio, loss_model):
    engine = jo_data_manager.create_database_engine_silent(db_name)
    return pd.read_sql_query(query, engine.connect())
```

Cache key is `(run_for, scenario, portfolio, loss_model)` — invalidate on new Loss Calculation run by calling `cache.delete_memoized(get_loss_results, ...)` at the end of `execute_loss_methodology`.

---

## Callback Pattern

All dashboard callbacks follow a single **"read-only from SQL → render chart"** pattern with no side effects — unlike the simulation callbacks which write to SQL. This keeps the dashboard completely safe to use while a simulation is running.

```python
@callback(
    Output("dashboard-loss-chart", "figure"),
    Input("dashboard-run-for", "value"),
    Input("dashboard-scenario", "value"),
    Input("dashboard-segment", "value"),
    Input("dashboard-loss-model", "value"),
    prevent_initial_call=True
)
def update_loss_chart(run_for, scenario, segments, loss_model):
    df = get_loss_results(run_for, scenario, ...)   # cached
    fig = px.line(df[df["Segment Name"].isin(segments)],
                  x="Quarter", y="Loss", color="Segment Name")
    return fig
```

---

## Sidebar Addition

```python
html.Details([
    html.Summary('Dashboard'),
    html.Div([
        dcc.Link('Loss Dashboard', href='/dashboard-loss', className='sidebar-sub-link-1'),
        dcc.Link('PD/EAD/LGD Trends', href='/dashboard-projections', className='sidebar-sub-link-1'),
    ])
], className='sidebar-group'),
```

---

## What to Avoid

- **Separate Streamlit/Gradio app** — would require a second DB connection to the same LocalDB instance, which is fragile.
- **Power BI / Tableau embedded** — overkill given results are already in Python/SQL; adds a heavy external dependency.
- **Client-side callbacks for data fetching** — the result tables are too large; keep all SQL on the server side.
- **Polars for dashboard queries** — stick to pandas here since `read_sql_query` integration is already established and result sets are display-sized.
