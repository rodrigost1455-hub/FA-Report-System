"""
pdf_engine/engine.py
====================
Motor principal de generación de PDF.

Recibe los datos del reporte + imágenes procesadas y los inserta
sobre el PDF template original sin modificar el layout base.

Librería: PyMuPDF (fitz) — permite abrir un PDF existente e insertar
texto/imágenes en coordenadas absolutas.
"""

import json
import fitz                          # PyMuPDF
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


@dataclass
class ReportData:
    """Datos del reporte que se insertan en el PDF."""
    report_number:       str
    request_date:        str          # "24-Jun-25"
    completion_date:     str          # "25-Jun-25"
    part_name:           str
    part_number:         str
    yazaki_part_number:  str
    prepared_by:         str
    verified_by:         str
    requested_by:        str
    approved_by:         str
    is_ntf:              bool = False


@dataclass
class TestResultData:
    code:            str              # "5.1.1"
    result:          str              # "OK" | "NG"
    measurement_val: Optional[str]    # "000034 OHM"
    image_left:      Optional[bytes]  # JPEG bytes procesados
    image_right:     Optional[bytes]
    observation_text: str = "No anomalies were observed in the manual test."


class FAReportPDFEngine:
    """
    Motor de generación del reporte FA.
    Uso:
        engine = FAReportPDFEngine()
        engine.open_template()
        engine.fill_page_1_visual(report_data, images)
        engine.fill_page_2_terminals(images)
        engine.fill_page_3_eol(images)
        for page_tests in grouped_tests:
            engine.fill_electrical_test_page(page_tests)
        pdf_bytes = engine.save_pdf()
    """

    def __init__(self):
        self.template_path  = Path(settings.TEMPLATE_PDF_PATH)
        self.coords_path    = Path(settings.COORDINATES_JSON_PATH)
        self._doc: fitz.Document | None = None
        self._coords: dict = {}

    # ── Setup ─────────────────────────────────────────────────────────────

    def open_template(self) -> None:
        """Abre el PDF template y carga el mapa de coordenadas."""
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template PDF no encontrado: {self.template_path}")

        self._doc    = fitz.open(str(self.template_path))
        self._coords = json.loads(self.coords_path.read_text())

    # ── Página 1: Inspección Visual Externa ───────────────────────────────

    def fill_page_1_visual(
        self,
        report: ReportData,
        arrival_images: list[bytes],        # Hasta 6 imágenes JPEG procesadas
    ) -> None:
        """Llena la página 1 con datos del reporte e imágenes de inspección visual."""
        page   = self._doc[0]
        coords = self._coords["pages"]["page_1_visual_inspection"]

        # Encabezado
        self._insert_text(page, coords["header"]["report_number"],   report.report_number)
        self._insert_text(page, coords["header"]["request_date"],    report.request_date)
        self._insert_text(page, coords["header"]["completion_date"], report.completion_date)

        # Datos de la pieza
        self._insert_text(page, coords["part_info"]["part_name"],          report.part_name)
        self._insert_text(page, coords["part_info"]["part_number"],        report.part_number)
        self._insert_text(page, coords["part_info"]["yazaki_part_number"], report.yazaki_part_number)

        # Firmas
        self._insert_text(page, coords["signatures"]["prepared_by"],  report.prepared_by)
        self._insert_text(page, coords["signatures"]["verified_by"],  report.verified_by)
        self._insert_text(page, coords["signatures"]["requested_by"], report.requested_by)
        self._insert_text(page, coords["signatures"]["approved_by"],  report.approved_by)

        # Grid de imágenes de llegada
        grid_cfg = coords["images"]["arrival_grid"]
        for i, img_bytes in enumerate(arrival_images[:grid_cfg["max_images"]]):
            col = i % grid_cfg["cols"]
            row = i // grid_cfg["cols"]
            x = grid_cfg["origin_x"] + col * (grid_cfg["col_width"] + grid_cfg["gap_x"])
            y = grid_cfg["origin_y"] - row * (grid_cfg["row_height"] + grid_cfg["gap_y"])
            img_rect = fitz.Rect(x, y - grid_cfg["row_height"],
                                 x + grid_cfg["col_width"], y)
            # Convertir coordenadas PDF → PyMuPDF (origen arriba-izq)
            page_h = page.rect.height
            pdf_rect = fitz.Rect(img_rect.x0,
                                  page_h - img_rect.y1,
                                  img_rect.x1,
                                  page_h - img_rect.y0)
            page.insert_image(pdf_rect, stream=img_bytes, keep_proportion=True)

    # ── Página 2: Terminal Inspection ─────────────────────────────────────

    def fill_page_2_terminals(
        self,
        terminal_images: dict[str, bytes],  # slot_key → JPEG bytes
    ) -> None:
        """
        Llena la página 2 de inspección de terminales.
        terminal_images keys: "terminal_thumb_1".."9", "terminal_center"
        """
        page   = self._doc[1]
        coords = self._coords["pages"]["page_2_terminal_inspection"]

        for slot_key, img_coords in coords["images"].items():
            if slot_key.startswith("_"):
                continue
            slot_name = img_coords.get("slot")
            if slot_name and slot_name in terminal_images:
                self._insert_image(page, img_coords, terminal_images[slot_name])

        # Texto de observación fijo
        obs = coords["observation_box"]
        self._insert_text_in_box(page, obs, obs["auto_text"],
                                  border_color=obs["border_color"])

    # ── Página 3: EOL Tester ──────────────────────────────────────────────

    def fill_page_3_eol(
        self,
        eol_images: dict[str, bytes],  # "eol_tester", "eol_label", "eol_result", "eol_label_result"
    ) -> None:
        """Llena la página 3 con imágenes del tester EOL."""
        page   = self._doc[2]
        coords = self._coords["pages"]["page_3_eol_tester"]

        for slot_key, img_coords in coords["images"].items():
            if slot_key.startswith("_"):
                continue
            slot_name = img_coords.get("slot")
            if slot_name and slot_name in eol_images:
                self._insert_image(page, img_coords, eol_images[slot_name])

        obs = coords["observation_box"]
        self._insert_text_in_box(page, obs, obs["auto_text"],
                                  border_color=obs["border_color"])

    # ── Páginas 4–12: Pruebas Eléctricas ──────────────────────────────────

    def fill_electrical_test_page(
        self,
        page_index: int,
        tests: list[TestResultData],
    ) -> None:
        """
        Llena una página de pruebas eléctricas (páginas 4-12, index 3-11).
        Cada página contiene 2-3 pruebas con imágenes left/right/bottom.
        """
        page        = self._doc[page_index]
        layout      = self._coords["pages"]["pages_electrical_tests"]["layout_template"]
        overrides   = self._coords["pages"]["pages_electrical_tests"]["page_overrides"]
        page_override = overrides.get(f"page_index_{page_index}", {})

        test_map    = self._coords["test_to_page_map"]
        ng_style    = self._coords["ng_result_style"]

        for test in tests:
            test_pos = test_map.get(test.code, {}).get("position", "left")
            is_ng    = test.result == "NG"

            # Seleccionar coordenadas de imagen según posición
            if test_pos == "left":
                img_coords   = layout["image_left"]
                label_coords = layout["test_label_left"]
                badge_coords = layout["test_badge_left"]
                img_bytes    = test.image_left
            elif test_pos == "right":
                img_coords   = layout["image_right"]
                label_coords = layout["test_label_right"]
                badge_coords = layout["test_badge_right"]
                img_bytes    = test.image_right
            else:  # "bottom"
                img_coords   = page_override.get("image_bottom_left", layout["image_bottom_single"])
                label_coords = page_override.get("test_label_bottom", layout["test_label_left"])
                badge_coords = page_override.get("test_badge_bottom", layout["test_badge_left"])
                img_bytes    = test.image_left or test.image_right

            # Insertar imagen
            if img_bytes:
                self._insert_image(page, img_coords, img_bytes)

            # Insertar label del número de prueba (ej: "5.1.1")
            self._insert_text_in_box(page, label_coords, test.code,
                                      bold=True, border=True)

            # Insertar badge de tipo de prueba (lo lee del catálogo via parámetro extra si se pasa)
            # El texto del badge viene en test.observation_text como info de contexto
            # En implementación real: pasar check_type como campo

            # Insertar caja de observación con estilo OK/NG
            obs_cfg      = layout["observation_box"]
            border_color = ng_style["observation_box_border_color"] if is_ng else obs_cfg["border_color_ok"]
            text_color   = ng_style["observation_box_text_color"]   if is_ng else obs_cfg["text_color_ok"]
            bg_color     = ng_style["observation_box_bg_color"]      if is_ng else None
            obs_text     = test.observation_text if not is_ng else obs_cfg["text_ng"].replace("{code}", test.code)

            # Solo insertar la caja de observación una vez por página (para el último test)
            # La lógica de cuándo insertar se maneja en el servicio orquestador

        # Caja de observación al final de la página
        # (La inserta el service después de procesar todos los tests de esa página)

    # ── Helpers privados ──────────────────────────────────────────────────

    def _insert_text(self, page: fitz.Page, coords: dict, text: str) -> None:
        """Inserta texto en la posición indicada por el mapa de coordenadas."""
        page_h   = page.rect.height
        x, y, w, h = coords["x"], coords["y"], coords["w"], coords["h"]

        # Convertir sistema PDF (origen abajo-izq) → PyMuPDF (origen arriba-izq)
        rect = fitz.Rect(x, page_h - y - h, x + w, page_h - y)

        font_name = "helv"            # Helvetica en PyMuPDF
        if coords.get("font", "").endswith("-Bold"):
            font_name = "helvB"

        align_map = {"left": 0, "center": 1, "right": 2}
        align     = align_map.get(coords.get("align", "left"), 0)

        page.insert_textbox(
            rect,
            text,
            fontsize  = coords.get("font_size", 10),
            fontname  = font_name,
            align     = align,
            color     = (0, 0, 0),
        )

    def _insert_text_in_box(
        self,
        page: fitz.Page,
        coords: dict,
        text: str,
        bold: bool = False,
        border: bool = False,
        border_color: list | None = None,
        text_color: list | None = None,
        bg_color: list | None = None,
    ) -> None:
        """Inserta texto opcionalmente con borde y background."""
        page_h   = page.rect.height
        x, y, w, h = coords["x"], coords["y"], coords["w"], coords["h"]
        rect = fitz.Rect(x, page_h - y - h, x + w, page_h - y)

        if bg_color:
            page.draw_rect(rect, color=None, fill=bg_color)

        if border and border_color:
            page.draw_rect(rect, color=border_color, width=0.5)

        tc = tuple(text_color) if text_color else (0, 0, 0)
        page.insert_textbox(
            rect, text,
            fontsize = coords.get("font_size", 10),
            fontname = "helvB" if bold else "helv",
            align    = 1,   # centrado
            color    = tc,
        )

    def _insert_image(self, page: fitz.Page, coords: dict, img_bytes: bytes) -> None:
        """Inserta imagen JPEG en la posición indicada."""
        page_h   = page.rect.height
        x, y, w, h = coords["x"], coords["y"], coords["w"], coords["h"]
        rect = fitz.Rect(x, page_h - y - h, x + w, page_h - y)
        page.insert_image(rect, stream=img_bytes, keep_proportion=True)

    # ── Output ────────────────────────────────────────────────────────────

    def save_pdf(self) -> bytes:
        """Devuelve los bytes del PDF generado."""
        if not self._doc:
            raise RuntimeError("Llamar open_template() primero.")
        return self._doc.write()

    def close(self) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None

    def __enter__(self):
        self.open_template()
        return self

    def __exit__(self, *_):
        self.close()
