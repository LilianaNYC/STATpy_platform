# STATpy — Estructura de archivos

```
STATPY_DESKTOP_DASH
├── .idea
├── .venv
├── .vscode
└── Dash
    │
    ├── callbacks/
    │   ├── __pycache__
    │   ├── acl_models_callbacks.py
    │   ├── historical_portfolio_callbacks.py
    │   ├── lldr_calculations_callbacks.py
    │   ├── loss_calculations_callbacks.py
    │   ├── mev_input_callbacks.py
    │   ├── nco_models_callbacks.py
    │   └── results_callbacks.py
    │
    ├── pages/
    │   ├── __pycache__
    │   ├── acl_models_page.py
    │   ├── cbre_ncreif_input_page.py
    │   ├── create_model_csv_page.py
    │   ├── database_selector_page.py
    │   ├── dq_calculations_page.py
    │   ├── dq_visualization_page.py
    │   ├── export_model_to_mlflow_page.py
    │   ├── historical_portfolio_page.py
    │   ├── home_page.py
    │   ├── jump_off_input_page.py
    │   ├── lldr_calculation_page.py
    │   ├── loss_backtesting_page.py
    │   ├── loss_calculations_page.py
    │   ├── mev_input_page.py
    │   ├── model_assessment_page.py
    │   ├── nco_models_page.py
    │   ├── new_business_input_page.py
    │   ├── register_mlflow_model.py
    │   ├── results_calculation_page.py
    │   ├── run_config_page.py
    │   └── variable_transformation_page.py
    │
    ├── mlflow/
    │   ├── mlflow_script.txt
    │   └── mlflow.exe
    │
    ├── __pycache__
    ├── assets
    ├── backtesting
    ├── components
    ├── config
    ├── model_development
    │
    ├── __init__.py
    ├── app1.py
    ├── backtesting_run.py
    ├── data_manager.py
    ├── dockerfile
    ├── dscr_model.py
    ├── ead_model.py
    ├── ead_run.py
    ├── lgd_model.py
    ├── lgd_run.py
    ├── loss_models.py
    ├── mapper_handler.py
    ├── model_loader.py
    ├── model_mev_transformations.py
    ├── model_template.py
    ├── pd_model.py
    ├── pd_run.py
    ├── results_calculation.py
    ├── run_model.py
    ├── .gitignore
    ├── ECL_Transformation_Selection_Template…   (nombre truncado en la captura)
    ├── mlflow.db
    ├── python_packages.txt
    └── README.md
```

## Notas

- Las tres carpetas principales dentro de `Dash/` son **`callbacks/`**, **`pages/`** y **`mlflow/`**.
- `assets/`, `backtesting/`, `components/`, `config/`, `model_development/` y `__pycache__` son carpetas dentro de `Dash/` cuyo contenido no aparece en las capturas (quedan colapsadas).
- El resto son archivos sueltos directamente dentro de `Dash/`.
- El nombre `ECL_Transformation_Selection_Template…` aparece cortado en la imagen; falta confirmar la extensión completa.
```
