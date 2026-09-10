# Backtesting dashboard — implementation plan

A third dashboard, **Backtesting**, that compares credit-risk model projections
against realised outcomes. It sits beside Monitoring and SAAS in the sidebar and
reuses the platform's existing chrome, cards and chart language — it is a new
dashboard, not a new design system.

This document is a plan only. No implementation code is written by it.

---

## Resolved decisions

Two questions raised by the first draft have been answered. Both are recorded
here because they changed the design, not just the wording.

### D1 — No `shared/ui` promotion. Monitoring stays exactly as it is.

The §7 proposal to move `build_pd_test_card`, `build_pd_section_rag_card`,
`build_pd_section_heading`, `build_pd_chapter_heading` and `pd_rag_dot` into
`shared/ui/cards.py` is **declined**. Nothing moves; `features/monitoring/ui/views/cards.py`
is not touched.

Backtesting therefore imports the five builders directly from monitoring,
keeping their existing `pd_` names. See §7 for the consequences and the
revisit trigger.

### D2 — There is no EAD column on the `pd`, `pd_crr` or `lgd` tabs.

Exposure weighting is still required (§1), so the weight must be **joined in
from `results.ead`** at facility × instrument × quarter grain. This is the
single largest change from the first draft: it turns a within-row multiplication
into a cross-tab join with a coverage problem, an ordering dependency, and a
mix-effect that contaminates the PD and LGD error unless it is explicitly
controlled for. §1 is rewritten around it, and it adds open questions Q19–Q22.

One note, stated once and then dropped: the workbook does not exist yet — the
next task creates it — so carrying an `EAD` column on the `pd`, `pd_crr` and
`lgd` tabs would be materially cheaper than the join described below, and would
also remove Q19–Q21 entirely. The plan below assumes the answer stands and
designs the join properly. If you'd rather add the column when generating the
workbook, §1 collapses back to the first draft's simpler form.

---

## Open questions

Every one of these is an assumption I had to make to write the plan. Each names
the section that depends on it and what changes if the answer differs.

| # | Assumption | Affects | If wrong |
|---|---|---|---|
| Q1 | The workbook is `source_data/backtesting.xlsx`, resolved by a new `settings.backtesting_file` property. | §5, M1 | Rename in one place (`config/settings.py`). Cheap. |
| Q2 | Each result tab carries **one** metric-value column named for the tab (`pd`, `pd_crr`, `lgd`, `ead`, `nco`), plus the run-identity columns, `Quarter`, `Facility ID`, `Credit Instrument ID` and `Execution Datetime`. | §1, §3, M2 | Loader column map changes; the aggregation rules in §1 are unaffected. |
| ~~Q3~~ | ~~An EAD exposure column is present on the `pd`, `pd_crr` and `lgd` tabs.~~ | — | **Answered: it is not.** See D2 and §1. |
| Q4 | `results.pd_crr` holds a **CRR rating grade** (ordinal master-scale bucket), not a probability. | §1 | If it is already a PD, it aggregates exactly like `results.pd` and the master-scale mapping drops out. |
| Q5 | `results.nco` is a **net charge-off amount** (currency), and `results.ead` is an **exposure amount** — both additive. | §1 | If `ead` is a CCF/utilisation *rate*, it must be limit-weighted, not summed. |
| Q6 | `J/N Flag` distinguishes judgemental (post-overlay) from non-judgemental (pure model) output. | §4, §8 | Only affects the default selection and the filter label. |
| Q7 | `Run For` uses the same vocabulary as SAAS (`CCAR 2026`, …) and `Segment Name` / `Model Name` match the `model_names` sheet in `dummy_mev_data.xlsx`. | §5 | Cross-dashboard filter parity breaks; backtesting would need its own catalogs rather than reusing the shared ones. |
| Q8 | `Month End Snapshot` always lands on a **quarter end**, so vintage ↔ target quarter is 1:1. | §2 | If snapshots are monthly, the "~9 forecasts per target" statement fails and the actuals diagonal in §2 develops holes. |
| Q9 | `Quarter` is an integer horizon offset from the snapshot, and the **lowest** value present (0 or 1) is the origin quarter. | §1, §2 | The actual-selection rule in §2 uses `min(Quarter)` rather than a hard-coded `0`, so it survives either convention — but the plan assumes one of them is the origin, not a lead. |
| Q10 | Max horizon is 9 quarters (from "~9 forecasts of any target quarter"). | §8, chart x-ranges | Cosmetic; axis ranges widen. |
| Q11 | `Execution Datetime` is a plain column, not part of the run key (it is absent from the run-identity list but named in the dedupe requirement). | §3 | If it *is* part of the key, there is nothing to dedupe and §3 becomes a no-op. |
| Q12 | Facility rows are never surfaced individually — the UI always shows the aggregate. | §1, §5 | A facility-grain drill-down needs a table layer and a much larger in-memory payload. |
| Q13 | Segment vs Model filters are mutually exclusive, as in both existing dashboards. | §5 | Filter cascade logic changes (see callback rule 2 in `CLAUDE.md`). |
| Q14 | A single page with five metric sections is the right shape (rather than five pages). | §5 | Registry-driven, so splitting later costs one edit to `page_registry.py`. |
| Q15 | Backtesting appends **after** SAAS in the sidebar, and `PRIMARY_DASHBOARD` stays Monitoring (root `/` stays PD Performance). | §5 | One-line change in `features_registry.py`. |
| Q16 | Amounts are in a single currency with no FX conversion needed. | §1 | Sums across segments become invalid without conversion. |
| Q17 | `Facility ID + Credit Instrument ID` is unique within a (run, quarter) after the §3 dedupe. | §1, §3 | Aggregates double-count. Worth an explicit loader assertion either way — see M2. |
| Q18 | `Model Name(s)` being plural means a run can name several models (a segment scored by more than one model), delimited within the cell. | §5 | The loader needs an explode step like SAAS's `_attribute_mev_rows_to_models`. |

### New questions raised by D2 (the exposure join)

| # | Assumption | Affects | If wrong |
|---|---|---|---|
| Q19 | A `results.ead` run names the **EAD model**, which is a different `Model Name` from the PD/LGD run it must supply weights to. The exposure join therefore matches on the run identity **excluding `Model Name`**: `(Segment Name, Month End Snapshot, Run For, Scenario, J/N Flag)` + `Facility ID` + `Credit Instrument ID` + `Quarter`. | §1 | If `Model Name` is shared across tabs, the join can use the full run key and Q20 disappears. |
| Q20 | After the §3 dedupe there is **exactly one** EAD row per facility × instrument × quarter within that reduced key. | §1 | The join fans out and silently multiplies rows. The loader must assert this; if a facility is genuinely covered by two EAD models, a tie-break rule is needed and none is obvious. **This is the new highest-risk unknown.** |
| Q21 | `results.ead` uses the same vintage × horizon grid as the other tabs — same `Month End Snapshot` values, same `Quarter` range. | §1, §2 | Weights are missing for horizons the EAD tab does not cover, and coverage collapses at the long end. |
| Q22 | Exposure coverage below ~95% (by matched exposure) makes an aggregate untrustworthy and should be flagged in the UI rather than shown plain. | §1, §8 | Only the threshold changes; the coverage surface is needed either way. |

---

# DATA

## 1. Aggregation rule per metric

Facility rows are collapsed to **one value per (run key, Quarter)** before
anything is charted. The run key is defined in §3.

| Tab | Aggregation | Formula |
|---|---|---|
| `results.pd` | Exposure-weighted mean, weight = EAD | `Σᵢ(EADᵢ · PDᵢ) / Σᵢ EADᵢ` |
| `results.pd_crr` | Map grade → master-scale PD, then exposure-weight in PD space | `Σᵢ(EADᵢ · PD(CRRᵢ)) / Σᵢ EADᵢ` |
| `results.lgd` | Exposure-weighted mean, weight = EAD | `Σᵢ(EADᵢ · LGDᵢ) / Σᵢ EADᵢ` |
| `results.ead` | Sum | `Σᵢ EADᵢ` |
| `results.nco` | Sum | `Σᵢ NCOᵢ` |

where *i* ranges over the facility × credit-instrument rows belonging to one
(run key, Quarter) after dedupe.

`EADᵢ` in the first three rows is **not** a column on those tabs — it is joined
in from `results.ead`. See *Where the weight comes from* below; that join is the
main piece of new work D2 introduces. The `ead` and `nco` rows are unaffected:
they are plain sums of their own tab.

### Confirming the PD and LGD weighting

**Confirmed — PD and LGD must be exposure-weighted by EAD, not simple means.**

For **PD**: a portfolio PD is only meaningful as expected defaults per unit of
exposure. A simple mean gives a \$10k facility the same weight as a \$500m one,
so the aggregate drifts toward whichever population happens to be most numerous
— typically the small-ticket tail. Exposure weighting is also the only choice
that satisfies the loss identity: expected defaulted exposure is `Σ EADᵢ·PDᵢ`,
so `Σ(EAD·PD)/Σ EAD` is the unique scalar that reproduces the portfolio's total
expected defaulted exposure when multiplied back by total EAD. A simple mean
does not, which means an error computed on it cannot be reconciled to any
currency figure.

For **LGD**: `Σ(EAD·LGD)/Σ EAD` is total expected loss-at-default over total
exposure, which is the number that rolls into EL. A simple mean over-weights
small facilities in exactly the same way.

**One nuance to record, not to act on:** the theoretically exact weight for LGD
is *defaulted* exposure, `EADᵢ · PDᵢ`, since LGD only applies conditional on
default. Using `EAD·PD` would make the LGD aggregate depend on the PD model
under test, so a PD miss would contaminate the LGD backtest. EAD-weighting keeps
the two metrics independently attributable, and matches standard practice. That
is the recommendation; it is a deliberate choice, not an oversight.

### Why `pd_crr` is different

CRR grades are **ordinal**, and the master scale is roughly geometric — the PD
gap between grades 1 and 2 is nothing like the gap between 8 and 9. Averaging
grade *numbers* therefore computes an approximately geometric mean of PDs with
the wrong weights, and produces a "mean grade" of e.g. 5.4 that corresponds to
no rating. The rule is: map each facility's grade through the master scale to a
PD, exposure-weight in PD space, then (for display only) map the result back to
the nearest grade. `shared/domain/constants.py` already carries
`DEFAULT_PD_CRR_MASTER_SCALE` and `CRR_MASTER_SCALE_SHEET_NAME`, so the mapping
table exists and should be reused rather than re-declared.

### Where the weight comes from (D2)

`results.pd`, `results.pd_crr` and `results.lgd` carry no EAD column, so the
weight is joined in from `results.ead`.

**Join key** — the run identity **minus `Model Name`**, plus the row grain
(Q19):

```
(Segment Name, Month End Snapshot, Run For, Scenario, J/N Flag)
  + Facility ID + Credit Instrument ID + Quarter
```

`Model Name` is deliberately excluded: the EAD run names the EAD model, which is
not the PD or LGD model it supplies weights to. Joining on the full run key
would match nothing.

The join runs **after** the §3 dedupe and **before** any aggregation, in
`domain/exposure.py::attach_exposure_weights()` — pure, unit-testable, and
independent of Dash.

#### Which EAD — forecast or actual?

This matters more than it looks, and the answer is "both, for different
purposes".

- **Own-vintage weighting** (the "as forecast" view): the forecast aggregate for
  vintage *V* at quarter *q* is weighted by the EAD forecast from the *same*
  vintage and quarter. This is internally consistent — it is the portfolio PD
  the model actually implied at the time, and it is what was reported then.
- **Fixed-weight variant** (the "isolated model error" view): weight *both* the
  forecast and the actual by the **actual** EAD for the target quarter. This
  removes the exposure mix effect.

The second exists because own-vintage weighting silently blends two model
errors: if the PD model is perfect but the EAD model over-forecast exposure in
high-PD segments, the aggregate PD is wrong anyway, and the dashboard would
attribute an EAD failure to the PD model. Holding weights fixed at realised
exposure is the standard way to isolate the metric under test.

**Recommendation:** compute both. Show the fixed-weight variant as the headline
PD/LGD error (it answers "is the PD model right"), and the own-vintage variant
alongside (it answers "was the reported number right"). They are one argument
apart once the join exists.

**Caveat:** the fixed-weight variant is undefined for the most recent ~9
quarters, because no actual EAD exists there yet (§2). Those points show the
own-vintage variant only, and must be visually distinguished — not silently
blank.

#### Ordering dependency

`results.ead`'s own actual series (§2) must be resolved **before** PD and LGD
actuals can be weighted. The service layer therefore runs in a fixed order:

```
dedupe (§3)
  → aggregate results.ead        (sum; needs no weight)
  → resolve actual EAD series    (§2 applied to the EAD tab)
  → attach exposure weights      (join, both variants)
  → aggregate pd / pd_crr / lgd  (§1 weighted means)
  → aggregate results.nco        (sum)
  → errors (§4 domain/errors.py)
```

This is orchestration, so it belongs in
`services/backtesting_service.py`, calling pure functions in `domain/`.

#### Coverage is a first-class output, not a footnote

The join will not match everything. Every aggregate therefore carries coverage
metadata:

- **row coverage** — matched rows / total rows on the metric tab;
- **exposure coverage** — matched EAD / total EAD available for that
  (segment, snapshot, quarter);
- **unmatched facility count**.

Unmatched rows are **dropped**, not equal-weighted. Mixing weighted and
unweighted rows produces a number that is neither, and is impossible to
reconcile. Dropping is defensible precisely because the coverage figure is shown
next to it.

Coverage below the Q22 threshold flags the aggregate in the UI (an existing RAG
tone on the card — no new visual vocabulary). An aggregate at 60% exposure
coverage is not a small caveat; it is a different portfolio.

### Fallbacks if the join proves unusable

Recorded in priority order, in case Q20 or Q21 breaks the join in practice:

1. **Add the `EAD` column to the metric tabs** when generating the workbook —
   removes the join entirely (see D2).
2. **Weight by a different exposure measure** if the workbook carries one
   (limit or balance). Monitoring's constants already name
   `LIMIT_AMOUNT_COLUMN` and `BALANCE_COLUMN`, though for `portfolio.xlsx`, not
   this workbook.
3. **Unweighted mean with a loud, permanent caveat on every affected card.**
   Last resort. It is a materially different metric, and it must never be
   presented as if it were exposure-weighted.

### Rules that apply to every metric

- **Zero, null or negative EAD** is excluded from both the weight and the
  numerator, and counts toward the unmatched total above.
- **Forecast and actual must be aggregated over comparable populations.** If a
  facility is present in the forecast but absent from the actual (or vice
  versa), the level difference is a population effect, not model error. Record
  the population count on both sides and expose the delta; do not silently
  reconcile it.
- **Aggregation is pure and lives in `domain/aggregation.py`**, applied once in
  the services layer. Neither UI nor callbacks compute it — that is the layering
  rule in `CLAUDE.md`.

---

## 2. Deriving a realised "actual"

No result tab has an actuals column, so the actual must be *identified* within
the forecast rows. Four options are visible.

**A. The nowcast diagonal — recommended.**
For target calendar quarter *T*, the actual is the aggregate from the vintage
whose `Month End Snapshot == T`, taken at its shortest horizon
(`Quarter == min(Quarter)` — see Q9). That run was executed at *T* against the
portfolio as it actually stood, with observed rather than projected drivers, so
its zero-horizon value is a measurement rather than a projection. Every target
quarter has exactly one such row set, the actual series is well defined for the
whole history, and it lives inside the same five tabs — no join to a second
source and no workbook change.

**B. A dedicated actuals run.**
Reserve a `Scenario` value (`"actual"`) or a `J/N Flag` value that marks a
realised run. Semantically the cleanest option, and it removes all ambiguity —
but it requires a workbook schema change and a commitment from whoever produces
the data. Worth asking for; not something the app can create.

**C. Join to `portfolio.xlsx`.**
The monitoring workbook already carries genuinely realised columns at
model/segment/quarter grain: `observed_default_rate` and `total_defaults`
(`PD_Performance_Metrics`), `actual_lgd`, `actual_ead`, and `nco_actual` /
`acl_actual` (`Loss_Performance_Metrics`). These are real outcomes, which is
attractive. But they come from a different pipeline at a different grain, keyed
on `reporting_cycle` / `model` / `segment` rather than
`Run For` / `Model Name` / `Segment Name`. Any level difference between the two
pipelines would then show up as model error, which is exactly the failure mode a
backtest must not have.

**D. Latest vintage wins.** Use the most recent vintage covering *T*. Rejected:
for recent *T* the most recent vintage is still a projection, so the "actual"
would be a forecast.

### Recommendation

**Option A**, isolated behind a single pure function —
`domain/actuals.py::resolve_actual_series(...)`. Everything downstream consumes
its output, so switching to B or C later is a one-module change with no ripple
into charts, errors or exports.

### What breaks if A is wrong

The failure mode is that the `Quarter == min` row is itself a **model fit under
a scenario** rather than an observed value. If so, every "error" the dashboard
reports is really vintage-to-vintage model drift, and the whole dashboard
measures the wrong thing — plausibly, with small short-horizon errors that look
like a well-calibrated model.

Two detection tests, both cheap and both worth building into M3 as assertions:

1. **The actual series must be invariant to `Scenario`.** A realised outcome
   cannot depend on which scenario was run. If flipping Scenario moves the
   actual, A is wrong.
2. **The actual series must be invariant to `J/N Flag`** for the same reason
   (assuming Q6 — a judgemental overlay applies to forecasts, not to what
   happened).

Two further consequences that hold under *any* option and must be handled in the
UI regardless:

- **The most recent ~9 quarters have no actual** — no vintage has reached them
  yet. Those points render forecast-only, and no error is plotted or scored for
  them. A chart that silently drops them would misrepresent the horizon.
- **Actuals are revised.** Under A, if a later vintage restates *T*, the dedupe
  rule in §3 chooses which row set wins. Show the winning
  `Execution Datetime` so a revision is visible rather than mysterious.

---

## 3. Using `Execution Datetime` to dedupe

The run key is:

```
(Segment Name, Model Name(s), Month End Snapshot, Run For, Scenario, J/N Flag)
```

Re-running the same configuration produces several row sets sharing that key and
differing only in `Execution Datetime`.

**Rule: keep the row set with `max(Execution Datetime)` per run key, and drop
every earlier execution wholesale.**

"Wholesale" is the load-bearing word. A row-level `max` would let a partial
re-run — one that emitted, say, quarters 0–4 — mix its rows with quarters 5–9
from the previous execution, producing a projection path that is internally
inconsistent and can be non-monotonic at the seam. Deduping at run granularity
makes that impossible.

Implementation notes:

- Applied in `repositories/loader.py` **immediately after read, before any
  aggregation**, so nothing downstream ever sees a superseded row. That also
  means the aggregates in §1 are computed on exactly one execution.
- Parse with `pd.to_datetime(..., errors="coerce")`. A row with an unparseable
  or missing timestamp becomes `NaT` and must never win over a real timestamp —
  make that explicit rather than relying on sort placement.
- **Exact ties** (two executions with an identical timestamp): keep the last in
  file order and log a warning. Deterministic and visible, rather than
  arbitrary and silent.
- Carry the winning `Execution Datetime` forward as run metadata so the UI can
  show "as executed &lt;ts&gt;" on the card.
- Carry a **superseded-run count** as well, for a data-quality note. A run key
  with 40 superseded executions is worth surfacing.
- Assert Q17 here too: after dedupe, `Facility ID + Credit Instrument ID` should
  be unique within (run key, Quarter). If it is not, aggregates double-count,
  and it is far cheaper to fail loudly at load than to debug a wrong number in a
  chart.

---

## 4. Scenario comparison, and the other scenarios in the UI

**Backtesting compares against Baseline only** (`"baseline"` — the value SAAS
already uses in `SAAS_SCENARIO_LABEL_MAP`, so labels stay consistent across
dashboards).

A backtest asks "did the model predict what actually happened". Only the
baseline path is a central-tendency forecast of what was expected to happen.
Severe and stress paths are *deliberately* conservative: comparing them against
realised outcomes measures the size of the conservatism buffer, not model
accuracy. Doing so would produce a large, systematic, entirely intended
over-prediction — and any RAG built on it would flag a correctly-behaving model
as a failure.

### What happens to the other scenarios

- **The Scenario filter stays in the top bar**, for parity with the other two
  dashboards, but is **defaulted and locked to Baseline** on every error, RAG and
  export surface. Render the other options present-but-disabled with a
  `monitoring-filter-help` line explaining why. Removing the filter entirely
  would read as an oversight next to Monitoring and SAAS; disabling it with a
  reason reads as a decision.
- **Optionally, a context-only overlay.** A "show scenario envelope" toggle
  draws the non-baseline paths as dashed reference lines on the projection
  chart, so a reader can see where the realised outcome sat inside the scenario
  fan. These traces are decoration: they never feed an error metric, a RAG, or
  an export.
- If the envelope is judged scope creep for v1, drop it and keep the
  disabled-with-explanation filter. Do not drop the filter.

---

# STRUCTURE

## 5. Module layout for `features/backtesting/`

`features/saas/` is the smallest complete template (its `stores.py` docstring
calls this the "onboarding contract"), so this mirrors it.

```
features/backtesting/
├── README.md              Routes, data sources, per-dashboard conventions
├── __init__.py
├── page_registry.py       PAGES: tuple[PageDefinition, ...]
├── dashboard.py           DASHBOARD = DashboardDefinition(...)
├── data_access.py         BACKTESTING_PAGE_DATA, loaded once at import time
├── stores.py              build_stores() -> []  (page keeps stores inline)
│
├── repositories/
│   └── loader.py          Reads the 5 result tabs; §3 dedupe; dtype
│                          normalisation; filter catalogs; empty-payload
│                          fallback. Feature-private — only data_access
│                          imports it.
│
├── services/
│   ├── backtesting_service.py   Orchestration in the fixed order set out in
│   │                            §1: dedupe → EAD aggregate → actual EAD →
│   │                            exposure join → weighted aggregates → errors
│   └── exports.py               (later milestone; dcc.Download pattern)
│
├── domain/                Pure. No Dash imports, no I/O.
│   ├── exposure.py        attach_exposure_weights (§1/D2): the cross-tab join,
│   │                      both weighting variants, coverage accounting
│   ├── aggregation.py     Per-metric aggregators (§1) + the AGGREGATORS map
│   ├── actuals.py         resolve_actual_series (§2), vintage selection
│   ├── errors.py          Error / bias / MAE / RMSE by horizon; RAG banding
│   ├── selectors.py       Filter selections → scoped runs (SAAS selectors shape)
│   └── records.py         Forecast/actual record shaping for the charts
│
├── ui/                    Dash composition ONLY. No calculations, no I/O.
│   ├── pages/
│   │   └── backtesting.py       Thin registration entrypoint (page_layout)
│   └── views/
│       ├── backtesting.py       Layout: top bar, sub-nav, five metric sections
│       ├── components.py        Reusable view blocks
│       └── figures.py           Thin wrappers over shared/ui/charts.py
│
├── callbacks/
│   └── backtesting.py     Idempotent register_callbacks(app)
│
└── tests/
    ├── conftest.py        sys.path shim (parents[4]), copied from saas
    ├── test_loader.py     Dedupe, empty payload, uniqueness assertion
    ├── test_exposure.py   Join key, fan-out guard, coverage accounting
    ├── test_aggregation.py / test_actuals.py / test_errors.py   Pure units
    ├── test_backtesting.py        Layout-builds test
    └── test_callbacks.py          Stub-app callback tests
```

### Layer discipline

- `ui/` has no I/O and no calculations. Aggregates arrive from `services/`
  already computed.
- `domain/` has no Dash imports. Everything in §1–§2 is testable without Dash.
- `repositories/loader.py` is feature-private; only `data_access.py` reads it.
- Data-domain constants (sheet names, column names, RAG bands) go in
  `shared/domain/constants.py`, **never inline in the loader** — that is an
  explicit `CLAUDE.md` rule. Workbook *locations* go in `config/settings.py`.

### Pages

**Recommendation: one page, `/backtesting`, with five metric sections** (PD, PD
CRR, LGD, EAD, NCO) reached through a `monitoring-section-subnav` bar. The
sections map 1:1 to the five result tabs, which keeps the mental model simple,
and it matches the PD page's chapter/section structure. Because routing is
registry-driven, splitting into five pages or adding a "Vintage Analysis" page
later is a `page_registry.py` edit with no central changes.

### Wiring checklist

| File | Change |
|---|---|
| `features_registry.py` | Append `backtesting_dashboard` to `DASHBOARDS` after SAAS. `PRIMARY_DASHBOARD` unchanged. |
| `config/settings.py` | Add the `backtesting_file` property. |
| `shared/domain/constants.py` | Sheet names, column names, CRR reuse. |
| `features/backtesting/dashboard.py` | `register_callbacks` guarded by `already_registered(app, "dashboard:backtesting")`. |
| `features/backtesting/callbacks/backtesting.py` | Guarded by `already_registered(app, "page:backtesting.backtesting")`. |

Once registered, `tests/test_registry.py` and `tests/test_shell.py` cover the new
dashboard for free (unique paths, reachability, callable page definitions,
sidebar grouping). Run those **first** — cheapest signal that the wiring is right.

### Callback rules that apply

From `CLAUDE.md`'s callback-wiring section, all four are live here because the
top bar has a Segment ↔ Model cascade:

1. Never take a callback's own output prop as an `Input` — use `State`.
2. Two-way cascades listen to the option buttons' `n_clicks`, not the value; read
   the picked value from `ctx.triggered_id`, not from `State`; and guard against
   the remount firing with `n_clicks == 0`.
3. Never mix `Input`s from inside a callback-rendered container with `Input`s
   from outside it — the callback body silently never runs.
4. Do not copy the mutually-syncing select-all pattern; it is known-unfixed.

---

## 6. Shared presentation vocabulary — inventory

`assets/styles.css` defines 868 classes. They fall into three groups.

### Generic — reuse as-is

| Group | Classes |
|---|---|
| Page chrome | `page-shell`, `top-bar`, `content`, `main`, `tab-panel` (+`.active`), `section-card`, `section-title`, `chart-box` |
| Buttons | `btn`, `btn-primary` |
| Dropdowns | `checkbox-dropdown`, `checkbox-dropdown-toggle`, `checkbox-dropdown-menu` (+`.open`), `single-select-dropdown`, `single-select-option` (+`.is-selected`), `single-select-option-label`, `single-select-option-check` |
| Loading | all 24 `dashboard-loading-*` classes |
| Shell / theme | `monitoring-shell`, `theme-light`, `theme-dark`, `app-theme-*`, `sidebar*`, `nav-*` |

### `monitoring-*` is generic despite its name

All 13 `monitoring-*` classes are top-bar / filter / sub-nav chrome, not
Monitoring-dashboard styling. SAAS already uses `monitoring-controls`,
`monitoring-filter`, `monitoring-filter-help`, `monitoring-model-filter`,
`monitoring-dashboard-title` and the `monitoring-section-subnav*` family
verbatim — that is the rule-of-two precedent. Backtesting uses them directly.
Do not rename them, and do not duplicate them under `bt-`.

Full list: `monitoring-shell`, `monitoring-controls`, `monitoring-filter`,
`monitoring-filter-help`, `monitoring-model-filter`,
`monitoring-dashboard-title`, `monitoring-primary-filter-row`,
`monitoring-section-subnav`, `-subnav-group`, `-subnav-label`, `-subnav-links`,
`monitoring-top-select`, `monitoring-point-select`.

### Page-specific — do not reuse

- `overview-*` (311 classes) — the Monitoring Overview page only.
- `saas-*` (65) — the SAAS workspace only.
- `lgd-*` (11), `loss-*` (11) — those pages' flow diagrams only.

### `pd-*` is the awkward middle

331 classes, mostly PD-page-specific — but a documented subset is already
de-facto generic, because SAAS uses it. Verified by grepping SAAS's views and
callbacks, SAAS currently emits 48 `pd-*` classes, including:

`pd-content-section`, `pd-live-section`, `pd-performance-app`,
`pd-performance-note`, `pd-content-kicker`, `pd-section-subtitle`,
`pd-info-chip`, `pd-range-controls`, `pd-models-checklist`, `pd-models-search`,
`pd-models-select-all`, `pd-mev-filter-actions`, `pd-mev-filter-reset`,
`pd-mev-chart-title`, `pd-mev-chart-meta`, `pd-mev-empty-state`.

**Read `pd-` as a legacy prefix meaning "platform default chrome", not "the PD
page".** Renaming it is out of scope — `CLAUDE.md` forbids renaming existing
element IDs and keys, and it would mean rewriting ~331 selectors and every view
that emits them.

### The rule for backtesting

Reuse generic and `monitoring-*` classes directly. Reuse `pd-*` classes **only
through the builders that already emit them** — `build_range_controls`,
`build_chart_header`, `build_section_subnav`, `build_dashboard_loading_shell`
from `shared/ui/`, plus the five card builders imported from monitoring per §7
(D1). Do not hand-write `pd-` class strings in backtesting views. Anything
genuinely new gets a `bt-` prefix and lives in `assets/backtesting.css` (§9).

Because no card builder is being modified, the `pd-*` card CSS
(`pd-test-card`, `pd-test-status-*`, `pd-rag-dot`, `pd-domain-heading`,
`pd-chapter-heading`, …) is reused untouched and needs no `bt-` equivalent.

---

## 7. `cards.py` promotion — DECLINED (D1). Monitoring is not touched.

> **Decision: nothing moves.** The promotion described below was proposed and
> rejected; it is kept as a record of what was considered and why the current
> shape is a deliberate choice rather than an oversight. The *Adopted approach*
> at the end of this section is what gets built.

### What backtesting needs

Five builders from `features/monitoring/ui/views/cards.py`:
`build_pd_test_card`, `build_pd_section_rag_card`, `build_pd_section_heading`,
`build_pd_chapter_heading`, `pd_rag_dot` — plus three private helpers they
depend on: `_info_chip`, `_meta_rows`, `_snapshot_meta`.

Current consumers, all inside monitoring: `overview.py`, `pd_performance.py`,
`lgd_performance.py`, `ead_performance.py`, `loss_performance.py`,
`post_subjective.py`. Backtesting would be the second **dashboard** consumer,
which satisfies the rule of two.

### The promotion that was proposed (not happening)

New module: **`shared/ui/cards.py`**.

| Move from `features/monitoring/ui/views/cards.py` | To `shared/ui/cards.py` as | Rationale for the rename |
|---|---|---|
| `build_pd_test_card` | `build_test_card` | Already metric-agnostic — it takes `metric`, `thresholds`, `context`. The `pd_` prefix is now misleading. |
| `build_pd_section_rag_card` | `build_section_rag_card` | Same. |
| `build_pd_section_heading` | `build_section_heading` | Same. |
| `build_pd_chapter_heading` | `build_chapter_heading` | Same. |
| `pd_rag_dot` | `rag_dot` | Same. |
| `_info_chip`, `_meta_rows`, `_snapshot_meta` | unchanged names, still private | Only these five need them. |

**Stays in `features/monitoring/ui/views/cards.py`** (monitoring-only):

- `build_pd_ead_card` — the EAD-share card, specific to monitoring's EAD section.
- The nine `build_pd_overview_flow_*` / `build_pd_overview_heatmap` builders and
  their helpers `_flow_connector_spans`, `_flow_note_options`,
  `_notching_flow_options` — the 1.1 Overview process-flow diagram.

Note that `build_pd_overview_flow_metric` and `build_pd_overview_flow_performance`
call `pd_rag_dot`, so after the move they import `rag_dot` from `shared/ui/cards.py`.

### CSS would have stayed put

The promoted builders would have kept emitting their existing `pd-*` class names
(`pd-test-card`, `pd-test-status-*`, `pd-rag-dot`, `pd-domain-heading`,
`pd-chapter-heading`, `pd-content-kicker`, …). Renaming those classes is out of
scope for the reasons in §6. Shared builders, `pd-` classes — documented, not
accidental.

### Compatibility shim

Keep the old names in `features/monitoring/ui/views/cards.py` as re-export
aliases:

```python
from ....shared.ui.cards import build_test_card as build_pd_test_card   # etc.
```

Six monitoring view modules keep their current import lines unchanged, the diff
stays one line per name instead of touching six large files, and the change is
consistent with the repo's existing `layout.X` re-export convention (noted in
`CLAUDE.md` as a live pattern, not an accident).

### Adopted approach (D1)

**Backtesting imports the five builders directly from monitoring, under their
existing names, and monitoring is not modified at all:**

```python
from ...monitoring.ui.views.cards import (
    build_pd_chapter_heading,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_test_card,
    pd_rag_dot,
)
```

Consequences, recorded so they are choices rather than surprises:

- **No file in `features/monitoring/` changes**, which is the point. There is no
  shim, no rename, and no risk of regressing six monitoring view modules.
- **The `pd_` names stay** in backtesting's code. Read them the same way as the
  `pd-` CSS prefix (§6): legacy naming for platform-default card chrome, not a
  claim about the PD page. Worth one comment at the import site so the next
  reader doesn't file it as a bug.
- **The dependency direction is inverted** — a feature importing from a sibling
  feature's `ui/` layer, rather than both depending on `shared/`. There is one
  existing precedent: `features/saas/repositories/loader.py` imports
  `load_pd_mev_catalog` from monitoring's repository, and its module docstring
  explicitly flags that as the one place it reaches across. Backtesting's
  `ui/views/` should carry the same kind of note.
- **Monitoring's `cards.py` becomes a de-facto shared API without being marked
  as one.** A future change to those five signatures now breaks a second
  dashboard silently. Worth a short comment in monitoring's module — but that is
  itself an edit to monitoring, so it is **not** done here; noted for whenever
  monitoring is next legitimately in scope.

**Revisit trigger.** If a third consumer appears, or if the cross-feature import
causes a real problem (a circular import, or a monitoring change that breaks
backtesting), the promotion above is the ready-made answer — reopen this section
rather than re-deriving it.

**Not chosen:** duplicating the five builders under `bt-` names with parallel
CSS. That guarantees drift between two card implementations and is the outcome
the rule of two exists to prevent.

---

## 8. Theme-aware figures

New figures reuse the existing theming machinery in `shared/ui/charts.py`. No
new palette, no per-theme CSS for charts.

- **Theme threading.** Every builder takes `theme: str = "light"`, normalised
  through `normalize_theme_value` before it reaches the chart layer — the SAAS
  pattern (`selectors.normalize_theme_value` → `build_saas_mev_time_series_figure(theme=...)`).
  The active theme reaches the callback from `shared.theme.APP_THEME_ID`.
- **Colours** come from `_saas_theme_palette(theme)`, which returns the
  light/dark dict from `SAAS_THEME_PALETTES`: `axis_title`, `axis_tick`,
  `grid_color`, `axis_line`, `zero_line`, `marker_fill`, `legend_bg`,
  `legend_border`, `legend_font`, `hover_bg`, `hover_font`, `annotation_bg`,
  `annotation_text`, `empty_message`, `projection_band_fill`,
  `development_marker`, `scenario_date_marker`, `minmax_fill`.
- **Trend and reference lines** use `_monitoring_trend_line_color(theme)`.
- **Every figure ends with `_apply_transparent_background(fig)`.** This is *how*
  charts follow the theme: the card's CSS background flips with the theme and
  shows through the transparent plot. A figure with an opaque background is a
  white rectangle in dark mode.
- **No-data path** uses `_empty_figure(message, theme=theme)` — never a blank
  `dcc.Graph`. Backtesting will hit this often: the most recent ~9 quarters have
  no actual (§2).
- **Quarter axis** uses `build_pd_time_series_xaxis(labels, density=...)`, which
  gives the shared `YYYYQn` category axis, the compact quarter tick labels, and
  the fixed tick-count budget (`tight` 4 / `compact` 6 / `normal` 8 / `roomy` 10)
  used everywhere else.
- **`AXIS_LINE_COLOR` / `GRID_COLOR`** are module-level light-theme constants
  (`#cbd5e1`) used by the older PD RAG-dot trend builders. New builders should
  prefer `palette["axis_line"]` / `palette["grid_color"]`, which are
  theme-aware; use the constants only where matching an existing light-only
  chart exactly.
- **Scenario colours and labels** come from `SAAS_SCENARIO_COLOR_MAP` /
  `SAAS_DARK_SCENARIO_COLOR_MAP` via `_saas_scenario_color`, and
  `SAAS_SCENARIO_LABEL_MAP` for text — so "Baseline" and "Severe" read
  identically across all three dashboards (§4).

### Where the new builders live

The helpers listed above (`_saas_theme_palette`, `_monitoring_trend_line_color`,
`_apply_transparent_background`, `_empty_figure`) are underscore-private to
`shared/ui/charts.py`. Importing privates across modules is the wrong shape.

**Recommendation: put the `build_backtesting_*` figure builders inside
`shared/ui/charts.py`**, alongside the SAAS ones, and keep
`features/backtesting/ui/views/figures.py` as the thin filter-applying wrapper —
exactly the shape `features/saas/ui/views/figures.py` already has.
`build_saas_mev_time_series_figure` lives in `shared/ui/charts.py` for the same
reason, and `CLAUDE.md` states outright that both dashboards' figure builders
live there. This adds no new public API.

The trade-off: `shared/ui/charts.py` is already 2,512 lines and this grows it.
The alternative — promoting four helpers to public names (`theme_palette`,
`empty_figure`, `apply_transparent_background`, `trend_line_color`) and building
figures inside the feature — is defensible and arguably cleaner, but it is a new
shared API surface and diverges from the established pattern.

**D1 settles this by analogy: no existing code moves or gets renamed.** Adding
`build_backtesting_*` functions to `shared/ui/charts.py` is purely additive — it
relocates nothing and changes no existing signature — which is consistent with
the decision in §7, whereas renaming four private helpers to public names is the
same kind of churn D1 declined. Recommendation stands: follow the SAAS
precedent.

### Plotly caveat

`plotly.py` in the venv is much newer than the plotly.js Dash bundles (v2.25.x).
Newer features silently no-op in the running app even though the Python API
accepts them. Hover and zoom behaviour must be verified with the Playwright
harness (a test page embedding Dash's own `plotly.min.js`) or reported as
unverified — not assumed working.

---

## 9. CSS — confirmations and two gotchas

**Confirmed, as specified:**

- New CSS goes in **`assets/backtesting.css`** (Dash auto-loads everything in
  `assets/`, including subfolders).
- All new classes carry a **`bt-`** prefix.
- **No new palette and no new CSS variables.** All colours come from the
  existing `:root` variables in `styles.css`.

### Gotcha 1 — `backtesting.css` loads *before* `styles.css`

Dash walks the assets folder with `sorted(files_gen)` (verified in
`dash/dash.py::_walk_assets_directory`), so `assets/backtesting.css` is served
**before** `assets/styles.css`. A `bt-` rule at equal specificity that tries to
override a `styles.css` rule will lose the cascade.

Mitigation: keep `assets/backtesting.css` to `bt-`-prefixed selectors only. Never
restyle a generic class from it. If a generic class is not right for a surface,
that is a signal to compose differently, not to override.

### Gotcha 2 — which variables actually flip in dark mode

Dark theme is scoped as `.monitoring-shell.theme-dark <selector>` (640
occurrences). Inside the `.monitoring-shell.theme-dark { … }` block, these
`:root` variables are re-bound and therefore flip automatically:

`--text`, `--text-muted`, `--border`, `--gray-light`, `--navy`, `--navy-accent`,
`--blue`, `--blue-light`, `--green`, `--red`, `--card-shadow`, `--pd-line`,
`--pd-panel`

These are **not** re-bound and will render a light-theme colour on a dark
surface: **`--pd-blue`, `--pd-blue-soft`**. Avoid them in `bt-` rules.

The block also *defines* a `--dark-*` family (`--dark-surface`, `--dark-text`,
`--dark-muted`, `--dark-accent`, `--dark-border`, …) available to any explicit
`.monitoring-shell.theme-dark .bt-x { … }` rule that genuinely needs one.

Also: several generic rules hard-code `#fff` (`.btn`, `.section-card`,
`.checkbox-dropdown-toggle`) and are overridden in the dark block from line 1627.
Do not hard-code `#fff` in `bt-` rules — use `var(--pd-panel)` or add an explicit
dark rule.

### JavaScript

- `assets/js/dropdown_click_outside.js` already handles click-away for **any**
  `.checkbox-dropdown` menu, so backtesting's dropdowns get that behaviour free
  by using the shared markup.
- If the metric sub-nav is added, it needs `assets/js/backtesting_subnav.js`
  modelled on `monitoring_pd_subnav.js`, keyed on `#bt-subnav`. The existing
  sub-nav scripts are id-scoped, so they will not pick up a new bar.

---

## 10. Milestones

Each milestone ends with the full suite green — `python -m pytest features/saas/tests
features/monitoring/tests shared tests -q` — plus the new feature's own tests.
A milestone is not done until it is.

| # | Milestone | Deliverable | Tests / verification |
|---|---|---|---|
| **M0** | Plan + decisions | This document. D1 and D2 are answered. Remaining gating questions: **Q9** (Quarter origin) and **Q19–Q21** (the exposure join), which gate M3. | — |
| **M1** | Workbook contract | `source_data/backtesting.xlsx` (next task). `settings.backtesting_file`. Sheet/column names into `shared/domain/constants.py`. | Constants import; path resolves. |
| **M2** | Loader + `data_access` | Read 5 tabs; §3 run-level dedupe; dtype normalisation; filter catalogs; empty-payload fallback on read failure (SAAS pattern). | Dedupe keeps latest per run key; superseded rows absent; NaT never wins; facility-uniqueness assertion; empty payload on missing file. |
| **M3a** | Domain — **exposure join** (new, from D2) | `domain/exposure.py`: the cross-tab join on the reduced run key, both weighting variants, coverage accounting. | Pure unit tests. **Fan-out guard (Q20): a duplicated EAD row must fail loudly, not silently multiply.** Coverage figures correct on a fixture with deliberate gaps; unmatched rows dropped, never equal-weighted. |
| **M3b** | Domain — aggregation + actuals | `domain/aggregation.py` (§1), `domain/actuals.py` (§2). CRR master-scale mapping reusing `DEFAULT_PD_CRR_MASTER_SCALE`. | Pure unit tests. **Includes the two §2 invariance assertions** (actual invariant to Scenario and to J/N Flag) — these validate the whole design. Plus: weighted mean ≠ simple mean on a skewed-exposure fixture, so the weighting is actually proven to be applied. |
| **M4** | Domain — errors, selectors, records | `errors.py` (error / bias / MAE / RMSE by horizon, RAG banding), `selectors.py`, `records.py`. | Pure unit tests, no Dash imports. |
| **M5** | Registry wiring skeleton | `dashboard.py`, `page_registry.py`, `stores.py`, `ui/pages/`, minimal layout (top bar + apply prompt + empty canvas), `features_registry.py` entry, `features/backtesting/README.md`. | **Run `tests/test_registry.py` and `tests/test_shell.py` first** — cheapest wiring signal. Plus a layout-builds test. |
| ~~**M6**~~ | ~~Cards promotion~~ | **Removed — declined (D1).** Backtesting imports monitoring's card builders directly (§7). No milestone, no monitoring edits. | — |
| **M7** | Figures | `build_backtesting_*` builders (§8) + `ui/views/figures.py` wrapper. | Figures build for `light` and `dark`; empty-data path returns `_empty_figure`. |
| **M8** | Page content | Five metric sections, cards (imported per §7), sub-nav, apply-filters gating (SAAS interaction model). **Includes the coverage surface from §1** and the forecast-only rendering for quarters with no actual (§2). | Layout-builds per section; card content assertions; a low-coverage fixture renders the flagged tone. |
| **M9** | Callbacks | Filters, Segment↔Model cascade, apply, theme sync — following all four callback rules in `CLAUDE.md`. | Stub-app callback tests. **Plus a browser check: dev-tools console error count before/after.** pytest does not catch dependency cycles. |
| **M10** | CSS + JS | `assets/backtesting.css`; `assets/js/backtesting_subnav.js` if the sub-nav lands. | Browser verification in **both** light and dark (Playwright, sandbox off; restart the app — no hot reload). |
| **M11** | Docs | `features/backtesting/README.md`; root `README.md` (dashboard list, project layout, data sources, routes); `CLAUDE.md` "two dashboards" → three. | Prose review. |
| **M12** | Optional — exports | `services/exports.py` following the existing `dcc.Download` pattern, heavy build delegated to services. | Export-builder unit tests. |

**Critical path:** M1 → M2 → **M3a** → M3b → M4 → M5 → M7 → M8 → M9 → M10 → M11.
M12 is optional.

M3a is new and sits on the critical path — under D2 nothing downstream of it can
produce a correct PD, PD CRR or LGD number, so it is worth building and testing
before any UI work starts.

**Blocked now:** M3a needs Q19–Q21 answered (the join key, the fan-out rule, and
horizon alignment); M3b needs Q9. Nothing else is blocked — M1 and M2 can start
as soon as the workbook exists, and the answers to Q19–Q21 may fall out of
building it.
