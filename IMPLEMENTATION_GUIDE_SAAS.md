# STATpy Platform — SAAS Workspace Implementation Guide

Step-by-step guide for setting up the STATpy platform with your own data, starting with the SAAS Workspace dashboard. No git clone or file downloads are required — you copy-paste code from the GitHub repo in your browser.

---

## Prerequisites

- Python 3.10 or later
- Browser access to the STATpy_platform GitHub repo
- Your own MEV data in Excel format

---

## Step 1: Run the scaffold script

The scaffold script creates the full folder structure, all `__init__.py` package files, and `requirements.txt` in one go — so you don't have to create 23 directories and 18 package files by hand.

1. Open `scaffold.py` in the GitHub repo
2. Copy its entire contents
3. On your machine, create a working directory and save the file as `scaffold.py`
4. Run it:

```bash
cd your_working_directory
python scaffold.py
```

This creates:

```
your_working_directory/
  scaffold.py              <-- you can delete this after
  STATpy_platform/
    __init__.py             ✓ created
    requirements.txt        ✓ created
    assets/                 ✓ created (empty, ready for CSS/JS)
    config/                 ✓ created with __init__.py
    components/             ✓ created with __init__.py
    shared/                 ✓ created with __init__.py
    data/                   ✓ created with all sub-packages
    features/               ✓ created with all sub-packages
    source_data/            ✓ created (empty, ready for your data)
```

---

## Step 2: Install dependencies

```bash
pip install -r STATpy_platform/requirements.txt
```

---

## Step 3: Copy-paste the code files

Open each file in the GitHub repo browser, copy the code, and paste it into the matching path on your machine. The files are grouped below by priority — start with Group A to get the app running.

### Group A: Core (8 files) — app starts with these

| # | GitHub path | Local path |
|---|------------|------------|
| 1 | `app.py` | `STATpy_platform/app.py` |
| 2 | `shell.py` | `STATpy_platform/shell.py` |
| 3 | `features_registry.py` | `STATpy_platform/features_registry.py` |
| 4 | `config/settings.py` | `STATpy_platform/config/settings.py` |
| 5 | `config/environments.py` | `STATpy_platform/config/environments.py` |
| 6 | `shared/types.py` | `STATpy_platform/shared/types.py` |
| 7 | `shared/theme.py` | `STATpy_platform/shared/theme.py` |
| 8 | `shared/registration.py` | `STATpy_platform/shared/registration.py` |

### Group B: Shared components and data layer (8 files)

| # | GitHub path | Local path |
|---|------------|------------|
| 9 | `components/charts.py` | `STATpy_platform/components/charts.py` |
| 10 | `components/filters.py` | `STATpy_platform/components/filters.py` |
| 11 | `data/common/text.py` | `STATpy_platform/data/common/text.py` |
| 12 | `data/analytics/constants.py` | `STATpy_platform/data/analytics/constants.py` |
| 13 | `data/analytics/calculations.py` | `STATpy_platform/data/analytics/calculations.py` |
| 14 | `data/analytics/mev_range.py` | `STATpy_platform/data/analytics/mev_range.py` |
| 15 | `data/analytics/rank_ordering.py` | `STATpy_platform/data/analytics/rank_ordering.py` |
| 16 | `data/monitoring/loader.py` | `STATpy_platform/data/monitoring/loader.py` |

### Group C: SAAS dashboard (12 files) — the workspace page

| # | GitHub path | Local path |
|---|------------|------------|
| 17 | `data/saas/loader.py` | `STATpy_platform/data/saas/loader.py` |
| 18 | `features/saas/dashboard.py` | `STATpy_platform/features/saas/dashboard.py` |
| 19 | `features/saas/data_access.py` | `STATpy_platform/features/saas/data_access.py` |
| 20 | `features/saas/page_registry.py` | `STATpy_platform/features/saas/page_registry.py` |
| 21 | `features/saas/stores.py` | `STATpy_platform/features/saas/stores.py` |
| 22 | `features/saas/pages/workspace/page.py` | `STATpy_platform/features/saas/pages/workspace/page.py` |
| 23 | `features/saas/pages/workspace/callbacks.py` | `STATpy_platform/features/saas/pages/workspace/callbacks.py` |
| 24 | `features/saas/pages/workspace/views.py` | `STATpy_platform/features/saas/pages/workspace/views.py` |
| 25 | `features/saas/pages/workspace/selectors.py` | `STATpy_platform/features/saas/pages/workspace/selectors.py` |
| 26 | `features/saas/pages/workspace/records.py` | `STATpy_platform/features/saas/pages/workspace/records.py` |
| 27 | `features/saas/pages/workspace/figures.py` | `STATpy_platform/features/saas/pages/workspace/figures.py` |
| 28 | `features/saas/pages/workspace/metrics.py` | `STATpy_platform/features/saas/pages/workspace/metrics.py` |

### Group D: Monitoring dashboard (10 files) — PD Performance page

| # | GitHub path | Local path |
|---|------------|------------|
| 29 | `features/monitoring/dashboard.py` | `STATpy_platform/features/monitoring/dashboard.py` |
| 30 | `features/monitoring/data_access.py` | `STATpy_platform/features/monitoring/data_access.py` |
| 31 | `features/monitoring/page_registry.py` | `STATpy_platform/features/monitoring/page_registry.py` |
| 32 | `features/monitoring/stores.py` | `STATpy_platform/features/monitoring/stores.py` |
| 33 | `features/monitoring/pages/pd_performance/page.py` | `STATpy_platform/features/monitoring/pages/pd_performance/page.py` |
| 34 | `features/monitoring/pages/pd_performance/callbacks.py` | `STATpy_platform/features/monitoring/pages/pd_performance/callbacks.py` |
| 35 | `features/monitoring/pages/pd_performance/cards.py` | `STATpy_platform/features/monitoring/pages/pd_performance/cards.py` |
| 36 | `features/monitoring/pages/lgd_performance/page.py` | `STATpy_platform/features/monitoring/pages/lgd_performance/page.py` |
| 37 | `features/monitoring/pages/lgd_performance/callbacks.py` | `STATpy_platform/features/monitoring/pages/lgd_performance/callbacks.py` |
| 38 | `features/monitoring/pages/ead_performance/page.py` | `STATpy_platform/features/monitoring/pages/ead_performance/page.py` |
| 39 | `features/monitoring/pages/ead_performance/callbacks.py` | `STATpy_platform/features/monitoring/pages/ead_performance/callbacks.py` |

### Group E: SAAS exports (2 files) — optional, for Excel/PDF export

| # | GitHub path | Local path |
|---|------------|------------|
| 40 | `features/saas/pages/workspace/exports.py` | `STATpy_platform/features/saas/pages/workspace/exports.py` |
| 41 | `features/saas/pages/workspace/reports.py` | `STATpy_platform/features/saas/pages/workspace/reports.py` |

### Group F: Assets (3 files) — styling and navigation

| # | GitHub path | Local path |
|---|------------|------------|
| 42 | `assets/styles.css` | `STATpy_platform/assets/styles.css` |
| 43 | `assets/js/saas_workspace_subnav.js` | `STATpy_platform/assets/js/saas_workspace_subnav.js` |
| 44 | `assets/js/monitoring_pd_subnav.js` | `STATpy_platform/assets/js/monitoring_pd_subnav.js` |

**Note on the font file:** The repo includes `assets/fonts/InterVariable.woff2` (a binary font file that cannot be copy-pasted). The app works without it — the CSS falls back to system fonts (Arial, Helvetica). If you want the exact font, you'll need someone to transfer the file to you.

**Total: 44 files to copy-paste.** Groups A–C (28 files) are sufficient for the SAAS Workspace. Group D adds the PD Performance dashboard. Groups E–F add exports and styling.

---

## Step 4: Prepare your SAAS MEV workbook

Create an Excel file named `dummy_mev_data.xlsx` with four sheets. Use the descriptions below — or, if available, open the bundled file from the repo as a visual reference.

### Sheet 1: `transformed_mevs_description`

One row per model + transformed MEV combination.

| Column | Type | Description |
|--------|------|-------------|
| `Model Name` | text | Model identifier (e.g., `"PD Model A"`) |
| `Segment` | text | Portfolio segment (e.g., `"Corporate"`) |
| `US Mnemonic` | text | Transformed MEV identifier (e.g., `"RRGDPQ"`) |
| `Long Name` | text | Human-readable name (e.g., `"Real GDP Growth Rate"`) |
| `Description` | text | One-line MEV description |
| `SAAS_raw_mnemonic` | text | Comma-separated raw MEV names (e.g., `"RGDPQ,GDPQ"`) |
| `Model controbution` | number | Model contribution weight (note: intentional misspelling) |

### Sheet 2: `raw_mevs_description`

One row per raw MEV. If you have no raw MEVs, create the sheet with headers and leave it empty.

| Column | Type | Description |
|--------|------|-------------|
| `US Mnemonic` | text | Raw MEV identifier |
| `Long Name` | text | Human-readable name |
| `Description` | text | One-line description |
| `Group Mnemonic` | text | Group-level mnemonic |

### Sheet 3: `mev_data`

One row per model + MEV + scenario + date observation.

| Column | Type | Description |
|--------|------|-------------|
| `Date` | date | Observation date (e.g., `2020-03-31`) |
| `Quarter` | integer | `0` = projection start, negative = history, positive = projection |
| `Run For` | text | Reporting cycle (e.g., `"CCAR 2025"`) |
| `Scenario` | text | `"baseline"`, `"intsevere"`, or `"other"` |
| `MEV Name` | text | Must match `US Mnemonic` from the description sheets |
| `MEV Value` | number | The observed or projected value |
| `Model Name` | text | Must match `Model Name` from `transformed_mevs_description` |

**Example rows:**

| Date | Quarter | Run For | Scenario | MEV Name | MEV Value | Model Name |
|------|---------|---------|----------|----------|-----------|------------|
| 2022-03-31 | -8 | CCAR 2024 | baseline | RRGDPQ | 2.15 | PD Model A |
| 2024-03-31 | 0 | CCAR 2024 | baseline | RRGDPQ | 2.30 | PD Model A |
| 2024-06-30 | 1 | CCAR 2024 | baseline | RRGDPQ | 2.45 | PD Model A |
| 2024-03-31 | 0 | CCAR 2024 | intsevere | RRGDPQ | -1.20 | PD Model A |

### Sheet 4: `model_characteristic`

One row per model + reporting cycle.

| Column | Type | Description |
|--------|------|-------------|
| `Model Name` | text | Must match `Model Name` from `transformed_mevs_description` |
| `Run For` | text | Must match a `Run For` from `mev_data` |
| `Development date` | date | Model development date |
| `Model descriptive name` | text | Human-readable model name for card headers |

---

## Step 5: Place your workbook

Save your workbook as:

```
STATpy_platform/source_data/dummy_mev_data.xlsx
```

To use a different folder, set the environment variable before running:

```bash
# Mac / Linux
export STATPY_SOURCE_DATA_DIR=/path/to/your/data/folder

# Windows (Command Prompt)
set STATPY_SOURCE_DATA_DIR=C:\path\to\your\data\folder

# Windows (PowerShell)
$env:STATPY_SOURCE_DATA_DIR = "C:\path\to\your\data\folder"
```

---

## Step 6: Launch

From the directory that contains `STATpy_platform/`:

```bash
python -m STATpy_platform.app
```

Open `http://127.0.0.1:8050/saas` in your browser.

---

## Step 7: Verify

1. **Reporting Cycle** dropdown lists your `Run For` values
2. **Segment** dropdown lists your segments
3. **Specific Models** shows your model names
4. Select a Reporting Cycle and click **Apply filters**
5. Model cards appear with charts

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError` | Missing file or wrong path | Verify the file exists at the exact path shown in Step 3 |
| Empty dropdowns | Sheet/column names don't match | Compare names **exactly** against Step 4 (case-sensitive) |
| "No MEV time-series data" | `MEV Name` or `Model Name` mismatch between sheets | Use identical values across all sheets |
| No projection shading | Missing `Quarter == 0` rows | Add at least one row with `Quarter = 0` per Reporting Cycle |
| Monitoring pages error | Missing `portfolio.xlsx` / threshold files | Expected — only affects Monitoring, not SAAS |
| Styled but no colors/fonts | Missing `styles.css` | Copy `assets/styles.css` from the repo |

Watch the terminal for loader warnings when the app starts.

---

## Changing configuration

| What to change | Where to edit |
|----------------|---------------|
| Data file name | `config/settings.py` → `dummy_mev_data_file` property |
| Sheet names | `data/analytics/constants.py` → `DUMMY_MEV_*_SHEET_NAME` constants |
| Column names in workbook | `data/saas/loader.py` — search for the column name string |
| Scenario colors | `components/charts.py` — search for `#16a34a` (baseline), `#dc2626` (severe) |

---

## Summary

```
1.  Copy scaffold.py from the repo         (1 file)
2.  Run: python scaffold.py                 (creates 23 dirs + 19 files)
3.  Run: pip install -r ...                 (installs dependencies)
4.  Copy-paste 28 code files (Groups A–C)   (SAAS Workspace)
5.  Copy-paste styles.css + 1 JS file       (styling)
6.  Prepare dummy_mev_data.xlsx             (your data)
7.  Run: python -m STATpy_platform.app      (launch)
```
