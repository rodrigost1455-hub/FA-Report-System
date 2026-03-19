"""
services/report_service.py
Lógica de negocio para reportes FA. Sin lógica HTTP — solo opera con la DB.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.report      import Report, ReportStatus
from app.models.test_result import TestResult, TestResultEnum
from app.models.report_image import ReportImage
from app.models.audit_log   import ReportAuditLog, ActionEnum
from app.schemas.report     import ReportCreate, ReportUpdate, ReportResponse, ReportSummary, ReportListResponse
from fastapi import HTTPException, status


class ReportService:

    # ── CREATE ────────────────────────────────────────────────────────────

    async def create(self, db: AsyncSession, payload: ReportCreate) -> Report:
        """Crea un nuevo reporte. completion_date = hoy automáticamente."""

        # Verificar que el report_number no exista ya
        existing = await db.scalar(
            select(Report).where(Report.report_number == payload.report_number)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El número de reporte '{payload.report_number}' ya existe."
            )

        report = Report(
            report_number      = payload.report_number,
            title              = payload.title,
            request_date       = payload.request_date,
            completion_date    = date.today(),          # Auto
            part_name          = payload.part_name,
            part_number        = payload.part_number,
            yazaki_part_number = payload.yazaki_part_number,
            prepared_by_id     = payload.prepared_by_id,
            verified_by_id     = payload.verified_by_id,
            requested_by_id    = payload.requested_by_id,
            approved_by_id     = payload.approved_by_id,
            prepared_by_name   = payload.prepared_by_name,
            verified_by_name   = payload.verified_by_name,
            requested_by_name  = payload.requested_by_name,
            approved_by_name   = payload.approved_by_name,
            is_ntf             = payload.is_ntf,
            reuse_images       = payload.reuse_images,
            source_report_id   = payload.source_report_id,
            notes              = payload.notes,
            status             = ReportStatus.draft,
        )
        db.add(report)
        await db.flush()   # Obtener el id sin hacer commit todavía

        # Audit log
        db.add(ReportAuditLog(
            report_id  = report.id,
            action     = ActionEnum.created,
            new_value  = report.report_number,
        ))

        await db.commit()
        await db.refresh(report)
        return report

    # ── GET ONE ───────────────────────────────────────────────────────────

    async def get_by_id(self, db: AsyncSession, report_id: uuid.UUID) -> Report:
        """Obtiene un reporte completo con imágenes y resultados de pruebas."""
        result = await db.execute(
            select(Report)
            .where(Report.id == report_id)
            .options(
                selectinload(Report.images),
                selectinload(Report.test_results).selectinload(TestResult.catalog),
                selectinload(Report.test_results).selectinload(TestResult.image_left),
                selectinload(Report.test_results).selectinload(TestResult.image_right),
                selectinload(Report.prepared_by_user),
                selectinload(Report.verified_by_user),
                selectinload(Report.requested_by_user),
                selectinload(Report.approved_by_user),
            )
        )
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail=f"Reporte {report_id} no encontrado.")
        return report

    async def get_by_number(self, db: AsyncSession, report_number: str) -> Report:
        result = await db.execute(
            select(Report).where(Report.report_number == report_number)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail=f"Reporte '{report_number}' no encontrado.")
        return await self.get_by_id(db, report.id)

    # ── LIST ──────────────────────────────────────────────────────────────

    async def list(
        self,
        db:          AsyncSession,
        page:        int = 1,
        page_size:   int = 20,
        search:      Optional[str] = None,
        status:      Optional[ReportStatus] = None,
        is_ntf:      Optional[bool] = None,
    ) -> ReportListResponse:
        """Lista reportes con filtros opcionales. Devuelve paginado."""
        query = select(Report).order_by(desc(Report.created_at))

        if search:
            term = f"%{search}%"
            query = query.where(
                Report.report_number.ilike(term) |
                Report.part_name.ilike(term)     |
                Report.part_number.ilike(term)
            )
        if status:
            query = query.where(Report.status == status)
        if is_ntf is not None:
            query = query.where(Report.is_ntf == is_ntf)

        # Total
        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        # Página
        query = query.offset((page - 1) * page_size).limit(page_size)
        rows  = (await db.execute(query)).scalars().all()

        # Calcular contadores de pruebas para cada reporte
        summaries = []
        for r in rows:
            counts = await self._test_counts(db, r.id)
            summaries.append(ReportSummary(
                id              = r.id,
                report_number   = r.report_number,
                part_name       = r.part_name,
                part_number     = r.part_number,
                status          = r.status,
                request_date    = r.request_date,
                completion_date = r.completion_date,
                is_ntf          = r.is_ntf,
                prepared_by     = r.get_signature("prepared"),
                pdf_url         = r.pdf_url,
                created_at      = r.created_at,
                updated_at      = r.updated_at,
                **counts,
            ))

        return ReportListResponse(
            items       = summaries,
            total       = total or 0,
            page        = page,
            page_size   = page_size,
            total_pages = max(1, -(-( total or 0) // page_size)),
        )

    # ── UPDATE ────────────────────────────────────────────────────────────

    async def update(self, db: AsyncSession, report_id: uuid.UUID, payload: ReportUpdate) -> Report:
        report = await self.get_by_id(db, report_id)

        changed_fields = {}
        for field, value in payload.model_dump(exclude_none=True).items():
            old = getattr(report, field, None)
            if old != value:
                changed_fields[field] = (str(old), str(value))
                setattr(report, field, value)

        if changed_fields:
            # Registrar cada campo cambiado
            for field_name, (old_val, new_val) in changed_fields.items():
                db.add(ReportAuditLog(
                    report_id  = report.id,
                    action     = ActionEnum.updated,
                    field_name = field_name,
                    old_value  = old_val,
                    new_value  = new_val,
                ))

        await db.commit()
        await db.refresh(report)
        return await self.get_by_id(db, report_id)  # Re-fetch con relaciones

    # ── HELPERS ───────────────────────────────────────────────────────────

    async def _test_counts(self, db: AsyncSession, report_id: uuid.UUID) -> dict:
        rows = (await db.execute(
            select(TestResult.result, func.count().label("n"))
            .where(TestResult.report_id == report_id)
            .group_by(TestResult.result)
        )).all()
        counts = {r.result: r.n for r in rows}
        total  = sum(counts.values())
        return {
            "total_tests":   total,
            "tests_ok":      counts.get(TestResultEnum.OK,      0),
            "tests_ng":      counts.get(TestResultEnum.NG,      0),
            "tests_pending": counts.get(TestResultEnum.pending, 0),
        }

    def build_response(self, report: Report, test_counts: dict | None = None) -> ReportResponse:
        """Construye el ReportResponse resolviendo firmas y contadores."""
        counts = test_counts or {
            "total_tests":   len(report.test_results),
            "tests_ok":      sum(1 for t in report.test_results if t.result == TestResultEnum.OK),
            "tests_ng":      sum(1 for t in report.test_results if t.result == TestResultEnum.NG),
            "tests_pending": sum(1 for t in report.test_results if t.result == TestResultEnum.pending),
        }

        return ReportResponse(
            id                 = report.id,
            report_number      = report.report_number,
            title              = report.title,
            request_date       = report.request_date,
            completion_date    = report.completion_date,
            part_name          = report.part_name,
            part_number        = report.part_number,
            yazaki_part_number = report.yazaki_part_number,
            notes              = report.notes,
            prepared_by        = report.get_signature("prepared"),
            verified_by        = report.get_signature("verified"),
            requested_by       = report.get_signature("requested"),
            approved_by        = report.get_signature("approved"),
            is_ntf             = report.is_ntf,
            reuse_images       = report.reuse_images,
            source_report_id   = report.source_report_id,
            status             = report.status,
            pdf_url            = report.pdf_url,
            pdf_generated_at   = report.pdf_generated_at,
            images             = [
                {
                    "id": img.id, "section": img.section, "slot_key": img.slot_key,
                    "sort_order": img.sort_order, "file_url": img.file_url,
                    "caption": img.caption, "is_reused": img.is_reused,
                }
                for img in sorted(report.images, key=lambda i: (i.section, i.sort_order))
            ],
            test_results       = [
                {
                    "id": tr.id, "catalog_id": tr.catalog_id,
                    "test_code": tr.catalog.code if tr.catalog else "",
                    "result": tr.result, "measurement_val": tr.measurement_val,
                    "observation_text": tr.observation_text,
                    "is_ng_override": tr.is_ng_override, "is_reused": tr.is_reused,
                }
                for tr in report.test_results
            ],
            created_at  = report.created_at,
            updated_at  = report.updated_at,
            **counts,
        )


report_service = ReportService()
