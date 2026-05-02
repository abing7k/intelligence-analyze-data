import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings

_LOCK = threading.Lock()


def _connect(settings: Settings | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    settings.ensure_runtime_dirs()
    conn = sqlite3.connect(settings.database_file)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(settings: Settings | None = None) -> None:
    with _LOCK, _connect(settings) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                stored_file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_time TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                column_count INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                history_id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL UNIQUE,
                dataset_id TEXT NOT NULL,
                user_question TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                text_result TEXT NOT NULL,
                table_result_json TEXT,
                chart_path TEXT,
                chart_url TEXT,
                plan_json TEXT,
                language TEXT NOT NULL DEFAULT 'en',
                created_time TEXT NOT NULL,
                FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                history_id TEXT NOT NULL,
                report_path TEXT NOT NULL,
                created_time TEXT NOT NULL,
                FOREIGN KEY(history_id) REFERENCES analysis_history(history_id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(query, params).fetchone()
    return row_to_dict(row)


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(query, params)
        conn.commit()


def execute_many(query: str, rows: list[tuple[Any, ...]]) -> None:
    with _LOCK, _connect() as conn:
        conn.executemany(query, rows)
        conn.commit()


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def remove_file(path_value: str | None) -> None:
    if not path_value:
        return
    path = Path(path_value)
    if path.exists() and path.is_file():
        path.unlink()
