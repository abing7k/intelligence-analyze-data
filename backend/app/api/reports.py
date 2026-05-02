from fastapi import APIRouter, Request

from app.core.responses import ok
from app.models.schemas import ReportExportRequest
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/export")
def export_report(request: Request, payload: ReportExportRequest):
    return ok(
        report_service.export_report(
            analysis_id=payload.analysis_id,
            history_id=payload.history_id,
            file_format=payload.format,
        ),
        request,
    )


@router.get("/{report_id}/download")
def download_report(report_id: str):
    return report_service.report_file_response(report_id)
