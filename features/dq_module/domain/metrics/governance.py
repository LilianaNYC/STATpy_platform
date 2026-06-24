"""Governance page data builders — exec summary, issues, recommendations."""

from __future__ import annotations

from datetime import datetime


def gen_exec_summary(tech: dict, completeness: dict, rules: dict, population: dict, drift: dict):
    rating = "GREEN" if completeness["overall_pct"] >= 98 and rules["critical_failures"] == 0 else \
             "MODERATE" if completeness["overall_pct"] >= 95 else "RED"
    return (
        f"Overall data quality is rated {rating} for this snapshot period. "
        f"Portfolio completeness stands at {completeness['overall_pct']:.1f}%, "
        f"with {rules['rules_failed']} of {rules['total_executed']} business rules reporting failures "
        f"({rules['critical_failures']} critical). "
        f"Population shows {population['new']} new and {population['dropped']} dropped accounts "
        f"(net {population['net_change']:+d}). "
        f"Distribution drift status is {drift['drift_status']} with average PSI of {drift['avg_psi']:.3f}. "
        f"Key areas requiring attention: completeness of CRE-specific fields and rating integrity."
    ), rating


def gen_population_insights(pop: dict) -> list[dict]:
    insights = [
        {
            "icon": "growth",
            "text": f"Population grew by {pop['net_change_pct']:+.2f}% driven by {pop['new']} new originations "
                    f"across all business segments.",
        },
        {
            "icon": "info",
            "text": f"PSI stands at {pop['psi']:.2f} ({pop['psi_label']}), indicating "
                    + ("no significant shift in overall population mix." if pop["psi_label"] == "Stable"
                       else "moderate population composition shifts requiring review."),
        },
    ]
    if pop["by_segment"]:
        top_churn = max(pop["by_segment"], key=lambda s: s.get("dropped_pct", 0))
        insights.append({
            "icon": "warning",
            "text": f"{top_churn['segment']} segment experienced highest churn "
                    f"({top_churn['dropped_pct']:.1f}% dropped) — monitor for paydowns and exits.",
        })
    insights.append({
        "icon": "monitor",
        "text": "Monitor continuing account distribution stability across segments for model input integrity.",
    })
    return insights


def gen_drift_insights(drift: dict) -> list[dict]:
    if not drift["by_variable"]:
        return [{"icon": "info", "text": "No drift data available for this period."}]
    top = drift["by_variable"][0] if drift["by_variable"] else None
    return [
        {
            "icon": "warning",
            "text": f"{top['column']} shows {top['level'].lower()} drift (PSI={top['psi']:.2f}) vs prior quarter, "
                    "primarily driven by portfolio mix shifts.",
        } if top else {"icon": "info", "text": "No significant drift detected."},
        {
            "icon": "info",
            "text": f"Average PSI across {drift['columns_analyzed']} variables is {drift['avg_psi']:.3f} "
                    f"({drift['drift_status']}). {drift['sig_drift_count']} variables exceed the 0.20 threshold.",
        },
        {
            "icon": "search",
            "text": "Loan amount and EAD distribution shifts are primarily driven by larger transactions in CIB.",
        },
        {
            "icon": "monitor",
            "text": "Monitor downstream impact on Expected Loss and Stress Testing model inputs.",
        },
    ]


def build_issues(rules: dict, completeness: dict) -> list[dict]:
    issues = []
    for r in rules["by_rule"]:
        if not r["passed"]:
            issues.append({
                "name": r["description"],
                "severity": r["severity"],
                "affected_records": r["failed_records"],
                "affected_pct": r["failure_rate_pct"],
                "root_cause": f"Validation failure in {r['column']} — records do not satisfy rule {r['code']}.",
                "impact": f"Affects {r['domain']} calculations and downstream reporting accuracy.",
                "use_cases": "ECL, CCAR, Regulatory Reporting",
                "owner": "Data Quality Team",
                "status": "Open",
                "opened_date": datetime.now().strftime("%Y-%m-%d"),
                "target_date": datetime.now().strftime("%Y-%m-%d"),
                "days_open": 0,
                "likelihood": "High" if r["severity"] in ("Critical", "High") else "Medium",
                "business_impact": "High" if r["severity"] == "Critical" else "Medium",
            })
    high_missing = [c for c in completeness["by_column"] if c["missing_pct"] >= 10.0][:3]
    for c in high_missing:
        issues.append({
            "name": f"High missing rate: {c['column']}",
            "severity": c["severity"],
            "affected_records": c["missing_n"],
            "affected_pct": c["missing_pct"],
            "root_cause": f"{c['column']} has {c['missing_pct']:.1f}% missing values — likely upstream sourcing gap.",
            "impact": "Incomplete data may skew portfolio risk metrics.",
            "use_cases": "Risk Analytics, Model Inputs",
            "owner": "Data Engineering",
            "status": "In Progress",
            "opened_date": datetime.now().strftime("%Y-%m-%d"),
            "target_date": datetime.now().strftime("%Y-%m-%d"),
            "days_open": 0,
            "likelihood": "Medium",
            "business_impact": "Medium",
        })
    return issues


def build_recommendations(rules: dict, completeness: dict, drift: dict) -> list[dict]:
    recs = []
    critical_rules = [r for r in rules["by_rule"] if r["severity"] == "Critical" and not r["passed"]]
    if critical_rules:
        recs.append({
            "text": f"Resolve {len(critical_rules)} critical rule failure(s) in {critical_rules[0]['column']} before next reporting cycle.",
            "priority": "Critical",
            "owner": "Data Quality Team",
            "eta": datetime.now().strftime("%Y-%m-%d"),
        })
    high_missing = [c for c in completeness["by_column"] if c["missing_pct"] >= 25.0]
    if high_missing:
        recs.append({
            "text": f"Investigate and remediate critical missing data in {high_missing[0]['column']} ({high_missing[0]['missing_pct']:.1f}% missing).",
            "priority": "High",
            "owner": "Data Engineering",
            "eta": datetime.now().strftime("%Y-%m-%d"),
        })
    if drift["sig_drift_count"] > 0:
        top_drift = drift["by_variable"][0]
        recs.append({
            "text": f"Review {top_drift['column']} distribution shift (PSI={top_drift['psi']:.2f}) — validate with upstream source teams.",
            "priority": "High",
            "owner": "Model Risk Team",
            "eta": datetime.now().strftime("%Y-%m-%d"),
        })
    recs.append({
        "text": "Schedule quarterly DQ review with model owners and risk managers for sign-off on governance notes.",
        "priority": "Medium",
        "owner": "Data Governance",
        "eta": datetime.now().strftime("%Y-%m-%d"),
    })
    return recs
