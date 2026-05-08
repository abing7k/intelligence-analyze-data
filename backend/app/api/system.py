from fastapi import APIRouter, Query, Request

from app.core.config import get_settings
from app.core.i18n import language_choices
from app.core.responses import ok
from app.services import llm_service

router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request):
    settings = get_settings()
    return ok(
        {
            "status": "ok",
            "version": settings.app_version,
            "environment": settings.app_env,
        },
        request,
    )


@router.get("/health/llm")
def llm_health(
    request: Request,
    model_id: str | None = Query(None),
    check_all: bool = Query(False),
):
    settings = get_settings()
    if check_all:
        return ok(
            {
                "default_model_id": settings.default_llm_model.id,
                "models": [llm_service.validate_model(model.id) for model in settings.llm_models],
            },
            request,
        )
    return ok(llm_service.validate_model(model_id), request)


@router.get("/config/client")
def client_config(request: Request):
    settings = get_settings()
    return ok(
        {
            "max_file_size_mb": settings.max_upload_mb,
            "supported_file_types": settings.supported_file_types,
            "provider": settings.provider,
            "model_name": settings.default_llm_model.model,
            "default_model_id": settings.default_llm_model.model,
            "models": settings.public_llm_models(),
            "supported_languages": language_choices(),
            "default_language": "en",
            "features": {
                "upload": True,
                "preview": True,
                "analysis": True,
                "history": True,
                "charts": True,
                "reports": True,
                "streaming": True,
            },
        },
        request,
    )
