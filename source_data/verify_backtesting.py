"""Integrity checker for ``backtesting_results.xlsx``.

Run from the repository root::

    .venv/bin/python source_data/verify_backtesting.py

Exits 0 when every check passes, 1 otherwise. Checks are grouped:

* **Structure** -- sheets, column names and order, row counts, dtypes.
* **Content** -- nulls, value ranges, allowed values.
* **Populations** -- ``results.pd`` and ``results.pd_crr`` are disjoint halves of
  the portfolio (split by owning PD model), and their union is exactly the
  population that ``results.lgd`` / ``results.ead`` / ``results.nco`` cover.
* **Joins** -- IDs align across sheets; the exposure join is 1:1 and cannot fan
  out; NCO reconciles to ``coalesce(pd, pd_crr) x LGD x EAD``.
* **Dedupe** -- repeated runs exist, and keeping the latest execution per run key
  behaves as ``Backtesting_Workbook_Guide.md`` documents.
* **Error structure** -- the injected signal is actually present, so a failure
  here means the workbook is valid but useless for a backtesting dashboard.

The dedupe rule implemented here is the one the app must use: keep the run whose
``Execution Datetime`` is the latest **per run key, wholesale**. Selecting the
max row-by-row would let a partial re-run mix quarters from two executions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

WORKBOOK_PATH = Path(__file__).resolve().parent / "backtesting_results.xlsx"

MAX_ROWS_PER_SHEET = 150_000
NCO_RELATIVE_TOLERANCE = 1e-9

# O&M is deliberately out of scope: the model catalogue has no PD model covering
# it, and a facility with no PD cannot be backtested.
SEGMENTS = {"Cyclical", "Defensive"}

# Which segments each PD model may score, per the model_names catalogue. The
# workbook is generated to match, so the dashboard's cascade can follow the
# catalogue without offering an empty combination.
PD_MODEL_SEGMENTS = {
    "PD_model_a": {"Cyclical"},
    "PD_model_b": {"Cyclical", "Defensive"},
}
SCENARIOS = {"Base", "Adverse", "Severe"}
JN_FLAGS = {"J", "N"}
RUN_FOR_VALUES = {"CCAR 2025", "CCAR 2026"}
LOSS_METHODS = {"Expected Loss"}
PD_MODELS = {"PD_model_a", "PD_model_b"}
LGD_MODELS = {"LGD_model_a", "LGD_model_b"}
EAD_MODELS = {"EAD_model_a", "EAD_model_b"}

# The PD population split: each PD sheet carries exactly one model's facilities.
PD_SHEETS = ("results.pd", "results.pd_crr")
PD_SHEET_MODEL = {"results.pd": "PD_model_a", "results.pd_crr": "PD_model_b"}
# Sheets covering the full population.
FULL_POPULATION_SHEETS = ("results.lgd", "results.ead", "results.nco")

EXPECTED_COLUMNS = {
    "results.pd": [
        "Segment Name", "Model Name", "Month End Snapshot", "Run For", "Scenario",
        "J/N Flag", "Facility ID", "Credit Instrument ID", "Quarter", "PD Value",
        "Execution Datetime",
    ],
    "results.pd_crr": [
        "Segment Name", "Model Name", "Month End Snapshot", "Run For", "Scenario",
        "J/N Flag", "Facility ID", "Credit Instrument ID", "Quarter", "PD Value",
        "Execution Datetime",
    ],
    "results.lgd": [
        "Segment Name", "Model Name", "Month End Snapshot", "Run For", "Scenario",
        "J/N Flag", "Facility ID", "Credit Instrument ID", "Quarter", "LGD Value",
        "Execution Datetime",
    ],
    "results.ead": [
        "Segment Name", "Model Name", "Month End Snapshot", "Run For", "Scenario",
        "J/N Flag", "Facility ID", "Credit Instrument ID", "Quarter", "EAD Value",
        "Execution Datetime",
    ],
    "results.nco": [
        "Segment Name", "PD Model Name", "LGD Model Name", "EAD Model Name",
        "Month End Snapshot", "Run For", "Scenario", "J/N Flag", "Loss Method",
        "Facility ID", "Credit Instrument ID", "Quarter", "NCO Value",
        "Execution Datetime",
    ],
}

METRIC_COLUMN = {
    "results.pd": "PD Value",
    "results.pd_crr": "PD Value",
    "results.lgd": "LGD Value",
    "results.ead": "EAD Value",
    "results.nco": "NCO Value",
}

# The run identity. ``results.nco`` names three models instead of one.
RUN_KEY = ["Segment Name", "Model Name", "Month End Snapshot", "Run For", "Scenario", "J/N Flag"]
NCO_RUN_KEY = [
    "Segment Name", "PD Model Name", "LGD Model Name", "EAD Model Name",
    "Month End Snapshot", "Run For", "Scenario", "J/N Flag", "Loss Method",
]
GRAIN = ["Facility ID", "Credit Instrument ID", "Quarter"]

# The exposure join key: the run identity *excluding* Model Name, because a
# facility's PD model is not its EAD model.
JOIN_KEY = [
    "Segment Name", "Month End Snapshot", "Run For", "Scenario", "J/N Flag",
    "Facility ID", "Credit Instrument ID", "Quarter",
]

SEGMENT_COLUMN = "Segment Name"

BAD_VINTAGE_INDEX = 4
N_SNAPSHOTS = 9
MAX_QUARTER = 9


# ---------------------------------------------------------------------------
# Check plumbing
# ---------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.results: list[tuple[bool, str, str]] = []
        self._group: str | None = None

    def group(self, name: str) -> None:
        self._group = name
        print(f"\n{name}")
        print("-" * len(name))

    def check(self, passed: bool, name: str, detail: str = "") -> bool:
        self.results.append((bool(passed), name, detail))
        mark = "PASS" if passed else "FAIL"
        suffix = f"  {detail}" if detail else ""
        print(f"  [{mark}] {name}{suffix}")
        return bool(passed)

    @property
    def failed(self) -> list[tuple[bool, str, str]]:
        return [row for row in self.results if not row[0]]

    def summary(self) -> int:
        total = len(self.results)
        failures = self.failed
        print("\n" + "=" * 62)
        if failures:
            print(f"FAILED  {len(failures)} of {total} checks")
            for _, name, detail in failures:
                print(f"    - {name}{('  ' + detail) if detail else ''}")
            return 1
        print(f"PASSED  all {total} checks")
        return 0


def dedupe_runs(frame: pd.DataFrame, run_key: list[str]) -> pd.DataFrame:
    """Keep only the latest execution of each run key, wholesale.

    Row-level selection is deliberately avoided: a partial re-run would
    otherwise contribute some quarters while the superseded execution
    contributed the rest.
    """
    latest = frame.groupby(run_key, observed=True)["Execution Datetime"].transform("max")
    return frame[frame["Execution Datetime"] == latest]


def combined_pd(deduped: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The portfolio's PD: ``results.pd`` and ``results.pd_crr`` stacked.

    The two sheets cover disjoint facilities, so stacking them yields exactly one
    PD row per join key across the whole population -- the ``coalesce(pd,
    pd_crr)`` the loss identity needs. Any duplicate join key here would mean the
    populations overlap, which the checks assert they do not.
    """
    return pd.concat(
        [deduped[sheet][JOIN_KEY + ["PD Value"]] for sheet in PD_SHEETS],
        ignore_index=True,
    )


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_structure(report: Report, sheets: dict[str, pd.DataFrame], sheet_names: list[str]) -> None:
    report.group("Structure")
    report.check(
        sheet_names == list(EXPECTED_COLUMNS),
        "sheet names and order",
        f"{sheet_names}",
    )
    for name, expected in EXPECTED_COLUMNS.items():
        actual = list(sheets[name].columns)
        report.check(actual == expected, f"{name}: column names in exact order",
                     "" if actual == expected else f"got {actual}")

    counts = {name: len(frame) for name, frame in sheets.items()}
    report.check(all(n <= MAX_ROWS_PER_SHEET for n in counts.values()),
                 f"every sheet under {MAX_ROWS_PER_SHEET:,} rows",
                 ", ".join(f"{k.split('.')[-1]}={v:,}" for k, v in counts.items()))

    # The PD sheets split one population, so their rows sum to a full-population
    # sheet rather than each matching it.
    pd_total = sum(counts[sheet] for sheet in PD_SHEETS)
    full = {counts[sheet] for sheet in FULL_POPULATION_SHEETS}
    report.check(len(full) == 1, "LGD / EAD / NCO have identical row counts", f"{sorted(full)}")
    report.check(pd_total == next(iter(full)),
                 "results.pd + results.pd_crr rows == full-population rows",
                 f"{counts['results.pd']:,} + {counts['results.pd_crr']:,} = {pd_total:,}")

    for name, frame in sheets.items():
        ok = (
            pd.api.types.is_integer_dtype(frame["Quarter"])
            and pd.api.types.is_datetime64_any_dtype(frame["Month End Snapshot"])
            and pd.api.types.is_datetime64_any_dtype(frame["Execution Datetime"])
            and pd.api.types.is_float_dtype(frame[METRIC_COLUMN[name]])
        )
        report.check(ok, f"{name}: dtypes (int Quarter, datetime dates, float value)")


def check_content(report: Report, sheets: dict[str, pd.DataFrame]) -> None:
    report.group("Content")
    for name, frame in sheets.items():
        nulls = frame.isna().sum()
        offenders = nulls[nulls > 0]
        report.check(offenders.empty, f"{name}: no nulls in any column",
                     "" if offenders.empty else f"{offenders.to_dict()}")

    for name, frame in sheets.items():
        # Subset, not equality: a PD sheet legitimately covers only the segments
        # its model serves. The union across sheets is asserted separately.
        report.check(set(frame[SEGMENT_COLUMN].unique()) <= SEGMENTS,
                     f"{name}: Segment Name values within the known set",
                     f"{sorted(set(frame[SEGMENT_COLUMN].unique()))}")
        report.check(set(frame["Scenario"].unique()) == SCENARIOS, f"{name}: Scenario values")
        report.check(set(frame["J/N Flag"].unique()) == JN_FLAGS, f"{name}: J/N Flag values")
        report.check(set(frame["Run For"].unique()) <= RUN_FOR_VALUES, f"{name}: Run For values")
        quarters = set(frame["Quarter"].unique())
        report.check(quarters == set(range(MAX_QUARTER + 1)), f"{name}: Quarter in 0..{MAX_QUARTER}")
        report.check(frame["Month End Snapshot"].nunique() == N_SNAPSHOTS,
                     f"{name}: {N_SNAPSHOTS} distinct Month End Snapshots")
        report.check(
            frame["Month End Snapshot"].dt.is_month_end.all(),
            f"{name}: every Month End Snapshot is a month end",
        )

    for sheet, model in PD_SHEET_MODEL.items():
        actual = set(sheets[sheet]["Model Name"].unique())
        report.check(actual == {model}, f"{sheet}: Model Name is exactly {{{model}}}",
                     "" if actual == {model} else f"got {sorted(actual)}")
    report.check(set(sheets["results.lgd"]["Model Name"].unique()) == LGD_MODELS, "results.lgd: LGD model names")
    report.check(set(sheets["results.ead"]["Model Name"].unique()) == EAD_MODELS, "results.ead: EAD model names")
    nco = sheets["results.nco"]
    report.check(set(nco["PD Model Name"].unique()) == PD_MODELS, "results.nco: PD Model Name values")
    report.check(set(nco["LGD Model Name"].unique()) == LGD_MODELS, "results.nco: LGD Model Name values")
    report.check(set(nco["EAD Model Name"].unique()) == EAD_MODELS, "results.nco: EAD Model Name values")
    report.check(set(nco["Loss Method"].unique()) == LOSS_METHODS, "results.nco: Loss Method values")

    report.group("Value ranges")
    for name in ("results.pd", "results.pd_crr", "results.lgd"):
        values = sheets[name][METRIC_COLUMN[name]]
        report.check(values.between(0.0, 1.0).all(), f"{name}: value within [0, 1]",
                     f"min={values.min():.6g} max={values.max():.6g}")
    ead = sheets["results.ead"]["EAD Value"]
    report.check((ead > 0).all(), "results.ead: EAD strictly positive",
                 f"min={ead.min():,.0f} max={ead.max():,.0f}")
    nco_values = sheets["results.nco"]["NCO Value"]
    report.check((nco_values >= 0).all(), "results.nco: NCO non-negative",
                 f"min={nco_values.min():,.2f} max={nco_values.max():,.2f}")


def check_joins(report: Report, sheets: dict[str, pd.DataFrame], deduped: dict[str, pd.DataFrame]) -> None:
    report.group("Populations")
    id_sets = {
        name: set(map(tuple, frame[["Facility ID", "Credit Instrument ID"]].drop_duplicates().to_numpy()))
        for name, frame in sheets.items()
    }
    pd_ids, pd_crr_ids = id_sets["results.pd"], id_sets["results.pd_crr"]
    overlap = pd_ids & pd_crr_ids
    report.check(not overlap, "results.pd and results.pd_crr populations are disjoint",
                 f"{len(pd_ids):,} + {len(pd_crr_ids):,} pairs, overlap {len(overlap)}")
    report.check(bool(pd_ids) and bool(pd_crr_ids),
                 "both PD sheets carry facilities", f"pd={len(pd_ids):,} pd_crr={len(pd_crr_ids):,}")

    union = pd_ids | pd_crr_ids
    for name in FULL_POPULATION_SHEETS:
        ids = id_sets[name]
        report.check(ids == union, f"{name}: covers exactly the union of both PD populations",
                     "" if ids == union else f"symmetric difference {len(ids ^ union)}")
    report.check(len(union) > 0, "facility x instrument pairs present", f"{len(union):,} pairs")

    # Catalogue alignment: a PD sheet must not carry a segment its model does
    # not cover, or the dashboard's catalogue-driven cascade would offer
    # combinations with no rows (and hide rows that do exist).
    for sheet, model in PD_SHEET_MODEL.items():
        actual = set(sheets[sheet][SEGMENT_COLUMN].unique())
        allowed = PD_MODEL_SEGMENTS[model]
        report.check(actual <= allowed,
                     f"{sheet}: segments stay within what {model} covers in model_names",
                     f"{sorted(actual)} vs allowed {sorted(allowed)}")

    # Each PD sheet must hold only its own model's facilities -- the population
    # split and the Model Name column have to tell the same story.
    for sheet, model in PD_SHEET_MODEL.items():
        models_per_pair = sheets[sheet].groupby(
            ["Facility ID", "Credit Instrument ID"], observed=True
        )["Model Name"].nunique()
        report.check((models_per_pair == 1).all(),
                     f"{sheet}: every facility maps to a single PD model")

    report.group("Joins")

    # The exposure join the dashboard depends on: PD rows must each find exactly
    # one EAD row on the reduced key. A fan-out here would silently multiply
    # every exposure-weighted aggregate.
    ead = deduped["results.ead"][JOIN_KEY + ["EAD Value"]]
    report.check(not ead.duplicated(JOIN_KEY).any(),
                 "results.ead: one row per exposure-join key (no fan-out possible)")
    for name in ("results.pd", "results.pd_crr", "results.lgd"):
        left = deduped[name][JOIN_KEY]
        merged = left.merge(ead, on=JOIN_KEY, how="left")
        report.check(len(merged) == len(left), f"{name}: exposure join does not fan out",
                     f"{len(left):,} -> {len(merged):,}")
        report.check(merged["EAD Value"].notna().all(), f"{name}: every row finds its exposure row",
                     f"unmatched={int(merged['EAD Value'].isna().sum()):,}")

    report.group("NCO reconciliation")
    all_pd = combined_pd(deduped)
    report.check(not all_pd.duplicated(JOIN_KEY).any(),
                 "stacked PD sheets are unique on the join key (populations do not overlap)",
                 f"{len(all_pd):,} combined PD rows")

    nco = deduped["results.nco"][JOIN_KEY + ["NCO Value"]]
    joined = (
        nco.merge(all_pd, on=JOIN_KEY)
           .merge(deduped["results.lgd"][JOIN_KEY + ["LGD Value"]], on=JOIN_KEY)
           .merge(ead, on=JOIN_KEY)
    )
    report.check(len(joined) == len(nco),
                 "NCO joins 1:1 to coalesce(pd, pd_crr) / LGD / EAD",
                 f"{len(nco):,} -> {len(joined):,}")
    report.check(
        len(joined) == len(nco) and joined["PD Value"].notna().all(),
        "every NCO row finds a PD row in one of the two PD sheets",
    )
    expected = joined["PD Value"] * joined["LGD Value"] * joined["EAD Value"]
    relative = ((joined["NCO Value"] - expected).abs() / expected.where(expected != 0, 1.0))
    report.check(relative.max() <= NCO_RELATIVE_TOLERANCE,
                 f"NCO = PD x LGD x EAD within {NCO_RELATIVE_TOLERANCE:g} relative",
                 f"max relative error {relative.max():.3e}")


def check_dedupe(report: Report, sheets: dict[str, pd.DataFrame], deduped: dict[str, pd.DataFrame]) -> None:
    report.group("Dedupe")
    for name, frame in sheets.items():
        run_key = NCO_RUN_KEY if name == "results.nco" else RUN_KEY
        executions = frame.groupby(run_key, observed=True)["Execution Datetime"].nunique()
        repeated = int((executions > 1).sum())
        report.check(repeated > 0, f"{name}: repeated runs exist for dedupe to act on",
                     f"{repeated} of {len(executions)} run keys re-run")

        report.check(frame.duplicated(run_key + GRAIN).any(),
                     f"{name}: grain is NOT unique before dedupe",
                     f"{int(frame.duplicated(run_key + GRAIN).sum()):,} duplicate rows")

        after = deduped[name]
        report.check(not after.duplicated(run_key + GRAIN).any(),
                     f"{name}: grain IS unique after dedupe",
                     f"{len(after):,} rows")

        one_execution = after.groupby(run_key, observed=True)["Execution Datetime"].nunique()
        report.check((one_execution == 1).all(),
                     f"{name}: exactly one execution survives per run key")

    # Superseded rows are deliberately inconsistent with the loss identity, so a
    # consumer that reconciles before deduping cannot pass by accident.
    report.group("Superseded rows")
    nco_all = sheets["results.nco"]
    superseded = nco_all.merge(
        deduped["results.nco"][JOIN_KEY + ["NCO Value"]].rename(columns={"NCO Value": "_kept"}),
        on=JOIN_KEY, how="left",
    )
    superseded = superseded[superseded["NCO Value"] != superseded["_kept"]]
    report.check(len(superseded) > 0, "superseded NCO rows present",
                 f"{len(superseded):,} rows")

    # Join every sheet on the execution too, so each raw row meets its own
    # execution's counterparts and the count below is the true number of
    # superseded rows rather than a fan-out artefact.
    execution_key = JOIN_KEY + ["Execution Datetime"]
    raw_pd = pd.concat(
        [sheets[sheet][execution_key + ["PD Value"]] for sheet in PD_SHEETS],
        ignore_index=True,
    )
    joined = (
        sheets["results.nco"][execution_key + ["NCO Value"]]
        .merge(raw_pd, on=execution_key)
        .merge(sheets["results.lgd"][execution_key + ["LGD Value"]], on=execution_key)
        .merge(sheets["results.ead"][execution_key + ["EAD Value"]], on=execution_key)
    )
    report.check(len(joined) == len(sheets["results.nco"]),
                 "raw rows join 1:1 on (join key + execution)",
                 f"{len(sheets['results.nco']):,} -> {len(joined):,}")
    product = joined["PD Value"] * joined["LGD Value"] * joined["EAD Value"]
    mismatched = ((joined["NCO Value"] - product).abs() / product > NCO_RELATIVE_TOLERANCE).sum()
    report.check(mismatched > 0,
                 "reconciling WITHOUT dedupe fails (proves dedupe is required)",
                 f"{int(mismatched):,} of {len(joined):,} raw rows do not reconcile")


def _actual_vs_forecast(frame: pd.DataFrame, value_column: str) -> pd.DataFrame:
    """Forecast-vs-actual pairs on the Base scenario, using the Quarter-0 anchor.

    The actual for calendar quarter *t* is the Quarter-0 row of the vintage whose
    snapshot *is* *t*; a forecast of *t* is any row where snapshot index + Quarter
    equals *t*.
    """
    snapshots = sorted(frame["Month End Snapshot"].unique())
    index = {value: position for position, value in enumerate(snapshots)}
    frame = frame.copy()
    frame["_s"] = frame["Month End Snapshot"].map(index)
    frame["_t"] = frame["_s"] + frame["Quarter"]

    actuals = (
        frame[frame["Quarter"] == 0][["Facility ID", "Credit Instrument ID", "_s", value_column]]
        .drop_duplicates(["Facility ID", "Credit Instrument ID", "_s"])
        .rename(columns={"_s": "_t", value_column: "_actual"})
    )
    forecasts = frame[(frame["Quarter"] >= 1) & (frame["Scenario"] == "Base")]
    paired = forecasts.merge(actuals, on=["Facility ID", "Credit Instrument ID", "_t"])
    paired["_rel"] = paired[value_column] / paired["_actual"] - 1.0
    return paired


def check_error_structure(report: Report, deduped: dict[str, pd.DataFrame]) -> None:
    report.group("Anchors and coverage")
    # Measured on the portfolio's PD -- both sheets stacked -- because neither
    # PD sheet alone covers the population.
    frame = combined_pd(deduped)
    anchors = frame[frame["Quarter"] == 0]
    report.check(len(anchors) > 0, "Quarter 0 realised anchors present", f"{len(anchors):,} rows")

    invariance = anchors.groupby(
        ["Facility ID", "Credit Instrument ID", "Month End Snapshot"], observed=True
    )["PD Value"].nunique()
    report.check((invariance == 1).all(),
                 "Quarter 0 identical across all scenarios and both J/N flags",
                 f"max distinct values {int(invariance.max())}")

    paired = _actual_vs_forecast(frame, "PD Value")
    report.check(len(paired) > 0, "forecast/actual pairs resolvable", f"{len(paired):,} pairs")
    unmatched_targets = frame[(frame["Quarter"] >= 1)].assign(
        _t=frame["Month End Snapshot"].map(
            {v: i for i, v in enumerate(sorted(frame["Month End Snapshot"].unique()))}
        ) + frame["Quarter"]
    )
    beyond = int((unmatched_targets["_t"] > N_SNAPSHOTS - 1).sum())
    report.check(beyond > 0,
                 "recent horizons have no actual yet (as in production)",
                 f"{beyond:,} forecast rows target quarters past the last snapshot")

    report.group("Injected error structure")
    clean = paired[paired["_s"] != BAD_VINTAGE_INDEX]

    by_horizon = clean.groupby("Quarter")["_rel"].apply(lambda s: s.abs().mean())
    increasing = by_horizon.is_monotonic_increasing
    report.check(increasing, "error grows monotonically with projection horizon",
                 f"q1={by_horizon.iloc[0]:.4f} -> q{int(by_horizon.index[-1])}={by_horizon.iloc[-1]:.4f}")

    near = clean[clean["Quarter"] <= 2]["_rel"].mean()
    long_horizon = clean[clean["Quarter"] >= 6]["_rel"].mean()
    report.check(long_horizon < 0 and long_horizon < near,
                 "optimistic (loss under-forecasting) bias at long horizons",
                 f"mean error q<=2 {near:+.4f} vs q>=6 {long_horizon:+.4f}")

    by_flag = paired.groupby("J/N Flag")["_rel"].apply(lambda s: s.abs().mean())
    report.check(by_flag["J"] < by_flag["N"], "J-flagged runs more accurate than N",
                 f"J={by_flag['J']:.4f} vs N={by_flag['N']:.4f}")

    by_vintage = paired.groupby("_s")["_rel"].apply(lambda s: s.abs().mean())
    bad = by_vintage.get(BAD_VINTAGE_INDEX)
    others = by_vintage.drop(index=BAD_VINTAGE_INDEX)
    report.check(bad is not None and bad > others.max() * 2,
                 "one deliberately bad vintage stands out across its horizons",
                 f"vintage {BAD_VINTAGE_INDEX} MAE {bad:.4f} vs worst other {others.max():.4f}")

    by_segment = paired.groupby("Segment Name")["_rel"].apply(lambda s: s.abs().mean())
    worst = by_segment.idxmax()
    rest = by_segment.drop(index=worst)
    report.check(by_segment[worst] > rest.max() * 1.4,
                 "one segment materially worse than the others",
                 f"{worst}={by_segment[worst]:.4f} vs " +
                 ", ".join(f"{k}={v:.4f}" for k, v in rest.items()))

    # Both populations must carry the structure independently -- a dashboard
    # filtered to one PD source should still show a horizon effect.
    for sheet in PD_SHEETS:
        sheet_paired = _actual_vs_forecast(deduped[sheet], "PD Value")
        sheet_clean = sheet_paired[sheet_paired["_s"] != BAD_VINTAGE_INDEX]
        horizon = sheet_clean.groupby("Quarter")["_rel"].apply(lambda s: s.abs().mean())
        report.check(horizon.iloc[-1] > horizon.iloc[0] * 2,
                     f"{sheet}: error grows with horizon within its own population",
                     f"q{int(horizon.index[0])}={horizon.iloc[0]:.4f} -> q{int(horizon.index[-1])}={horizon.iloc[-1]:.4f}")


def main() -> int:
    if not WORKBOOK_PATH.exists():
        print(f"Workbook not found: {WORKBOOK_PATH}")
        print("Run: .venv/bin/python source_data/generate_backtesting_data.py")
        return 1

    print(f"Verifying {WORKBOOK_PATH.name}  ({WORKBOOK_PATH.stat().st_size / (1024 * 1024):.1f} MB)")
    workbook = pd.ExcelFile(WORKBOOK_PATH)
    sheet_names = list(workbook.sheet_names)
    sheets = {name: workbook.parse(name) for name in sheet_names if name in EXPECTED_COLUMNS}

    missing = set(EXPECTED_COLUMNS) - set(sheets)
    if missing:
        print(f"Missing required sheets: {sorted(missing)}")
        return 1

    deduped = {
        name: dedupe_runs(frame, NCO_RUN_KEY if name == "results.nco" else RUN_KEY)
        for name, frame in sheets.items()
    }

    report = Report()
    check_structure(report, sheets, sheet_names)
    check_content(report, sheets)
    check_joins(report, sheets, deduped)
    check_dedupe(report, sheets, deduped)
    check_error_structure(report, deduped)
    return report.summary()


if __name__ == "__main__":
    sys.exit(main())
