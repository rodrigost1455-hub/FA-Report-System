"""models/report.py"""
import uuid
from datetime import date, datetime
from sqlalchemy import String, Boolean, Text, Date, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class ReportStatus(str, enum.Enum):
    draft       = "draft"
    in_progress = "in_progress"
    final       = "final"
    archived    = "archived"


class Report(Base):
    __tablename__ = "reports"

    id:                  Mapped[uuid.UUID]     = mapped_column(primary_key=True, default=uuid.uuid4)

    # Identificación
    report_number:       Mapped[str]           = mapped_column(String(20), unique=True, nullable=False)
    title:               Mapped[str]           = mapped_column(String(120), default="Warranty Plant Return")

    # Fechas
    request_date:        Mapped[date]          = mapped_column(Date, nullable=False)
    completion_date:     Mapped[date]          = mapped_column(Date, nullable=False, server_default=func.current_date())

    # Pieza
    part_name:           Mapped[str]           = mapped_column(String(120), nullable=False)
    part_number:         Mapped[str]           = mapped_column(String(60),  nullable=False)
    yazaki_part_number:  Mapped[str]           = mapped_column(String(60),  nullable=False)

    # Firmas — FK opcionales
    prepared_by_id:      Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_by_id:      Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    requested_by_id:     Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by_id:      Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    # Firmas — texto libre (fallback si no hay FK)
    prepared_by_name:    Mapped[str | None]    = mapped_column(String(120))
    verified_by_name:    Mapped[str | None]    = mapped_column(String(120))
    requested_by_name:   Mapped[str | None]    = mapped_column(String(120))
    approved_by_name:    Mapped[str | None]    = mapped_column(String(120))

    # Lógica NTF
    is_ntf:              Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    reuse_images:        Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    source_report_id:    Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"))

    # Estado y PDF
    status:              Mapped[ReportStatus]  = mapped_column(SAEnum(ReportStatus), default=ReportStatus.draft, nullable=False)
    pdf_url:             Mapped[str | None]    = mapped_column(Text)
    pdf_generated_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes:               Mapped[str | None]    = mapped_column(Text)
    created_by:          Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at:          Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:          Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    prepared_by_user:   Mapped["User | None"]              = relationship("User", foreign_keys=[prepared_by_id],  back_populates="prepared_reports")
    verified_by_user:   Mapped["User | None"]              = relationship("User", foreign_keys=[verified_by_id],  back_populates="verified_reports")
    requested_by_user:  Mapped["User | None"]              = relationship("User", foreign_keys=[requested_by_id], back_populates="requested_reports")
    approved_by_user:   Mapped["User | None"]              = relationship("User", foreign_keys=[approved_by_id],  back_populates="approved_reports")
    images:             Mapped[list["ReportImage"]]        = relationship("ReportImage",        back_populates="report", cascade="all, delete-orphan", lazy="selectin")
    test_results:       Mapped[list["TestResult"]]         = relationship("TestResult",         back_populates="report", cascade="all, delete-orphan", lazy="selectin", order_by="TestResult.catalog_id")
    audit_logs:         Mapped[list["ReportAuditLog"]]     = relationship("ReportAuditLog",     back_populates="report", cascade="all, delete-orphan", lazy="noload")
    source_report:      Mapped["Report | None"]            = relationship("Report", remote_side="Report.id", foreign_keys=[source_report_id])

    # ── Helpers ─────────────────────────────────────────────────────────
    def get_signature(self, role: str) -> str:
        """Devuelve el nombre de firma resolviendo FK → texto libre."""
        mapping = {
            "prepared":  (self.prepared_by_user,  self.prepared_by_name),
            "verified":  (self.verified_by_user,  self.verified_by_name),
            "requested": (self.requested_by_user, self.requested_by_name),
            "approved":  (self.approved_by_user,  self.approved_by_name),
        }
        user_obj, name_str = mapping.get(role, (None, None))
        if user_obj:
            return user_obj.full_name
        return name_str or ""
