"""
core/exceptions.py
Manejadores globales de errores para FastAPI.
Centraliza el formato de respuesta de error para toda la API.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError


def register_exception_handlers(app: FastAPI) -> None:
    """Registra todos los handlers en la app FastAPI."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Errores de validación Pydantic — devuelve 422 con detalle legible."""
        errors = []
        for err in exc.errors():
            field = " → ".join(str(loc) for loc in err["loc"] if loc != "body")
            errors.append({"field": field, "message": err["msg"], "type": err["type"]})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Error de validación", "errors": errors},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        """Violaciones de constraint en PostgreSQL (unique, fk, etc.)."""
        msg = str(exc.orig) if exc.orig else str(exc)
        # Detectar duplicado de report_number
        if "unique" in msg.lower() and "report_number" in msg.lower():
            detail = "Ya existe un reporte con ese número. Usa un número diferente."
        else:
            detail = "Conflicto de datos en la base de datos."
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": detail},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        """Captura cualquier error no manejado — evita exponer stack traces."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Error interno del servidor. Contacta al administrador."},
        )
