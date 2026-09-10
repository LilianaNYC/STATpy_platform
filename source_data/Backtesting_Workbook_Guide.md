# Backtesting workbook guide — `backtesting_results.xlsx`

Dummy facility-grain source data for the Backtesting dashboard: model
projections of PD (over two disjoint facility populations), LGD, EAD and NCO,
against which realised outcomes can be measured.

| | |
|---|---|
| **File** | `source_data/backtesting_results.xlsx` (~12 MB) |
| **Generator** | `source_data/generate_backtesting_data.py` (deterministic, `SEED = 20260909`) |
| **Verifier** | `source_data/verify_backtesting.py` (122 checks) |
| **Sheets** | 5 result tabs, 230,880 rows total (see §3 for per-sheet counts) |
| **Regenerate** | `.venv/bin/python source_data/generate_backtesting_data.py` |
| **Verify** | `.venv/bin/python source_data/verify_backtesting.py` |

The generator is fully deterministic — the same seed always produces the same
values, so the verifier's tolerances and error-structure thresholds are stable
across regenerations. Timestamps use a CRC32-based hash rather than Python's
`hash()`, which is salted per interpreter run.

---

## 1. Design decisions

Four decisions shape everything below. They resolve open questions raised in
`docs/backtesting_plan.md`.

### The two PD sheets are disjoint populations, not two views of one facility

`results.pd` and `results.pd_crr` carry **identical structure** — same columns,
same dtypes, same kind of value (a probability in `[0,1]`), same error structure.
What differs is **which facilities they cover**, split by the PD model that owns
the facility:

| Sheet | `Model Name` | Facility × instrument pairs |
|---|---|---|
| `results.pd` | `PD_model_a` (only) | 28 |
| `results.pd_crr` | `PD_model_b` (only) | 76 |
| | | **104, no overlap** |

Consequences:

- **Neither sheet alone covers the portfolio.** A portfolio-level PD requires the
  **union** of the two. Reading only `results.pd` silently drops 73% of the
  facilities.
- **`results.lgd`, `results.ead` and `results.nco` each cover the full 104
  pairs**, since every facility needs an exposure, a loss rate and a charge-off
  regardless of where its PD came from.
- **`NCO = coalesce(pd, pd_crr) × LGD × EAD`.** Reconciling NCO means stacking
  both PD sheets first. Because the populations are disjoint, the stack has
  exactly one PD row per join key — the verifier asserts that directly, which is
  also the strongest available check that the populations really don't overlap.
- A facility's PD source is visible in the row itself, via `Model Name`, and on
  `results.nco` via `PD Model Name`.

### The PD population follows the model catalogue

`model_names` in `dummy_mev_data.xlsx` says which segments each PD model serves,
and this workbook is generated to match:

| PD model | Segments served |
|---|---|
| `PD_model_a` | Cyclical |
| `PD_model_b` | Cyclical, Defensive |

**O&M is excluded entirely** — no PD model covers it, and a facility with no PD
cannot be backtested.

**Only the PD side is aligned.** The catalogue confines LGD models to O&M and EAD
models to Defensive; aligning those too would leave no segment with a full
PD+LGD+EAD triple, making exposure weighting and the NCO identity uncomputable.
LGD and EAD therefore cover the same facilities the PD sheets do.

### Quarter 0 is the realised anchor

Each `Month End Snapshot` carries `Quarter` 0 through 9.

- **`Quarter = 0`** is the **observed** value at the snapshot date. It carries no
  forecast error and no scenario overlay, and is therefore **identical across
  all three scenarios and both J/N flags**.
- **`Quarter = 1..9`** are projections carrying the injected error structure and
  the scenario overlay.

This mirrors the convention already used by the SAAS workbook (`Quarter <= 0` is
history, `>= 1` is projection). It is what makes the workbook backtestable: the
actual for calendar quarter *T* is the Quarter-0 row of the vintage whose
snapshot *is* *T*, and every earlier vintage's forecast of *T* can be scored
against it.

**Consequence — the recent horizons have no actual.** With nine snapshots and
nine horizons, only targets falling on or before the last snapshot have an
anchor. 11,232 forecast/actual pairs are resolvable; **42,120 forecast rows
target quarters past the final snapshot and have no actual at all.** That is
production-realistic and must be rendered as forecast-only rather than as zero
error.

### Exposure lives only on `results.ead`

The PD, PD-CRR and LGD sheets carry **no EAD column**, by design. Exposure
weighting therefore requires a join to `results.ead` on the run identity
**excluding `Model Name`** — a facility's PD model is not its EAD model.

Every facility is assigned exactly **one** PD model, **one** LGD model and
**one** EAD model, which guarantees that join is 1:1 and cannot fan out. Because
`results.ead` covers the full population, both PD sheets join into it cleanly
with nothing unmatched. The verifier asserts all of this directly.

### NCO is the expected-loss identity

`Loss Method` is `"Expected Loss"` on every row, and

```
NCO Value = PD Value x LGD Value x EAD Value
```

for the matching facility / instrument / quarter / run. The product is computed
on the *emitted* (post-clip) values, so reconciliation is exact to float
precision — the verifier measures a maximum relative error of 1.3e-15.

---

## 2. Sheets and columns

Column order below is exact and is asserted by the verifier.

### `results.pd` — PD for the `PD_model_a` population (28 pairs, 15,400 rows)

| # | Column | Dtype | Allowed values |
|---|---|---|---|
| 1 | `Segment Name` | str | `Cyclical`, `Defensive` |
| 2 | `Model Name` | str | `PD_model_a` (single value) |
| 3 | `Month End Snapshot` | datetime | 9 quarter-end dates, `2023-03-31` .. `2025-03-31` |
| 4 | `Run For` | str | `CCAR 2025`, `CCAR 2026` |
| 5 | `Scenario` | str | `Base`, `Adverse`, `Severe` |
| 6 | `J/N Flag` | str | `J`, `N` |
| 7 | `Facility ID` | str | `F-{CYC\|DEF\|ONM}-nnn` |
| 8 | `Credit Instrument ID` | str | `CI-{CYC\|DEF\|ONM}-nnn-i` |
| 9 | `Quarter` | int | `0`..`9` (0 = realised anchor) |
| 10 | `PD Value` | float | `[0.0001, 0.9999]`; observed range `0.0001 .. 0.6807` |
| 11 | `Execution Datetime` | datetime | 3–6 days after the snapshot |

### `results.pd_crr` — PD for the `PD_model_b` population (76 pairs, 42,320 rows)

Columns are **identical to `results.pd`**, including the `PD Value` name, except
that `Model Name` is `PD_model_b` (single value).

This sheet is **structurally the same data over a different population** — not a
different kind of number. The value is a probability, not a rating grade, so it
needs no master-scale mapping and aggregates exactly like `results.pd`. It is
generated by the same machinery from the same underlying realised paths and
carries the same injected error structure.

Observed range `0.0001 .. 0.3877`. The narrower top end versus `results.pd` is a
population effect — its 72 facilities simply do not include the highest-PD names
— not a difference in how the value is produced.

### `results.lgd` — loss given default (104 pairs, 57,720 rows)

Same columns as `results.pd`, except:

| # | Column | Dtype | Allowed values |
|---|---|---|---|
| 2 | `Model Name` | str | `LGD_model_a`, `LGD_model_b` |
| 10 | `LGD Value` | float | `[0.0001, 0.9999]`; observed `0.0082 .. 0.9999`, median `0.412` |

### `results.ead` — exposure at default (104 pairs, 57,720 rows)

Same columns as `results.pd`, except:

| # | Column | Dtype | Allowed values |
|---|---|---|---|
| 2 | `Model Name` | str | `EAD_model_a`, `EAD_model_b` |
| 10 | `EAD Value` | float | strictly positive currency; observed `125,876 .. 27,219,300` |

### `results.nco` — net charge-off (104 pairs, 57,720 rows)

| # | Column | Dtype | Allowed values |
|---|---|---|---|
| 1 | `Segment Name` | str | as above |
| 2 | `PD Model Name` | str | `PD_model_a`, `PD_model_b` (whichever PD sheet covers the facility) |
| 3 | `LGD Model Name` | str | `LGD_model_a`, `LGD_model_b` |
| 4 | `EAD Model Name` | str | `EAD_model_a`, `EAD_model_b` |
| 5 | `Month End Snapshot` | datetime | as above |
| 6 | `Run For` | str | as above |
| 7 | `Scenario` | str | as above |
| 8 | `J/N Flag` | str | as above |
| 9 | `Loss Method` | str | `Expected Loss` (single value) |
| 10 | `Facility ID` | str | as above |
| 11 | `Credit Instrument ID` | str | as above |
| 12 | `Quarter` | int | `0`..`9` |
| 13 | `NCO Value` | float | non-negative currency; observed `4.81 .. 2,939,350` |
| 14 | `Execution Datetime` | datetime | as above |

**Note on clipping.** PD, PD-CRR and LGD are clipped to `[0.0001, 0.9999]`, and
EAD floored at `1,000`. Saturation is negligible — a few hundred rows out of 230,880 sit exactly on a
bound. Exactly-bound values are the clip working on extreme tails, not a defect.

---

## 3. Population and dimensions

| Dimension | Count | Values |
|---|---|---|
| Segments | 2 | `Cyclical`, `Defensive` (O&M excluded — see §1) |
| PD models | 2 | `PD_model_a` (`results.pd`), `PD_model_b` (`results.pd_crr`) |
| LGD / EAD models | 2 each | `{LGD,EAD}_model_{a,b}`, both on one sheet |
| Facilities per segment | 40 | 80 total |
| Facility × instrument pairs | 104 | ~30% of facilities carry a 2nd instrument |
| Month End Snapshots | 9 | quarter-ends `2023-03-31` .. `2025-03-31` |
| Quarters per snapshot | 10 | `0` anchor + `1..9` projections |
| Scenarios | 3 | `Base`, `Adverse`, `Severe` |
| J/N flags | 2 | `J`, `N` |

### Row counts

Rows per sheet = `pairs × 9 snapshots × 10 quarters × 3 scenarios × 2 flags`,
plus superseded duplicates (§5).

| Sheet | Pairs | Canonical | Superseded | Total |
|---|---|---|---|---|
| `results.pd` | 28 | 15,120 | 280 | **15,400** |
| `results.pd_crr` | 76 | 41,040 | 1,280 | **42,320** |
| `results.lgd` | 104 | 56,160 | 1,560 | **57,720** |
| `results.ead` | 104 | 56,160 | 1,560 | **57,720** |
| `results.nco` | 104 | 56,160 | 1,560 | **57,720** |
| | | | | **230,880** |

The two PD sheets sum to a full-population sheet (`15,400 + 42,320 = 57,720`),
which the verifier asserts — it is the cheapest check that the partition is
complete and non-overlapping. Every sheet is comfortably under the 150,000 cap.

The segment, model and cycle vocabulary is deliberately identical to the
`model_names` sheet of `dummy_mev_data.xlsx`, so the Backtesting dashboard's
filters line up with Monitoring's and SAAS's instead of introducing parallel
names for the same things.

`Run For` is a deterministic function of the snapshot — snapshots on or before
`2024-06-30` are `CCAR 2025`, later ones `CCAR 2026` — so it never affects the
exposure join.

---

## 4. Joining the sheets

**Facility ID and Credit Instrument ID are stable across all five sheets**, so
the tabs join on them directly. The ID *sets* differ by design, though:

- `results.pd` ∩ `results.pd_crr` = **∅** (disjoint populations)
- `results.pd` ∪ `results.pd_crr` = `results.lgd` = `results.ead` = `results.nco`

The verifier asserts both the emptiness of the intersection and the exactness of
the union.

### The exposure join

To attach an exposure weight to a PD, PD-CRR or LGD row, join to `results.ead`
on the run identity **excluding `Model Name`**, plus the row grain:

```
Segment Name + Month End Snapshot + Run For + Scenario + J/N Flag
  + Facility ID + Credit Instrument ID + Quarter
```

Verified properties: `results.ead` has exactly one row per join key (no fan-out
is possible), and every post-dedupe row on all three metric sheets finds its
exposure row — 45,360 / 38,880 / 84,240 rows, zero unmatched. Because
`results.ead` covers the union, neither PD population has exposure gaps.

**Join after deduping, never before.** Superseded rows share the join key with
their canonical replacements and would double every match.

### Aggregation

Per `docs/backtesting_plan.md` §1:

| Sheet | Aggregation |
|---|---|
| `results.pd` | `Σ(EAD·PD) / Σ EAD` — exposure-weighted |
| `results.pd_crr` | `Σ(EAD·PD) / Σ EAD` — exposure-weighted (already a PD; no master-scale mapping needed) |

**A portfolio-level PD must aggregate the two PD sheets together**, stacking
them before weighting. Aggregating either sheet alone yields the PD of that
sub-population, not of the portfolio.
| `results.lgd` | `Σ(EAD·LGD) / Σ EAD` — exposure-weighted |
| `results.ead` | `Σ EAD` — sum |
| `results.nco` | `Σ NCO` — sum |

---

## 5. Repeated runs and dedupe

The **run key** is:

```
Segment Name + Model Name + Month End Snapshot + Run For + Scenario + J/N Flag
```

(`results.nco` uses its three model columns plus `Loss Method` in place of the
single `Model Name`.)

Three run configurations are deliberately emitted twice — a superseded first
attempt with an **earlier** `Execution Datetime` and values scaled by `0.94`,
followed by the canonical re-run:

| Segment | Snapshot | Scenario | J/N |
|---|---|---|---|
| `Cyclical` | `2023-09-30` | `Base` | `N` |
| `Defensive` | `2024-06-30` | `Severe` | `J` |
| `Defensive` | `2025-03-31` | `Adverse` | `N` |

Each spans both models in that sheet, so **6 of 324 run keys** carry two
executions (24 of 1,296 on `results.nco`, whose key is finer), adding **1,560
duplicate rows** per sheet.

**The dedupe rule:** keep the run whose `Execution Datetime` is the latest **per
run key, wholesale**. Do not select the max row-by-row — a partial re-run would
otherwise contribute some quarters while the superseded execution contributed
the rest, producing an internally inconsistent projection path.

`Execution Datetime` deliberately does **not** vary with `Model Name`: one
execution produces every model's rows for a given segment / snapshot / scenario
/ flag.

### Superseded rows deliberately break the loss identity

Every sheet scales its superseded values by the same `0.94`, so a superseded NCO
row is `0.94×` its canonical value while the superseded `PD × LGD × EAD` product
is `0.94³×`. **Superseded rows therefore do not satisfy
`NCO = PD × LGD × EAD`.**

This is intentional: any consumer that reconciles before deduping fails loudly
instead of quietly folding a botched first attempt into the answer. The verifier
asserts both directions — reconciliation passes post-dedupe (1.3e-15 relative)
and fails pre-dedupe.

---

## 6. Injected error structure

Without a deliberate error signal the dashboard would have nothing to show.
Forecasts are built as:

```
forecast = realised(target quarter)
           × (1 + vintage_shift + bias(q) + noise(q))
           × scenario_overlay(scenario, q)
```

where `bias` and `noise` are both scaled by the J/N and segment factors below.
`Quarter 0` bypasses all of it.

### The five injected effects

| Effect | Mechanism | Measured result (PD, Base scenario) |
|---|---|---|
| **Error grows with horizon** | noise sd = `0.030 + 0.022q` | MAE rises monotonically `0.0462` (q1) → `0.1856` (q8) |
| **Optimistic bias at long horizons** | `bias = −0.012 × max(0, q−2)`; losses under-forecast | mean error `+0.0004` at q≤2 vs **`−0.0578`** at q≥6 |
| **One bad vintage** | snapshot index 4 (`2024-03-31`), `+35%` across every horizon | vintage 4 MAE `0.3412` vs `0.1186` worst other |
| **J more accurate than N** | error scaled `0.65` for `J`, `1.00` for `N` | J MAE `0.1044` vs N MAE `0.1416` |
| **One segment materially worse** | error scaled `2.20` for `Cyclical` | Cyclical `0.1736` vs Defensive `0.0921` |

Note the bad vintage over-forecasts (`+35%`) while the horizon bias
under-forecasts, so the two are distinguishable by sign rather than only by
magnitude. Vintage 4 is excluded when checking horizon monotonicity, since it
would otherwise dominate the short horizons where it still has an anchor.

### Per-metric error parameters

| Metric | noise sd | bias slope | bad-vintage shift |
|---|---|---|---|
| `pd` | `0.030 + 0.022q` | `−0.012` | `+0.35` |
| `lgd` | `0.020 + 0.014q` | `−0.008` | `+0.22` |
| `ead` | `0.018 + 0.010q` | `0.000` (no bias on exposure) | `+0.12` |

There is no separate `pd_crr` row: both PD sheets are drawn from the **same** PD
series and then split by population, so the error structure is identical either
side of the partition. The verifier confirms it holds within each sheet
independently (`results.pd` q1 0.0456 → q8 0.1908; `results.pd_crr` q1 0.0469 →
q8 0.1795).

`NCO` inherits its error from the product of the three.

### Scenario overlay

Scenarios layer deterministic conservatism on top of the Base path — this is a
scenario effect, **not** model error. Backtesting compares **Base** against
realised; `Adverse` and `Severe` exist as context.

| Scenario | Slope per quarter |
|---|---|
| `Base` | `0.000` |
| `Adverse` | `0.045` |
| `Severe` | `0.100` |

Each metric absorbs a fraction of the overlay: PD `1.00`, LGD `0.35`,
EAD `0.15`. Both PD sheets absorb it identically, being one series.

### Underlying realised paths

The "true" realised path per facility-instrument combines a facility base level,
a segment risk level (`Cyclical 1.30`, `Defensive 0.70`), a shared
14-quarter systemic credit cycle (`±35%` on PD), and idiosyncratic noise. LGD
moves with the cycle far less than PD; EAD drifts up ~0.4% per quarter and is
close to cycle-neutral.

---

## 7. What the verifier checks

`verify_backtesting.py` runs 120 checks in eight groups and exits non-zero on any
failure.

| Group | Checks |
|---|---|
| **Structure** | sheet names and order; column names in exact order per sheet; row counts identical and under the cap; dtypes |
| **Content** | no nulls in any column; allowed values for every categorical; `Quarter` in 0..9; 9 month-end snapshots; per-sheet model-name sets; single `Loss Method` |
| **Value ranges** | PD / PD-CRR / LGD within `[0,1]`; EAD strictly positive; NCO non-negative |
| **Populations** | the two PD sheets are disjoint; their union is exactly what LGD / EAD / NCO cover; each PD sheet maps every facility to a single model |
| **Joins** | `results.ead` unique on the join key; exposure join does not fan out and leaves nothing unmatched, for both PD populations and LGD |
| **NCO reconciliation** | stacked PD sheets unique on the join key; 1:1 join to `coalesce(pd, pd_crr)` / LGD / EAD; `NCO = PD × LGD × EAD` within `1e-9` relative |
| **Dedupe** | repeated runs exist; grain not unique before dedupe and unique after; one execution survives per run key; superseded rows present; reconciliation fails pre-dedupe |
| **Anchors and coverage** | Quarter-0 anchors present and invariant across scenario and J/N flag; forecast/actual pairs resolvable; recent horizons have no actual |
| **Error structure** | all five injected effects measurably present on the combined PD, plus a horizon effect within each PD population separately |

The error-structure group is the one that matters most for the dashboard: the
workbook can be structurally perfect and still useless if the injected signal
is absent, so those checks assert the signal rather than the schema.
