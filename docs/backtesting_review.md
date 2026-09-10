# Backtesting dashboard review and improvement proposal

This is a read-only audit of the current implementation and the rendered Dash
page. No application code, source workbook, or dependency has been changed.

The live-page review used the default applied scope (all populations, all model
use case / cycles, Base scenario, both J/N flags, all vintages) and inspected all
six sections. The page rendered 17 Plotly charts: two in Overview and three in
each of the five metric sections. Browser verification covered light and dark
themes, hover labels, drag-to-zoom, the six sub-navigation targets, and console
errors. Plotly.py is 6.8.0 while Dash bundles Plotly.js 2.25.2, so the findings
below distinguish Python figure configuration from what actually rendered.

## 1. WHAT THE PAGE ANSWERS TODAY

A backtest needs to answer:

1. Is the model biased?
2. Does accuracy decay with horizon?
3. Is a problem systemic or isolated to one vintage or segment?
4. For NCO, does the error come from PD, LGD, or EAD?

| Existing figure | Question(s) it addresses | Assessment |
|---|---|---|
| `build_forecast_actual_figure` | Primarily (a); weakly (c) by calendar period and vintage | This is the most useful current level view. The actual line and forecast paths show over- or under-forecasting in context, and the right panel exposes signed percentage errors. It does not aggregate the direction into an explicit bias diagnostic or show tolerance bands. At the default scope it also joins unrelated records into the same vintage line: there are 2 PD, 4 PD CRR, 8 LGD/EAD, and 24 NCO records for each unique vintage-target pair, but the figure groups only by vintage. The resulting vertical/zig-zag connections are not a valid forecast path. |
| `build_horizon_error_figure` | Directly (a) and (b) | This is the best-aligned existing figure. MAPE answers magnitude/decay and bias answers direction. It is weakened by missing accuracy thresholds, falling sample counts being hover-only, raw/unformatted bias units, and positive-bias-is-green/negative-bias-is-red marker logic. It answers nothing about which vintage, segment, or NCO component caused the pattern. |
| `build_vintage_curve_figure` | At most a weak version of (c) | Raw projected paths by cohort age can reveal an unusual-looking vintage, but there is no actual or error on the chart. A high or low path may simply reflect the portfolio state rather than poor accuracy. It therefore does not reliably answer any of the four questions. It is also reused for the two Overview loss charts, even though those are portfolio-development views rather than backtest diagnostics. |
| `build_cumulative_loss_figure` | None of (a)-(d) | It answers “how much NCO has accumulated for each static pool by age,” not whether the forecast was accurate. It is potentially useful in portfolio monitoring, but it is not a backtest result. |
| `build_periodic_loss_figure` | None of (a)-(d) | It answers “when did each pool's losses arrive.” That is useful context, but it is not forecast error. It partially duplicates NCO-by-vintage because both show the timing pattern of raw NCO, with the periodic chart merely normalizing by opening EAD. |

No current figure answers question (d). Question (c) is only weakly served: no
chart localizes error by segment, and the raw vintage chart can confuse a real
level difference with an accuracy problem.

There is also a correctness issue beneath the figures that must be resolved
before interpreting them. Aggregates retain run/model/J-N identity, while the
actual lookup keys only on segment and target quarter. Multiple distinct anchor
values therefore overwrite the same dictionary key. Conversely, the forecast
chart collapses multiple runs to one line by vintage. The default live page
showed 36 unique vintage-target combinations but 72 PD records, 144 PD CRR
records, 288 LGD records, 288 EAD records, and 864 NCO records. Those are
alternative or subpopulation records, not repeated observations that may be
connected or scored against an arbitrary shared actual.

## 2. INFORMATION ARCHITECTURE

The current metric-major structure is not the right primary architecture. It
turns three chart shapes into 15 near-identical charts, then adds two unrelated
loss-development charts. The rendered page is roughly nine thousand vertical
pixels at a 1440 px desktop viewport. The repetition makes cross-metric diagnosis
hard: answering “does accuracy decay?” means manually comparing five distant
horizon charts, and answering “what drove NCO?” is impossible.

I recommend a hybrid structure: a cross-metric diagnostics chapter organized by
the four questions, followed by thin metric detail sections.

### Proposed page structure

1. **Backtest scorecard — “Is anything wrong?”** A cross-metric table/strip with
   PD (including the PD CRR population), LGD, EAD, and NCO as rows and scored
   count, signed percentage bias, MAE, RMSE, MAPE, hit rate, and RAG as columns.
   It must show the comparison grain and paired coverage rather than silently
   combining alternative runs.
2. **Bias and calibration — “In which direction, and at what scale?”** One
   metric-selectable actual-versus-predicted scatter with a 45-degree line,
   horizon color, and a concise signed-error distribution or bias readout.
3. **Horizon decay — “Does the model get worse further out?”** One cross-metric
   horizon chart using scale-free measures (MAPE and hit rate), with sample counts
   and the approved RAG bands. Raw-unit bias belongs in the selected metric detail,
   not on a cross-metric axis.
4. **Localization — “Systemic, one vintage, one segment, or one calendar
   event?”** One diagnostic surface with a metric selector and two compact
   heatmaps: vintage × horizon and segment × horizon. This is where signed error,
   target quarter, counts, and coverage belong.
5. **J/N effectiveness — “Did the judgmental overlay help?”** One paired,
   cross-metric comparison of the change in absolute percentage error, with pair
   coverage and results by horizon.
6. **NCO attribution — “Which component drove the NCO miss?”** An NCO-only
   waterfall that reconciles PD, LGD, EAD, and any residual to total NCO error.
7. **Metric detail — “Show me the underlying path.”** Four thin sections: PD,
   LGD, EAD, and NCO. Each gets one correctly-grained forecast-versus-actual
   chart and its metric-formatted statistics. `results.pd` and
   `results.pd_crr` are the same probability measure over disjoint populations,
   so they should be facets/subpopulations within PD rather than two full,
   repetitive metric chapters. Internal keys and Dash IDs do not need to be
   renamed.

This preserves metric-specific context without multiplying every new diagnostic
by five. It also follows the house pattern in PD Performance: begin with an
at-a-glance command surface, group detailed analysis by the decision it supports,
and keep long-form detail downstream. As in SAAS, diagnostic display controls
should be local to their chart surface and should not require re-applying the top
scope filters.

Before this reorganization, the service must define a valid analysis grain. A
single “All” value cannot mean “sum the same portfolio across two cycles and two
J/N alternatives.” Model partitions that cover disjoint facilities may be
combined; alternative runs must remain separate, be paired explicitly, or require
a primary selection.

## 3. GAPS

### Vintage × horizon error heatmap — accept, high priority

**Place:** Localization in the cross-metric diagnostics chapter, driven by the
local metric selector.

**Why it earns a place:** It is the highest-information-density answer to
question (c). A vertical band reads as horizon decay, a horizontal band as one
bad vintage, and a diagonal as a common target-quarter/calendar event. The color
must represent mean signed percentage error and be centered on zero; hover should
also report MAPE/absolute error, count, target quarter(s), and coverage so
offsetting errors do not look healthy.

**Domain requirement:** Add a pure matrix builder that groups correctly-grained
error records by `(vintage_quarter, horizon)`, returns mean signed percentage
error, MAPE, count, pair/actual coverage, and target-quarter metadata, and fixes a
symmetric color range after excluding non-finite cells. Do not pivot or average
inside the view.

**Displaces:** All five raw `build_vintage_curve_figure` metric charts. It answers
the intended vintage question using error rather than raw level.

### Actual vs predicted scatter with 45-degree line — accept

**Place:** Bias and calibration in the cross-metric chapter, with one locally
selected metric rather than five permanent copies.

**Why it earns a place:** The time-series chart hides calibration slope,
heteroscedasticity, and horizon-dependent spread. The scatter directly reveals
systematic over/under-prediction around the identity line. For EAD/NCO, compact
currency axes and optional log display may be useful, but the default should stay
linear and preserve zero.

**Domain requirement:** Return one paired point per valid comparison grain with
forecast, actual, horizon, vintage, target quarter, segment/model labels, and
coverage. Return display bounds or enough domain metadata for a shared figure
builder to create an equal-scale square plot without a view-layer calculation.
The domain must first resolve duplicate alternative runs; overplotting invalid
pairs does not become valid merely because it is a scatter.

**Displaces:** The current right-hand error-dot panel of
`build_forecast_actual_figure`. The thin metric detail keeps a simpler level
time series; the cross-metric calibration surface owns the scatter/residual view.

### NCO error attribution waterfall — accept, after the correctness work

**Place:** NCO attribution in the cross-metric chapter and linked from the NCO
detail section.

**Why it earns a place:** It is the only proposed chart that answers question
(d), and the workbook supports it: `results.nco` names the PD, LGD, and EAD model
for each row, and NCO is defined as `PD × LGD × EAD`.

**Domain requirement:** At facility × instrument × vintage × horizon grain,
join the NCO row to the named PD/PD-CRR, LGD, and EAD rows, and join the comparable
actual anchors for the target quarter. Use an order-independent three-factor
Shapley decomposition of
`forecast PD × forecast LGD × forecast EAD - actual PD × actual LGD × actual EAD`.
Aggregate the three contributions only after the facility-level decomposition.
Return join coverage, fan-out validation, and an explicit reconciliation residual
between component-implied error and workbook NCO error. Even though the current
dummy workbook reconciles to floating-point precision, production data must not
silently assume that identity.

**Displaces:** Both static-pool Overview charts and the NCO raw-vintage chart.
The waterfall is a backtest diagnostic; those three are loss-development context.

### J vs N paired comparison — accept

**Place:** J/N effectiveness in the cross-metric chapter.

**Why it earns a place:** The current filter can show J or N separately but
cannot answer whether the overlay improved accuracy. Worse, “All” currently
treats J and N as extra observations in the same summary. A paired comparison
controls for vintage, target, horizon, model/cycle, and population and shows the
incremental value of judgment.

**Domain requirement:** Pair J and N error records on every identity field except
`J/N Flag`; require the same realised actual; calculate
`abs(percentage_error_J) - abs(percentage_error_N)`, win/loss/tie, and change in
signed error; summarize by metric and horizon. Return eligible count, paired
count, and unmatched reasons. The chart should only claim improvement on paired
coverage.

**Displaces:** “J/N = All” as an unqualified pooling behavior. It also replaces
the need to repeat a J and an N version of each metric chart; the top filter may
remain for single-path inspection.

### Vintage revision chart — do not make it a permanent chart in the first pass

**Place if later accepted:** A drill-down from a selected heatmap cell or target
quarter in Localization.

**Assessment:** It is analytically sound and useful for investigating
convergence/thrashing, but it is lower-density than the vintage × horizon heatmap
and requires a fixed-target selector plus another callback path. The heatmap
already tells the reviewer which target/vintage deserves investigation. Add this
only after real-user evidence that hover plus the thin forecast detail is not
enough.

**Domain requirement:** Select one target quarter, return every preceding
vintage's forecast, revision from the prior vintage, distance to the final actual,
and the actual execution timestamp. Actual selection must remain independent of
the forecast-vintage filter.

**Would displace:** It should replace, never accompany, the raw vintage-curve
chart for the selected metric. In the initial proposal, that space goes to the
heatmap.

### Additional candidate: segment × horizon error heatmap — accept

**Place:** Beside the vintage × horizon heatmap in Localization, using the same
metric selector and signed-error scale.

**Why it is stronger than an unscoped revision chart:** It directly answers the
required systemic-versus-segment question. If all segment rows deteriorate at the
same horizons, the issue is systemic; one hot row identifies isolation. Neither
the current page nor the proposed vintage heatmap can make that distinction.

**Domain requirement:** The same matrix contract as the vintage heatmap, grouped
by `(segment, horizon)`, with signed percentage error, MAPE, count, and coverage.
The service must preserve segment identity even when the top filter is All.

**Displaces:** The separate, repeated horizon chart in each metric section. One
cross-metric horizon view plus this localization matrix is more diagnostic than
five copies of the same two-panel chart.

## 4. IMPROVEMENTS TO WHAT EXISTS

The following are concrete defects, ordered by severity.

### Correctness and analysis grain

- **Snapshot filtering removes the actuals required to score the selected
  vintage.** `features/backtesting/services/backtesting_service.py:108-110`
  filters the source frame to one snapshot before `build_error_records` constructs
  its actual lookup. Selecting either tested snapshot produced zero scored PD
  records and 18 “unscored” forecasts. Snapshot must filter forecast vintages,
  while actual anchors must be resolved from the full otherwise-comparable
  history.
- **Actual values collide across retained run/model partitions.**
  `features/backtesting/domain/errors.py:102-120` keys the lookup only by segment
  and target quarter, then overwrites that key for every anchor row. But
  `features/backtesting/domain/aggregation.py:160-162` retains the full metric run
  key. In LGD/EAD/NCO, model partitions can have different subpopulation actuals;
  in all metrics, cycle and J/N alternatives are separate runs. Aggregate to the
  intended analysis population before resolving actuals, or include a validated
  comparable-population key. Do not depend on row order.
- **The forecast paths connect unrelated records.**
  `shared/ui/charts.py:2600-2613` groups only by `vintage_quarter`. With All cycle
  and J/N selections, each trace contains duplicate target quarters from
  different runs and connects them as a single line. The live default scope had
  multiplicities of 2/4/8/8/24 per vintage-target pair for
  PD/PD-CRR/LGD/EAD/NCO. The domain/service must emit one path per declared
  comparison series, and the figure must group by that series key rather than
  inventing it from vintage alone.
- **Raw vintage aggregation can double-count alternative runs.**
  `features/backtesting/services/backtesting_service.py:157-159` deliberately
  drops every grouping dimension except snapshot. For additive EAD and NCO, All
  cycles and both J/N flags sum alternative estimates of the same facilities.
  Combining disjoint model populations is legitimate; summing alternative cycles
  or overlays is not. The service needs explicit dimension semantics.
- **Scenario policy is inconsistent with the documented backtest.**
  `features/backtesting/ui/views/backtesting.py:216-227` offers every scenario,
  and `features/backtesting/services/backtesting_service.py:299-304` scores the
  selected scenario, despite the code comments and original plan saying only Base
  is scored. Either lock scoring to Base and label non-Base as context-only, or
  explicitly redefine the product. Recommendation: enforce Base for all accuracy
  summaries/RAG and allow other scenarios only as unscored overlays.
- **Exposure fan-out is detected but still allowed to corrupt the result.**
  `features/backtesting/domain/aggregation.py:116-130` sets `fanned_out=True` and
  returns the duplicated merged rows. The plan and tests describe this as a
  fail-loud condition. Raise a domain error before aggregation; a warning flag
  after multiplication is too late.
- **“Exposure coverage” is actually row coverage.**
  `features/backtesting/domain/aggregation.py:122-128` exposes row coverage and
  matched exposure but no total available exposure or exposure-coverage ratio.
  `features/backtesting/ui/views/backtesting.py:529-535` then labels row coverage
  as “Exposure coverage.” Add both ratios in the domain and label each accurately.

### Layering

- **The view performs service orchestration.**
  `features/backtesting/ui/views/backtesting.py:635-636` computes the two loss
  series, and `features/backtesting/ui/views/backtesting.py:722-724` builds the
  entire dashboard payload by calling the service. Under `CLAUDE.md`, UI is
  composition only. The callback should call the service and pass an already
  prepared plain payload into a pure layout builder. Figure construction may stay
  in the view wrapper, but data selection, aggregation, error calculation, and
  loss-series generation may not.

### Summary and metric formatting

- **The summary strip omits MAE even though the domain computes it.**
  `features/backtesting/ui/views/backtesting.py:503-512` displays count, bias,
  MAPE, RMSE, and hit rate only.
- **Bias and RMSE are formatted as generic decimals.** The same lines use
  `+,.4f` and `,.4f` for every metric. PD/LGD should display percentage points or
  percentages with an explicit convention; EAD/NCO should display currency. In
  the live default scope EAD bias rendered as `+6,022,531.4271` and NCO bias as
  `+34,942.4439`, with no currency sign or compact units.
- **The horizon bias panel has the same defect.**
  `shared/ui/charts.py:2733-2735` hard-codes a `+.4f` hover and
  `shared/ui/charts.py:2765-2768` supplies no metric tick format. The wrapper at
  `features/backtesting/ui/views/figures.py:64-70` does not pass the metric's
  value format. Live EAD hover rendered `Bias: 5982255.69319859`; PD and LGD
  rendered long raw fractions instead of percentages.

### Reference lines, bands, and visual semantics

- **MAPE has no accuracy bands.** The 10%/25% thresholds are declared at
  `shared/ui/charts.py:2529-2531`, but the horizon chart at
  `shared/ui/charts.py:2737-2764` draws only the zero/legend shapes. Add Green,
  Amber, and Red horizontal bands or boundary lines to make 9%, 14%, and 30%
  immediately interpretable. The forecast-error panel at
  `shared/ui/charts.py:2644-2672` likewise has only zero; it should show at least
  the ±10% tolerance band and optionally the ±25% boundary.
- **Bias marker colors encode direction as quality.**
  `shared/ui/charts.py:2728-2731` colors every non-negative bias Green and every
  negative bias Red, regardless of magnitude. A +60% miss is not Green, and a
  tiny negative miss is not Red. Use a neutral/diverging sign color for direction
  and RAG severity based on absolute percentage bias or a governed threshold.
- **Threshold logic lives in presentation code.** `backtest_error_rag` and its
  bands at `shared/ui/charts.py:2529-2542` are domain policy inside a Plotly
  module. Move classification to backtesting domain logic and source the bands
  from the governed constants described in section 6.

### Hover behavior and Plotly bundle compatibility

- **Vintage-based hovers render `Q+Q+1`.**
  `shared/ui/charts.py:2873-2876` prefixes `Q+` to `%{x}`. Under the bundled
  Plotly.js 2.25.2, `%{x}` is rendered using the axis tick text (`Q+1`), producing
  `Q+Q+1`. This was reproduced in the live PD vintage, cumulative-loss, and
  periodic-loss charts. Put the raw integer horizon in `customdata` and format
  from that, or remove the manual prefix. This is exactly the kind of Python/API
  success but browser failure warned about in `CLAUDE.md`.
- Forecast/actual hover and horizon-summary hover otherwise rendered with the
  expected vintage, target, horizon, error, count, and hit-rate content. Browser
  drag-to-zoom also changed the x-axis range and double-click reset worked.

### Theme response

- **Theme response is partial, not SAAS-equivalent.** Transparent plot and paper
  backgrounds are correct, and the live toggle changed fonts/grid from the light
  to dark palette. However the actual and forecast lines remained `#dc2626` and
  `#2563eb` in both themes because they are hard-coded at
  `shared/ui/charts.py:2524-2527`. Vintage lines similarly always use the fixed
  `PD_MEV_PALETTE` at `shared/ui/charts.py:2853-2856`. Follow the existing SAAS
  light/dark mapping pattern using only the existing palette values; do not add a
  new palette or CSS variables.

### Empty states

- The pre-apply empty state matches the house treatment and should be retained.
- **Applied-but-empty sections render three redundant empty graphs.**
  `features/backtesting/ui/views/backtesting.py:697-703` shows the house empty card
  only when `view is None`, but the service always returns an empty view dictionary
  at `features/backtesting/services/backtesting_service.py:262-275`. Detect an
  empty/no-score view and render one `section-card pd-mev-empty-state` explaining
  whether the cause is no rows, no comparable actual, or no paired coverage.

### Callback wiring

No dependency-cycle violation was found in the current callbacks. The cascade at
`features/backtesting/callbacks/backtesting.py:108-193` uses option-button clicks
as its only Input and current values as State, and the render callback at
`features/backtesting/callbacks/backtesting.py:245-254` has no self-reference.
The live default apply, six subnav interactions, and theme toggle produced zero
browser console errors and zero page errors. This is a pass, not permission to
skip browser verification when the proposed local diagnostic controls are added.

## 5. WHAT TO REMOVE

1. Remove the cumulative and periodic loss-performance charts from Backtesting.
   If the business still needs them, they belong in a portfolio/loss monitoring
   page. Do not replace them with more Overview decoration.
2. Remove all five raw “by vintage” charts. The vintage × horizon error heatmap
   replaces their intended diagnostic role with an actual accuracy measure.
3. Replace the five repeated error-by-horizon charts with one cross-metric
   horizon-decay surface plus the segment × horizon localization heatmap.
4. Merge PD and PD CRR into one PD detail section with explicit population/model
   facets. The workbook guide confirms both sheets contain the same probability
   measure over disjoint facility populations; the current separate full section
   implies a metric difference that does not exist.
5. Simplify `build_forecast_actual_figure` to the underlying level time series in
   metric detail. Move its current error-dot panel to the stronger calibration and
   localization diagnostics rather than showing two cramped panels everywhere.
6. Do not add a permanent vintage-revision chart in the initial redesign. Keep it
   as a drill-down backlog item so the first release gets shorter as it becomes
   more diagnostic.

The target is approximately eight or nine charts instead of 17: four thin metric
level charts, one cross-metric horizon view, one calibration scatter, two
localization heatmaps in one surface, one J/N comparison, and one NCO waterfall.
The scorecard is a compact table/card surface, not another plot. Some diagnostic
surfaces can share a local metric selector, so they do not multiply by metric.

## 6. SUMMARY STATISTICS AND RAG

### What the strip shows today

The strip currently shows:

- scored forecast count;
- raw-unit mean signed bias;
- MAPE;
- raw-unit RMSE;
- hit rate within ±10%;
- an unscored-forecast note when recent targets have no actual;
- a purported exposure-coverage note only when row coverage is below 100%.

At the live default Base/all scope it displayed:

| Metric section | Scored | Bias | MAPE | RMSE | Hit rate ±10% |
|---|---:|---:|---:|---:|---:|
| PD | 72 | +0.0007 | 9.3% | 0.0036 | 67% |
| PD CRR | 144 | +0.0003 | 6.9% | 0.0025 | 83% |
| LGD | 288 | -0.0123 | 7.3% | 0.0384 | 73% |
| EAD | 288 | +6,022,531.4271 | 12.5% | 8,819,983.3254 | 51% |
| NCO | 864 | +34,942.4439 | 56.7% | 138,652.6775 | 18% |

These values document the current display, not an approved accuracy result: the
comparison-grain defects in section 4 mean the All-scope counts and some actuals
are not yet trustworthy.

Coverage against the requested set is therefore:

| Statistic | Computed in domain | Shown today | Assessment |
|---|---:|---:|---|
| Bias | Yes | Yes | Direction is useful, but display units are wrong and raw bias is not cross-metric comparable. Add mean signed percentage error alongside metric-unit bias. |
| MAE | Yes | **No** | Add it with metric-aware formatting. |
| RMSE | Yes | Yes | Keep, metric-formatted; also show `RMSE / MAE` or an outlier cue only if it earns space. |
| MAPE | Yes | Yes | Keep as the primary cross-metric accuracy measure, with zero-actual denominator count visible. |
| Hit rate within tolerance | Yes | Yes | Keep; the tolerance must be governed and displayed, not embedded independently in domain and copy. |

### M1a results

M1a separated the snapshot-scoped forecast set from the full-history actual
set, matched each forecast to an anchor on its validated comparable-population
key, and made Base the only scoreable scenario. The table below reruns the exact
default scope recorded above: all populations, all model use case / cycles,
Base scenario, both J/N flags, and all vintages.

| Metric section | Scored before | Scored after | Bias before | Bias after | MAPE before | MAPE after | RMSE before | RMSE after | Hit rate before | Hit rate after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PD | 72 | 36 | +0.0007 | +0.0009 | 9.3% | 7.0% | 0.0036 | 0.0033 | 67% | 78% |
| PD CRR | 144 | 72 | +0.0003 | +0.0002 | 6.9% | 4.1% | 0.0025 | 0.0022 | 83% | 93% |
| LGD | 288 | 144 | -0.0123 | +0.0032 | 7.3% | 2.8% | 0.0384 | 0.0226 | 73% | 94% |
| EAD | 288 | 144 | +6,022,531.4271 | +375,326.1288 | 12.5% | 1.7% | 8,819,983.3254 | 1,839,813.5193 | 51% | 94% |
| NCO | 864 | 432 | +34,942.4439 | +7,994.9899 | 56.7% | 10.5% | 138,652.6775 | 50,733.2461 | 18% | 77% |

Every metric moved because of defect 2, the actual-key collision. The former
segment-plus-target lookup let each model/cycle/J-N run borrow whichever anchor
happened to appear last for that segment. The corrected key retains the metric's
model partition (all three model names and Loss Method for NCO), Model Use Case /
Cycle, Base scenario, and J/N flag, while replacing snapshot with target quarter.
That correction also halves the scored count in this workbook: forecasts for
which the same comparable run has no realised anchor are now correctly unscored
instead of borrowing another run's actual.

- **PD and PD CRR:** the collision fix removed cross-model/cycle/J-N borrowing;
  MAPE fell by 2.3 and 2.8 percentage points respectively.
- **LGD:** the collision fix is also a model-partition fix. It changed the sign
  of bias from -0.0123 to +0.0032 and reduced MAPE by 4.5 percentage points.
- **EAD:** matching each EAD model partition to its own anchor removed the large
  cross-partition level mismatch; MAPE fell by 10.8 percentage points and hit
  rate rose by 43 percentage points.
- **NCO:** as expected, this moved most because its former lookup mixed 24
  records per vintage-target pair across PD/LGD/EAD model combinations, cycles,
  and J/N alternatives. MAPE fell from 56.7% to 10.5%, RMSE fell from
  138,652.6775 to 50,733.2461, and hit rate rose from 18% to 77%. This material
  movement is evidence that the collision fix is active rather than still
  selecting an arbitrary shared anchor.

Defect 1 does not change this all-vintages table, but it changes snapshot-scoped
behavior: selecting the 2023-Q1 snapshot now produces 10/20/40/40/120 scored
records for PD/PD CRR/LGD/EAD/NCO instead of zero. Defect 3 also does not change
the table because the recorded default is already Base. Selecting Severe now
keeps each metric's raw vintage context while returning zero scored records,
no MAPE or hit rate, and an explicit `context_only` scoring status.

### M1b results

M1b applies the analysis-grain contract documented in
`features/backtesting/README.md`: disjoint segment/model populations combine,
while Model Use Case / Cycle and J/N remain separate comparison dimensions.
The table reruns the same all-population, all-cycle, Base, both-J/N,
all-vintage scope and compares it with the M1a result.

| Metric section | Scored M1a | Scored M1b | Bias M1a | Bias M1b | MAPE M1a | MAPE M1b | RMSE M1a | RMSE M1b | Hit rate M1a | Hit rate M1b |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PD | 36 | 36 | +0.0009 | +0.0009 | 7.0% | 7.0% | 0.0033 | 0.0033 | 78% | 78% |
| PD CRR | 72 | 36 | +0.0002 | +0.0002 | 4.1% | 3.5% | 0.0022 | 0.0016 | 93% | 94% |
| LGD | 144 | 36 | +0.0032 | +0.0032 | 2.8% | 2.2% | 0.0226 | 0.0213 | 94% | 94% |
| EAD | 144 | 36 | +375,326.1288 | +1,501,304.5151 | 1.7% | 1.3% | 1,839,813.5193 | 6,595,416.1615 | 94% | 94% |
| NCO | 432 | 36 | +7,994.9899 | +95,939.8788 | 10.5% | 7.8% | 50,733.2461 | 441,425.8027 | 77% | 94% |

The count changes are aggregation-grain changes, not scoring changes:

- **PD stays at 36** because `results.pd` already contains one segment/model
  population per cycle/J-N comparison; there was nothing further to combine.
- **PD CRR falls from 72 to 36** because its two disjoint segment populations
  now form one exposure-weighted portfolio observation for each vintage,
  horizon, cycle, and J/N flag.
- **LGD and EAD fall from 144 to 36** because four disjoint segment/model
  partitions now form one portfolio observation per comparison grain.
- **NCO falls from 432 to 36** because twelve disjoint segment and component-model
  partitions now sum once into the portfolio NCO for each comparison grain.
  The two cycles and two J/N alternatives remain separate; they are not included
  in the sum.

The larger EAD/NCO bias and RMSE values are expected unit effects: they are now
errors on portfolio currency totals instead of averages across smaller partition
errors. Their scale-free accuracy improves (EAD MAPE 1.7% to 1.3%; NCO MAPE
10.5% to 7.8%) because offsetting partition errors reconcile at portfolio level.

M1b also makes duplicate EAD keys raise `ExposureFanOutError` before a merge can
multiply rows. Exposure joins now return both row coverage and exposure coverage:
the regression fixture deliberately produces 50% row coverage but 25% exposure
coverage, and the summary copy labels the two measures independently.

### RAG recommendation

Backtest accuracy should use the same RAG visual language and
`shared/domain/constants.PD_RAG_COLOR`, but it should not pretend the monitoring
PD/LGD/EAD tests and a backtest statistic are the same policy. Use one explicit,
scale-free headline RAG initially:

- **Green:** MAPE ≤ 10%.
- **Amber:** 10% < MAPE ≤ 25%.
- **Red:** MAPE > 25%.
- **N/A:** no valid non-zero actuals, no comparable pairs, or the agreed minimum
  sample/coverage condition is not met.

Use the same 10% and 25% boundaries for individual absolute percentage-error
markers and heatmap reference bands. Keep signed bias directional rather than
giving every positive value Green. Hit rate remains a supporting measure under a
10% tolerance; do not invent a second hit-rate RAG until owners approve separate
bands. Always show scored count, MAPE denominator count, and comparison coverage
beside a RAG.

The current 10%/25% bands are hidden in `shared/ui/charts.py`; that is the wrong
layer. Because this task explicitly forbids workbook changes, put named
backtesting policy constants (RAG bands, hit tolerance, minimum count, minimum
pair/actual coverage) in `shared/domain/constants.py`, and perform classification
in `features/backtesting/domain/errors.py` or a dedicated pure domain module.
Continue to reuse `PD_RAG_COLOR` for presentation. If workbook changes are ever
authorized later, the long-term governed home is a dedicated Backtesting
threshold sheet loaded through the repository—not an unrelated PD or Loss row
whose metric happens to have similar numbers.

## 7. SEQUENCED PLAN

Each milestone below is one commit. Every commit ends with:

```bash
.venv/bin/python -m pytest features/backtesting/tests features/saas/tests features/monitoring/tests shared tests -q
```

Browser-facing milestones additionally use Dash's bundled Plotly.js, verify both
themes, exercise hover/zoom, and compare console error counts. No milestone adds a
dependency, edits `source_data/`, or changes a workbook.

### M1 — Correctness foundation and comparison contract

- Define the analysis grain and distinguish combinable model partitions from
  alternative cycle/J-N/scenario runs.
- Resolve actuals from the comparable full history before applying the forecast
  vintage filter.
- Eliminate actual-key collisions and add invariance/uniqueness assertions.
- Enforce Base-only scoring; retain non-Base data only as context.
- Make exposure fan-out fail loudly and add true exposure coverage.
- Add regression tests for single-snapshot scoring, All-cycle/J-N behavior,
  comparable population actuals, and duplicate exposure rows.

**Callbacks:** No. Keep this pure domain/service work so every later chart rests
on valid records.

### M2 — Repair existing summaries and figures

- Add MAE; format bias/MAE/RMSE by metric.
- Move error classification out of `shared/ui/charts.py` into domain policy.
- Add MAPE and signed-error tolerance bands.
- Replace sign-as-RAG bias markers with correct direction/severity semantics.
- Fix `Q+Q+n` hovers using the bundled Plotly.js-compatible data shape.
- Make trace colors respond to theme using the existing palette only.
- Collapse applied-but-empty metric sections to one house-style empty card.

**Callbacks:** No dependency changes. Browser verification is mandatory.

### M3 — Install the hybrid information architecture and restore the UI boundary

- Build the cross-metric scorecard and single horizon-decay surface.
- Merge PD/PD CRR presentation into one PD detail section.
- Thin metric detail to one level chart each.
- Remove the two static-loss charts, five raw-vintage charts, and five repeated
  horizon charts.
- Move service invocation out of `ui/views/backtesting.py`; the callback obtains
  the prepared dashboard payload and passes it to a pure view builder.

**Callbacks: YES.** This changes the render callback's implementation and output
payload flow. Capture real outputs for representative filter combinations and
check the browser console for dependency cycles.

### M4 — Localization heatmaps

- Add pure domain matrix builders for vintage × horizon and segment × horizon.
- Add one local metric selector and the two heatmaps in a shared Localization
  surface.
- Include signed error, MAPE, counts, target quarter, and coverage in hover.
- Use a zero-centered diverging scale made only from existing palette colors.

**Callbacks: YES.** A new local selector/store or callback-rendered container is
the main cycle risk. Do not mix its dynamic Inputs with always-present top-bar
Inputs; follow `CLAUDE.md` rule 3 and verify real browser console output.

### M5 — Calibration scatter and paired J/N effectiveness

- Add the metric-selectable actual-versus-predicted scatter with a 45-degree
  reference line and horizon color.
- Add J/N pairing, pair-coverage diagnostics, improvement rate, and error delta
  by horizon.
- Reuse the existing local diagnostic metric state rather than creating another
  competing selector.

**Callbacks: YES.** This extends the diagnostic render path. Keep current values
as State where an output preserves a selection, and re-run the cycle audit.

### M6 — NCO component attribution

- Add component joins keyed by the three model-name columns.
- Implement facility-level Shapley attribution and reconciliation residual.
- Add coverage/fan-out tests and hand-calculated decomposition fixtures.
- Render the NCO waterfall with explicit total and residual bars.

**Callbacks:** No new callback is required if it follows the applied scope. If a
target/vintage drill-down is added, split that into a separately reviewed
callback milestone rather than expanding this commit.

### M7 — Stabilization, documentation, and acceptance evidence

- Update feature documentation to describe the four-question reading order,
  comparison grain, Base-only scoring, RAG policy, and N/A rules.
- Add layout tests for the shorter chart inventory and house empty states.
- Capture before/after results across approximately ten representative filter
  combinations, including one snapshot, one segment, one model, each J/N value,
  All for J/N comparison, and light/dark themes.
- Verify all hovers and interactions against Dash's bundled Plotly.js and record
  zero dependency-cycle console errors.

**Callbacks:** No planned wiring change; this milestone verifies every callback
change from M3-M5.

The vintage-revision drill-down is intentionally not in this sequence. Reassess
it only after the localization heatmaps are in use and there is evidence that a
selected target-quarter revision history is still needed.
