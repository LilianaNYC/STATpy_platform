from __future__ import annotations

import pandas as pd

from STATpy_platform.features.monitoring.repositories import loader as monitoring_loader
from STATpy_platform.features.saas.repositories import loader as saas_loader


class _DummyExcelFile:
    def close(self) -> None:
        return None


def test_saas_loader_reads_model_contribution_column(monkeypatch):
    transformed_df = pd.DataFrame(
        [
            {
                "Model Name": "Model A",
                "Segment": "Segment A",
                "US Mnemonic": "TRANS_A",
                "Long Name": "Transformed A",
                "Description": "Example",
                "SAAS_raw_mnemonic": "RAW_A",
                "Model Contribution": 0.42,
            }
        ]
    )
    raw_df = pd.DataFrame(
        [
            {
                "US Mnemonic": "RAW_A",
                "Long Name": "Raw A",
                "Description": "Raw example",
                "Group Mnemonic": "GROUP_A",
            }
        ]
    )
    time_series_df = pd.DataFrame(
        [
            {
                "Date": "2025-03-31",
                "Quarter": 0,
                "Run For": "2025Q4",
                "Scenario": "baseline",
                "MEV Name": "TRANS_A",
                "MEV Value": 1.0,
            }
        ]
    )
    characteristic_df = pd.DataFrame(
        [
            {
                "Model Name": "Model A",
                "Run For": "2025Q4",
                "Model Descriptive Name": "Model A",
                "Development Date": "2025-03-31",
            }
        ]
    )

    def fake_read_excel(_source, sheet_name=None, usecols=None, **_kwargs):
        if sheet_name == saas_loader.config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME:
            if usecols:
                return transformed_df[list(usecols)]
            return transformed_df.copy()
        if sheet_name == saas_loader.config.DUMMY_MEV_RAW_DESCRIPTION_SHEET_NAME:
            return raw_df.copy()
        if sheet_name == saas_loader.config.DUMMY_MEV_TIME_SERIES_SHEET_NAME:
            return time_series_df.copy()
        if sheet_name == saas_loader.config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME:
            return characteristic_df.copy()
        raise AssertionError(f"Unexpected sheet requested: {sheet_name}")

    monkeypatch.setattr(saas_loader.pd, "read_excel", fake_read_excel)

    payload = saas_loader.load_saas_mev_workbook_data()

    assert payload["model_mev_contribution_map"] == {"Model A": {"TRANS_A": 0.42}}


def test_monitoring_loader_reads_model_contribution_column(monkeypatch):
    characteristic_df = pd.DataFrame(
        [
            {
                "Model Name": "Model A",
                "Development Date": "2025-03-31",
                "Model Descriptive Name": "Model A",
                "Model Type": "PD",
            }
        ]
    )
    description_df = pd.DataFrame(
        [
            {
                "Model Name": "Model A",
                "Segment": "Segment A",
                "US Mnemonic": "TRANS_A",
                "Long Name": "Transformed A",
                "Description": "Example",
                "Model Contribution": 0.42,
            }
        ]
    )
    time_series_df = pd.DataFrame(
        [
            {
                "Model Name": "Model A",
                "Date": "2025-03-31",
                "Quarter": 0,
                "Run For": "2025Q4",
                "Scenario": "baseline",
                "MEV Name": "TRANS_A",
                "MEV Value": 1.0,
            }
        ]
    )

    def fake_read_excel(_source, sheet_name=None, **_kwargs):
        if sheet_name == monitoring_loader.config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME:
            return characteristic_df.copy()
        if sheet_name == monitoring_loader.config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME:
            return description_df.copy()
        if sheet_name == monitoring_loader.config.DUMMY_MEV_TIME_SERIES_SHEET_NAME:
            return time_series_df.copy()
        raise AssertionError(f"Unexpected sheet requested: {sheet_name}")

    monkeypatch.setattr(monitoring_loader.pd, "ExcelFile", lambda _path: _DummyExcelFile())
    monkeypatch.setattr(monitoring_loader.pd, "read_excel", fake_read_excel)

    catalog, _mev_map, _desc_map = monitoring_loader.load_pd_mev_catalog()

    assert catalog["Model A"]["contributions"] == {"Transformed A": 0.42}


def test_saas_loader_ignores_legacy_model_controbution_column(monkeypatch):
    transformed_df = pd.DataFrame(
        [
            {
                "Model Name": "Model A",
                "Segment": "Segment A",
                "US Mnemonic": "TRANS_A",
                "Long Name": "Transformed A",
                "Description": "Example",
                "SAAS_raw_mnemonic": "RAW_A",
                "Model controbution": 0.42,
            }
        ]
    )
    raw_df = pd.DataFrame(
        [
            {
                "US Mnemonic": "RAW_A",
                "Long Name": "Raw A",
                "Description": "Raw example",
                "Group Mnemonic": "GROUP_A",
            }
        ]
    )
    time_series_df = pd.DataFrame(
        [
            {
                "Date": "2025-03-31",
                "Quarter": 0,
                "Run For": "2025Q4",
                "Scenario": "baseline",
                "MEV Name": "TRANS_A",
                "MEV Value": 1.0,
            }
        ]
    )
    characteristic_df = pd.DataFrame(
        [
            {
                "Model Name": "Model A",
                "Run For": "2025Q4",
                "Model Descriptive Name": "Model A",
                "Development Date": "2025-03-31",
            }
        ]
    )

    def fake_read_excel(_source, sheet_name=None, usecols=None, **_kwargs):
        if sheet_name == saas_loader.config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME:
            if usecols:
                return transformed_df[list(usecols)]
            return transformed_df.copy()
        if sheet_name == saas_loader.config.DUMMY_MEV_RAW_DESCRIPTION_SHEET_NAME:
            return raw_df.copy()
        if sheet_name == saas_loader.config.DUMMY_MEV_TIME_SERIES_SHEET_NAME:
            return time_series_df.copy()
        if sheet_name == saas_loader.config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME:
            return characteristic_df.copy()
        raise AssertionError(f"Unexpected sheet requested: {sheet_name}")

    monkeypatch.setattr(saas_loader.pd, "read_excel", fake_read_excel)

    payload = saas_loader.load_saas_mev_workbook_data()

    assert payload["model_mev_contribution_map"] == {}
