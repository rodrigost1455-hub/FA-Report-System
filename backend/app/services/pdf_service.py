"""
services/pdf_service.py
Orquestador del motor PDF.

1. Recopila todos los datos del reporte desde la BD
2. Descarga las imágenes procesadas
3. Llama al FAReportPDFEngine página por página
4. Sube el PDF generado a Supabase Storage
5. Actualiza el registro del reporte con la URL del PDF
"""
import uuid
import httpx
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from supabase import create_client, Client

from app.core.config            import settings
from app.models.report          import Report, ReportStatus
from app.models.report_image    import ReportImage, ImageSection
from app.models.test_result     import TestResult, TestResultEnum
from app.models.electrical_test import ElectricalTestCatalog
from app.models.audit_log       import ReportAuditLog, ActionEnum
from app.pdf_engine.engine      import FAReportPDFEngine, ReportData, TestResultData
from app.schemas.test_result    import PDFGenerateResponse


class PDFService:

    def __init__(self):
        self._supabase: Client | None = None

    @property
    def supabase(self) -> Client:
        if not self._supabase:
            self._supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return self._supabase

    # ── GENERATE ─────────────────────────────────────────────────────────

    async def generate(self, db: AsyncSession, report_id: uuid.UUID) -> PDFGenerateResponse:
        """
        Pipeline completo de generación PDF.
        Lanza HTTPException si falta algún dato requerido.
        """
        # 1. Cargar reporte con todas sus relaciones
        report = await self._load_report_full(db, report_id)

        # 2. Validar que el reporte está listo para generar PDF
        self._validate_ready(report)

        # 3. Construir ReportData
        report_data = ReportData(
            report_number      = report.report_number,
            request_date       = report.request_date.strftime("%-d-%b-%y"),   # "24-Jun-25"
            completion_date    = report.completion_date.strftime("%-d-%b-%y"),
            part_name          = report.part_name,
            part_number        = report.part_number,
            yazaki_part_number = report.yazaki_part_number,
            prepared_by        = report.get_signature("prepared"),
            verified_by        = report.get_signature("verified"),
            requested_by       = report.get_signature("requested"),
            approved_by        = report.get_signature("approved"),
            is_ntf             = report.is_ntf,
        )

        # 4. Agrupar imágenes por sección y slot
        images_by_section = defaultdict(dict)     # section → slot_key → bytes
        arrival_images    = []                    # Sección visual: lista ordenada

        async with httpx.AsyncClient(timeout=30) as client:
            # Ordenar imágenes por sección y sort_order
            sorted_images = sorted(report.images, key=lambda i: (i.section, i.sort_order))

            for img in sorted_images:
                img_bytes = await self._fetch_image(client, img.file_url)
                if img.section == ImageSection.visual_inspection:
                    arrival_images.append(img_bytes)
                elif img.slot_key:
                    images_by_section[img.section][img.slot_key] = img_bytes

        # 5. Agrupar resultados de prueba por página del PDF
        test_results_by_page = defaultdict(list)
        coord_map = self._load_test_page_map()

        for tr in sorted(report.test_results, key=lambda t: t.catalog.sort_order if t.catalog else 99):
            if not tr.catalog:
                continue
            page_idx = coord_map.get(tr.catalog.code, {}).get("page_index")
            if page_idx is None:
                continue

            left_bytes  = await self._fetch_image_by_id(db, tr.image_left_id)
            right_bytes = await self._fetch_image_by_id(db, tr.image_right_id)

            test_results_by_page[page_idx].append(TestResultData(
                code             = tr.catalog.code,
                result           = tr.result.value,
                measurement_val  = tr.measurement_val,
                image_left       = left_bytes,
                image_right      = right_bytes,
                observation_text = tr.observation_text,
            ))

        # 6. Generar el PDF
        with FAReportPDFEngine() as engine:
            # Página 1: Inspección visual
            engine.fill_page_1_visual(report_data, arrival_images)

            # Página 2: Terminal inspection
            terminal_imgs = images_by_section.get(ImageSection.terminal_inspection, {})
            engine.fill_page_2_terminals(terminal_imgs)

            # Página 3: EOL Tester
            eol_imgs = images_by_section.get(ImageSection.eol, {})
            engine.fill_page_3_eol(eol_imgs)

            # Páginas 4-12: Pruebas eléctricas (índices 3-11)
            for page_index in range(3, 12):
                tests_in_page = test_results_by_page.get(page_index, [])
                if tests_in_page:
                    engine.fill_electrical_test_page(page_index, tests_in_page)

            pdf_bytes = engine.save_pdf()

        # 7. Subir a Supabase Storage
        storage_path = f"pdfs/{report_id}/{report.report_number}.pdf"
        self.supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
            path         = storage_path,
            file         = pdf_bytes,
            file_options = {"content-type": "application/pdf", "upsert": "true"},
        )
        pdf_url = self.supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

        # 8. Actualizar reporte en BD
        now = datetime.now(timezone.utc)
        report.pdf_url          = pdf_url
        report.pdf_generated_at = now
        report.status           = ReportStatus.final

        db.add(ReportAuditLog(
            report_id  = report_id,
            action     = ActionEnum.pdf_generated,
            new_value  = pdf_url,
            extra_data = {"pages": 12, "size_bytes": len(pdf_bytes)},
        ))
        await db.commit()

        return PDFGenerateResponse(
            report_id        = report_id,
            pdf_url          = pdf_url,
            pdf_generated_at = now.isoformat(),
            pages            = 12,
        )

    # ── HELPERS ───────────────────────────────────────────────────────────

    async def _load_report_full(self, db: AsyncSession, report_id: uuid.UUID) -> Report:
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
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        return report

    def _validate_ready(self, report: Report) -> None:
        """Verifica que el reporte tiene lo mínimo para generar el PDF."""
        errors = []

        if not report.images:
            errors.append("El reporte no tiene imágenes de inspección visual.")

        # Verificar que al menos tiene la firma de quien preparó
        if not report.get_signature("prepared"):
            errors.append("Falta la firma de 'Preparado por'.")

        if errors:
            raise HTTPException(
                status_code=422,
                detail={"message": "El reporte no está listo para generar PDF.", "errors": errors}
            )

    async def _fetch_image(self, client: httpx.AsyncClient, url: str) -> bytes:
        """Descarga bytes de una imagen desde su URL pública."""
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Error al descargar imagen: {e}")

    async def _fetch_image_by_id(
        self, db: AsyncSession, image_id: uuid.UUID | None
    ) -> bytes | None:
        if not image_id:
            return None
        img = await db.get(ReportImage, image_id)
        if not img:
            return None
        async with httpx.AsyncClient(timeout=30) as client:
            return await self._fetch_image(client, img.file_url)

    def _load_test_page_map(self) -> dict:
        """Carga el test_to_page_map desde pdf_coordinates.json."""
        import json
        from pathlib import Path
        coords = json.loads(Path(settings.COORDINATES_JSON_PATH).read_text())
        return coords.get("test_to_page_map", {})


pdf_service = PDFService()
