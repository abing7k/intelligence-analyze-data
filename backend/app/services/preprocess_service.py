from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import AppError


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [to_jsonable(item) for item in value.tolist()]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def dataframe_records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    view = df.head(limit) if limit else df
    return [
        {str(key): to_jsonable(value) for key, value in row.items()}
        for row in view.to_dict(orient="records")
    ]


def read_dataframe(file_path: str | Path) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return _read_csv(path)
        if suffix in {".xls", ".xlsx"}:
            return pd.read_excel(path)
    except Exception as exc:
        raise AppError(
            code="DATASET_READ_FAILED",
            message=f"Unable to read dataset: {exc}",
            status_code=400,
        ) from exc
    raise AppError(code="FILE_INVALID_TYPE", message="Only CSV, XLS, and XLSX files are supported.", status_code=400)


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gbk", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.read_csv(path, low_memory=False)


def schema_for_dataframe(dataset_id: str, df: pd.DataFrame) -> dict[str, Any]:
    columns = []
    for column in df.columns:
        series = df[column]
        samples = [
            to_jsonable(value)
            for value in series.dropna().head(5).tolist()
        ]
        columns.append(
            {
                "name": str(column),
                "dtype": str(series.dtype),
                "missing_count": int(series.isna().sum()),
                "sample_values": samples,
            }
        )
    return {
        "dataset_id": dataset_id,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": columns,
    }


def preview_for_dataframe(dataset_id: str, df: pd.DataFrame, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    dtypes = {str(column): str(dtype) for column, dtype in df.dtypes.items()}
    missing_values = {str(column): int(df[column].isna().sum()) for column in df.columns}
    return {
        "dataset_id": dataset_id,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(column) for column in df.columns],
        "dtypes": dtypes,
        "missing_values": missing_values,
        "preview_rows": dataframe_records(df, limit),
        "statistics": statistics_for_dataframe(df),
    }


def profile_for_dataframe(dataset_id: str, df: pd.DataFrame) -> dict[str, Any]:
    numeric_columns = [str(column) for column in df.select_dtypes(include=[np.number]).columns]
    datetime_columns = _detect_datetime_columns(df)
    categorical_columns = [
        str(column)
        for column in df.columns
        if str(column) not in numeric_columns and str(column) not in datetime_columns
    ]
    return {
        "dataset_id": dataset_id,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "numeric_columns": numeric_columns,
        "datetime_columns": datetime_columns,
        "categorical_columns": categorical_columns,
        "statistics": statistics_for_dataframe(df),
        "null_summary": {str(column): int(df[column].isna().sum()) for column in df.columns},
    }


def statistics_for_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        return {}
    described = numeric_df.describe().replace([np.inf, -np.inf], np.nan)
    return {
        str(column): {str(metric): to_jsonable(value) for metric, value in described[column].items()}
        for column in described.columns
    }


def _detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    detected: list[str] = []
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            detected.append(str(column))
            continue
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        sample = series.dropna().astype(str).head(50)
        if sample.empty:
            continue
        parsed = pd.to_datetime(sample, errors="coerce")
        if parsed.notna().mean() >= 0.8:
            detected.append(str(column))
    return detected
