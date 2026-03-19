"""
tests/conftest.py
Fixtures compartidos para todos los tests.
Usa una base de datos SQLite en memoria para aislar los tests.
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base, get_db
from main import app

# ── Engine de test (SQLite en memoria) ───────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession,
    expire_on_commit=False, autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Crea todas las tablas antes de correr los tests."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Sesión de DB aislada por test — hace rollback al finalizar."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """Cliente HTTP que usa la sesión de test (no la de producción)."""
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ── Datos de prueba reutilizables ─────────────────────────────────────────────

SAMPLE_REPORT_PAYLOAD = {
    "report_number":      "TEST-001",
    "title":              "Warranty Plant Return",
    "request_date":       "2025-06-24",
    "part_name":          "PHEV BEC GEN 4",
    "part_number":        "L1M8 10C666 GF",
    "yazaki_part_number": "7370-2573-8W",
    "prepared_by_name":   "Rodrigo Santana",
    "verified_by_name":   "Juan Barraza",
    "requested_by_name":  "Chandni Bhavsar",
    "approved_by_name":   "Horacio Martinez",
    "is_ntf":             False,
}
