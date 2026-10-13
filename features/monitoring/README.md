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
│   └── common.py        Shared single-select filter-dropdown shell helpers
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
This feature owns its repository (`repositories/loader.py`, which reads the
workbook tabs into the precomputed metric stores), but the rest of its
UI/domain/persistence is shared because the SAAS dashboard and the `shared/ui`
layer reuse parts of it:

- `shared/repositories/filters_config.py` — the `Filters` config sheet (cycles,
  scenarios, segments, models), read by both dashboards and `shared/ui`.
- `shared/domain/` — shared calculation engine: `calculations`, `mev_range`,
  `quarter_labels`, and domain `constants` (RAG colours, threshold helpers).
- `shared/ui/charts.py`, `shared/ui/controls.py` — shared chart / filter-bar /
  control builders. (KPI/RAG card builders live in this feature's
  `ui/views/cards.py`.)
- `config/settings.py` — source-data file locations.
- `shared/` — registry types, theme constants, idempotent-registration helper.

## Data sources
- `source_data/portfolio.xlsx` — precomputed metric tabs
  (`PD/LGD/EAD/Loss_Performance_Metrics`), the `Filters` config sheet, and
  `PD_Sensitivity_Projections` (with `MM_P0` / `MM_Pm` margins).
- `source_data/monitoring_rules.xlsx` — PD / CRR-master-scale /
  RAG-assignment / LGD / Loss / scenario-test threshold tables.
- `source_data/dummy_mev_data.xlsx` — the MEV time-series catalog (MEV Range).

Loading happens in `repositories/loader.py`; the enriched payload is exposed
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

## Top filter bar

All five tabs present the same filters in the same order, as a two-row bar: a
**Scope** row that picks the slice of data, then a **Focus** row that narrows
within it and applies. Each row is captioned with that word, in a stub column
down the left of the bar, so the split is visible rather than implied.

| Row | PD / LGD / EAD | Loss | Overview |
|---|---|---|---|
| **Scope** | Region · Portfolio · Model Use Case · Reporting Cycle | *same* | *same* |
| **Focus** | Model · Segment · Monitoring Point → **Apply filters** | Model · Segment · Monitoring Point · Scenario → **Apply filters** | Model Group · Model · Monitoring Point → **Apply filters** |

**Scenario is not in the bar on PD/LGD/EAD.** It only ever drove one section —
**2.5 MEV Range** — so it lives in that section's own *Display filters* row,
beside Window/From/To (`shared.ui.controls.build_mev_scenario_control`). Not
Sensitivity Analysis, and not Scenario Ranking, which has its own in-section
picker. Consequences, all deliberate:

* it **re-renders immediately**, without Apply, exactly like the range controls
  it shares a row with — it is a display control for one section, not part of
  the page's scope;
* Apply is no longer gated on it (seven filters instead of eight);
* `apply_*_filters` no longer snapshots it, but a deep link's `?scenario=` still
  reaches the render through the applied store, so an Overview escalation card
  lands on the scenario its RAG was computed under;
* saving a review writes the **in-section** value back to `portfolio.xlsx`, not
  the applied scope's, which can now be stale.

Loss keeps its bar control: it has no MEV Range section to move it into.

**The default is `intsevere`**, from `filters_config.default_scenario()`. The
option list is alphabetical (the repo-wide ordering rule), so the old
`scenarios[0]` fallback meant "baseline" by accident of the alphabet; this is a
stress dashboard, so a reviewer should land on the severe scenario — which is
what the MEV figure builders already defaulted their own `scenario` argument to.
Only the *default* moved; the menu still reads alphabetically. Every fallback in
the app goes through that one helper — Overview's, for rows with no saved
scenario, and each tab's, for a scope that has not picked one — because if the
two disagreed a deep link from an escalation card would render under a different
scenario than the card's RAG was computed under.
`test_every_fallback_goes_through_the_one_helper` pins that, and the helper
degrades to the first available value if a data set has no `intsevere` at all.

Overview's row 2 differs because it is the cross-portfolio roll-up: no Segment
or Scenario, but it is the only tab with a **Model Group** filter. The
performance tabs each show exactly one group, so the control there could only
ever return its own name — its value drove nothing (the group is hardcoded at
every `models_matching` call site), the sidebar/title/URL already state it, and
once the bar started empty it became a required click with a foregone answer.
So it was removed from PD/LGD/EAD/Loss and kept on Overview, where picking
between PD/LGD/EAD/Loss is a real choice.

Everything else — order, the two-row split and the divider — is identical.
Cascade chevrons appear on the **Scope** row only, on every tab; Overview's
Focus row used to draw them too, which made the same row read differently
there. Apply sits directly after the final filter so the controls and their
action read as one workflow.

Loss is the other exception: it has a single portfolio-wide entity ("All
Models") carrying no per-model Region or Portfolio, so those two filters stay
fixed placeholders showing only "All" rather than dropping it like the other
tabs.

Layout lives in CSS, not Python: `.monitoring-primary-filter-row` /
`.saas-secondary-filter-row` size the performance tabs and
`.overview-primary-filter-row` / `.overview-secondary-filter-row` size Overview.
All peer filters use the same width: 160px on wide screens and 140px at medium
widths. The **Apply filters** track is content-sized and follows the final focus
control; medium-width rows wrap naturally, while small screens stack the
controls and use a full-width action.

The captions come from `shared.ui.controls.build_scope_caption` /
`build_focus_caption` and are `.monitoring-filter-row-caption`, deliberately
**not** `.monitoring-filter`: that class carries the per-filter track sizing and
the cascade chevron, which is drawn before every `.monitoring-filter` preceded
by another one, so reusing it would put an arrow between the caption and the
first filter. Both rows lead with a caption track of the same width
(`--filter-caption-track`, set once on `.monitoring-controls.saas-top-filter-row`)
— that shared width is what keeps each row's filter columns lined up with the
row above, across the divider. Below 901px the rows stack and the caption
becomes a plain heading over its group.

### Where the filter values come from

The full provenance table for **both** dashboards — which workbook, sheet and
column backs every filter — is in the root `README.md`, under
"Where each filter's values come from". The rest of this section covers the
monitoring-specific details behind it.

### Where the Model options come from

Every tab takes its Model list from **the sheet whose metrics it renders** —
`PD_/LGD_/EAD_/Loss_Performance_Metrics` — so a tab can only ever offer a model
it has data for. Nothing is hardcoded, including Loss's `All Models`, which is
simply what its own sheet contains.

portfolio.xlsx stores the **raw model code** (`PD_model_a`), mirroring the
production table. `shared.repositories.tables` resolves it to the
`Model Descriptive Name` from `model_names` on read, because the descriptive
name is the model's identity everywhere above that line: `mev_catalog` is keyed
by it, the metrics store is keyed by it, and it is what the filter shows.

Two properties of that lookup are deliberate:

* It is keyed on the **code**, not the descriptive name. Keyed the other way it
  would be a no-op on production data and quietly leave codes in the filter.
* An unresolvable code **passes through unchanged** rather than being dropped.
  Loss's `All Models` has no catalogue entry by design, and an unknown code
  should surface in the filter rather than empty the tab with no error.

The mapping is **many-to-one** — `PD_model_d` and `PD_model_e` both resolve to
`PD Model D` — because the descriptive name is a group identity, not a rename.

This used to read the MEV catalogue instead. The two sources agreed until
portfolio.xlsx was trimmed, after which PD's bar listed five models whose panels
came back empty and whose scope could never enable Apply.

### portfolio.xlsx stores only `Run For`

Both parts are derived from it, not stored:

| | |
|---|---|
| model use case | the leading token — `CCAR 2026` → `CCAR` |
| bare cycle | the text after the first space — `CCAR 2026` → `2026` |

`shared.domain.reporting_cycle.split_run_for` does both, verbatim, with no
relabelling: the filter shows exactly what `Run For` says. The sheets used to
carry `Model Use Case` and `Reporting Cycle` as their own columns, which meant
three columns holding one fact and a standing risk they drifted apart — a
consistency test existed purely to catch that. Deriving them retires the risk,
and because nothing is remapped, a new programme needs no code at all.

**Both dashboards derive it**, through the same helper, so neither workbook
stores the parts: `dummy_mev_data.xlsx`'s `model_names` dropped them too. That
sheet used to say `ST - CCAR` where `Run For` said `CCAR`, which is exactly the
disagreement deriving removes — the two dashboards can now differ only in which
cycles they *have data for*, never in what a cycle is called.

`test_no_workbook_stores_the_derived_cycle_parts` covers both files, and
`test_both_workbooks_derive_to_the_same_use_cases` pins the agreement.

### PD's monitoring point vs its cohort quarter

PD alone separates the two, because PD alone has a `horizon`:

| Column | Meaning |
|---|---|
| `monitoring_point` | the **as-of** reporting date |
| `Quarter` | the **cohort start** — one year back for `1y`/`nco_1y`, two for `2y` |

So one monitoring point spans three different quarters:

```
monitoring_point  Quarter  horizon
2025Q4            2024Q4   1y
2025Q4            2023Q4   2y
2025Q4            2024Q4   nco_1y
2025Q4            2024Q4   (blank — the horizon-agnostic summary row)
```

LGD/EAD/Loss have no `horizon`, so their `Quarter` is already the as-of and they
carry no `monitoring_point`.

Everything downstream — the metrics store, the Monitoring Point filter, every
trend — means the **as-of** when it says `quarter`. Rather than teach each reader
the difference, `shared.domain.reporting_cycle._promote_monitoring_point` swaps
them once at the read seam: `quarter` becomes the as-of and the cohort start stays
available as `cohort_quarter`. Sheets without the column pass through untouched.
Skip that swap and the metrics store and the filter both shift one to two years
back — `test_the_read_seam_promotes_pd_monitoring_point_into_quarter` pins it.

PD also carries `MM_P0`, `MM_Pm` and `abs_delta_MM`, joined from
`PD_Sensitivity_Projections` on `(Run For, Model, Segment, monitoring_point)`.
`abs_delta_MM` is `|MM_Pm − MM_P0|`. All three are blank where a model has no
projections — PD Model E and F have none at all, and CECL has none for any model —
and they are blank *together*, so a missing margin never reads as a real zero.

### One model, except on Overview

| Tab | Model filter | Why |
|---|---|---|
| PD / LGD / EAD / Loss | **single-select** | the page reports one model's diagnostics |
| Overview | multi-select checklist | it pools models rather than reporting one |

This is a rule, not an accident, and it is load-bearing. These tabs **look up**
their metrics rather than computing them: `calculations.ctx_store_keys`
resolves a single `(model, segment, quarter, horizon)` row, and the store holds
only per-model rows — there is no aggregate row for an arbitrary subset. Handed
several models it returns `models[0]` and silently drops the rest, so a
multi-select there would render one model's numbers under a toggle claiming
several. Making it correct would need one panel per selected model, aggregate
rows in the workbook, or a recompute path — never a change to the filter alone.

`test_filter_shells.py` pins both halves: the four tabs must expose a
single-select `Dropdown`, and Overview must expose a `Checklist`.

Both kinds are **searchable**. The four tabs' single-select menus carry the same
"Type to search models…" box as the checklists, via
`build_single_select_dropdown(search_id=…)`. Two rules make it behave:

* The search **hides** options, it never removes them — so the toggle still
  names a selection that is filtered out of view, because the label resolves
  against the full list.
* The option buttons live in their own container
  (`controls.single_select_option_list_id`) and the shell callback rewrites
  *that*, not the menu. The menu is rebuilt on every value/options change, so an
  input placed directly inside it would be destroyed on each keystroke, losing
  focus and text. `test_the_search_box_survives_a_menu_rebuild` pins the
  structure.

Only Model gets a search box; a search on Segment would be noise,
and `test_no_other_filter_gets_a_search_box` keeps it that way.

Overview's picker otherwise matches SAAS's workspace control exactly — toggle
summary, search box, "All", checklist — including the two behaviours that are
easy to get wrong: the search only *hides* options (a checked model stays
selected while hidden), and "All" adds or removes only the visible ones.

### The page opens with nothing selected

Every filter starts unanswered, showing a "Select …" placeholder, and **Apply
stays disabled until all of them have a real value** — nothing can be applied
against a half-specified scope. The machinery is in `shared/ui/controls.py`:
`UNSELECTED` (the empty value), `with_placeholder`, `keep_or_unselected`, `SELECT_PROMPTS` and
`all_selected`.

One exemption only: **Loss's Region/Portfolio**, which are fixed "All"
placeholders because its single entity is the portfolio-wide "All Models",
carrying neither attribute. Every other filter on every tab starts unanswered.

Model Group was the other one-option control, and rather than exempt it the
filter itself was removed from PD/LGD/EAD/Loss (see above) — a filter that can
only return one answer is a label, not a filter.

Three rules for anyone touching a cascade after this:

1. **Never fall back to `options[0]`.** Use `keep_or_unselected`: keep a
   still-valid pick, otherwise leave the filter unanswered. The cascade runs on
   the first render, so a first-option fallback fills the whole bar in before
   the user touches it. `tests/test_empty_start.py` greps for this specific
   regression.
2. **Every option list a callback writes needs its placeholder**, via
   `with_placeholder`. The value `""` has to match an option, or `_option_label`
   falls back to a bare `"Select"` and the control reads as broken.
3. **Do not use `resolve_monitoring_point_value` from a filter callback.** It
   answers the filter with the latest quarter. It is still correct for deep
   links, which supply a scope deliberately.

Because Apply now needs the *whole* scope, a combination with no data behind it
is a dead end rather than a thin render: pick a region/portfolio with no CECL
data, pick CECL, and Reporting Cycle comes back empty with no way forward. So
the performance tabs now narrow **Model Use Case** and **Reporting Cycle** by
Region/Portfolio, and **Model** by Reporting Cycle, the way Overview already
did. All three read filters to their left, so the cascade stays one-way (see
callback rule 2). `test_every_offered_cycle_still_has_a_model` walks every
reachable scope and fails if any of them offers no model.

### Option ordering

One rule, applied to every filter on every tab, and to SAAS's bar too. It lives
in `shared/domain/filter_order.py`:

| Kind of value | Order | Filters |
|---|---|---|
| Text | A–Z, case-insensitive | Region, Portfolio, Model Use Case, Model Group, Model, Segment, Scenario |
| Dates, quarters, numbers | Most recent / largest first | Reporting Cycle, Monitoring Point |

Two things are deliberately **outside** the rule:

* **Aggregate sentinels** — "All", "Select model", "Select segment". They are
  not values, they are the absence of a choice, so they stay pinned at the head
  of the list instead of sorting into it. Sentinels are matched by *value*, not
  label: Loss labels its aggregate "All models" while its one real model is
  named "All Models", and a label match cannot tell those apart.
* **`domain/overview.MODEL_GROUPS`** (PD → LGD → EAD → Loss). That is the
  loss-decomposition sequence every chart and table sorts on, not a filter.
  Only the Model Group *filter* is alphabetized; the figure order is untouched.

Ordering and **defaults are separate concerns**, because several defaults are
taken from `options[0]`. Listing Model Use Case A–Z puts "CECL" first, so
`filters_config.default_use_case` supplies the default instead — the owner of
the most recent cycle — and every tab still opens on the live CCAR cycle.
Reporting Cycle and Monitoring Point need no such treatment: descending already
puts the newest first.

Sorting periods is a parse, not a string compare, so "10" outranks "9". A bare
year counts as the whole year and therefore outranks its own quarters ("2025"
above "2025Q1"). Composite cycles sort on the part after the family name —
compared whole, "CECL 2025Q1" would outrank "CCAR 2026".

`tests/test_filter_order.py` covers the rule; the per-tab guards
(`features/monitoring/tests/test_filter_bar_ordering.py`,
`features/saas/tests/test_filter_ordering.py`) check the rendered bars obey it.

### The cascade

Each filter narrows the ones after it, so the bar can never offer a combination
with no data behind it. One rule per line.

**PD, LGD and EAD**

| Picking this… | …narrows the options of |
|---|---|
| Region | Portfolio |
| Model Use Case | Reporting Cycle |
| Region + Portfolio + Reporting Cycle | Model |
| Model | Segment |
| Reporting Cycle + Model + Segment | Monitoring Point |

```
Region → Portfolio ─┐
                    ├→ Model → Segment → Monitoring Point
Model Use Case → Reporting Cycle ─┘
```

Reporting Cycle still narrows Scenario, but that edge is no longer in the bar:
the MEV Range control is built with the scenarios the MEV workbook has for the
applied cycle (falling back to the full config list for cycles the sheet does
not cover, e.g. CECL), so the narrowing happens at render time instead of
through a callback.

**Overview** — no Segment or Scenario, and its Model Use Case is itself narrowed
by the Region/Portfolio scope:

| Picking this… | …narrows the options of |
|---|---|
| Region | Portfolio |
| Region + Portfolio | Model Use Case |
| Region + Portfolio + Model Use Case | Reporting Cycle |
| Region + Portfolio + Reporting Cycle + Model Group | Model |
| Reporting Cycle + Model | Monitoring Point |

**Loss** — fewest edges, since its Region/Portfolio are placeholders (above) and
it has one portfolio-wide entity:

| Picking this… | …narrows the options of |
|---|---|
| Model Use Case | Reporting Cycle |
| Reporting Cycle | Monitoring Point |
| Reporting Cycle | Scenario |
| Model | Segment |

### The rule that keeps it acyclic

**Every arrow points rightward along the bar.** No callback may write a filter
that sits to the left of any filter it reads — a backwards edge is exactly how
Dash dependency cycles arise here (see the callback rules in `CLAUDE.md`), and
they surface only in the browser console, never in pytest.

This is enforced. `features/monitoring/tests/test_performance_tab_filters.py`
parses the real `@app.callback` decorators on PD, LGD, EAD and Loss and fails on
any backwards edge; `features/monitoring/tests/test_overview_use_case_filter.py`
does the same for Overview. Overview carries the one known-unfixed violation —
`sync_overview_model_select_all`, the mutually-syncing select-all, which both
reads and writes the Model value (see callback rule 4 in `CLAUDE.md`). It is
pinned *by name* rather than hidden, so a **new** backwards edge still fails the
test.

Reordering the bar therefore means re-checking direction. When Reporting Cycle
moved ahead of Model, the old "Model/Segment narrows the cycle list" edges had
to be inverted into "Reporting Cycle narrows the Model list"; keeping both would
have closed the loop.

### Model Use Case / Reporting Cycle

These two were one combined "Model Use Case / Cycle" control. They are now
separate, fed by the workbook's own `Model Use Case` and `Reporting Cycle`
columns. The cycle dropdown **labels** the bare cycle ("2026") but its **value
stays the composite** ("CCAR 2026") — that composite is the join key behind
every store, figure, export and Dash element ID, so nothing downstream changed.

Region, Portfolio, Model Use Case and Reporting Cycle carry **no "All" option**:
each offers only values with data in the scope its predecessors set. Monitoring
Point lists most-recent-first to match Reporting Cycle; the default is resolved
with `max()`, not by position, so the display order cannot change which quarter
is selected.

## Conventions
- Every `register_callbacks(app)` is **idempotent** via
  `shared.registration.already_registered(app, key)`.
- Dashboard-level stores are surfaced from `stores.py` (currently all owned by
  the PD page) and rendered once in the shell so filter/range state survives
  navigation.
- Shared code lives under `shared/` (`shared/ui`, `shared/domain`,
  `shared/repositories`); promote feature-local code there only once a second
  page/dashboard needs it ("rule of two").
