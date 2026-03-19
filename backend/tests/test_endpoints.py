"""
tests/test_endpoints.py
Tests de integración para los 5 endpoints principales.

Cubre:
  POST /api/reports
  GET  /api/reports/{id}
  POST /api/reports/{id}/images
  POST /api/reports/{id}/electrical-tests
  POST /api/reports/{id}/generate-pdf  (mock del motor PDF)
"""
import io
import uuid
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

from tests.conftest import SAMPLE_REPORT_PAYLOAD


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/reports
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateReport:

    @pytest.mark.asyncio
    async def test_create_report_success(self, client: AsyncClient):
        """Crea un reporte con datos mínimos válidos."""
        resp = await client.post("/api/reports", json=SAMPLE_REPORT_PAYLOAD)
        assert resp.status_code == 201

        data = resp.json()
        assert data["report_number"]      == "TEST-001"
        assert data["part_name"]          == "PHEV BEC GEN 4"
        assert data["part_number"]        == "L1M8 10C666 GF"
        assert data["yazaki_part_number"] == "7370-2573-8W"
        assert data["status"]             == "draft"
        assert data["is_ntf"]             is False
        assert data["prepared_by"]        == "Rodrigo Santana"
        assert data["completion_date"]    is not None   # auto-generada
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_report_duplicate_number(self, client: AsyncClient):
        """El mismo número de reporte no puede crearse dos veces."""
        payload = {**SAMPLE_REPORT_PAYLOAD, "report_number": "DUPL-001"}
        await client.post("/api/reports", json=payload)
        resp = await client.post("/api/reports", json=payload)
        assert resp.status_code == 409
        assert "ya existe" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_report_missing_prepared_by(self, client: AsyncClient):
        """Debe fallar si no hay firma de 'prepared by'."""
        payload = {**SAMPLE_REPORT_PAYLOAD, "report_number": "NOFIRM-001"}
        del payload["prepared_by_name"]
        resp = await client.post("/api/reports", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_ntf_requires_source(self, client: AsyncClient):
        """reuse_images=True sin source_report_id debe fallar."""
        payload = {
            **SAMPLE_REPORT_PAYLOAD,
            "report_number": "NTF-FAIL-001",
            "is_ntf":        True,
            "reuse_images":  True,
            # source_report_id ausente
        }
        resp = await client.post("/api/reports", json=payload)
        assert resp.status_code == 422
        body = resp.json()
        assert any("source_report_id" in str(e) for e in body.get("errors", [body.get("detail", "")]))

    @pytest.mark.asyncio
    async def test_create_ntf_valid(self, client: AsyncClient):
        """NTF con source_report_id válido (aunque el reporte fuente no exista) crea el reporte."""
        # Primero crea un reporte fuente
        source = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD,
            "report_number": "SOURCE-001",
        })
        source_id = source.json()["id"]

        payload = {
            **SAMPLE_REPORT_PAYLOAD,
            "report_number":   "NTF-OK-001",
            "is_ntf":          True,
            "reuse_images":    True,
            "source_report_id": source_id,
        }
        resp = await client.post("/api/reports", json=payload)
        assert resp.status_code == 201
        assert resp.json()["is_ntf"] is True


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/reports/{id}
# ══════════════════════════════════════════════════════════════════════════════

class TestGetReport:

    @pytest.mark.asyncio
    async def test_get_report_success(self, client: AsyncClient):
        """Obtiene un reporte existente por ID."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": "GET-001"
        })
        report_id = create.json()["id"]

        resp = await client.get(f"/api/reports/{report_id}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["id"]            == report_id
        assert data["report_number"] == "GET-001"
        assert "images"              in data
        assert "test_results"        in data
        assert "total_tests"         in data

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, client: AsyncClient):
        """UUID inexistente devuelve 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/reports/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_report_by_number(self, client: AsyncClient):
        """Busca reporte por número de reporte."""
        await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": "BYNUM-001"
        })
        resp = await client.get("/api/reports/by-number/BYNUM-001")
        assert resp.status_code == 200
        assert resp.json()["report_number"] == "BYNUM-001"

    @pytest.mark.asyncio
    async def test_list_reports_pagination(self, client: AsyncClient):
        """Lista con paginación funciona correctamente."""
        resp = await client.get("/api/reports?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "items"       in data
        assert "total"       in data
        assert "total_pages" in data
        assert data["page"]  == 1

    @pytest.mark.asyncio
    async def test_list_reports_search(self, client: AsyncClient):
        """Búsqueda por número de reporte filtra correctamente."""
        await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": "SEARCH-999"
        })
        resp = await client.get("/api/reports?search=SEARCH-999")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(r["report_number"] == "SEARCH-999" for r in items)


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/reports/{id}/images
# ══════════════════════════════════════════════════════════════════════════════

class TestUploadImages:

    def _make_jpeg(self, size: tuple = (100, 80)) -> bytes:
        """Genera una imagen JPEG válida mínima en memoria."""
        from PIL import Image
        import io
        img = Image.new("RGB", size, color=(200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    @pytest.mark.asyncio
    async def test_upload_visual_inspection_image(self, client: AsyncClient):
        """Sube una imagen de inspección visual."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": "IMG-001"
        })
        report_id = create.json()["id"]

        with patch("app.services.image_service.ImageService.supabase") as mock_sb:
            # Mock Supabase Storage
            mock_sb.storage.from_.return_value.upload.return_value = {}
            mock_sb.storage.from_.return_value.get_public_url.return_value = \
                "https://supabase.co/storage/v1/object/public/fa-reports/test.jpg"

            jpeg = self._make_jpeg()
            resp = await client.post(
                f"/api/reports/{report_id}/images",
                data={"section": "visual_inspection", "sort_order": "0"},
                files={"file": ("test.jpg", jpeg, "image/jpeg")},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["section"]    == "visual_inspection"
        assert data["report_id"]  == report_id
        assert data["is_reused"]  is False
        assert data["file_url"]   != ""

    @pytest.mark.asyncio
    async def test_upload_invalid_mime(self, client: AsyncClient):
        """Archivo PDF no es aceptado como imagen."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": "IMG-MIME-001"
        })
        report_id = create.json()["id"]

        resp = await client.post(
            f"/api/reports/{report_id}/images",
            data={"section": "visual_inspection"},
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "tipo" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_images_by_section(self, client: AsyncClient):
        """Lista imágenes filtradas por sección."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": "IMG-LIST-001"
        })
        report_id = create.json()["id"]

        resp = await client.get(
            f"/api/reports/{report_id}/images?section=visual_inspection"
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/reports/{id}/electrical-tests
# ══════════════════════════════════════════════════════════════════════════════

class TestElectricalTests:

    async def _create_report_and_catalog(self, client: AsyncClient, db) -> tuple[str, str]:
        """Helper: crea reporte y obtiene el primer catalog_id del seed."""
        from sqlalchemy import select
        from app.models.electrical_test import ElectricalTestCatalog

        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"ELEC-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        # Obtener catálogo desde la BD de test (necesita seed data)
        # En tests reales se haría con el endpoint /api/tests-catalog
        # Aquí usamos un UUID simulado
        catalog_id = str(uuid.uuid4())   # En integración real: del seed
        return report_id, catalog_id

    @pytest.mark.asyncio
    async def test_save_ok_result(self, client: AsyncClient, db):
        """Guarda un resultado OK para una prueba eléctrica."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"ELEC-OK-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        # Necesitamos un catalog_id real — obtenerlo del catálogo
        catalog_resp = await client.get("/api/tests-catalog")
        if catalog_resp.status_code == 200 and catalog_resp.json():
            catalog_id = catalog_resp.json()[0]["id"]   # Primer test: 5.1.1
        else:
            pytest.skip("Catálogo sin datos — ejecutar seed primero")

        payload = {
            "catalog_id":     catalog_id,
            "result":         "OK",
            "measurement_val": "000034 OHM",
        }
        resp = await client.post(f"/api/reports/{report_id}/electrical-tests", json=payload)
        assert resp.status_code == 201

        data = resp.json()
        assert data["result"]          == "OK"
        assert data["measurement_val"] == "000034 OHM"
        assert data["is_ng_override"]  is False

    @pytest.mark.asyncio
    async def test_save_ng_result(self, client: AsyncClient):
        """Resultado NG se guarda con observación correcta."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"ELEC-NG-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        catalog_resp = await client.get("/api/tests-catalog")
        if not catalog_resp.json():
            pytest.skip("Catálogo sin datos")
        catalog_id = catalog_resp.json()[0]["id"]

        payload = {
            "catalog_id":      catalog_id,
            "result":          "NG",
            "measurement_val": "OPEN",
            "is_ng_override":  False,
        }
        resp = await client.post(f"/api/reports/{report_id}/electrical-tests", json=payload)
        assert resp.status_code == 201

        data = resp.json()
        assert data["result"]         == "NG"
        assert "NG" in data["observation_text"]

    @pytest.mark.asyncio
    async def test_upsert_existing_result(self, client: AsyncClient):
        """Guardar el mismo catalog_id dos veces actualiza el resultado (upsert)."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"UPSERT-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        catalog_resp = await client.get("/api/tests-catalog")
        if not catalog_resp.json():
            pytest.skip("Catálogo sin datos")
        catalog_id = catalog_resp.json()[0]["id"]

        # Primera vez: OK
        await client.post(f"/api/reports/{report_id}/electrical-tests", json={
            "catalog_id": catalog_id, "result": "OK"
        })
        # Segunda vez: NG (actualiza)
        resp = await client.post(f"/api/reports/{report_id}/electrical-tests", json={
            "catalog_id": catalog_id, "result": "NG"
        })
        assert resp.status_code == 201
        assert resp.json()["result"] == "NG"

    @pytest.mark.asyncio
    async def test_list_test_results(self, client: AsyncClient):
        """GET electrical-tests devuelve lista con contadores."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"LIST-TR-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        resp = await client.get(f"/api/reports/{report_id}/electrical-tests")
        assert resp.status_code == 200

        data = resp.json()
        assert "results"   in data
        assert "total"     in data
        assert "has_ng"    in data
        assert "completed" in data


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/reports/{id}/generate-pdf
# ══════════════════════════════════════════════════════════════════════════════

class TestGeneratePDF:

    @pytest.mark.asyncio
    async def test_generate_pdf_no_images_fails(self, client: AsyncClient):
        """Sin imágenes el PDF no se puede generar — debe devolver 422."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"PDF-NOIMGS-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        resp = await client.post(f"/api/reports/{report_id}/generate-pdf")
        assert resp.status_code == 422
        assert "errors" in resp.json()

    @pytest.mark.asyncio
    async def test_generate_pdf_not_found(self, client: AsyncClient):
        """UUID inexistente devuelve 404."""
        resp = await client.post(f"/api/reports/{uuid.uuid4()}/generate-pdf")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_pdf_mocked(self, client: AsyncClient):
        """PDF generado con motor y storage mockeados — verifica respuesta."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"PDF-MOCK-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        # Mock del motor PDF y de Supabase para no necesitar archivos reales
        mock_pdf_bytes = b"%PDF-1.4 mock content"
        fake_url = f"https://supabase.co/storage/v1/object/public/fa-reports/pdfs/{report_id}/test.pdf"

        with patch("app.services.pdf_service.FAReportPDFEngine") as MockEngine, \
             patch("app.services.pdf_service.PDFService.supabase") as mock_sb, \
             patch("app.services.pdf_service.PDFService._fetch_image", new_callable=AsyncMock) as mock_fetch:

            # Configurar mocks
            mock_engine_instance = MagicMock()
            mock_engine_instance.__enter__ = MagicMock(return_value=mock_engine_instance)
            mock_engine_instance.__exit__  = MagicMock(return_value=False)
            mock_engine_instance.save_pdf.return_value = mock_pdf_bytes
            MockEngine.return_value = mock_engine_instance

            mock_sb.storage.from_.return_value.upload.return_value = {}
            mock_sb.storage.from_.return_value.get_public_url.return_value = fake_url
            mock_fetch.return_value = b"fake_image_bytes"

            # Agregar imagen mock directamente a la BD para pasar la validación
            from app.models.report_image import ReportImage, ImageSection
            from tests.conftest import TestSessionLocal
            async with TestSessionLocal() as session:
                session.add(ReportImage(
                    report_id   = uuid.UUID(report_id),
                    section     = ImageSection.visual_inspection,
                    file_url    = "https://example.com/fake.jpg",
                    sort_order  = 0,
                ))
                await session.commit()

            resp = await client.post(f"/api/reports/{report_id}/generate-pdf")

        assert resp.status_code == 200
        data = resp.json()
        assert data["pdf_url"]          == fake_url
        assert data["pdf_generated_at"] is not None
        assert data["pages"]            == 12

    @pytest.mark.asyncio
    async def test_download_redirect(self, client: AsyncClient):
        """GET /download redirige al PDF cuando existe."""
        # Primero generar el reporte con pdf_url configurado
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"PDF-DL-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        # Forzar pdf_url en la BD
        from tests.conftest import TestSessionLocal
        from app.models.report import Report as ReportModel
        async with TestSessionLocal() as session:
            r = await session.get(ReportModel, uuid.UUID(report_id))
            r.pdf_url = "https://supabase.co/test.pdf"
            await session.commit()

        resp = await client.get(f"/api/reports/{report_id}/download", follow_redirects=False)
        assert resp.status_code == 302
        assert "supabase.co" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_download_no_pdf_yet(self, client: AsyncClient):
        """GET /download sin PDF generado devuelve 404."""
        create = await client.post("/api/reports", json={
            **SAMPLE_REPORT_PAYLOAD, "report_number": f"PDF-NODL-{uuid.uuid4().hex[:6]}"
        })
        report_id = create.json()["id"]

        resp = await client.get(f"/api/reports/{report_id}/download", follow_redirects=False)
        assert resp.status_code == 404
