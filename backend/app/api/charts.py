from fastapi import APIRouter

from app.services import chart_service

router = APIRouter(prefix="/charts", tags=["charts"])


@router.get("/{chart_id}")
def get_chart(chart_id: str):
    return chart_service.chart_file_response(chart_id, download=False)


@router.get("/{chart_id}/download")
def download_chart(chart_id: str):
    return chart_service.chart_file_response(chart_id, download=True)

