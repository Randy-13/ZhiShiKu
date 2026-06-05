from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiError(Exception):
    code: str
    message: str
    status_code: int = 400
    details: Any = None

    def __str__(self) -> str:
        return self.message


def error_payload(error: ApiError) -> dict[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "code": error.code,
        "message": error.message,
    }
    if error.details is not None:
        payload["details"] = error.details
    return {"error": payload}
