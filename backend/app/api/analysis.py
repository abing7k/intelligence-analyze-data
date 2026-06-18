import json
import queue
from typing import Any
from threading import Thread

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.core.errors import AppError
from app.core.i18n import normalize_language
from app.core.responses import ok
from app.models.schemas import AnalysisRequest
from app.services import analysis_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/query")
def query_analysis(request: Request, payload: AnalysisRequest):
    return ok(analysis_service.submit_analysis(payload), request)


@router.post("/query/stream")
def stream_analysis_post(payload: AnalysisRequest):
    return _streaming_analysis_response(payload)


@router.get("/query/stream")
def stream_analysis(
    dataset_id: str,
    question: str,
    language: str = Query("en"),
    model_id: str | None = Query(None),
    chart_preference: str = Query("auto"),
    include_generated_code: bool = Query(True),
):
    payload = AnalysisRequest(
        dataset_id=dataset_id,
        question=question,
        options={
            "language": normalize_language(language),
            "model_id": model_id,
            "chart_preference": chart_preference,
            "include_generated_code": include_generated_code,
        },
    )
    return _streaming_analysis_response(payload)


@router.get("/history")
def list_history(
    request: Request,
    dataset_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return ok(analysis_service.list_history(dataset_id=dataset_id, page=page, page_size=page_size), request)


@router.delete("/history/{history_id}")
def delete_history(request: Request, history_id: str):
    return ok(analysis_service.delete_history(history_id), request)


@router.get("/{analysis_id}/code")
def get_generated_code(request: Request, analysis_id: str):
    return ok(analysis_service.get_generated_code(analysis_id), request)


@router.post("/{analysis_id}/rerun")
def rerun_analysis(request: Request, analysis_id: str):
    return ok(analysis_service.rerun_analysis(analysis_id), request)


@router.get("/{analysis_id}")
def get_analysis(request: Request, analysis_id: str):
    return ok(analysis_service.get_analysis(analysis_id), request)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _streaming_analysis_response(payload: AnalysisRequest) -> StreamingResponse:
    return StreamingResponse(
        _analysis_events(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _analysis_events(payload: AnalysisRequest):
    yield _sse("status", {"stage": "accepted", "message": "Analysis request accepted."})
    events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()

    def run_analysis() -> None:
        try:
            result = analysis_service.submit_analysis(payload)
            events.put(("result", result))
            events.put(("done", {"analysis_id": result["analysis_id"]}))
        except AppError as exc:
            events.put(
                (
                    "error",
                    {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    },
                )
            )
        except Exception as exc:
            events.put(("error", {"code": "INTERNAL_ERROR", "message": str(exc)}))

    Thread(target=run_analysis, daemon=True).start()
    yield _sse("status", {"stage": "running", "message": "Generating and executing analysis."})
    while True:
        try:
            event, data = events.get(timeout=10)
        except queue.Empty:
            yield _sse("heartbeat", {"stage": "running", "message": "Analysis is still running."})
            continue
        yield _sse(event, data)
        if event in {"done", "error"}:
            break
    yield _sse("close", {"message": "Analysis stream closed."})
