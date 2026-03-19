"""
api/routes/reports.py
POST /api/reports          — Crear reporte
GET  /api/reports          — Listar reportes (búsqueda, paginación)
GET  /api/reports/{id}     — Obtener reporte completo
PATCH /api/reports/{id}    — Actualizar reporte
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database      import get_db
from app.models.report      import ReportStatus
from app.schemas.report     import (
    ReportCreate, ReportUpdate,
    ReportResponse, ReportListResponse,
)
from app.services.report_service import report_service

router = APIRouter()


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo reporte FA",
    description="""
    Crea un nuevo reporte de análisis de fallas.

    - `completion_date` se asigna automáticamente a la fecha de hoy.
    - Las firmas pueden pasarse como UUID de usuario o como texto libre.
    - Si `reuse_images=True`, se requiere `source_report_id`.
    """,
)
async def create_report(
    payload: ReportCreate,
    db:      AsyncSession = Depends(get_db),
) -> ReportResponse:
    report = await report_service.create(db, payload)
    return report_service.build_response(report)


@router.get(
    "",
    response_model=ReportListResponse,
    summary="Listar reportes con búsqueda y paginación",
)
async def list_reports(
    page:      int             = Query(default=1,  ge=1),
    page_size: int             = Query(default=20, ge=1, le=100),
    search:    Optional[str]   = Query(default=None, description="Busca en número de reporte, nombre y número de parte"),
    status:    Optional[ReportStatus] = Query(default=None),
    is_ntf:    Optional[bool]  = Query(default=None),
    db:        AsyncSession    = Depends(get_db),
) -> ReportListResponse:
    return await report_service.list(db, page, page_size, search, status, is_ntf)


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Obtener reporte completo por ID",
)
async def get_report(
    report_id: uuid.UUID,
    db:        AsyncSession = Depends(get_db),
) -> ReportResponse:
    report = await report_service.get_by_id(db, report_id)
    return report_service.build_response(report)


@router.get(
    "/by-number/{report_number}",
    response_model=ReportResponse,
    summary="Obtener reporte por número (ej: 2506-002)",
)
async def get_report_by_number(
    report_number: str,
    db:            AsyncSession = Depends(get_db),
) -> ReportResponse:
    report = await report_service.get_by_number(db, report_number)
    return report_service.build_response(report)


@router.patch(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Actualizar campos del reporte",
)
async def update_report(
    report_id: uuid.UUID,
    payload:   ReportUpdate,
    db:        AsyncSession = Depends(get_db),
) -> ReportResponse:
    report = await report_service.update(db, report_id, payload)
    return report_service.build_response(report)
