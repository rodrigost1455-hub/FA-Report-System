"""
api/routes/test_results.py
POST /api/reports/{id}/electrical-tests              — Guardar resultado de una prueba
POST /api/reports/{id}/electrical-tests/batch        — Guardar múltiples resultados
POST /api/reports/{id}/electrical-tests/reuse        — Reutilizar resultados de otro reporte (NTF)
GET  /api/reports/{id}/electrical-tests              — Listar todos los resultados del reporte
GET  /api/reports/{id}/electrical-tests/{catalog_id} — Obtener resultado de una prueba específica
"""
import uuid

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database       import get_db
from app.models.test_result  import TestResult
from app.models.electrical_test import ElectricalTestCatalog
from app.schemas.test_result import (
    TestResultCreate,
    TestResultBatchCreate,
    TestResultResponse,
    TestResultsListResponse,
    ReuseTestResultsRequest,
)
from app.services.test_service import test_service

router = APIRouter()


# ── SAVE ONE ──────────────────────────────────────────────────────────────────

@router.post(
    "/{report_id}/electrical-tests",
    response_model=TestResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar resultado de una prueba eléctrica",
    description="""
    Guarda el resultado (OK / NG) de una prueba eléctrica.

    - Si ya existe un resultado para ese `catalog_id` en el reporte, lo **actualiza** (upsert).
    - `image_left_id` / `image_right_id` deben ser UUIDs de imágenes previamente subidas
      con sección `electrical_test`.
    - Si `result=NG` e `is_ng_override=False`, el reporte queda en estado `in_progress`
      esperando que el usuario decida si continúa con más pruebas.
    - Si `result=NG` e `is_ng_override=True`, el usuario decidió continuar y el sistema
      registra el flag en el resultado.

    **Flujo NG:**
    1. Usuario sube resultado NG → sistema guarda y devuelve el resultado.
    2. Frontend muestra modal "¿Agregar pruebas adicionales con componente OK?"
    3. Si "Sí" → continuar llamando a este endpoint con las pruebas restantes.
    4. Si "No" → llamar a `POST /api/reports/{id}/generate-pdf` directamente.
    """,
)
async def save_test_result(
    report_id: uuid.UUID,
    payload:   TestResultCreate,
    db:        AsyncSession = Depends(get_db),
) -> TestResultResponse:
    tr = await test_service.save_result(db, report_id, payload)

    # Recargar con relaciones para construir la respuesta completa
    tr = await db.scalar(
        select(TestResult)
        .where(TestResult.id == tr.id)
        .options(
            selectinload(TestResult.catalog),
            selectinload(TestResult.image_left),
            selectinload(TestResult.image_right),
        )
    )
    return test_service._build_result_response(tr)


# ── BATCH SAVE ────────────────────────────────────────────────────────────────

@router.post(
    "/{report_id}/electrical-tests/batch",
    response_model=list[TestResultResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Guardar múltiples resultados en una sola llamada",
    description="""
    Guarda hasta 20 resultados de prueba en una sola transacción.
    Útil al finalizar el wizard o en el flujo NTF cuando todos los resultados son OK.
    El orden de `results` no importa — el backend ordena por `sort_order` del catálogo.
    """,
)
async def save_test_results_batch(
    report_id: uuid.UUID,
    payload:   TestResultBatchCreate,
    db:        AsyncSession = Depends(get_db),
) -> list[TestResultResponse]:
    results = await test_service.save_batch(db, report_id, payload)

    # Recargar cada uno con sus relaciones
    built = []
    for tr in results:
        tr_full = await db.scalar(
            select(TestResult)
            .where(TestResult.id == tr.id)
            .options(
                selectinload(TestResult.catalog),
                selectinload(TestResult.image_left),
                selectinload(TestResult.image_right),
            )
        )
        if tr_full:
            built.append(test_service._build_result_response(tr_full))
    return built


# ── REUSE NTF ─────────────────────────────────────────────────────────────────

@router.post(
    "/{report_id}/electrical-tests/reuse",
    response_model=list[TestResultResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Copiar resultados de prueba de un reporte anterior (flujo NTF)",
    description="""
    Copia todos los resultados de prueba del `source_report_id` al reporte actual.
    Las imágenes quedan vinculadas al reporte fuente (`is_reused=True`).
    Usado cuando `is_ntf=True` y el usuario eligió "Sí, reutilizar".
    """,
)
async def reuse_test_results(
    report_id: uuid.UUID,
    payload:   ReuseTestResultsRequest,
    db:        AsyncSession = Depends(get_db),
) -> list[TestResultResponse]:
    results = await test_service.reuse_from_report(db, report_id, payload)

    built = []
    for tr in results:
        tr_full = await db.scalar(
            select(TestResult)
            .where(TestResult.id == tr.id)
            .options(
                selectinload(TestResult.catalog),
                selectinload(TestResult.image_left),
                selectinload(TestResult.image_right),
            )
        )
        if tr_full:
            built.append(test_service._build_result_response(tr_full))
    return built


# ── LIST ALL ──────────────────────────────────────────────────────────────────

@router.get(
    "/{report_id}/electrical-tests",
    response_model=TestResultsListResponse,
    summary="Listar todos los resultados de prueba del reporte",
    description="""
    Devuelve los resultados ordenados por `sort_order` del catálogo (secuencia 5.1.1 → 5.4.5).
    Las pruebas aún no ejecutadas aparecen con `result=pending`.
    Incluye URLs de las imágenes asociadas a cada prueba.
    """,
)
async def list_test_results(
    report_id: uuid.UUID,
    db:        AsyncSession = Depends(get_db),
) -> TestResultsListResponse:
    return await test_service.get_results_for_report(db, report_id)


# ── GET ONE ───────────────────────────────────────────────────────────────────

@router.get(
    "/{report_id}/electrical-tests/{catalog_id}",
    response_model=TestResultResponse,
    summary="Obtener resultado de una prueba específica",
)
async def get_test_result(
    report_id:  uuid.UUID,
    catalog_id: uuid.UUID,
    db:         AsyncSession = Depends(get_db),
) -> TestResultResponse:
    tr = await db.scalar(
        select(TestResult)
        .where(
            TestResult.report_id  == report_id,
            TestResult.catalog_id == catalog_id,
        )
        .options(
            selectinload(TestResult.catalog),
            selectinload(TestResult.image_left),
            selectinload(TestResult.image_right),
        )
    )
    if not tr:
        raise HTTPException(
            status_code=404,
            detail="No se encontró resultado para esta prueba en el reporte."
        )
    return test_service._build_result_response(tr)
