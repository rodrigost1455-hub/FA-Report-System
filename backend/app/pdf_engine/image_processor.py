"""
pdf_engine/image_processor.py
==============================
Procesa imágenes antes de insertarlas en el PDF:
  - Resize al tamaño del slot sin distorsionar
  - Compresión JPEG controlada
  - Conversión de formato (PNG → JPEG para reducir tamaño en el PDF)
"""

import io
from PIL import Image


def process_for_slot(
    image_bytes: bytes,
    slot_width:  int,
    slot_height: int,
    quality:     int = 85,
) -> bytes:
    """
    Redimensiona la imagen al tamaño del slot manteniendo proporción.
    Rellena con fondo blanco si la proporción no coincide exactamente.
    Devuelve bytes JPEG listos para insertar en el PDF.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Calcular tamaño con aspect-ratio preservado (fit dentro del slot)
    img.thumbnail((slot_width * 2, slot_height * 2), Image.LANCZOS)

    # Crear canvas blanco del tamaño exacto del slot (en px @2x para calidad)
    canvas = Image.new("RGB", (slot_width * 2, slot_height * 2), (255, 255, 255))

    # Centrar la imagen en el canvas
    offset_x = (canvas.width  - img.width)  // 2
    offset_y = (canvas.height - img.height) // 2
    canvas.paste(img, (offset_x, offset_y))

    # Redimensionar al tamaño final del slot
    canvas = canvas.resize((slot_width, slot_height), Image.LANCZOS)

    # Serializar a JPEG
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def validate_image(image_bytes: bytes, max_size_mb: int = 10) -> tuple[bool, str]:
    """
    Valida que la imagen sea procesable.
    Retorna (válida, mensaje_de_error).
    """
    if len(image_bytes) > max_size_mb * 1024 * 1024:
        return False, f"Imagen excede {max_size_mb}MB"

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        return True, ""
    except Exception as e:
        return False, f"Imagen inválida o corrupta: {str(e)}"


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Devuelve (width, height) de la imagen en píxeles."""
    img = Image.open(io.BytesIO(image_bytes))
    return img.size
