"""
schemas/report_image.py — Schemas para imágenes
"""
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from app.models.report_image import ImageSection


class ImageUploadResponse(BaseModel):
    id:              uuid.UUID
    report_id:       uuid.UUID
    section:         ImageSection
    slot_key:        Optional[str]
    sort_order:      int
    file_url:        str
    file_name:       Optional[str]
    file_size_bytes: Optional[int]
    orig_width:      Optional[int]
    orig_height:     Optional[int]
    proc_width:      Optional[int]
    proc_height:     Optional[int]
    is_reused:       bool
    caption:         Optional[str]

    model_config = {"from_attributes": True}


class ImageReuseRequest(BaseModel):
    """Reutilizar imágenes de otro reporte (flujo NTF)."""
    source_report_id: uuid.UUID
    section:          ImageSection
    slot_key:         Optional[str] = None   # None = reutiliza todos los slots de esa sección
