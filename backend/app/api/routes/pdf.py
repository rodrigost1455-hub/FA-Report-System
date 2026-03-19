"""
api/routes/pdf.py
POST /api/reports/{id}/generate-pdf  — Genera el PDF final usando la plantilla
GET  /api/reports/{id}/download      — Descarga o redirige al PDF generado
"""
import uuid

from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database       import get_db
from app.models.report       import Report
from app.schemas.test_result import PDFGenerateResponse
from app.services.pdf_service import pdf_service

router = APIRouter()


# ── GENERATE ──────────────────────────────────────────────────────────────────

@router.post(
    "/{report_id}/generate-pdf",
    response_model=PDFGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generar PDF final del reporte",
    description="""
    Genera el PDF de análisis de fallas usando el template original como base.

    **Pre-condiciones:**
    - El reporte debe tener al menos imágenes de `visual_inspection`.
    - Debe existir la firma de "Preparado por".
    - Si hay pruebas eléctricas pendientes, el PDF se genera con lo que haya hasta el momento.

    **Proceso interno:**
    1. Carga todos los datos del reporte con sus imágenes y resultados.
    2. Abre el PDF template original (sin modificarlo).
    3. Inserta texto e imágenes en las coordenadas preconfiguradas.
    4. Sube el PDF a Supabase Storage.
    5. Actualiza `pdf_url` y `pdf_generated_at` en el reporte.
    6. Cambia el status del reporte a `final`.

    Se puede llamar múltiples veces — cada llamada regenera el PDF con los datos actuales.
    El archivo anterior en Storage se sobreescribe (upsert).
    """,
)
async def generate_pdf(
    report_id: uuid.UUID,
    db:        AsyncSession = Depends(get_db),
) -> PDFGenerateResponse:
    return await pdf_service.generate(db, report_id)


# ── DOWNLOAD ──────────────────────────────────────────────────────────────────

@router.get(
    "/{report_id}/download",
    status_code=status.HTTP_302_FOUND,
    summary="Descargar el PDF generado",
    description="""
    Redirige a la URL pública del PDF en Supabase Storage.
    Si el PDF aún no ha sido generado, devuelve 404.
    """,
    responses={
        302: {"description": "Redirect a la URL del PDF en Supabase Storage"},
        404: {"description": "PDF aún no generado para este reporte"},
        409: {"description": "El reporte está en borrador — genera el PDF primero"},
    },
)
async def download_pdf(
    report_id: uuid.UUID,
    db:        AsyncSession = Depends(get_db),
) -> RedirectResponse:
    report = await db.get(Report, report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")

    if not report.pdf_url:
        raise HTTPException(
            status_code=404,
            detail="El PDF aún no ha sido generado. "
                   "Llama a POST /api/reports/{id}/generate-pdf primero."
        )

    # Redirect a la URL pública del PDF en Supabase Storage
    return RedirectResponse(url=report.pdf_url, status_code=302)


# ── PDF STATUS ────────────────────────────────────────────────────────────────

@router.get(
    "/{report_id}/pdf-status",
    summary="Verificar si el PDF fue generado",
    description="Devuelve el estado de generación del PDF sin redirigir.",
)
async def pdf_status(
    report_id: uuid.UUID,
    db:        AsyncSession = Depends(get_db),
) -> dict:
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")

    return {
        "report_id":        str(report_id),
        "report_number":    report.report_number,
        "pdf_generated":    report.pdf_url is not None,
        "pdf_url":          report.pdf_url,
        "pdf_generated_at": report.pdf_generated_at.isoformat() if report.pdf_generated_at else None,
        "status":           report.status.value,
    }
