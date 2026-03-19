"""models/audit_log.py"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class ActionEnum(str, enum.Enum):
    created        = "created"
    updated        = "updated"
    deleted        = "deleted"
    pdf_generated  = "pdf_generated"
    status_changed = "status_changed"


class ReportAuditLog(Base):
    __tablename__ = "report_audit_log"

    id:               Mapped[uuid.UUID]        = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id:        Mapped[uuid.UUID]        = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    action:           Mapped[ActionEnum]       = mapped_column(SAEnum(ActionEnum), nullable=False)
    changed_by_id:    Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_by_name:  Mapped[str | None]       = mapped_column(String(120))
    field_name:       Mapped[str | None]       = mapped_column(String(80))
    old_value:        Mapped[str | None]       = mapped_column(Text)
    new_value:        Mapped[str | None]       = mapped_column(Text)
    extra_data:       Mapped[dict | None]      = mapped_column(JSONB)
    created_at:       Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped["Report"] = relationship("Report", back_populates="audit_logs")
