# Building a New Dashboard — Architecture Blueprint

This guide describes how to build a new dashboard on the **same foundation** as the
Wholesale Portfolio DQ Dashboard. The base codebase is structured to make a
domain swap (DQ monitoring → process monitoring, or any other tabular monitoring
use case) a matter of:

1. Copying the chrome and architecture verbatim
2. Replacing the per-tab logic with the new domain's metrics, charts, and copy
3. Pointing the data manager at the new source

The architecture intentionally mirrors STATpy's Dash app conventions (`pages/`,
`callbacks/`, `components/`, `config/`, plus root-level modules), so when you
later want to fold this into STATpy, the file layout already matches.

---

## TL;DR — What gets borrowed vs. what changes

| Layer | Borrow as-is | Rename/Adapt | Replace |
|---|---|---|---|
| **HTML chrome / CSS** | `components/styles.py` | — | — |
| **Sidebar, tabs, top-bar, footer** | `components/layout.py` (skeleton) | `TABS` list | — |
| **JS formatters** (`fmt`, `fmtN`, `pct`, `qLabel`, `badge`, etc.) | `components/helpers_js.py` | `qLabel` if periods aren't quarterly | — |
| **Comparison mode + filter dropdowns** | `components/comparison_mode.py` (pattern) | Re-tune QoQ/YoY/Historical to match your time grain | — |
| **PDF Export (single + all tabs)** | `components/layout.py:exportData/exportAllTabs` | — | — |
| **CLI entry point** | `app.py` (pipeline) | Output filenames, log messages | — |
| **Renderer assembler** | `renderer.py` | — | — |
| **Excel export** | `excel_export.py` (pattern) | Sheet definitions | — |
| **Data ingestion** | `data_manager.py` (pattern) | — | Replace with your source: SQL, CSV, API, logs |
| **Validation / metric engine** | `validation.py` (pattern of pure functions) | — | Replace with process-specific rules |
| **Per-page callbacks** | `callbacks/__init__.py` placeholder + module pattern | — | Replace each `*_callbacks.py` |
| **Per-page renderers** | `pages/__init__.py` placeholder + module pattern | — | Replace each `*_page.py` |
| **Config** | `config/load_config.py` (YAML loader) | — | Replace `config.yaml` schema; replace `config/dashboard_config.py` constants |

**Estimated effort**: 1–2 days to fully replicate, of which ~80% is per-domain
chart/KPI code in `pages/` and `callbacks/`. The chrome (sidebar, nav, top-bar,
filters, export buttons, modal overlay, KPI cards CSS) requires zero changes.

---

## File structure (STATpy-aligned)

The new dashboard should use the **exact same tree** as this codebase. Just
rename the project folder.

```
NewDashboard/
├── app.py                          # CLI entry point — same pattern as run_dq.py
├── config.yaml                     # Domain config (your schema)
├── README.md
│
├── data_manager.py                 # I/O — replaces load_portfolio()
├── processor.py                    # Orchestrator — runs per-period loop, builds metrics dict
├── validation.py                   # Pure-logic metric engine (replace with your rules)
├── renderer.py                     # Thin HTML assembler — keep verbatim
├── excel_export.py                 # Workbook generator
│
├── pages/                          # 1 file per dashboard tab
│   ├── __init__.py
│   ├── overview_page.py            # Always exists — D0
│   ├── <your_tab1>_page.py
│   └── ...
│
├── callbacks/                      # 1 file per page — data builders
│   ├── __init__.py
│   ├── <your_tab1>_callbacks.py
│   └── ...
│
├── components/                     # Shared chrome (BORROW VERBATIM)
│   ├── __init__.py
│   ├── layout.py                   # Sidebar, tabs, init JS, exportData, exportAllTabs
│   ├── styles.py                   # CSS — entirely reusable
│   ├── helpers_js.py               # fmt/fmtN/pct/badge — entirely reusable
│   └── comparison_mode.py          # Mode bar + period filters (adapt to your time grain)
│
├── config/
│   ├── __init__.py
│   ├── load_config.py              # YAML loader (reusable)
│   └── dashboard_config.py         # Per-domain constants (replace with yours)
│
└── output/                         # Run artifacts
```

---

## What each component does (so you know what to keep vs. swap)

### Files to copy verbatim (no changes needed)

#### `components/styles.py`
Inlined CSS string defining:
- Navy sidebar + nav items
- KPI cards (`.kpi-card`, `.kpi-grid`)
- Section cards (`.section-card`, `.section-title`)
- Grid layouts (`.grid-2`, `.grid-3`, `.grid-1-2`, `.grid-2-1`)
- Tables, badges (`.badge-critical/high/medium/low/green/amber/red`)
- Completeness cells (`.cell-none/low/medium/high/critical`)
- Heat-map cells (`.hm-cell`, `.hm-none/minor/moderate/high`)
- Insight cards, governance badges
- Export split-button + dropdown menu (`.export-menu-wrap`, `.export-btn-main`, etc.)
- Export progress overlay (`.export-overlay`, `.export-overlay-card`)
- PDF-export hiding rule (`body.exporting-pdf .tab-panel button { display:none }`)
- Responsive breakpoint at 900px

**Action**: Copy file as-is. If your brand needs different colors, change only
the CSS variables at the top (`--navy`, `--blue`, etc.).

#### `components/helpers_js.py`
JS string exposing formatters and small DOM helpers used by every page:
- `fmt(v, d)`, `fmtN(v)`, `fmtB(v)` (currency-billions), `pct(v, d)`
- `arrow(d, good)` — colored ▲/▼ delta indicator
- `badge(severity)` — colored badge factory
- `hm(psi)` — heat-map cell factory (PSI-style — rename buckets if needed)
- `completenessCell(pct)` — cell factory for missing-data tables
- `spark(values)` — Unicode sparkline string
- `qLabel(q)` — formats "2025Q4" → "2025 Q4"
- `getQData(q)`, `getQoQ(q)` — dict accessors against `DASH_DATA.by_quarter[q]`

**Action**: Copy. If your time periods aren't "2025Q4"-style strings,
rewrite `qLabel(q)` to format your period keys (e.g. "2025-12" → "Dec 2025").

#### `renderer.py`
Thin HTML assembler — does NOT touch metrics, just stitches together:
- HTML doctype + head
- Plotly + html2pdf CDN scripts
- Embedded CSS (from `components/styles.py`)
- Sidebar + top-bar + tab panel divs + footer
- `<script>` block with: `DASH_DATA = {json}`, helpers, comparison mode,
  dispatch JS, each page's `JS` constant, init JS

**Action**: Copy. Only customize the page title and the top-bar inner text.

#### `app.py`
CLI entry point:
- argparse (--config, --quarter/--period, --dry-run, --log-level)
- Loads config + data via `data_manager`
- Runs `processor.process_all`
- Writes HTML + Excel + JSON to versioned `output/<ts>/` folder

**Action**: Copy. Rename `--quarter` to `--period` (or whatever time grain
suits your domain). Adjust output filenames.

### Files to customize lightly

#### `components/layout.py`
Contains:
- `TABS` list — **edit this** to define your tab IDs, labels, icons, and
  the JS function name each tab calls
- `nav_html()` — auto-generated from TABS (no edits needed)
- `tab_panels_html()` — auto-generated (no edits needed)
- `dispatch_js()` — auto-generated (no edits needed)
- `INIT_JS` — contains: `initSelectors`, `setCurrentQuarter`, `setCompareQuarter`,
  `initFooter`, `renderAll`, `TAB_LABELS_FOR_PDF`, `_showExportOverlay`,
  `_hideExportOverlay`, `exportData()`, `exportAllTabs()`, `toggleExportMenu`,
  `closeExportMenu`, the click-outside-to-close listener, and the `init` IIFE

**Action**: Edit `TABS`. Update `TAB_LABELS_FOR_PDF` to match new tab IDs (the
labels are used in PDF filenames). Rename `CQ`/`PQ` variables to `CP`/`PP`
("current period" / "prior period") if your time grain isn't quarterly. The
rest (export logic, modal overlay, init pattern) is universal.

#### `components/comparison_mode.py`
The three-mode comparison bar (QoQ / YoY / Historical) with conditional
sub-bars showing different selectors per mode. Pattern is fully reusable —
just adapt the period labels:

| This dashboard | New dashboard examples |
|---|---|
| QoQ — Same Portfolio | "WoW — Same Process" / "Last 12 weeks" |
| YoY — 2024 vs 2025 | "MoM — Month vs Month" / "Year vs Year" |
| Historical Comparison | "Historical" / "Full range" |

The state variables `CMP_MODE`, `YOY_24_YEAR`, `YOY_25_YEAR`, `HIST_START`,
`HIST_END` are generic — rename to match your domain but keep the pattern.

The helpers `_cmpTS24`, `_cmpTS25`, `_cmpFilter`, `_cmpX`, `_cmpTraces`,
`_cmpLayout` assume two datasets being compared (port24 vs port25). If you
only have one, simplify `_cmpTraces` to a single series.

#### `config/load_config.py`
- `load_config(path)` — generic YAML loader. **Keep verbatim**.
- `resolve_key_vars(schema_df, df_columns)` — DQ-specific (filters schema rows
  where `key_variable == "Y"`). **Replace** with your own resolver if you have
  schema metadata, otherwise delete.

#### `config/dashboard_config.py`
DQ-specific constants:
- `SEVERITY_ORDER`, `SOURCE_SYSTEMS`, `DEFAULT_PSI_THRESHOLDS`,
  `DEFAULT_COMPLETENESS_THRESHOLDS`

**Action**: Replace with your domain's constants (e.g., SLA thresholds, status
ordering, process categories, color maps).

### Files to fully replace

#### `data_manager.py`
The DQ version reads Excel/SQL + parses quarter labels from a date column. Your
new version probably reads from a different source. **Keep the function
signatures** so `processor.py` doesn't need to change:

```python
def load_data(cfg, base_dir) -> pd.DataFrame: ...   # raw records
def load_schema(cfg, base_dir) -> pd.DataFrame: ... # optional, for column metadata
def get_periods(df) -> list[str]: ...               # ordered list of period keys
def get_period_df(df, period) -> pd.DataFrame: ...  # slice by period
def get_snapshot_date(df, period) -> str: ...       # ISO date string for a period
```

Common sources:
- **SQL** (e.g., LocalDB like STATpy uses): `pd.read_sql_query(...)` against
  your monitoring tables
- **CSV / logs**: `pd.read_csv()` with glob
- **API / cloud**: `requests` + `pd.DataFrame.from_records`

#### `validation.py`
This file holds the *pure-computation* layer — given a DataFrame, return a
metrics dict. The current functions are DQ-specific (`apply_rules`,
`compute_completeness`, `compute_drift`, `compute_psi`, `compute_population`,
`compute_schema_validation`).

For process monitoring, replace with:
- `compute_throughput(df, period)` — records processed per period
- `compute_latency_distribution(df)` — p50/p95/p99 timings
- `compute_error_rate(df)` — failures / total
- `compute_sla_compliance(df, sla_threshold_seconds)` — pct within SLA
- `compute_queue_depth(df)` — backlog over time
- `compute_process_status(df)` — counts by status (Running/Completed/Failed)
- `detect_anomalies(df, baseline)` — std-dev breaches

Keep functions **pure and testable** (no I/O, no global state).

#### `pages/*.py`
Each file exports a `JS` string constant containing one `renderXxx()` JS
function. **The pattern**:

```python
JS = f"""
function renderXxx() {{
  const d = getQData(CP);   // CP = current period
  const metrics = d.your_section || {{}};

  // Build KPIs
  const kpis = [
    {{icon:'⚡', label:'Throughput', val:fmtN(metrics.throughput), sub:'records/hr'}},
    ...
  ];
  const kpiHtml = kpis.map(k => `<div class="kpi-card">...</div>`).join('');

  // Build tables / sub-sections
  // ...

  // Set the panel's innerHTML
  document.getElementById('tab-xxx').innerHTML = `
    <div class="dash-header">...</div>
    ${{_modeBar()}}
    <div class="kpi-grid">${{kpiHtml}}</div>
    <div class="grid-2">
      <div class="section-card"><div id="chart-1"></div></div>
      <div class="section-card"><div id="chart-2"></div></div>
    </div>
  `;

  // Plotly charts (after innerHTML so divs exist)
  Plotly.react('chart-1', ..., ..., {{responsive:true,displayModeBar:false}});
}}
"""
```

**Critical pattern** for the JS string:
- File is a Python module that exposes `JS = f"""...JavaScript code..."""`
- The f-string is evaluated *once at import time*; doubled braces (`{{`/`}}`)
  collapse to single braces (`{`/`}`) — this is how you embed JS object literals
- Don't include Python interpolations *inside* the f-string except for the
  ones that genuinely vary at HTML generation time (rare; usually none)
- `renderer.py` substitutes each page's `JS` into the master HTML template
  via simple `f"...{module.JS}..."` — already-resolved strings, no
  re-parsing of braces

#### `callbacks/*.py`
Each file exports functions that build the dict consumed by its matching
page. **The pattern**:

```python
"""<Tab name> data builders."""
import pandas as pd

def build_<section>(period_df: pd.DataFrame, ...) -> dict:
    """Return the dict that pages/<tab>_page.py reads as d.<section>."""
    return {
        "metric_a": ...,
        "metric_b": ...,
        "by_category": [...],
    }
```

Then `processor.py` imports and calls these inside the per-period loop:

```python
from callbacks.<tab>_callbacks import build_<section>
# ...
by_period[p]["<section>"] = build_<section>(period_df, ...)
```

#### `processor.py`
Orchestrator: loops over periods, calls validation + callbacks, accumulates
into one big dict. **Keep the shape**:

```python
return {
    "run_id": str,
    "data_as_of": str,
    "last_refresh": str,
    "source": str,
    "periods": [str],            # was: "quarters"
    "latest_period": str,        # was: "latest_quarter"
    "prior_period": str,
    "by_period": {period: {...metrics...}},
    "time_series": {...},        # arrays for trend charts
    # ...any cross-period analyses
}
```

The shape is what `pages/` reads as `DASH_DATA`. Stay consistent.

---

## Step-by-step: scaffolding the new project

### 1. Bootstrap

```bash
# From the existing Dashboards repo
mkdir ../NewDashboard
cd ../NewDashboard

# Copy verbatim chrome
cp -r ../Dashboards/components .
cp ../Dashboards/renderer.py .
cp ../Dashboards/excel_export.py .

# Copy patterns
cp -r ../Dashboards/config .
cp ../Dashboards/app.py .
cp ../Dashboards/data_manager.py .
cp ../Dashboards/processor.py .
cp ../Dashboards/validation.py .

# Empty package dirs
mkdir pages callbacks
touch pages/__init__.py callbacks/__init__.py
```

### 2. Define the tabs (`components/layout.py`)

```python
TABS = [
    ("overview", "Overview",            "📊", "renderOverview"),
    ("runs",     "Process Runs",        "▶️", "renderRuns"),
    ("errors",   "Error Analytics",     "🚨", "renderErrors"),
    ("sla",      "SLA Compliance",      "⏱️", "renderSLA"),
    ("perf",     "Performance Trends",  "📈", "renderPerf"),
    # …
]

TAB_LABELS_FOR_PDF = {
    "overview": "Overview",
    "runs":     "Process_Runs",
    "errors":   "Error_Analytics",
    "sla":      "SLA_Compliance",
    "perf":     "Performance_Trends",
}
```

### 3. Create stub pages and callbacks for each tab

```python
# pages/runs_page.py
JS = f"""
function renderRuns() {{
  document.getElementById('tab-runs').innerHTML = '<div class="dash-header"><h2>Process Runs</h2></div>';
}}
"""
```

```python
# callbacks/runs_callbacks.py
def build_runs_metrics(period_df):
    return {"total_runs": len(period_df), "success_rate": 0.95}
```

### 4. Wire pages into the renderer

```python
# renderer.py — already auto-iterates a PAGE_MODULES list. Just add imports:
from pages import overview_page, runs_page, errors_page, sla_page, perf_page

PAGE_MODULES = [overview_page, runs_page, errors_page, sla_page, perf_page]
```

### 5. Point `data_manager.py` at your source

Rewrite `load_portfolio()` → `load_data()`. Adapt `get_quarters` → `get_periods`
if your time grain differs.

### 6. Replace `validation.py` with domain functions

Pure functions taking a DataFrame and returning dicts. Use the existing file as
a syntactic template (logging, type hints, signature shape).

### 7. Update `processor.py` to call your new callbacks

Replace `process_all()`'s per-quarter loop body with calls to your new
callbacks. Keep the outer loop and result dict shape.

### 8. Smoke test

```bash
python3 app.py --config config.yaml --dry-run
python3 app.py --config config.yaml
open output/<latest>/dashboard.html
```

---

## Pattern cookbook (with code)

Snippets you'll reach for repeatedly. All assume the conventions already
described.

### Adding a KPI card

```javascript
const kpis = [
  {icon:'⚡', label:'Throughput',  val:fmtN(m.throughput),    sub:'records/min', delta:arrow(m.throughput_delta, true)},
  {icon:'🎯', label:'SLA Met %',    val:pct(m.sla_pct),        sub:'this period',  delta:''},
  {icon:'⏱️', label:'p95 Latency',  val:fmt(m.p95_sec,1)+'s',  sub:'',             delta:arrow(-m.p95_delta, true)},
];
const kpiHtml = kpis.map(k => `<div class="kpi-card">
  <div class="kpi-icon">${k.icon}</div>
  <div class="kpi-label">${k.label}</div>
  <div class="kpi-value">${k.val}</div>
  ${k.sub ? `<div class="kpi-sub">${k.sub}</div>` : ''}
  ${k.delta ? `<div class="kpi-delta">${k.delta}</div>` : ''}
</div>`).join('');
```

Render via: `<div class="kpi-grid" style="grid-template-columns:repeat(N,1fr)">${kpiHtml}</div>`.

### Adding a 2-column section row

```javascript
document.getElementById('tab-x').innerHTML = `
  <div class="grid-2">
    <div class="section-card">
      <div class="section-title">Throughput Over Time</div>
      <div id="chart-throughput" class="chart-box"></div>
    </div>
    <div class="section-card">
      <div class="section-title">Error Rate by Step</div>
      <table>...</table>
    </div>
  </div>
`;
```

### Adding a time-series chart with two series

```javascript
Plotly.react('chart-throughput', [
  {
    type:'scatter', mode:'lines+markers',
    name:'Current',
    x: m.throughput_ts.map(r => r.label),
    y: m.throughput_ts.map(r => r.value),
    line:{color:'#2563eb', width:2},
    marker:{size:3, color:'#2563eb'},
  },
  {
    type:'scatter', mode:'lines',
    name:'Baseline (90d avg)',
    x: m.throughput_ts.map(r => r.label),
    y: m.throughput_ts.map(r => r.baseline),
    line:{color:'#6b7280', width:1, dash:'dot'},
  },
], {
  margin:{t:10,r:10,b:50,l:50}, height:220,
  paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  xaxis:{tickfont:{size:9}, tickangle:-45},
  yaxis:{title:'Records/min', gridcolor:'#f1f5f9', tickfont:{size:9}},
  legend:{orientation:'h', y:1.18, x:0, font:{size:9}},
}, {responsive:true, displayModeBar:false});
```

### Adding a discrete-category bar chart (e.g. error counts by step)

```javascript
Plotly.react('chart-errors-by-step', [{
  type:'bar',
  x: m.by_step.map(r => r.step),
  y: m.by_step.map(r => r.count),
  marker:{color: m.by_step.map(r => r.count > 10 ? '#dc2626' : '#16a34a')},
  text: m.by_step.map(r => r.count),
  textposition:'outside',
}], {
  bargap: 0.25,
  margin:{t:30, r:20, b:60, l:60}, height:260,
  paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  xaxis:{type:'category', title:{text:'<b>Step</b>'}, tickfont:{size:10}},
  yaxis:{title:{text:'<b>Errors</b>'}, gridcolor:'#e5e7eb', tickfont:{size:10}},
  showlegend:false,
}, {responsive:true, displayModeBar:false});
```

> **Important**: For categorical x-axes (CRR grades, step names, status labels),
> always set `xaxis.type: 'category'` and `categoryorder: 'array'` with
> `categoryarray`. Otherwise Plotly treats values as numeric and bars become
> thin hairlines with skipped tick labels. This was a real bug in the DQ
> dashboard's CRR migration chart.

### Adding a filter dropdown row (single-active-filter pattern)

Pattern from Population's segment filter. State:

```javascript
let X_FILTER = { dim: null, value: null };
function setXFilter(dim, value) {
  X_FILTER = value ? {dim, value} : {dim:null, value:null};
  renderTab(activeTab);
}
function clearXFilter() {
  X_FILTER = {dim:null, value:null};
  renderTab(activeTab);
}
```

Pre-compute slices server-side per (dim, value), store in `metrics["by_period"][p]["section"]["slices"]`,
then in the render function look up `slices[dim][value]` when a filter is active.

### Adding the "Export current tab" PDF button

You don't have to add this — it's already in `components/layout.py`. Every
tab gets the split-button automatically. To make sure your tab's content
captures correctly:

1. Ensure all Plotly charts are inside the tab panel (`#tab-xxx`)
2. Don't use `position:fixed` or `position:absolute` inside the panel — html2canvas struggles with those
3. Interactive controls auto-hide via `body.exporting-pdf` CSS rule

### Adding the comparison mode bar

Just call `${_modeBar()}` inside your tab's `innerHTML` template. The
sub-bar with period selectors appears automatically based on `CMP_MODE`.
You'll also need to either:
- Use `_cmpTraces(tsKey, yKey)` to build trace arrays (handles all 3 modes), OR
- Manually slice with `_cmpFilter(arr, portfolio)` and `_cmpX(arr)`

---

## Conventions and gotchas

### Python 3.9 compatibility

- ✅ `dict | None` type hints work in annotations only (via `from __future__ import annotations`)
- ❌ Don't use `match` statements
- ✅ Walrus operator `:=` is fine
- ❌ `Self` type requires `typing_extensions` or 3.11+

### F-string brace escaping in `pages/*.py`

All `pages/*.py` files use `JS = f"""..."""` so the JS code lives in an
**f-string**. This means:

- Literal `{` in JS → write as `{{` in the Python file
- Literal `}` in JS → write as `}}`
- JS template literal `${var}` → write as `${{var}}`

When you forget, Python raises `NameError: name 'someVar' is not defined`
at import time.

### CMP_MODE state and renderTab()

When the user changes any global state (mode, filter, period), call
`renderTab(activeTab)` to re-render the *current* tab only. Avoid
`renderAll()` unless you really need every tab refreshed — it's slow
because each tab re-runs Plotly.

### Plotly chart lifecycle

- Use `Plotly.react(divId, traces, layout, config)` for charts that re-render
  on state change (most charts) — it diffs efficiently
- Use `Plotly.newPlot(...)` only for charts created once and never updated
- After viewport resize: `Plotly.Plots.resize(divEl)` — useful in the PDF
  export to force SVGs to settle before capture

### PDF export and html2canvas

- The full-report export switches tabs sequentially. Each tab gets ~700ms
  to render before capture; bump this if your charts are heavy
- Interactive controls (buttons, selects, mode bar) are hidden via
  `body.exporting-pdf` CSS during capture
- Page break hints: `pagebreak: { avoid: ['.section-card', '.kpi-card'] }`
- Filename format: `<DashName>_<TabName>_<Period>.pdf`

### Data size budget

Self-contained HTML embeds `DASH_DATA` as a JSON literal. Keep the metrics
dict under ~5MB for a smooth single-file experience:

- Time series with 100s of periods → fine
- Per-record raw data → don't embed; aggregate first
- Combinatorial slices (e.g., 3 dimensions × 88 periods) → fine if metrics are slim
  (10–20 numeric fields)

Use `json.dumps(..., default=str)` to handle dates and other non-JSON types.

### Naming: "quarter" → "period" (or whatever)

The DQ dashboard uses "quarter" everywhere. For a process-monitoring dashboard,
the natural unit might be:
- Day (`"2025-12-15"`)
- Week (`"2025-W50"`)
- Hour (`"2025-12-15T14"`)

Pick a string format and stick to it. The JS `qLabel()` and `_cmpX()` functions
in `helpers_js.py` and `comparison_mode.py` need updating to format your strings.

---

## Sketched example: Process Monitoring Dashboard

A concrete instantiation of the template for monitoring "process runs"
(e.g. ETL jobs, model scoring runs, batch pipelines).

### Tabs (in `components/layout.py`)

```python
TABS = [
    ("overview", "Overview",         "📊", "renderOverview"),
    ("runs",     "Run History",      "▶️", "renderRuns"),
    ("perf",     "Performance",      "📈", "renderPerf"),
    ("errors",   "Errors & Alerts",  "🚨", "renderErrors"),
    ("sla",      "SLA Compliance",   "⏱️", "renderSLA"),
    ("audit",    "Audit Trail",      "📝", "renderAudit"),
]
```

### Time grain

Daily snapshots → period keys like `"2025-12-15"`. Update `qLabel`:

```javascript
function qLabel(p) { return p ? p : ''; }  // already a human label
// Or, for weekly: p = "2025-W50" → return "Week 50, 2025"
```

### Per-page sketch

#### `pages/runs_page.py` — KPIs + run-volume time series + status donut

```python
JS = f"""
function renderRuns() {{
  const d = getQData(CP);
  const m = d.runs || {{}};

  const kpis = [
    {{icon:'▶️', label:'Total Runs', val:fmtN(m.total), sub:'this period', delta:''}},
    {{icon:'✅', label:'Success Rate', val:pct(m.success_pct), sub:'', delta:arrow(m.success_delta,true)}},
    {{icon:'❌', label:'Failed Runs',  val:fmtN(m.failed), sub:'auto-retried: '+fmtN(m.retried), delta:''}},
    {{icon:'⏱️', label:'Avg Duration', val:fmt(m.avg_dur_sec/60,1)+'min', sub:'', delta:''}},
    {{icon:'📈', label:'p95 Duration', val:fmt(m.p95_dur_sec/60,1)+'min', sub:'', delta:''}},
    {{icon:'🕒', label:'Last Run',     val:m.last_run_at||'—', sub:m.last_run_status||'', delta:''}},
  ];

  const kpiHtml = kpis.map(k => `<div class="kpi-card">...</div>`).join('');

  document.getElementById('tab-runs').innerHTML = `
    <div class="dash-header"><h2>Run History — ${{CP}}</h2></div>
    ${{_modeBar()}}
    <div class="kpi-grid" style="grid-template-columns:repeat(6,1fr)">${{kpiHtml}}</div>
    <div class="grid-2">
      <div class="section-card">
        <div class="section-title">Run Volume Over Time</div>
        <div id="runs-chart-volume" class="chart-box"></div>
      </div>
      <div class="section-card">
        <div class="section-title">Status Breakdown</div>
        <div id="runs-chart-status" style="min-height:240px"></div>
      </div>
    </div>
    <div class="section-card">
      <div class="section-title">Recent Failures (Top 10)</div>
      <table>...</table>
    </div>
  `;

  // ... Plotly calls
}}
"""
```

#### `callbacks/runs_callbacks.py`

```python
def build_runs_metrics(df_period):
    success = df_period["status"] == "Success"
    return {
        "total":         len(df_period),
        "success_pct":   round(success.mean() * 100, 2),
        "failed":        int((~success).sum()),
        "retried":       int(df_period["was_retried"].sum()) if "was_retried" in df_period else 0,
        "avg_dur_sec":   round(df_period["duration_sec"].mean(), 1),
        "p95_dur_sec":   round(df_period["duration_sec"].quantile(0.95), 1),
        "last_run_at":   str(df_period["started_at"].max()),
        "last_run_status": df_period.sort_values("started_at").iloc[-1]["status"] if len(df_period) else None,
    }
```

#### `validation.py` (process monitoring version)

```python
def compute_sla_compliance(df, sla_threshold_sec):
    if "duration_sec" not in df.columns or df.empty:
        return {"pct": None, "breaches": 0}
    breaches = (df["duration_sec"] > sla_threshold_sec).sum()
    return {
        "pct": round((1 - breaches / len(df)) * 100, 2),
        "breaches": int(breaches),
        "threshold_sec": sla_threshold_sec,
    }

def detect_anomalies(current_series, baseline_mean, baseline_std, z_threshold=2.0):
    z = (current_series - baseline_mean) / max(baseline_std, 1e-6)
    return {
        "n_anomalies": int((z.abs() > z_threshold).sum()),
        "max_z": round(float(z.abs().max()), 2),
    }
```

#### `data_manager.py` (process monitoring version, SQL source)

```python
def load_data(cfg, base_dir):
    from sqlalchemy import create_engine
    engine = create_engine(cfg["data"]["connection_string"])
    query = "SELECT * FROM process_runs WHERE started_at >= :since"
    df = pd.read_sql_query(query, engine, params={"since": cfg["data"]["lookback_start"]})
    df["_period"] = df["started_at"].dt.strftime("%Y-%m-%d")  # daily
    df["_snapshot_date"] = df["started_at"].dt.date
    return df

def get_periods(df):
    return sorted(df["_period"].unique())

def get_period_df(df, period):
    return df[df["_period"] == period].copy()
```

#### Config (`config.yaml`)

```yaml
data:
  connection_string: "postgresql://..."   # or sqlite, mssql, etc.
  table: process_runs
  lookback_days: 90

sla:
  default_threshold_sec: 600
  by_process:
    daily_etl: 1800
    model_scoring: 300

alerts:
  failure_pct_threshold: 5.0
  duration_z_threshold: 2.5

output:
  directory: output
  versioned: true
  html_filename: process_dashboard.html
  excel_filename: process_report.xlsx
```

---

## Inventory of reusable patterns (quick reference)

| Pattern | Where in this repo | When to use |
|---|---|---|
| **KPI card grid** | `components/styles.py` `.kpi-card`, `.kpi-grid` | Any 4–11 numeric summary metrics at top of a tab |
| **Section card** | `.section-card`, `.section-title` | Container for any chart/table block |
| **Grid layouts** | `.grid-2`, `.grid-3`, `.grid-1-2`, `.grid-2-1` | Multi-column rows of section cards |
| **Badge** | `badge()` in `helpers_js.py` | Color-coded labels (Critical/High/Medium/Low/Open/Resolved/etc.) |
| **Comparison mode bar** | `components/comparison_mode.py` | Tabs that show period-over-period time series |
| **Conditional sub-bar** | `_quarterDropdowns()` | Show different filter controls per mode |
| **Single-active-filter** | `pages/population_page.py` `POP_FILTER` pattern | 3 dropdowns where selecting one clears others |
| **Multi-page PDF export** | `components/layout.py` `exportAllTabs()` | Stitches all tabs into one PDF via html2pdf chained API |
| **Modal progress overlay** | `_showExportOverlay`, `_hideExportOverlay` | Long async operations with user feedback |
| **Sankey diagram** | `pages/tech_dq_page.py` `tech-fcl-sankey` | Flow/migration visualization (prior → current state) |
| **Waterfall chart** | `pages/population_page.py` `pop-chart-waterfall` | Decomposing a delta into named components |
| **Heatmap (Plotly + HTML table hybrid)** | `pages/drift_page.py` `hm()` helper | Time × dimension intensity grids |
| **Stacked area (% groupnorm)** | `pages/population_page.py` `pop-chart-segment-mix` | Composition over time |
| **Stacked bar (positive + negative)** | `pages/population_page.py` `pop-chart-churn` | Net flow with components above/below zero |
| **Materiality grid (HTML/CSS)** | `pages/governance_page.py` `matGrid` | 3×3 risk grid with numbered badges |
| **Scorecard table with RAG** | `pages/scorecard_page.py` | Side-by-side comparison with status colors |
| **Drill-down clickable cards** | `pages/overview_page.py` `ov-card` `onclick="switchTab(...)"` | Overview tab linking to detail tabs |

---

## Final notes

- **STATpy integration**: when ready, the file layout is already compatible.
  Each `pages/*_page.py` becomes a Dash page (`layout = dbc.Container(...)`),
  each `callbacks/*_callbacks.py` becomes `@callback(Output, Input)` decorators.
  The pure metric functions in `validation.py` and `processor.py` move as-is.
- **One file per dashboard tab** is a hard rule. It makes ownership clear and
  makes future Dash conversion mechanical.
- **The renderer never knows about your domain** — it just stitches strings.
  When you add a tab, you only touch `components/layout.py:TABS`,
  `pages/<new>_page.py`, `callbacks/<new>_callbacks.py`, and import the new
  page module in `renderer.py:PAGE_MODULES`.
- **Test the export early**. PDF generation can fail silently for layouts that
  use `position:fixed`, transforms, or external images without CORS. Run
  Export All on a 3-tab MVP before fleshing out the full app.
