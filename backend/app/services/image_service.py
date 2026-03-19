"""
services/image_service.py
Upload de imágenes, procesamiento con Pillow, y almacenamiento en Supabase Storage.
"""
import uuid
import io
from typing import Optional

from fastapi import UploadFile, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from supabase import create_client, Client

from app.core.config        import settings
from app.models.report      import Report
from app.models.report_image import ReportImage, ImageSection
from app.pdf_engine.image_processor import process_for_slot, validate_image, get_image_dimensions

# Dimensiones de slot por sección (en px — deben coincidir con pdf_coordinates.json)
SLOT_DIMENSIONS: dict[str, dict[str, int]] = {
    # Visual inspection — grid 2 cols
    "arrival_default":    {"w": 260, "h": 110},
    # Terminal inspection
    "terminal_thumb":     {"w": 100, "h":  90},
    "terminal_center":    {"w": 390, "h": 170},
    "terminal_side":      {"w":  55, "h":  90},
    # EOL
    "eol_tester":         {"w": 420, "h": 180},
    "eol_label":          {"w": 110, "h": 100},
    "eol_result":         {"w": 420, "h": 210},
    "eol_label_result":   {"w": 110, "h": 100},
    # Pruebas eléctricas
    "electrical_left":    {"w": 260, "h": 220},
    "electrical_right":   {"w": 266, "h": 220},
    "electrical_bottom":  {"w": 200, "h": 180},
}

MAX_IMAGES_PER_SECTION = {
    ImageSection.visual_inspection:  6,
    ImageSection.terminal_inspection: 9,
    ImageSection.eol:                 4,
    ImageSection.electrical_test:     40,  # 2 por prueba × 20 pruebas
}


class ImageService:

    def __init__(self):
        self._supabase: Client | None = None

    @property
    def supabase(self) -> Client:
        if not self._supabase:
            self._supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return self._supabase

    # ── UPLOAD ────────────────────────────────────────────────────────────

    async def upload(
        self,
        db:         AsyncSession,
        report_id:  uuid.UUID,
        file:       UploadFile,
        section:    ImageSection,
        slot_key:   Optional[str] = None,
        sort_order: int = 0,
        caption:    Optional[str] = None,
    ) -> ReportImage:
        """
        Procesa y sube una imagen al Storage de Supabase.
        Devuelve el registro ReportImage creado.
        """
        # 1. Verificar que el reporte existe
        report = await db.get(Report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")

        # 2. Leer bytes
        raw_bytes = await file.read()

        # 3. Validar
        valid, err = validate_image(raw_bytes, settings.MAX_IMAGE_SIZE_MB)
        if not valid:
            raise HTTPException(status_code=400, detail=err)

        # 4. Verificar límite de imágenes por sección
        count = await db.scalar(
            select(ReportImage)
            .where(ReportImage.report_id == report_id, ReportImage.section == section)
            .with_only_columns(__import__("sqlalchemy").func.count())
        )
        max_allowed = MAX_IMAGES_PER_SECTION.get(section, 99)
        if (count or 0) >= max_allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Límite de {max_allowed} imágenes para la sección '{section}' alcanzado."
            )

        # 5. Dimensiones originales
        orig_w, orig_h = get_image_dimensions(raw_bytes)

        # 6. Redimensionar al tamaño del slot
        slot_cfg  = self._resolve_slot_dimensions(section, slot_key)
        proc_bytes = process_for_slot(raw_bytes, slot_cfg["w"], slot_cfg["h"], settings.IMAGE_QUALITY)
        proc_w, proc_h = slot_cfg["w"], slot_cfg["h"]

        # 7. Subir a Supabase Storage
        storage_path = f"reports/{report_id}/{section}/{slot_key or sort_order}_{uuid.uuid4().hex[:8]}.jpg"
        self.supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
            path        = storage_path,
            file        = proc_bytes,
            file_options = {"content-type": "image/jpeg"},
        )

        # 8. Obtener URL pública
        public_url = self.supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

        # 9. Guardar registro en BD
        image = ReportImage(
            report_id       = report_id,
            section         = section,
            slot_key        = slot_key,
            sort_order      = sort_order,
            file_url        = public_url,
            file_name       = file.filename,
            mime_type       = "image/jpeg",
            file_size_bytes = len(proc_bytes),
            orig_width      = orig_w,
            orig_height     = orig_h,
            proc_width      = proc_w,
            proc_height     = proc_h,
            caption         = caption,
            is_reused       = False,
        )
        db.add(image)
        await db.commit()
        await db.refresh(image)
        return image

    # ── UPLOAD MÚLTIPLE ───────────────────────────────────────────────────

    async def upload_many(
        self,
        db:        AsyncSession,
        report_id: uuid.UUID,
        files:     list[UploadFile],
        section:   ImageSection,
    ) -> list[ReportImage]:
        """Sube múltiples imágenes en secuencia, asignando sort_order automáticamente."""
        # Obtener el sort_order actual más alto en esta sección
        from sqlalchemy import func
        current_max = await db.scalar(
            select(func.max(ReportImage.sort_order))
            .where(ReportImage.report_id == report_id, ReportImage.section == section)
        ) or -1

        results = []
        for i, file in enumerate(files):
            img = await self.upload(
                db         = db,
                report_id  = report_id,
                file       = file,
                section    = section,
                sort_order = current_max + 1 + i,
            )
            results.append(img)
        return results

    # ── REUSE (NTF) ───────────────────────────────────────────────────────

    async def reuse_from_report(
        self,
        db:              AsyncSession,
        target_report_id: uuid.UUID,
        source_report_id: uuid.UUID,
        section:          ImageSection,
        slot_key:         Optional[str] = None,
    ) -> list[ReportImage]:
        """
        Copia las imágenes de un reporte fuente al reporte destino
        (flujo NTF: reutilizar imágenes de pruebas anteriores).
        Crea registros con is_reused=True y source_image_id apuntando al original.
        """
        # Verificar que el reporte fuente existe
        source = await db.get(Report, source_report_id)
        if not source:
            raise HTTPException(status_code=404, detail="Reporte fuente no encontrado.")

        # Obtener imágenes del reporte fuente
        query = select(ReportImage).where(
            ReportImage.report_id == source_report_id,
            ReportImage.section   == section,
        )
        if slot_key:
            query = query.where(ReportImage.slot_key == slot_key)

        source_images = (await db.execute(query)).scalars().all()

        if not source_images:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontraron imágenes en sección '{section}' del reporte fuente."
            )

        new_images = []
        for src in source_images:
            img = ReportImage(
                report_id       = target_report_id,
                section         = src.section,
                slot_key        = src.slot_key,
                sort_order      = src.sort_order,
                file_url        = src.file_url,    # Misma URL — no se duplica el archivo
                file_name       = src.file_name,
                mime_type       = src.mime_type,
                file_size_bytes = src.file_size_bytes,
                orig_width      = src.orig_width,
                orig_height     = src.orig_height,
                proc_width      = src.proc_width,
                proc_height     = src.proc_height,
                is_reused       = True,
                source_image_id = src.id,
                caption         = src.caption,
            )
            db.add(img)
            new_images.append(img)

        await db.commit()
        return new_images

    # ── DELETE ────────────────────────────────────────────────────────────

    async def delete(self, db: AsyncSession, report_id: uuid.UUID, image_id: uuid.UUID) -> None:
        image = await db.get(ReportImage, image_id)
        if not image or image.report_id != report_id:
            raise HTTPException(status_code=404, detail="Imagen no encontrada.")

        # Solo borrar del Storage si NO es reutilizada (para no romper otros reportes)
        if not image.is_reused:
            try:
                path = image.file_url.split(f"{settings.SUPABASE_STORAGE_BUCKET}/")[1].split("?")[0]
                self.supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([path])
            except Exception:
                pass  # Si falla el borrado en Storage, igual borra el registro

        await db.delete(image)
        await db.commit()

    # ── HELPERS ───────────────────────────────────────────────────────────

    def _resolve_slot_dimensions(self, section: ImageSection, slot_key: Optional[str]) -> dict:
        """Devuelve las dimensiones del slot según sección y clave."""
        if slot_key:
            for key, dims in SLOT_DIMENSIONS.items():
                if slot_key.startswith(key) or key in slot_key:
                    return dims

        defaults = {
            ImageSection.visual_inspection:   SLOT_DIMENSIONS["arrival_default"],
            ImageSection.terminal_inspection:  SLOT_DIMENSIONS["terminal_thumb"],
            ImageSection.eol:                  SLOT_DIMENSIONS["eol_tester"],
            ImageSection.electrical_test:      SLOT_DIMENSIONS["electrical_left"],
        }
        return defaults.get(section, {"w": 260, "h": 180})


image_service = ImageService()
