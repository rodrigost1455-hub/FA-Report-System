"""
core/config.py — Settings con soporte para descarga del template PDF desde Supabase.
En Railway no hay filesystem persistente — el template se descarga desde
Supabase Storage al arrancar si no existe en disco.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str            = "postgresql+asyncpg://postgres:postgres@localhost:5432/fa_reports"
    SUPABASE_URL: str            = ""
    SUPABASE_KEY: str            = ""
    SUPABASE_STORAGE_BUCKET: str = "fa-reports"

    # URL pública del template en Supabase Storage (se genera con upload_template.py)
    TEMPLATE_PDF_URL: str  = ""
    # Ruta local — /tmp funciona en Railway (efímero, se descarga en cada deploy)
    TEMPLATE_PDF_PATH: str = "/tmp/FA_BEC_2.pdf"

    COORDINATES_JSON_PATH: str = str(
        Path(__file__).parent.parent / "pdf_engine" / "pdf_coordinates.json"
    )

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://fa-reports.vercel.app",
    ]

    MAX_IMAGE_SIZE_MB: int = 10
    IMAGE_QUALITY:     int = 85

    class Config:
        env_file = ".env"


settings = Settings()


async def ensure_template_downloaded() -> None:
    """Descarga el PDF template si no existe. Llamado en startup de FastAPI."""
    template = Path(settings.TEMPLATE_PDF_PATH)
    if template.exists():
        print(f"✓ Template PDF listo: {template}")
        return
    if not settings.TEMPLATE_PDF_URL:
        print("⚠  TEMPLATE_PDF_URL no configurada — PDF engine no disponible.")
        return
    print("↓ Descargando template PDF desde Supabase Storage...")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(settings.TEMPLATE_PDF_URL)
            r.raise_for_status()
            template.write_bytes(r.content)
        print(f"✓ Template descargado ({len(r.content)//1024} KB)")
    except Exception as e:
        print(f"✗ Error al descargar template: {e}")
