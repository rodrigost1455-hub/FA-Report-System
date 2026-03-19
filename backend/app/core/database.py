"""
core/database.py
Async SQLAlchemy engine + session factory para FastAPI.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,           # True para ver SQL en logs de desarrollo
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # Valida la conexión antes de usar
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""
    pass


# ── Dependency ────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """FastAPI dependency: yield de sesión async, con rollback automático en error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
