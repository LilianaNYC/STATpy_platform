# Overview of STATpy Functionality and Structure

# STATpy — Application Summary

## Overview

STATpy (US STATpy) is an internal credit risk stress testing and loss forecasting desktop web application built with **Python Dash (Plotly)**. It provides a UI-driven workflow to run credit loss projections (PD, EAD, LGD), compute loss metrics (NCO, ACL, NPL, LLDR), manage model lifecycle via MLflow, and review/export results — all backed by a local **SQL Server (LocalDB)** database and a local **MLflow** model registry.

The app is launched by running two services in parallel:

1. An **MLflow tracking server** (SQLite backend + local artifact store)
2. The **Dash app** (`app1.py`)

---

## Architecture

| Layer | Technology |
|---|---|
| Frontend / UI | Plotly Dash + Dash Bootstrap Components (FLATLY theme) |
| Backend logic | Python (pandas, polars, numpy, scikit-learn) |
| Database | Microsoft SQL Server LocalDB (`(LocalDB)\STAT_UAT`) via SQLAlchemy + pyodbc |
| Model registry | MLflow (localhost:5000) |
| Web server | Flask (embedded in Dash) |

The layout is a **sidebar navigation + page content** pattern using Dash's `use_pages=True` multi-page feature. All callbacks are modularized in the `callbacks/` directory and imported at startup in `app1.py`.

---

## Core Modules

| Module | File | Role |
|---|---|---|
| DataManager | `data_manager.py` | Abstract base + concrete implementations for Jumpoff, New Business Growth (NBG), MEV data sources. Handles all SQL read/write operations against LocalDB. |
| MlflowModelLoader | `model_loader.py` | Connects to MLflow registry, lists/loads versioned PD/EAD/LGD models (pyfunc), exports custom models. |
| CalculationModule | `run_model.py` | Orchestrates model projection runs — loads portfolio data, applies MEV transformations, executes loaded MLflow models, writes results back to SQL. |
| LossCalculations | `loss_models.py` | Aggregates PD/EAD/LGD projection outputs from SQL and applies loss methodologies (NCO, NPL, ACL) to compute facility-level and segment-level losses. |
| ModelMevTransformation | `model_mev_transformations.py` | Applies variable transformations to Macroeconomic Variables (MEVs) before model scoring. |
| Config | `nco_models_config.py`, `config/loss_calculations_config.py` | Loads active segment names and registered model lists dynamically from `STAT_Config` DB and MLflow at startup. |

---

## Database Structure (SQL Server LocalDB)

The app connects to multiple named databases:

- **`STAT_Config`** — master configuration: run-for definitions, segment logic, model metadata (`dbo.run_details`, `dbo.segment_logic`, `ModelInformation` ORM table).
- **Input databases** (per run) — portfolio data: `input.Jumpoff_ALLL`, `input.new_business`, `input.scenario`, CBRE/NCREIF data.
- **Result databases** (NCO/ACL per run) — projection outputs: `results.pd`, `results.pd_crr`, `results.ead`, `results.lgd`, loss outputs.

---

## Navigation Structure & Pages

### Model Development

- **Create Model CSV** — prepares training data CSVs for model development.
- **Export Model to MLflow** — packages a trained model and logs it to the MLflow tracking server.
- **Register MLflow Model** — promotes a logged run to a named registered model version.

### Configuration

- **Database Selector** — maps a "Run For" stress testing cycle to its input/output databases.
- **Run Configuration** — defines projection parameters for a stress testing cycle (projection length, portfolio date, etc.).
- **Variable Transformation** — configures MEV variable transformation logic per segment/model.

### Data Input

- **Scenario Input (MEV)** — loads macroeconomic scenario data (e.g., GDP, unemployment) into the input database.
- **Jumpoff Portfolio** — uploads/manages the jumpoff loan portfolio snapshot.
- **New Business Growth** — uploads/manages the new business growth portfolio.
- **CBRE & NCREIF Input** — uploads real estate index data used in CRE model projections.
- **Historical Portfolio** — manages historical portfolio data used for backtesting and DQ.

### Simulation

- **NCO Models** — runs PD/EAD/LGD model projections for NCO/NPL stress scenarios; user selects run-for, scenario, portfolio, and specific registered MLflow models per segment.
- **ACL Models** — same workflow as NCO but for ACL (CECL) projections.
- **Loss Calculations** — combines PD/EAD/LGD projection results per segment into NCO, NPL, or ACL loss figures; user selects model outputs to combine and the loss methodology.
- **Loss Backtesting** — runs backtesting of loss projections against actuals.
- **LLDR Calculation** — computes Loan Loss Disclosure Ratio from projection results.
- **Results Summary** — aggregates and displays final loss results across segments and scenarios.
- **Model Assessment** — evaluates model performance metrics on projection results.

### Visualization

- **Scenarios** — DQ and visualization of MEV scenario data (charts of macroeconomic inputs).
- **NCO/ACL Dashboard** — visual dashboard of projection outputs and loss results across runs.

---

## Key Workflows

### End-to-end stress test run

1. Configure a **Run For** cycle in the Configuration section → defines which databases to use.
2. Load **scenario MEV data** and **portfolio data** (Jumpoff or NBG) via Data Input pages.
3. Run **NCO/ACL Model Projections** → `CalculationModule` loads MLflow models, scores portfolio, writes PD/EAD/LGD results to SQL.
4. Run **Loss Calculations** → `LossCalculations` reads PD/EAD/LGD from SQL and writes NCO/ACL loss outputs.
5. Review aggregated outputs in **Results Summary** and **NCO/ACL Dashboard**.

### Model lifecycle

- Develop model in Jupyter notebooks (`model_development/`) → export to MLflow → register → select in simulation pages.

### Backtesting Sub-application

A separate Flask **Blueprint** (`backtesting.py`) is mounted onto the Dash server, serving Jinja2 HTML templates for backtesting model projections (PD, EAD) against historical data. It uses `BacktestingModelExecutioner` and exposes REST-style routes (e.g., `/backtesting_model_projection`).
