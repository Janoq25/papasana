"""Errores de dominio y manejadores centralizados (formato único de error)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi.errors import RateLimitExceeded

from app.core.context import get_request_context

log = logging.getLogger("papasana")


class AppError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str, *, detail: Any = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "no_encontrado"


class ConflictError(AppError):
    status_code = 409
    code = "conflicto"


class AuthError(AppError):
    status_code = 401
    code = "no_autenticado"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "sin_permiso"


class BusinessRuleError(AppError):
    status_code = 422
    code = "regla_de_negocio"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "servicio_no_disponible"


class AccountLockedError(AppError):
    status_code = 423
    code = "cuenta_bloqueada"


def _body(code: str, message: str, detail: Any = None) -> dict:
    return {"code": code, "message": message, "detail": detail, "trace_id": get_request_context().trace_id}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(_body(exc.code, exc.message, exc.detail), status_code=exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = [
            {"campo": ".".join(str(p) for p in e.get("loc", [])[1:]), "mensaje": e.get("msg")}
            for e in exc.errors()
        ]
        return JSONResponse(_body("validacion", "Los datos enviados no son válidos.", errors), status_code=422)

    @app.exception_handler(ValidationError)
    async def _pydantic(_: Request, exc: ValidationError):
        errors = [{"campo": ".".join(str(p) for p in e.get("loc", [])), "mensaje": e.get("msg")} for e in exc.errors()]
        return JSONResponse(_body("validacion", "Los datos enviados no son válidos.", errors), status_code=422)

    @app.exception_handler(RateLimitExceeded)
    async def _rate(_: Request, exc: RateLimitExceeded):
        return JSONResponse(
            _body("demasiadas_solicitudes", "Demasiadas solicitudes. Espere un momento e intente de nuevo."),
            status_code=429,
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Error no controlado", exc_info=exc)
        return JSONResponse(_body("error_interno", "Ocurrió un error interno."), status_code=500)
