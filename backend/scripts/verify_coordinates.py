"""
verify_coordinates.py
=====================
Script de calibración: abre el PDF template y reporta las dimensiones
reales de la página y las coordenadas de los bloques de texto existentes.

Usar para validar / corregir pdf_coordinates.json antes de producción.

Uso:
    pip install pymupdf
    python scripts/verify_coordinates.py --pdf path/to/FA_BEC_2.pdf
"""

import json
import sys
import argparse
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF no instalado. Ejecuta: pip install pymupdf")
    sys.exit(1)


def analyze_pdf(pdf_path: str, output_json: str | None = None) -> dict:
    doc = fitz.open(pdf_path)
    report = {
        "pdf_path": str(pdf_path),
        "total_pages": len(doc),
        "pages": []
    }

    for page_num, page in enumerate(doc):
        rect = page.rect
        page_data = {
            "page_index": page_num,
            "page_number": page_num + 1,
            "width_pt":  round(rect.width,  2),
            "height_pt": round(rect.height, 2),
            "text_blocks": [],
            "images": []
        }

        # ── Bloques de texto ──────────────────────────────────────────
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0:   # 0 = texto
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if not text:
                        continue
                    bbox = span["bbox"]           # (x0, y0, x1, y1) en pt, origen arriba-izq
                    # Convertir a sistema origen abajo-izquierda (PDF estándar)
                    pdf_y  = rect.height - bbox[3]
                    pdf_y1 = rect.height - bbox[1]
                    page_data["text_blocks"].append({
                        "text":      text[:80],
                        "font":      span.get("font", ""),
                        "size":      round(span.get("size", 0), 1),
                        "bbox_raw":  [round(v, 1) for v in bbox],
                        "bbox_pdf":  [round(bbox[0], 1), round(pdf_y, 1),
                                      round(bbox[2] - bbox[0], 1), round(pdf_y1 - pdf_y, 1)],
                        "_comment":  "bbox_pdf = [x, y, width, height] en sistema PDF (origen abajo-izq)"
                    })

        # ── Imágenes embebidas ────────────────────────────────────────
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            # Obtener posición de la imagen en la página
            for item in page.get_image_rects(xref):
                pdf_y  = rect.height - item.y1
                page_data["images"].append({
                    "xref": xref,
                    "bbox_pdf": [round(item.x0, 1), round(pdf_y, 1),
                                 round(item.width, 1), round(item.height, 1)],
                    "_comment": "bbox_pdf = [x, y, width, height]"
                })

        report["pages"].append(page_data)

    doc.close()

    if output_json:
        Path(output_json).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Reporte guardado en: {output_json}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return report


def print_summary(report: dict):
    print("\n" + "="*60)
    print(f"PDF: {report['pdf_path']}")
    print(f"Páginas: {report['total_pages']}")
    print("="*60)

    for pg in report["pages"]:
        print(f"\n── Página {pg['page_number']} (index {pg['page_index']}) ──")
        print(f"   Tamaño: {pg['width_pt']} x {pg['height_pt']} pt")
        print(f"   Bloques de texto: {len(pg['text_blocks'])}")
        print(f"   Imágenes embebidas: {len(pg['images'])}")

        # Mostrar primeros 5 bloques de texto como referencia de coordenadas
        for i, tb in enumerate(pg["text_blocks"][:5]):
            print(f"   [{i}] \"{tb['text'][:40]}\"")
            print(f"        x={tb['bbox_pdf'][0]}, y={tb['bbox_pdf'][1]}, "
                  f"w={tb['bbox_pdf'][2]}, h={tb['bbox_pdf'][3]}  "
                  f"font={tb['font']} size={tb['size']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verificar coordenadas del PDF template FA")
    parser.add_argument("--pdf",    required=True, help="Ruta al PDF template (FA_BEC_2.pdf)")
    parser.add_argument("--output", default=None,  help="Guardar reporte en JSON (opcional)")
    parser.add_argument("--summary", action="store_true", help="Solo mostrar resumen (sin JSON completo)")
    args = parser.parse_args()

    report = analyze_pdf(args.pdf, args.output if not args.summary else None)
    if args.summary:
        print_summary(report)
