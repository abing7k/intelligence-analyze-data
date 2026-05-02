import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.models import database
from app.services import analysis_service, markdown_report_service


def export_report(analysis_id: str | None = None, history_id: str | None = None, file_format: str = "html") -> dict[str, Any]:
    if not analysis_id and not history_id:
        raise AppError(
            code="REPORT_SOURCE_REQUIRED",
            message="analysis_id or history_id is required.",
            status_code=400,
        )

    history = _find_history(analysis_id=analysis_id, history_id=history_id)
    report_id = f"rep_{uuid4().hex}"
    created_time = datetime.now(timezone.utc).isoformat()
    file_format = _normalize_format(file_format)
    suffix = _report_suffix(file_format)
    settings = get_settings()
    report_path = settings.report_path / f"{report_id}{suffix}"
    if file_format == "pdf":
        markdown_report_service.render_markdown_pdf_with_images(
            markdown_report_service.render_analysis_markdown(history),
            report_path,
            image_paths=markdown_report_service.chart_image_paths(history),
        )
    else:
        content = _render_content(history, file_format)
        report_path.write_text(content, encoding="utf-8")

    database.execute(
        """
        INSERT INTO reports (report_id, history_id, report_path, created_time)
        VALUES (?, ?, ?, ?)
        """,
        (report_id, history["history_id"], str(report_path), created_time),
    )
    return {
        "report_id": report_id,
        "history_id": history["history_id"],
        "analysis_id": history["analysis_id"],
        "report_url": f"/api/reports/{report_id}/download",
        "format": file_format,
        "created_time": created_time,
    }


def report_file_response(report_id: str) -> FileResponse:
    report = database.fetch_one("SELECT * FROM reports WHERE report_id = ?", (report_id,))
    if report is None:
        raise NotFoundError(code="REPORT_NOT_FOUND", message="Report was not found.")
    path = Path(report["report_path"])
    if not path.exists():
        raise NotFoundError(code="REPORT_NOT_FOUND", message="Report file was not found.")
    media_type = _media_type(path.suffix)
    return FileResponse(
        path=path,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


def _find_history(analysis_id: str | None, history_id: str | None) -> dict[str, Any]:
    row = None
    if analysis_id:
        row = database.fetch_one("SELECT * FROM analysis_history WHERE analysis_id = ?", (analysis_id,))
        if row is None:
            raise NotFoundError(code="ANALYSIS_NOT_FOUND", message="Analysis was not found.")
    else:
        row = database.fetch_one("SELECT * FROM analysis_history WHERE history_id = ?", (history_id,))
    if row is None:
        raise NotFoundError(code="HISTORY_NOT_FOUND", message="History record was not found.")
    return analysis_service._history_row_to_result(row, include_code=True)


def _normalize_format(file_format: str) -> str:
    normalized = file_format.lower().strip()
    return "md" if normalized == "markdown" else normalized


def _report_suffix(file_format: str) -> str:
    return {
        "html": ".html",
        "txt": ".txt",
        "md": ".md",
        "pdf": ".pdf",
    }[file_format]


def _render_content(history: dict[str, Any], file_format: str) -> str:
    if file_format == "html":
        return _render_html(history)
    if file_format == "md":
        return markdown_report_service.render_analysis_markdown(history)
    return _render_text(history)


def _media_type(suffix: str) -> str:
    return {
        ".html": "text/html; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")


def _render_html(history: dict[str, Any]) -> str:
    table_rows = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(value))}</td>" for value in row.values())
        + "</tr>"
        for row in history.get("table_result", [])[:50]
    )
    headers = ""
    if history.get("table_result"):
        headers = "<tr>" + "".join(
            f"<th>{html.escape(str(key))}</th>" for key in history["table_result"][0].keys()
        ) + "</tr>"
    chart_html = ""
    if history.get("chart_url"):
        chart_html = f'<p>Chart URL: {html.escape(history["chart_url"])}</p>'
    return f"""<!doctype html>
<html lang="{html.escape(history.get("language", "en"))}">
<head>
  <meta charset="utf-8" />
  <title>Analysis Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    h1 {{ font-size: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    pre {{ white-space: pre-wrap; background: #f9fafb; padding: 12px; }}
  </style>
</head>
<body>
  <h1>Analysis Report</h1>
  <p><strong>Question:</strong> {html.escape(history["question"])}</p>
  <p><strong>Created:</strong> {html.escape(history["created_time"])}</p>
  <h2>Summary</h2>
  <p>{html.escape(history["text_result"])}</p>
  {chart_html}
  <h2>Result Table</h2>
  <table>{headers}{table_rows}</table>
  <h2>Generated Code</h2>
  <pre>{html.escape(history.get("generated_code", ""))}</pre>
</body>
</html>
"""


def _render_text(history: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Analysis Report",
            f"Question: {history['question']}",
            f"Created: {history['created_time']}",
            "",
            "Summary:",
            history["text_result"],
            "",
            f"Chart URL: {history.get('chart_url') or 'N/A'}",
            "",
            "Generated Code:",
            history.get("generated_code", ""),
        ]
    )
