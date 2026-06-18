import os
from pathlib import Path

import pandas as pd

os.environ["OPENAI_API_KEY"] = ""
os.environ["API_KEY"] = ""
os.environ["MODEL_1_API_KEY"] = ""
os.environ["MODEL_2_API_KEY"] = ""
os.environ["DATABASE_PATH"] = str(Path(__file__).resolve().parents[1] / "storage" / "test_app.sqlite3")

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import normalize_openai_base_url
from app.models.schemas import GeneratedAnalysis
from app.services import analysis_service, comprehensive_analysis_service


def test_openai_base_url_normalization_accepts_service_roots():
    assert normalize_openai_base_url("https://api.86gamestore.com") == "https://api.86gamestore.com/v1"
    assert normalize_openai_base_url("https://api.86gamestore.com/v1") == "https://api.86gamestore.com/v1"
    assert (
        normalize_openai_base_url("https://api.86gamestore.com/v1/chat/completions")
        == "https://api.86gamestore.com/v1"
    )


def test_upload_preview_and_client_config():
    with TestClient(app) as client:
        config = client.get("/api/config/client")
        assert config.status_code == 200
        languages = config.json()["data"]["supported_languages"]
        assert {item["code"] for item in languages} == {"en", "zh", "ms"}
        models = config.json()["data"]["models"]
        assert config.json()["data"]["default_model_id"]
        assert models

        response = client.post(
            "/api/datasets/upload",
            files={"file": ("economic.csv", b"country,year,gdp\nMalaysia,2020,337\nChina,2020,14722\n", "text/csv")},
        )
        assert response.status_code == 200
        dataset_id = response.json()["data"]["dataset_id"]

        preview = client.get(f"/api/datasets/{dataset_id}/preview")
        assert preview.status_code == 200
        assert preview.json()["data"]["row_count"] == 2


def test_analysis_query_history_and_report(monkeypatch):
    def fake_generate_analysis_code(dataset_schema, question, language, chart_preference="auto", model_id=None):
        return GeneratedAnalysis.model_validate(
            {
                "intent": "comparison",
                "target_fields": ["country", "gdp"],
                "filters": [],
                "chart_type": "bar",
                "steps": ["group by country", "sum GDP"],
                "code": (
                    "result_table = df.groupby('country', as_index=False)['gdp'].sum()\n"
                    "chart_spec = {'chart_type': 'bar', 'x_field': 'country', "
                    "'y_field': 'gdp', 'title': 'GDP by country'}"
                ),
                "chart_spec": {
                    "chart_type": "bar",
                    "x_field": "country",
                    "y_field": "gdp",
                    "title": "GDP by country",
                },
                "confidence": 0.9,
            }
        )

    monkeypatch.setattr(analysis_service.llm_service, "generate_analysis_code", fake_generate_analysis_code)
    monkeypatch.setattr(
        analysis_service.llm_service,
        "explain_result",
        lambda **kwargs: "The table compares GDP by country.",
    )

    with TestClient(app) as client:
        upload = client.post(
            "/api/datasets/upload",
            files={"file": ("analysis.csv", b"country,year,gdp\nMalaysia,2020,337\nChina,2020,14722\n", "text/csv")},
        )
        dataset_id = upload.json()["data"]["dataset_id"]

        response = client.post(
            "/api/analysis/query",
            json={
                "dataset_id": dataset_id,
                "question": "Compare GDP by country",
                "options": {
                    "language": "zh",
                    "model_id": "gpt-5.5",
                    "chart_preference": "bar",
                    "include_generated_code": True,
                },
            },
        )
        assert response.status_code == 200
        analysis = response.json()["data"]
        assert analysis["model_id"] == "gpt-5.5"
        assert analysis["generated_code"]
        assert analysis["chart_url"]
        assert "## Summary" in analysis["markdown_result"]
        assert "```python" in analysis["markdown_result"]
        assert "| country | gdp |" in analysis["markdown_result"]

        history = client.get("/api/analysis/history", params={"dataset_id": dataset_id})
        assert history.status_code == 200
        assert history.json()["data"]["total"] >= 1

        report = client.post("/api/reports/export", json={"analysis_id": analysis["analysis_id"], "format": "html"})
        assert report.status_code == 200
        assert report.json()["data"]["report_url"].endswith("/download")

        markdown_report = client.post(
            "/api/reports/export",
            json={"analysis_id": analysis["analysis_id"], "format": "md"},
        )
        assert markdown_report.status_code == 200
        markdown_download = client.get(markdown_report.json()["data"]["report_url"])
        assert markdown_download.status_code == 200
        assert "# Analysis Report" in markdown_download.text
        assert "| country | gdp |" in markdown_download.text

        pdf_report = client.post(
            "/api/reports/export",
            json={"analysis_id": analysis["analysis_id"], "format": "pdf"},
        )
        assert pdf_report.status_code == 200
        pdf_download = client.get(pdf_report.json()["data"]["report_url"])
        assert pdf_download.status_code == 200
        assert pdf_download.content.startswith(b"%PDF")


def test_analysis_query_retries_after_generated_code_validation_error(monkeypatch):
    calls = []

    def fake_generate_analysis_code(
        dataset_schema,
        question,
        language,
        chart_preference="auto",
        model_id=None,
        retry_feedback=None,
    ):
        calls.append(retry_feedback)
        if len(calls) == 1:
            code = "import os\nresult_table = []\nchart_spec = {'chart_type': 'table', 'title': 'Invalid'}"
        else:
            assert retry_feedback["error_code"] == "CODE_UNSAFE"
            code = (
                "result_table = df.groupby('country', as_index=False)['gdp'].sum()\n"
                "chart_spec = {'chart_type': 'bar', 'x_field': 'country', "
                "'y_field': 'gdp', 'title': 'GDP by country'}"
            )
        return GeneratedAnalysis.model_validate(
            {
                "intent": "comparison",
                "target_fields": ["country", "gdp"],
                "filters": [],
                "chart_type": "bar",
                "steps": ["group by country", "sum GDP"],
                "code": code,
                "chart_spec": {
                    "chart_type": "bar",
                    "x_field": "country",
                    "y_field": "gdp",
                    "title": "GDP by country",
                },
                "confidence": 0.8,
            }
        )

    monkeypatch.setattr(analysis_service.llm_service, "generate_analysis_code", fake_generate_analysis_code)
    monkeypatch.setattr(
        analysis_service.llm_service,
        "explain_result",
        lambda **kwargs: "The table compares GDP by country.",
    )

    with TestClient(app) as client:
        upload = client.post(
            "/api/datasets/upload",
            files={"file": ("retry.csv", b"country,year,gdp\nMalaysia,2020,337\nChina,2020,14722\n", "text/csv")},
        )
        dataset_id = upload.json()["data"]["dataset_id"]

        response = client.post(
            "/api/analysis/query",
            json={
                "dataset_id": dataset_id,
                "question": "Compare GDP by country",
                "options": {"language": "en", "model_id": "gpt-5.5"},
            },
        )

    assert response.status_code == 200
    assert len(calls) == 2
    assert response.json()["data"]["table_result"]


def test_comprehensive_analysis_includes_predictive_metrics():
    frame = {
        "age": list(range(20, 120)),
        "income": [3200 + index * 11 for index in range(100)],
        "segment": ["A" if index % 2 else "B" for index in range(100)],
        "churn": ["yes" if index % 3 == 0 else "no" for index in range(100)],
    }
    report = comprehensive_analysis_service.build_comprehensive_analysis(
        dataset_id="ds_metrics_test",
        df=pd.DataFrame(frame),
        question="predict churn",
    )

    model = report["predictive_model"]
    assert model["status"] == "completed"
    assert model["task_type"] == "classification"
    assert "accuracy" in model["holdout_metrics"]
    assert "f1_macro" in model["holdout_metrics"]
    assert "accuracy_mean" in model["cross_validation"]
    assert "f1_macro_mean" in model["cross_validation"]
    assert report["charts"]
