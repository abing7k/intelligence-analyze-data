from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.i18n import normalize_language


ChartType = Literal["auto", "line", "bar", "pie", "scatter", "heatmap", "table"]


class AnalysisOptions(BaseModel):
    language: str = "en"
    model_id: str | None = None
    chart_preference: ChartType = "auto"
    include_generated_code: bool = True

    @field_validator("language")
    @classmethod
    def normalize_requested_language(cls, value: str) -> str:
        return normalize_language(value)


class AnalysisRequest(BaseModel):
    dataset_id: str = Field(min_length=1)
    question: str = Field(min_length=2, max_length=4000)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ReportExportRequest(BaseModel):
    analysis_id: str | None = None
    history_id: str | None = None
    format: Literal["html", "txt", "md", "markdown", "pdf"] = "html"


class DatasetColumn(BaseModel):
    name: str
    dtype: str
    missing_count: int
    sample_values: list[Any] = Field(default_factory=list)


class DatasetSchema(BaseModel):
    dataset_id: str
    row_count: int
    column_count: int
    columns: list[DatasetColumn]


class ChartSpec(BaseModel):
    chart_type: ChartType = "auto"
    x_field: str | None = None
    y_field: str | None = None
    group_field: str | None = None
    title: str | None = None


class GeneratedAnalysis(BaseModel):
    intent: str = "data_analysis"
    target_fields: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    chart_type: ChartType = "auto"
    steps: list[str] = Field(default_factory=list)
    code: str
    chart_spec: ChartSpec = Field(default_factory=ChartSpec)
    confidence: float | None = None
