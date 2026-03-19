"""models/user.py"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id:          Mapped[uuid.UUID]  = mapped_column(primary_key=True, default=uuid.uuid4)
    full_name:   Mapped[str]        = mapped_column(String(120), nullable=False)
    employee_id: Mapped[str | None] = mapped_column(String(30),  unique=True)
    role:        Mapped[str | None] = mapped_column(String(60))
    department:  Mapped[str | None] = mapped_column(String(80))
    email:       Mapped[str | None] = mapped_column(String(120), unique=True)
    is_active:   Mapped[bool]       = mapped_column(Boolean, default=True, nullable=False)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships (back-refs desde Report)
    prepared_reports:   Mapped[list["Report"]] = relationship("Report", foreign_keys="Report.prepared_by_id",  back_populates="prepared_by_user")
    verified_reports:   Mapped[list["Report"]] = relationship("Report", foreign_keys="Report.verified_by_id",  back_populates="verified_by_user")
    requested_reports:  Mapped[list["Report"]] = relationship("Report", foreign_keys="Report.requested_by_id", back_populates="requested_by_user")
    approved_reports:   Mapped[list["Report"]] = relationship("Report", foreign_keys="Report.approved_by_id",  back_populates="approved_by_user")
