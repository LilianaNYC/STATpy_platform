# Wholesale Portfolio Model Monitoring Dashboard (standalone, multi-page)

A standalone [Dash](https://dash.plotly.com/) multi-page app. The **PD
Performance** page is a full port of the **PD Performance** tab from
`pages/monitoring_pd_models_page.py` (the original monolithic JS-in-Python
monitoring dashboard): it loads the same source data files directly and
reproduces the tab's calculations, layout, charts and interactivity using
Dash callbacks instead of hand-written JavaScript. **LGD Performance** and
**EAD Performance** are placeholder pages with no data source yet, ready to
be filled in following the same per-page structure.

## Running the app

This app is self-contained - it can be run from inside the
`pd_performance_dash/` folder regardless of where that folder lives on disk.

```bash
pip install -r requirements.txt
python -m pd_performance_dash.app
```

(or, from the parent directory: `python -m pd_performance_dash.app`, after
`pip install -r pd_performance_dash/requirements.txt`)

This starts a Dash dev server (default `http://127.0.0.1:8050`). The sidebar
links navigate between `/` (PD Performance), `/lgd-performance` and
`/ead-performance`.

## Data sources

Source data lives in `pd_performance_dash/source_data/` (see
`monitoring_config.py`), bundled with the app so it works regardless of where
the `pd_performance_dash/` folder is moved:

- `portfolio.xlsx` (sheet `Portfolio`) - facility-level portfolio extract
- `statpy_monitoring_thresholds.xlsm` (sheets `PD_Thresholds`,
  `CRR_Master_Scale`, `RAG_Assignment_PD`) - calibration/discrimination
  thresholds, master-scale PDs, and RAG bands
- `mev_dummy_data.json` - macroeconomic-variable scenario catalog
- `facilities_dummy_data.json` - facility-level scenario rank-ordering paths

`load_pd_performance_data()` re-reads these files from `source_data/` on app
startup.

## Project layout

```
pd_performance_dash/
  app.py                  # entry point (create_app / app / server): builds the
                            # shell, registers each page's callbacks + the router
  shell.py                # sidebar nav, page footer, URL routing between pages
  data_store.py           # module-level data singletons shared across pages
                            # (PD_PERFORMANCE_DATA, loaded once at import time)
  monitoring_config.py    # paths, column names, RAG groups, thresholds, etc.
  pages/
    monitoring_pd_performance_layout.py   # page layout + the master content-rendering function
    monitoring_lgd_performance_layout.py  # placeholder page layout
    monitoring_ead_performance_layout.py  # placeholder page layout
  callbacks/
    monitoring_pd_performance_callbacks.py   # all PD Performance callbacks (filters, ranges, MEV, etc.)
    monitoring_lgd_performance_callbacks.py  # placeholder (no callbacks yet)
    monitoring_ead_performance_callbacks.py  # placeholder (no callbacks yet)
  data/
    data_loader.py         # reads portfolio.xlsx / thresholds / MEV / facilities JSON
    transformations.py      # calculation engine (RAG, calibration, discrimination, ...)
    mev.py                  # MEV Range section helpers (catalog, thresholds, RAG)
    rank_ordering.py         # Scenario Rank Ordering helpers + YYYY-Qn quarter utils
  components/
    filters.py              # global filter bar, section sub-nav + per-chart range/horizon controls
    kpis.py                  # RAG/test/EAD/static-info card builders
    charts.py                # Plotly figure builders
  assets/
    styles.css               # stylesheet (auto-loaded by Dash)
    pd_subnav.js             # section sub-nav scroll-sync/jump-link behaviour (auto-loaded by Dash)
  source_data/
    portfolio.xlsx                     # facility-level portfolio extract
    statpy_monitoring_thresholds.xlsm  # PD thresholds, master scale, RAG assignment
    mev_dummy_data.json                # macroeconomic-variable scenario catalog
    facilities_dummy_data.json         # facility-level scenario rank-ordering paths
```

### Multi-page structure

The app is split into three pages under `pages/`, named
`monitoring_<page>_layout.py`, each with a `page_layout()` function returning
that page's top bar + content. Each page's callbacks live in
`callbacks/monitoring_<page>_callbacks.py`, with a
`register_callbacks(app, ...)` function. `shell.py` builds the persistent
chrome (sidebar, page footer, and the PD Performance `dcc.Store`s) and a
small router that swaps `#page-content` based on `dcc.Location.pathname`:

- `/` -> PD Performance (`pages/monitoring_pd_performance_layout.py` /
  `callbacks/monitoring_pd_performance_callbacks.py`) - fully ported,
  see "Coverage" below.
- `/lgd-performance` -> LGD Performance
  (`pages/monitoring_lgd_performance_layout.py` /
  `callbacks/monitoring_lgd_performance_callbacks.py`) - placeholder
  page/card only, no data source yet.
- `/ead-performance` -> EAD Performance
  (`pages/monitoring_ead_performance_layout.py` /
  `callbacks/monitoring_ead_performance_callbacks.py`) - placeholder
  page/card only, no data source yet.

`data_store.py` loads `load_pd_performance_data()` once at import time so
both `pages/monitoring_pd_performance_layout.py` (called on every navigation
to `/`) and `callbacks/monitoring_pd_performance_callbacks.py` share
the same in-memory data without re-reading the source workbook.

## Coverage

The app reproduces the **full PD Performance tab**, i.e. both chapters
rendered by `renderPdModels()`:

- **Chapter 1 - ECL PIT PD Performance**
  - 1.1 Overview (the "RAG Assignment Overview" 5-stage process-flow
    diagram: Calibration / Discrimination / Balance Sheet RAGs feeding the
    overall Performance PD RAG)
  - 1.2 ECL PIT PD - Calibration Conservatism (CI test, Notching test,
    default-rate trends, calibration trend)
  - 1.3 ECL PIT PD - Discrimination Power (Accuracy Ratio, Gini, KS,
    Kendall's Tau, discrimination trend charts)
  - 1.4 ECL PIT PD - Performance vs Actuals (EAD-weighted summary,
    Scenario Rank Ordering, MEV Range charts with model/MEV chart filters)
- **Chapter 2 - Balance Sheet PD Performance**
  - 2.1-2.4 mirror the Chapter 1 sections for the Balance Sheet PD horizon
    (`nco_1y`), where source data is available; sections without data
    render as placeholder cards (matching the original page's behaviour
    when the corresponding JS sections had no live implementation)

The PDF export button from the original page is intentionally **not**
included (out of scope per the porting brief).

## Assumptions and simplifications

This section documents every place where this port deliberately diverges
from, or simplifies, the original `monitoring_pd_models_page.py` /
`monitoring_layout.py` / `monitoring_style.py` behaviour.

### State management

- The original page held global mutable state (`MONITORING_MODELS`,
  `PD_TIME_RANGES`, `PD_CALIBRATION_TREND_HORIZON`, `PD_MEV_FILTER_*`, ...)
  and called `renderPdModels()` after every change. Here that state lives in
  the global filter controls plus three `dcc.Store` components
  (`pd-range-store`, `pd-trend-horizon-store`, `pd-mev-filter-store`), and a
  single master callback re-renders `layout.render_pd_performance_content`
  whenever any filter or store changes.
- **Per-chart range controls** (`buildPdRangeControls`): each chart panel
  that has a "Window / From / To" control uses one of 13 unique
  `range_key`s (`calibration_rag`, `calibration_ci`, `calibration_notching`,
  `calibration_default_rate`, `discrimination_rag`, `discrimination_accuracy`,
  `discrimination_trend`, `balance_sheet_calibration_rag`,
  `balance_sheet_ci`, `balance_sheet_notching`,
  `balance_sheet_default_rate`, `rank_ordering`, `mev`), all stored as
  `{range_key: {"from": ..., "to": ...}}` in `pd-range-store`. The
  Window/From/To preset logic (`getPdRangePreset` / `setPdRangePreset` /
  `setPdRangeBoundary`, including the "swap the other boundary if from >
  to" behaviour) is ported as-is.
- **Trend PD-horizon controls** (calibration trend / discrimination trend
  1y vs 2y selectors): the original page kept one horizon per *section*. Here
  every control that affects the same section shares one entry in
  `pd-trend-horizon-store` via `layout.TREND_HORIZON_GROUPS`
  (`{"calibration_ci": "calibration", "calibration_notching": "calibration",
  "calibration_default_rate": "calibration", "discrimination_trend":
  "discrimination"}`), defaulting to `{"calibration": "1y",
  "discrimination": "1y"}`.
- **"Specific Models" checkbox-dropdown** (`.checkbox-dropdown` /
  `toggleMonitoringModelMenu` / `monitoring-model-toggle` /
  `monitoring-model-menu`): the Models filter is a collapsed
  `pd-models-toggle` button (label computed exactly as in
  `syncMonitoringFilterControls`: `"Select models"` if none are checked,
  `"All models"` if every model is checked, the model's name if exactly one
  is checked, otherwise `"N models selected"`, or `"Disabled while Segment
  is selected"` when a Portfolio Segment is active) that opens/closes a
  `pd-models-menu` dropdown containing the "All" toggle and the per-model
  checkboxes, via `.checkbox-dropdown-toggle` / `.checkbox-dropdown-menu`
  (ported from `monitoring_style.py`). As in the original, the menu only
  toggles open/closed on clicking the button (no click-outside-to-close
  handler exists for this menu in the source page either) and stays open
  while making selections.
- **"Select all models" sync** (`setMonitoringModels` /
  `syncMonitoringFilterControls`): the two-way sync between the "All"
  checkbox and the models checklist is ported (selecting "All" selects
  every model; selecting every model individually re-checks "All").
- **Segment/model mutual-exclusivity** (`syncMonitoringFilterControls`'s
  `isPerformanceTab` branch, via `hasSegmentSelection` /
  `hasSpecificModelSelection`) is ported: selecting a non-"All" Portfolio
  Segment disables the Models checklist (and its "All" toggle); selecting a
  strict subset of models disables the Portfolio Segment dropdown. A help
  text below the filter bar (`pd-filter-help`, replacing
  `#monitoring-filter-help`) explains which filter is active, matching the
  original's three messages. Neither control's *value* is reset when it
  becomes disabled - exactly as in the original, the user must reset one
  filter to "All"/all-models before the other becomes selectable again.
- **No "Time Horizon" / "PD Input" filter controls**: the original page's
  `MONITORING_TIME_HORIZON` / `MONITORING_PD_INPUT` are page-level JS
  globals (defaulting to `'1y'` / `'time_horizon'`) read by
  `getActivePdInputKey()` for the LGD/EAD tabs - the actual top-bar
  (`TOP_BAR_CONTROLS_HTML` in `monitoring_layout.py`) never renders a
  "Time Horizon" or "PD Input" dropdown for the PD Performance tab. This
  port likewise has no such controls; `PdFilterContext` only carries
  `quarters` / `models` / `segment` / `monitoring_point`, and each PD
  Performance section hardcodes its own horizon (1y / 2y / `nco_1y`) as the
  original sections do.

### MEV Range chart filters

- `pd-mev-filter-store = {"model": "all" | <model_name>, "names": None | []
  | [list]}`. `"model"` selects which PD model's MEV panel(s) are shown
  (`resolve_pd_mev_chart_model_names`); `"names"` selects which MEVs are
  shown within that scope (`resolve_pd_mev_chart_names`).
- `"names": None` means "no explicit selection yet" and resolves to *all*
  available MEV names for the current model scope. Once the user makes an
  explicit multi-select choice, `"names"` becomes a list (which **may be
  empty**).
- **Behavioural difference from the original JS**: in the original page, an
  empty MEV multi-select was treated the same as "all" (showing every MEV
  chart). In this Dash port, an explicitly-empty multi-select shows **zero**
  MEV charts (the empty-state card is rendered instead). This was judged the
  more useful/intuitive behaviour for a Dash `dcc.Dropdown(multi=True)` and
  is easily reversible if the original behaviour is required.
- "Reset chart filters" restores `pd-mev-filter-store` to
  `{"model": "all", "names": None}` and clears the `"mev"` entry from
  `pd-range-store`.

### Quarter formats

- Portfolio data and most PD-performance calculations use the `YYYYQn`
  quarter label format (e.g. `2022Q4`).
- Scenario Rank Ordering and MEV data (`facilities_dummy_data.json`,
  `mev_dummy_data.json`) use the `YYYY-Qn` format (e.g. `2022-Q4`), produced
  from ISO dates via `iso_date_to_pd_quarter`. `data/rank_ordering.py` and
  `data/mev.py` keep this format and provide their own
  `compare_pd_quarter_labels` / `_pd_quarter_sort_key` helpers - it is **not**
  normalized to `YYYYQn`, matching the original page.

### "1.1 Overview" section

- The original page's 1.1 Overview renders a large, hand-coded CSS-grid
  "flow diagram" (`buildPdOverviewHeatmap`, with `buildPdOverviewFlow*`
  helper functions and `.pd-overview-flow*` / `.pd-flow-*` CSS, ~50 rules)
  connecting input ECL PIT PD / Balance Sheet PD nodes through the
  calibration and discrimination tests to an overall Performance PD RAG
  gauge. It is live - rendered inside `<section id="pd-analysis-scope">` as
  part of `renderPdModels()` - and is **faithfully ported** here as
  `build_pd_overview_heatmap` in `components/kpis.py`.
- The diagram is a 5-stage process flow (Components / Tests / RAG Assignment
  / Monitoring Dimension RAG / Performance PD RAG) laid out with CSS Grid
  `grid-template-areas`, including:
  - The "Calibration Conservatism RAG (ECL PIT)" 1-year and 2-year
    notching/confidence-interval test nodes feeding their RAG-assignment
    nodes, which feed the "Calibration Conservatism RAG (ECL PIT)" dimension
    node.
  - The "Discriminatory Power RAG" Accuracy Ratio / Delta Accuracy Ratio test
    nodes feeding the "Discriminatory Power RAG" dimension node (with a
    pass-through connector spanning the unused RAG-assignment column).
  - The "Calibration Conservatism RAG (Balance Sheet)" notching/confidence
    interval test nodes feeding the "Calibration Conservatism RAG (Balance
    Sheet)" dimension node (also via a pass-through connector).
  - All three dimension RAG nodes feeding into the overall "Performance PD
    RAG" gauge (`build_pd_overview_flow_performance`,
    `calculate_pd_overview_performance_rag` -> weighted 0.25/0.25/0.50 score
    -> rounded RAG, exactly as in the original).
  - Connector-arrow spans (`.pd-overview-flow-connector-in/-out`) reproduce
    the original's directional arrows between stages.
- Each of the three dimension RAG nodes (and the per-horizon RAG-assignment
  nodes) is an in-page anchor link (`href="#pd-calibration-rag"`,
  `"#pd-discrimination-rag"`, `"#pd-balance-sheet-calibration"`) that jumps
  to the corresponding 1.2/1.3/2.1 section, matching the original's
  `data-pd-section-link` navigation.
- RAG-valued nodes carry an "info chip" tooltip (`.pd-info-chip`,
  `aria-label`/`title`) with the same explanatory text used by the
  corresponding 1.2/1.3/2.1 section cards (e.g. the calibration RAG tooltip
  from `build_pd_calibration_tooltip`, the discrimination RAG tooltip, and
  the balance-sheet calibration-assignment tooltip), and the Performance PD
  RAG gauge's tooltip is `build_pd_overview_performance_rag_tooltip`.

### Dead code intentionally not ported

The following functions/markup exist in the original page but are never
invoked by `renderPdModels()` (or only feed sections outside the PD
Performance tab) and were excluded:

- `buildPdRagMovement` and the RAG history table/movement matrix
  (`.pd-rag-table*`, `.pd-rag-movement*`, `.pd-rag-cell*`, `.pd-rag-legend`,
  `.pd-view-toggle`)
- The rating-migration matrix/heatmap functions and `.pd-migration-*` /
  `.pd-rating-*` / `.pd-subchart-*` markup
- `drawPdStabilityTrend` / `drawPdDistributionShift` and
  `.pd-stability-trend-*` markup
- `buildPdExecutiveSignals` / the retention-warning banner and
  `.pd-executive-grid` / `.pd-signal-card*` / `.pd-retention-*` /
  `.pd-scope-bar` / `.pd-page-header` / `.pd-overall-status` markup
- The standalone `performanceRag` / `trendPeriods` globals (superseded by
  `PdFilterContext` / per-call return values)
- `data-pd-expand-title` / chart-expand modal behaviour (no equivalent
  "expand chart" UI in this port)
- `_build_model_rows`, `_build_model_quarter_breakdown`,
  `_build_model_segment_quarter_breakdown`, `_build_threshold_summary` from
  `data_manager.py` (they feed model-overview tables on *other* tabs, not
  the PD Performance tab)

### CSS (`assets/styles.css`)

`assets/styles.css` is adapted from the single `CSS` string in
`components/monitoring_style.py` (688 lines, shared across the whole
monitoring dashboard). Changes made when porting:

- **No sidebar**: the original `body{display:flex;height:100vh;
  overflow:hidden}` assumed a fixed-height sidebar layout with
  internally-scrolling panels. This standalone app has no sidebar, so
  `body` just scrolls normally (`background:#f8fafc;min-height:100vh`).
- **`#tab-pd_models` -> `.pd-performance-app`**: the ~30 spacing/density
  override rules scoped to `#tab-pd_models` (and to `#pd-analysis-scope`,
  the 1.1 Overview section's id) are re-scoped to `.pd-performance-app`,
  the class set on the PD Performance page's content wrapper
  (`pages/monitoring_pd_performance_layout.py`'s `page_layout`).
- **New global filter bar styles** (`.pd-filter-bar`, `.pd-filter-control`,
  `.pd-filter-control-models`, `.pd-models-select-all`,
  `.pd-models-checklist`): the original sidebar top-bar's
  `.monitoring-filter` / `<select>`-based controls have no direct
  equivalent for this app's `dcc.Dropdown` / `dcc.Checklist`-based filter
  bar, so minimal new rules were written.
- **Sticky top bar**: the original `.top-bar` was `flex-shrink:0` inside
  a `display:flex; overflow:hidden` `.main` column, so it stayed pinned in
  place while only `.content` scrolled underneath it. This standalone app's
  body scrolls normally (no internal scroll containers), so the new
  `.pd-top-bar` wrapper (containing the filter bar and section sub-nav) is
  given `position:sticky; top:0; z-index:50` to reproduce the same "stays
  visible while the page scrolls" behaviour.
- **Section sub-navigation** (`#monitoring-pd-subnav` /
  `.monitoring-section-subnav*` -> `#pd-subnav` / `.pd-subnav-*`,
  `components/filters.py`'s `build_section_subnav`): the "RAG Assignment"
  and "Post Subjective Review Analysis" jump-link bars are ported, including
  the two-tone active styling (blue accent bar for RAG Assignment, orange for
  Post Subjective Review Analysis). `assets/pd_subnav.js` is a small
  client-side script (ported from `setMonitoringPdSubnavActive` /
  `updateMonitoringPdSubnavActiveState` / `jumpToMonitoringSection`) that
  smooth-scrolls to a section on click and highlights whichever
  link/group corresponds to the section currently at the top of the
  viewport. This is implemented as a plain `.js` file in `assets/` (which
  Dash auto-loads) rather than a callback, since it is purely presentational
  and doesn't affect chart data or filter state.
- **`.pd-overview-flow*` / `.pd-flow-*`** (the 1.1 Overview process-flow
  diagram, ~50 rules) are ported as-is, with the `#tab-pd_models`-scoped
  density overrides and `@media` rules re-scoped to `.pd-performance-app`
  (see "1.1 Overview" section above).
- **Omitted as out of scope / unused by this app's markup**: the top-bar
  mode switch (`.monitoring-mode-switch*`), PDF export menu/overlay/
  spinner (`.export-*`, `body.exporting-pdf`, `@keyframes spin`), `.badge*`,
  LGD/EAD and "monitoring overview" KPI grids (`.lgd-*`, `.ead-*`,
  `.monitoring-overview-*`, `.pd-kpi-dashboard-grid`),
  `.pd-filter-application-note` (dead code), and the CSS for the other
  dead-code PD features listed above (`.pd-rag-table*`, `.pd-rag-movement*`,
  `.pd-migration-*`, `.pd-stability-trend-*`, `.pd-executive-grid`,
  `.pd-signal-card*`, `.pd-retention-*`, `.pd-scope-bar`, `.pd-page-header`,
  `.pd-overall-status`, `.pd-formula-note`, `.pd-view-toggle`,
  `.pd-section-heading`, `.pd-metric-group*`, `.pd-performance-card`,
  `.pd-performance-grid`, `.grid-2`, `.grid-3`).

### Layout details

- Trend-detail chart pairs (e.g. default-rate trend + calibration trend)
  always render as a horizontal two-column grid (`.pd-trend-detail-grid`,
  `.pd-discrimination-trend-grid`) regardless of viewport, with a
  `@media(max-width:900px)` collapse to a single column - matching the
  original's responsive behaviour.
- Chart x-axis tick density is fixed (not recalculated from container
  width), as Plotly's own `automargin`/tick-reduction handles overcrowding
  reasonably for the data volumes involved.
- `PQ` (the previous monitoring quarter, `get_previous_pd_quarter(cq)`) is
  computed once per render and threaded into the calibration/discrimination
  trend and EAD-comparison helpers, exactly as the JS computed it once per
  `renderPdModels()` call.
