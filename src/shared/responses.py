from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from src.shared.errors import ApiError, error_payload


def success_payload(data: Any = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "data": {} if data is None else data,
        "meta": {} if meta is None else meta,
    }


def success_response(
    data: Any = None,
    meta: dict[str, Any] | None = None,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=success_payload(data=data, meta=meta))


def error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content=error_payload(error))
