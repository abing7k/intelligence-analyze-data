from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.models import database
from app.services.preprocess_service import (
    preview_for_dataframe,
    profile_for_dataframe,
    read_dataframe,
    schema_for_dataframe,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


async def save_uploaded_dataset(file: UploadFile) -> dict:
    settings = get_settings()
    original_name = Path(file.filename or "").name
    extension = _safe_extension(original_name)
    if extension not in settings.supported_file_types:
        raise AppError(
            code="FILE_INVALID_TYPE",
            message="Only CSV, XLS, and XLSX files are supported.",
            status_code=400,
        )

    dataset_id = f"ds_{uuid4().hex}"
    stored_file_name = f"{dataset_id}{extension}"
    destination = settings.upload_path / stored_file_name
    total_size = 0

    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > settings.max_upload_bytes:
                    raise AppError(
                        code="FILE_TOO_LARGE",
                        message=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
                        status_code=413,
                    )
                output.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink()
        raise
    finally:
        await file.close()

    if total_size == 0:
        if destination.exists():
            destination.unlink()
        raise AppError(code="FILE_EMPTY", message="Uploaded file is empty.", status_code=400)

    try:
        df = read_dataframe(destination)
        row_count = int(len(df))
        column_count = int(len(df.columns))
    except Exception:
        if destination.exists():
            destination.unlink()
        raise

    database.execute(
        """
        INSERT INTO datasets (
            dataset_id, file_name, stored_file_name, file_path,
            upload_time, row_count, column_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_id,
            original_name,
            stored_file_name,
            str(destination),
            utc_now(),
            row_count,
            column_count,
        ),
    )

    return get_dataset(dataset_id)


def list_datasets(page: int = 1, page_size: int = 20) -> dict:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size
    total_row = database.fetch_one("SELECT COUNT(*) AS count FROM datasets")
    items = database.fetch_all(
        """
        SELECT dataset_id, file_name, upload_time, row_count, column_count
        FROM datasets
        ORDER BY upload_time DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    return {
        "items": items,
        "total": int(total_row["count"] if total_row else 0),
        "page": page,
        "page_size": page_size,
    }


def get_dataset(dataset_id: str) -> dict:
    dataset = database.fetch_one(
        """
        SELECT dataset_id, file_name, stored_file_name, file_path,
               upload_time, row_count, column_count
        FROM datasets
        WHERE dataset_id = ?
        """,
        (dataset_id,),
    )
    if dataset is None:
        raise NotFoundError(code="DATASET_NOT_FOUND", message="Dataset was not found.")
    return dataset


def load_dataset_dataframe(dataset_id: str):
    dataset = get_dataset(dataset_id)
    return read_dataframe(dataset["file_path"])


def delete_dataset(dataset_id: str) -> dict:
    dataset = get_dataset(dataset_id)
    histories = database.fetch_all(
        "SELECT chart_path, plan_json FROM analysis_history WHERE dataset_id = ?",
        (dataset_id,),
    )
    reports = database.fetch_all(
        """
        SELECT r.report_path
        FROM reports r
        JOIN analysis_history h ON h.history_id = r.history_id
        WHERE h.dataset_id = ?
        """,
        (dataset_id,),
    )
    for history in histories:
        database.remove_file(history.get("chart_path"))
        plan = database.json_loads(history.get("plan_json"), {})
        for chart in plan.get("charts", []):
            if isinstance(chart, dict):
                database.remove_file(chart.get("chart_path"))
    for report in reports:
        database.remove_file(report.get("report_path"))
    database.remove_file(dataset.get("file_path"))
    database.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))
    return {"deleted": True, "dataset_id": dataset_id}


def dataset_preview(dataset_id: str, limit: int = 20) -> dict:
    df = load_dataset_dataframe(dataset_id)
    return preview_for_dataframe(dataset_id, df, limit=limit)


def dataset_schema(dataset_id: str) -> dict:
    df = load_dataset_dataframe(dataset_id)
    return schema_for_dataframe(dataset_id, df)


def dataset_profile(dataset_id: str) -> dict:
    df = load_dataset_dataframe(dataset_id)
    return profile_for_dataframe(dataset_id, df)
