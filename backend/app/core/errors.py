"""Domain exceptions and FastAPI exception handlers.

All error bodies share the shape ``{"detail": "<human readable string>", "code": "<machine code>"}``
because the frontend reads ``body.detail`` as a string.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("praman.errors")


class PramanError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.extra = extra or {}


class NotFoundError(PramanError):
    status_code = 404
    code = "not_found"


class ForbiddenError(PramanError):
    status_code = 403
    code = "forbidden"


class UnauthorizedError(PramanError):
    status_code = 401
    code = "unauthorized"


class ConflictError(PramanError):
    status_code = 409
    code = "conflict"


class UnprocessableError(PramanError):
    status_code = 422
    code = "unprocessable"


class ServiceUnavailableError(PramanError):
    status_code = 503
    code = "service_unavailable"


def _body(detail: str, code: str, **extra: Any) -> dict[str, Any]:
    return {"detail": detail, "code": code, **extra}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PramanError)
    async def _praman_error(_: Request, exc: PramanError) -> JSONResponse:
        headers = {"WWW-Authenticate": "DemoHeaders"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.message, exc.code, **exc.extra),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Prefer structured dict details from intake rejections without stringifying secrets.
        if isinstance(exc.detail, dict):
            message = str(exc.detail.get("message") or exc.detail.get("detail") or "Request failed")
            code = str(exc.detail.get("code") or f"http_{exc.status_code}")
            extra = {
                k: v
                for k, v in exc.detail.items()
                if k not in {"message", "detail", "code"}
                and not any(s in str(k).lower() for s in ("secret", "password", "token", "content", "bytes"))
            }
            return JSONResponse(
                status_code=exc.status_code,
                content=_body(message, code, **extra),
                headers=getattr(exc, "headers", None),
            )
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(detail, f"http_{exc.status_code}"),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            errors.append({"field": loc, "message": err.get("msg", "invalid value")})
        summary = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
        return JSONResponse(
            status_code=422,
            content=_body(summary or "Validation error", "validation_error", errors=errors),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Integrity error: %s", exc.orig)
        return JSONResponse(
            status_code=409, content=_body("Request conflicts with existing data.", "integrity_error")
        )

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error")
        return JSONResponse(status_code=500, content=_body("Database error.", "database_error"))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500, content=_body("Internal server error.", "internal_error")
        )
