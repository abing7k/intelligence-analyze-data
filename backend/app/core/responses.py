from typing import Any
from uuid import uuid4

from fastapi import Request


def request_id(request: Request | None = None) -> str:
    if request is not None and hasattr(request.state, "request_id"):
        return request.state.request_id
    return f"req_{uuid4().hex}"


def ok(data: Any, request: Request | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "error": None,
        "request_id": request_id(request),
    }


def fail(code: str, message: str, request: Request | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "request_id": request_id(request),
    }
