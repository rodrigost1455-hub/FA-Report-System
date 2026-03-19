"""
schemas/test_result.py — Schemas para resultados de pruebas eléctricas
"""
import uuid
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.models.test_result import TestResultEnum
from app.models.electrical_test import CheckType


# ── Catálogo (solo lectura) ───────────────────────────────────────────────────

class ElectricalTestCatalogResponse(BaseModel):
    id:               uuid.UUID
    code:             str
    sort_order:       int
    section_num:      int
    section_title:    str
    sub_code:         str
    sub_title:        str
    check_type:       CheckType
    terminal_pos:     Optional[str]
    terminal_neg:     Optional[str]
    voltage_source:   Optional[str]
    expected_result:  Optional[str]
    step_description: Optional[str]
    pdf_page:         int
    pdf_position:     str
    has_design_req:   bool
    design_req_text:  Optional[str]

    model_config = {"from_attributes": True}


# ── Resultado individual ──────────────────────────────────────────────────────

class TestResultCreate(BaseModel):
    """
    Payload para registrar el resultado de UNA prueba eléctrica.
    POST /api/reports/{id}/electrical-tests
    """
    catalog_id:       uuid.UUID
    result:           TestResultEnum
    measurement_val:  Optional[str]  = Field(None, max_length=40, examples=["000034 OHM", "027.396 OHM"])
    image_left_id:    Optional[uuid.UUID] = None   # UUID de una ReportImage ya subida
    image_right_id:   Optional[uuid.UUID] = None
    observation_text: Optional[str]  = None        # Si None, se usa el texto por defecto según result
    is_ng_override:   bool           = False        # El usuario eligió continuar después de NG

    @model_validator(mode="after")
    def set_default_observation(self) -> "TestResultCreate":
        if not self.observation_text:
            if self.result == TestResultEnum.NG:
                self.observation_text = "NG result was detected in this test."
            else:
                self.observation_text = "No anomalies were observed in the manual test."
        return self


class TestResultBatchCreate(BaseModel):
    """
    Guarda múltiples resultados en una sola llamada.
    Útil para el flujo NTF donde se copian todos de un golpe.
    """
    results: list[TestResultCreate] = Field(..., min_length=1, max_length=20)


class TestResultResponse(BaseModel):
    id:               uuid.UUID
    report_id:        uuid.UUID
    catalog_id:       uuid.UUID
    result:           TestResultEnum
    measurement_val:  Optional[str]
    observation_text: str
    is_ng_override:   bool
    is_reused:        bool

    # Datos del catálogo embebidos para el frontend
    test_code:        str
    check_type:       CheckType
    terminal_pos:     Optional[str]
    terminal_neg:     Optional[str]
    voltage_source:   Optional[str]
    expected_result:  Optional[str]

    # URLs de imágenes resueltas
    image_left_url:   Optional[str] = None
    image_right_url:  Optional[str] = None

    model_config = {"from_attributes": True}


class TestResultsListResponse(BaseModel):
    report_id:    uuid.UUID
    total:        int
    completed:    int
    pending:      int
    has_ng:       bool
    results:      list[TestResultResponse]


# ── Reuse NTF ────────────────────────────────────────────────────────────────

class ReuseTestResultsRequest(BaseModel):
    """Copiar resultados de prueba de un reporte anterior (NTF)."""
    source_report_id: uuid.UUID


# ── PDF Generation ────────────────────────────────────────────────────────────

class PDFGenerateResponse(BaseModel):
    report_id:        uuid.UUID
    pdf_url:          str
    pdf_generated_at: str
    pages:            int
    message:          str = "PDF generado exitosamente"
