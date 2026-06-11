# Dashboards

## Setup

Install the Python dependencies before running the pipeline:

```powershell
python -m pip install -r requirements.txt
```

Run the data quality dashboard:

```powershell
python app.py --config config.yaml
```

Run the monitoring dashboard:

```powershell
python app.py --config monitoring_config.yaml
```
