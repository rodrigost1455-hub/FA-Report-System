"""
api/routes/catalog.py
GET /api/tests-catalog           — Lista las 20 pruebas eléctricas en orden
GET /api/tests-catalog/{code}    — Obtiene una prueba por código (ej: "5.1.1")
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database          import get_db
from app.models.electrical_test import ElectricalTestCatalog
from app.schemas.test_result    import ElectricalTestCatalogResponse
from app.services.test_service  import test_service

router = APIRouter()


@router.get(
    "",
    response_model=list[ElectricalTestCatalogResponse],
    summary="Catálogo de pruebas eléctricas (secuencia fija)",
    description="""
    Devuelve las 20 pruebas eléctricas en el orden exacto de ejecución (5.1.1 → 5.4.5).
    Este catálogo es de solo lectura — define la secuencia fija del documento FA.

    Cada prueba incluye:
    - Código (`5.1.1`), tipo de verificación, terminales, fuente de voltaje
    - Instrucciones paso a paso (`step_description`)
    - Página del PDF donde aparece y posición (left / right / bottom)
    """,
)
async def get_catalog(db: AsyncSession = Depends(get_db)) -> list[ElectricalTestCatalogResponse]:
    tests = await test_service.get_catalog(db)
    return [ElectricalTestCatalogResponse.model_validate(t) for t in tests]


@router.get(
    "/{code}",
    response_model=ElectricalTestCatalogResponse,
    summary="Obtener prueba por código",
)
async def get_catalog_item(code: str, db: AsyncSession = Depends(get_db)) -> ElectricalTestCatalogResponse:
    test = await db.scalar(
        select(ElectricalTestCatalog).where(ElectricalTestCatalog.code == code)
    )
    if not test:
        raise HTTPException(status_code=404, detail=f"Prueba '{code}' no encontrada.")
    return ElectricalTestCatalogResponse.model_validate(test)
