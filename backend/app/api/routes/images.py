"""
api/routes/images.py
POST /api/reports/{id}/images              — Subir una imagen
POST /api/reports/{id}/images/batch        — Subir múltiples imágenes
POST /api/reports/{id}/images/reuse        — Reutilizar imágenes de otro reporte (NTF)
DELETE /api/reports/{id}/images/{image_id} — Eliminar imagen
GET  /api/reports/{id}/images              — Listar imágenes del reporte por sección
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database       import get_db
from app.models.report_image import ReportImage, ImageSection
from app.schemas.report_image import ImageUploadResponse, ImageReuseRequest
from app.services.image_service import image_service

router = APIRouter()

# Tipos MIME permitidos
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def _validate_mime(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {file.content_type}. "
                   f"Se aceptan: {', '.join(ALLOWED_MIME)}"
        )


# ── UPLOAD SINGLE ─────────────────────────────────────────────────────────────

@router.post(
    "/{report_id}/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una imagen al reporte",
    description="""
    Sube una imagen a la sección indicada del reporte.

    **Secciones disponibles:**
    - `visual_inspection` — Imágenes de llegada de la pieza (máx. 6)
    - `terminal_inspection` — Thumbnails de terminales (máx. 9)
    - `eol` — Imágenes del tester EOL (máx. 4)
    - `electrical_test` — Imágenes de pruebas eléctricas

    **slot_key** identifica la posición exacta en el PDF (ej: `arrival_1`, `eol_tester`, `terminal_center`).
    Si no se especifica, la imagen se asigna automáticamente por orden.
    """,
)
async def upload_image(
    report_id:  uuid.UUID,
    file:       UploadFile = File(..., description="Imagen JPEG / PNG / WebP"),
    section:    ImageSection = Form(...),
    slot_key:   Optional[str] = Form(default=None),
    sort_order: int           = Form(default=0),
    caption:    Optional[str] = Form(default=None),
    db:         AsyncSession  = Depends(get_db),
) -> ImageUploadResponse:
    _validate_mime(file)
    image = await image_service.upload(
        db         = db,
        report_id  = report_id,
        file       = file,
        section    = section,
        slot_key   = slot_key,
        sort_order = sort_order,
        caption    = caption,
    )
    return ImageUploadResponse.model_validate(image)


# ── UPLOAD BATCH ──────────────────────────────────────────────────────────────

@router.post(
    "/{report_id}/images/batch",
    response_model=list[ImageUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Subir múltiples imágenes de una sección",
    description="""
    Sube hasta 6 imágenes en una sola llamada.
    Todas van a la misma sección. El sort_order se asigna automáticamente
    en orden de llegada dentro del batch.
    """,
)
async def upload_images_batch(
    report_id: uuid.UUID,
    files:     list[UploadFile] = File(..., description="Hasta 6 imágenes"),
    section:   ImageSection     = Form(...),
    db:        AsyncSession     = Depends(get_db),
) -> list[ImageUploadResponse]:
    if len(files) > 6:
        raise HTTPException(status_code=400, detail="Máximo 6 imágenes por batch.")

    for f in files:
        _validate_mime(f)

    images = await image_service.upload_many(
        db        = db,
        report_id = report_id,
        files     = files,
        section   = section,
    )
    return [ImageUploadResponse.model_validate(img) for img in images]


# ── REUSE NTF ─────────────────────────────────────────────────────────────────

@router.post(
    "/{report_id}/images/reuse",
    response_model=list[ImageUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Reutilizar imágenes de otro reporte (flujo NTF)",
    description="""
    Copia las referencias de imágenes desde un reporte fuente al reporte actual.
    No duplica los archivos en Storage — solo crea nuevos registros con `is_reused=True`.

    Usado en el flujo NTF cuando el usuario elige "Sí, reutilizar imágenes anteriores".
    """,
)
async def reuse_images(
    report_id: uuid.UUID,
    payload:   ImageReuseRequest,
    db:        AsyncSession = Depends(get_db),
) -> list[ImageUploadResponse]:
    images = await image_service.reuse_from_report(
        db               = db,
        target_report_id = report_id,
        source_report_id = payload.source_report_id,
        section          = payload.section,
        slot_key         = payload.slot_key,
    )
    return [ImageUploadResponse.model_validate(img) for img in images]


# ── LIST BY SECTION ───────────────────────────────────────────────────────────

@router.get(
    "/{report_id}/images",
    response_model=list[ImageUploadResponse],
    summary="Listar imágenes del reporte",
)
async def list_images(
    report_id: uuid.UUID,
    section:   Optional[ImageSection] = Query(default=None, description="Filtrar por sección"),
    db:        AsyncSession = Depends(get_db),
) -> list[ImageUploadResponse]:
    query = (
        select(ReportImage)
        .where(ReportImage.report_id == report_id)
        .order_by(ReportImage.section, ReportImage.sort_order)
    )
    if section:
        query = query.where(ReportImage.section == section)

    rows = (await db.execute(query)).scalars().all()
    return [ImageUploadResponse.model_validate(img) for img in rows]


# ── DELETE ────────────────────────────────────────────────────────────────────

@router.delete(
    "/{report_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar imagen del reporte",
)
async def delete_image(
    report_id: uuid.UUID,
    image_id:  uuid.UUID,
    db:        AsyncSession = Depends(get_db),
) -> None:
    await image_service.delete(db, report_id, image_id)
