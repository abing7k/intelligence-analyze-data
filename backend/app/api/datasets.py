from fastapi import APIRouter, File, Query, Request, UploadFile

from app.core.responses import ok
from app.services import file_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload")
async def upload_dataset(request: Request, file: UploadFile = File(...)):
    return ok(await file_service.save_uploaded_dataset(file), request)


@router.get("")
def list_datasets(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return ok(file_service.list_datasets(page=page, page_size=page_size), request)


@router.get("/{dataset_id}")
def get_dataset(request: Request, dataset_id: str):
    return ok(file_service.get_dataset(dataset_id), request)


@router.delete("/{dataset_id}")
def delete_dataset(request: Request, dataset_id: str):
    return ok(file_service.delete_dataset(dataset_id), request)


@router.get("/{dataset_id}/preview")
def preview_dataset(request: Request, dataset_id: str, limit: int = Query(20, ge=1, le=100)):
    return ok(file_service.dataset_preview(dataset_id, limit=limit), request)


@router.get("/{dataset_id}/schema")
def dataset_schema(request: Request, dataset_id: str):
    return ok(file_service.dataset_schema(dataset_id), request)


@router.get("/{dataset_id}/profile")
def dataset_profile(request: Request, dataset_id: str):
    return ok(file_service.dataset_profile(dataset_id), request)

