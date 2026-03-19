"""
services/test_service.py
Lógica de pruebas eléctricas: secuencia, NG handling, reutilización NTF.
"""
import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.electrical_test  import ElectricalTestCatalog
from app.models.test_result      import TestResult, TestResultEnum
from app.models.report           import Report, ReportStatus
from app.models.report_image     import ReportImage
from app.models.audit_log        import ReportAuditLog, ActionEnum
from app.schemas.test_result     import (
    TestResultCreate, TestResultBatchCreate,
    TestResultResponse, TestResultsListResponse,
    ReuseTestResultsRequest,
)


class TestResultService:

    # ── SAVE ONE ──────────────────────────────────────────────────────────

    async def save_result(
        self,
        db:        AsyncSession,
        report_id: uuid.UUID,
        payload:   TestResultCreate,
    ) -> TestResult:
        """
        Registra o actualiza el resultado de una prueba.
        - Si ya existe un resultado para este catalog_id en este reporte, lo actualiza.
        - Si el resultado es NG y is_ng_override=False, el reporte queda en estado 'in_progress'
          esperando decisión del usuario.
        """
        # Verificar reporte
        report = await db.get(Report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")

        # Verificar que el catalog_id es válido
        catalog = await db.get(ElectricalTestCatalog, payload.catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Prueba del catálogo no encontrada.")

        # Verificar imágenes si se pasaron
        await self._verify_image_belongs_to_report(db, report_id, payload.image_left_id)
        await self._verify_image_belongs_to_report(db, report_id, payload.image_right_id)

        # Buscar resultado existente para este test en este reporte (upsert)
        existing = await db.scalar(
            select(TestResult).where(
                TestResult.report_id  == report_id,
                TestResult.catalog_id == payload.catalog_id,
            )
        )

        if existing:
            # Update
            existing.result          = payload.result
            existing.measurement_val = payload.measurement_val
            existing.image_left_id   = payload.image_left_id  or existing.image_left_id
            existing.image_right_id  = payload.image_right_id or existing.image_right_id
            existing.observation_text = payload.observation_text
            existing.is_ng_override  = payload.is_ng_override
            test_result = existing
        else:
            # Insert
            test_result = TestResult(
                report_id        = report_id,
                catalog_id       = payload.catalog_id,
                result           = payload.result,
                measurement_val  = payload.measurement_val,
                image_left_id    = payload.image_left_id,
                image_right_id   = payload.image_right_id,
                observation_text = payload.observation_text,
                is_ng_override   = payload.is_ng_override,
            )
            db.add(test_result)

        # Actualizar status del reporte
        await self._update_report_status(db, report, payload.result)

        # Audit si es NG
        if payload.result == TestResultEnum.NG:
            db.add(ReportAuditLog(
                report_id  = report_id,
                action     = ActionEnum.updated,
                field_name = f"test_{catalog.code}",
                new_value  = "NG",
                extra_data = {
                    "test_code":      catalog.code,
                    "override":       payload.is_ng_override,
                    "measurement":    payload.measurement_val,
                },
            ))

        await db.commit()
        await db.refresh(test_result)
        return test_result

    # ── SAVE BATCH ────────────────────────────────────────────────────────

    async def save_batch(
        self,
        db:        AsyncSession,
        report_id: uuid.UUID,
        payload:   TestResultBatchCreate,
    ) -> list[TestResult]:
        """Guarda múltiples resultados de prueba en una sola transacción."""
        results = []
        for item in payload.results:
            tr = await self.save_result(db, report_id, item)
            results.append(tr)
        return results

    # ── GET LIST ──────────────────────────────────────────────────────────

    async def get_results_for_report(
        self,
        db:        AsyncSession,
        report_id: uuid.UUID,
    ) -> TestResultsListResponse:
        """Lista todos los resultados de prueba de un reporte, en orden de secuencia."""
        # Verificar reporte
        report = await db.get(Report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")

        rows = (await db.execute(
            select(TestResult)
            .where(TestResult.report_id == report_id)
            .options(
                selectinload(TestResult.catalog),
                selectinload(TestResult.image_left),
                selectinload(TestResult.image_right),
            )
            .join(TestResult.catalog)
            .order_by(ElectricalTestCatalog.sort_order)
        )).scalars().all()

        built = [self._build_result_response(tr) for tr in rows]
        total     = len(built)
        completed = sum(1 for r in built if r.result != TestResultEnum.pending)
        has_ng    = any(r.result == TestResultEnum.NG for r in built)

        return TestResultsListResponse(
            report_id = report_id,
            total     = total,
            completed = completed,
            pending   = total - completed,
            has_ng    = has_ng,
            results   = built,
        )

    # ── REUSE (NTF) ───────────────────────────────────────────────────────

    async def reuse_from_report(
        self,
        db:              AsyncSession,
        target_report_id: uuid.UUID,
        payload:          ReuseTestResultsRequest,
    ) -> list[TestResult]:
        """
        Copia todos los resultados de prueba de un reporte fuente.
        Usado en el flujo NTF cuando el usuario elige reutilizar.
        Las imágenes se enlazan desde el reporte fuente (is_reused=True).
        """
        target = await db.get(Report, target_report_id)
        source = await db.get(Report, payload.source_report_id)

        if not target:
            raise HTTPException(status_code=404, detail="Reporte destino no encontrado.")
        if not source:
            raise HTTPException(status_code=404, detail="Reporte fuente no encontrado.")

        source_results = (await db.execute(
            select(TestResult)
            .where(TestResult.report_id == payload.source_report_id)
            .options(selectinload(TestResult.catalog))
        )).scalars().all()

        if not source_results:
            raise HTTPException(
                status_code=404,
                detail="El reporte fuente no tiene resultados de prueba para reutilizar."
            )

        new_results = []
        for src in source_results:
            tr = TestResult(
                report_id        = target_report_id,
                catalog_id       = src.catalog_id,
                result           = src.result,
                measurement_val  = src.measurement_val,
                image_left_id    = src.image_left_id,
                image_right_id   = src.image_right_id,
                observation_text = src.observation_text,
                is_reused        = True,
                source_result_id = src.id,
            )
            db.add(tr)
            new_results.append(tr)

        await db.commit()
        return new_results

    # ── GET CATALOG ───────────────────────────────────────────────────────

    async def get_catalog(self, db: AsyncSession) -> list[ElectricalTestCatalog]:
        """Devuelve el catálogo completo de pruebas en orden de ejecución."""
        rows = (await db.execute(
            select(ElectricalTestCatalog)
            .where(ElectricalTestCatalog.is_active == True)
            .order_by(ElectricalTestCatalog.sort_order)
        )).scalars().all()
        return list(rows)

    # ── HELPERS PRIVADOS ──────────────────────────────────────────────────

    async def _verify_image_belongs_to_report(
        self,
        db:        AsyncSession,
        report_id: uuid.UUID,
        image_id:  Optional[uuid.UUID],
    ) -> None:
        if not image_id:
            return
        img = await db.get(ReportImage, image_id)
        if not img or img.report_id != report_id:
            raise HTTPException(
                status_code=400,
                detail=f"La imagen {image_id} no pertenece a este reporte."
            )

    async def _update_report_status(
        self,
        db:     AsyncSession,
        report: Report,
        result: TestResultEnum,
    ) -> None:
        """Actualiza el status del reporte según el resultado recibido."""
        if report.status == ReportStatus.draft:
            report.status = ReportStatus.in_progress
        # Si NG y sin override → queda in_progress esperando decisión
        # Si el reporte ya era final, un NG lo regresa a in_progress
        if result == TestResultEnum.NG and not ReportStatus.final:
            report.status = ReportStatus.in_progress

    def _build_result_response(self, tr: TestResult) -> TestResultResponse:
        return TestResultResponse(
            id               = tr.id,
            report_id        = tr.report_id,
            catalog_id       = tr.catalog_id,
            result           = tr.result,
            measurement_val  = tr.measurement_val,
            observation_text = tr.observation_text,
            is_ng_override   = tr.is_ng_override,
            is_reused        = tr.is_reused,
            test_code        = tr.catalog.code       if tr.catalog else "",
            check_type       = tr.catalog.check_type if tr.catalog else "continuity",
            terminal_pos     = tr.catalog.terminal_pos  if tr.catalog else None,
            terminal_neg     = tr.catalog.terminal_neg  if tr.catalog else None,
            voltage_source   = tr.catalog.voltage_source if tr.catalog else None,
            expected_result  = tr.catalog.expected_result if tr.catalog else None,
            image_left_url   = tr.image_left.file_url  if tr.image_left  else None,
            image_right_url  = tr.image_right.file_url if tr.image_right else None,
        )


test_service = TestResultService()
