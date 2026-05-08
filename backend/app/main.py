from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import analysis, charts, datasets, reports, system
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.responses import fail, ok
from app.models.database import init_db
from app.services import llm_service

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"


@asynccontextmanager
async def lifespan(api_app: FastAPI):
    init_db(settings)
    api_app.state.llm_status = {
        "provider": settings.provider,
        "model": settings.default_model,
        "available": None,
        "message": "Model availability check is running.",
    }
    Thread(target=_refresh_llm_status, args=(api_app,), daemon=True).start()
    yield


app = FastAPI(
    title="Intelligent Data Analysis System API",
    version=settings.app_version,
    description="FastAPI backend for LangChain-based intelligent data analysis.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = f"req_{uuid4().hex}"
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def _refresh_llm_status(api_app: FastAPI) -> None:
    api_app.state.llm_status = llm_service.validate_model()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message, request, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=fail("VALIDATION_ERROR", "Request validation failed.", request, {"errors": exc.errors()}),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=fail("INTERNAL_ERROR", str(exc), request),
    )


@app.get("/api")
def api_root(request: Request):
    return ok(
        {
            "name": "Intelligent Data Analysis System API",
            "version": settings.app_version,
            "docs_url": "/docs",
        },
        request,
    )


app.include_router(system.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(charts.router, prefix="/api")
app.include_router(reports.router, prefix="/api")

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_fallback(full_path: str):
    if FRONTEND_INDEX.exists():
        requested_path = (FRONTEND_DIST / full_path).resolve()
        if requested_path.is_file() and FRONTEND_DIST.resolve() in requested_path.parents:
            return FileResponse(requested_path)
        return FileResponse(FRONTEND_INDEX)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": {
                "code": "FRONTEND_NOT_BUILT",
                "message": "Frontend assets are not available. Build the frontend or use /api endpoints.",
            },
        },
    )
