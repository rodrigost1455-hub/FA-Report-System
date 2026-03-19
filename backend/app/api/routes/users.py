"""
api/routes/users.py
GET  /api/users        — Listar usuarios activos (para los dropdowns de firmas)
POST /api/users        — Crear usuario
GET  /api/users/{id}   — Obtener usuario
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, EmailStr

from app.core.database import get_db
from app.models.user   import User

router = APIRouter()


# ── Schemas locales ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    full_name:   str            = Field(..., min_length=2, max_length=120)
    employee_id: Optional[str]  = Field(None, max_length=30)
    role:        Optional[str]  = Field(None, max_length=60)
    department:  Optional[str]  = Field(None, max_length=80)
    email:       Optional[str]  = Field(None, max_length=120)


class UserResponse(BaseModel):
    id:          uuid.UUID
    full_name:   str
    employee_id: Optional[str]
    role:        Optional[str]
    department:  Optional[str]
    email:       Optional[str]
    is_active:   bool

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[UserResponse],
    summary="Listar usuarios activos",
    description="Devuelve la lista de usuarios para los dropdowns de firmas en el wizard.",
)
async def list_users(
    search: Optional[str] = Query(default=None, description="Busca por nombre o rol"),
    db:     AsyncSession  = Depends(get_db),
) -> list[UserResponse]:
    query = select(User).where(User.is_active == True).order_by(User.full_name)
    if search:
        query = query.where(User.full_name.ilike(f"%{search}%"))
    rows = (await db.execute(query)).scalars().all()
    return [UserResponse.model_validate(u) for u in rows]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
)
async def create_user(
    payload: UserCreate,
    db:      AsyncSession = Depends(get_db),
) -> UserResponse:
    user = User(**payload.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Obtener usuario por ID",
)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return UserResponse.model_validate(user)
