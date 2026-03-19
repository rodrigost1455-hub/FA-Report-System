"""
schemas/report.py
Pydantic v2 schemas para reportes FA.
"""
import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.models.report import ReportStatus


# ── Base ──────────────────────────────────────────────────────────────────────

class ReportBase(BaseModel):
    report_number:      str   = Field(..., min_length=1, max_length=20,  examples=["2506-002"])
    title:              str   = Field(default="Warranty Plant Return",    max_length=120)
    request_date:       date
    part_name:          str   = Field(..., min_length=1, max_length=120,  examples=["PHEV BEC GEN 4"])
    part_number:        str   = Field(..., min_length=1, max_length=60,   examples=["L1M8 10C666 GF"])
    yazaki_part_number: str   = Field(..., min_length=1, max_length=60,   examples=["7370-2573-8W"])
    notes:              Optional[str] = None


# ── CREATE ────────────────────────────────────────────────────────────────────

class ReportCreate(ReportBase):
    """
    Payload para POST /api/reports.
    Las firmas se pueden pasar como UUID (si el user existe en BD)
    o como texto libre. Al menos uno de los dos debe estar presente.
    """
    # Firmas por FK
    prepared_by_id:   Optional[uuid.UUID] = None
    verified_by_id:   Optional[uuid.UUID] = None
    requested_by_id:  Optional[uuid.UUID] = None
    approved_by_id:   Optional[uuid.UUID] = None

    # Firmas por texto libre
    prepared_by_name:  Optional[str] = Field(None, max_length=120)
    verified_by_name:  Optional[str] = Field(None, max_length=120)
    requested_by_name: Optional[str] = Field(None, max_length=120)
    approved_by_name:  Optional[str] = Field(None, max_length=120)

    is_ntf:        bool = False
    reuse_images:  bool = False
    source_report_id: Optional[uuid.UUID] = None  # Sólo relevante si is_ntf=True y reuse_images=True

    @model_validator(mode="after")
    def validate_ntf_source(self) -> "ReportCreate":
        if self.reuse_images and not self.source_report_id:
            raise ValueError("source_report_id es requerido cuando reuse_images=True")
        return self

    @model_validator(mode="after")
    def validate_at_least_one_signature(self) -> "ReportCreate":
        has_prepared = self.prepared_by_id or self.prepared_by_name
        if not has_prepared:
            raise ValueError("Se requiere al menos prepared_by_id o prepared_by_name")
        return self


# ── UPDATE ────────────────────────────────────────────────────────────────────

class ReportUpdate(BaseModel):
    """PATCH /api/reports/{id} — todos los campos opcionales."""
    title:              Optional[str]   = Field(None, max_length=120)
    request_date:       Optional[date]  = None
    part_name:          Optional[str]   = Field(None, max_length=120)
    part_number:        Optional[str]   = Field(None, max_length=60)
    yazaki_part_number: Optional[str]   = Field(None, max_length=60)
    prepared_by_id:     Optional[uuid.UUID] = None
    verified_by_id:     Optional[uuid.UUID] = None
    requested_by_id:    Optional[uuid.UUID] = None
    approved_by_id:     Optional[uuid.UUID] = None
    prepared_by_name:   Optional[str]   = Field(None, max_length=120)
    verified_by_name:   Optional[str]   = Field(None, max_length=120)
    requested_by_name:  Optional[str]   = Field(None, max_length=120)
    approved_by_name:   Optional[str]   = Field(None, max_length=120)
    is_ntf:             Optional[bool]  = None
    reuse_images:       Optional[bool]  = None
    source_report_id:   Optional[uuid.UUID] = None
    status:             Optional[ReportStatus] = None
    notes:              Optional[str]   = None


# ── NESTED RESPONSE TYPES ─────────────────────────────────────────────────────

class ReportImageBrief(BaseModel):
    id:         uuid.UUID
    section:    str
    slot_key:   Optional[str]
    sort_order: int
    file_url:   str
    caption:    Optional[str]
    is_reused:  bool

    model_config = {"from_attributes": True}


class TestResultBrief(BaseModel):
    id:               uuid.UUID
    catalog_id:       uuid.UUID
    test_code:        str = Field(alias="catalog_code", default="")
    result:           str
    measurement_val:  Optional[str]
    observation_text: str
    is_ng_override:   bool
    is_reused:        bool

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── RESPONSE ─────────────────────────────────────────────────────────────────

class ReportResponse(ReportBase):
    """Respuesta completa del reporte con todos sus datos."""
    id:               uuid.UUID
    completion_date:  date
    status:           ReportStatus

    # Firmas resueltas (texto final para mostrar en UI y PDF)
    prepared_by:      str
    verified_by:      str
    requested_by:     str
    approved_by:      str

    is_ntf:           bool
    reuse_images:     bool
    source_report_id: Optional[uuid.UUID]

    pdf_url:          Optional[str]
    pdf_generated_at: Optional[datetime]

    # Colecciones
    images:           list[ReportImageBrief] = []
    test_results:     list[TestResultBrief]  = []

    # Contadores (calculados en el service)
    total_tests:   int = 0
    tests_ok:      int = 0
    tests_ng:      int = 0
    tests_pending: int = 0

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportSummary(BaseModel):
    """Versión compacta para listado/historial — sin imágenes ni test_results."""
    id:               uuid.UUID
    report_number:    str
    part_name:        str
    part_number:      str
    status:           ReportStatus
    request_date:     date
    completion_date:  date
    is_ntf:           bool
    prepared_by:      str
    pdf_url:          Optional[str]
    total_tests:      int
    tests_ok:         int
    tests_ng:         int
    tests_pending:    int
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items:       list[ReportSummary]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
