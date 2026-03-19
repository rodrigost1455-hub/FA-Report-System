"""models/report_image.py"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, SmallInteger, Boolean, Text, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class ImageSection(str, enum.Enum):
    visual_inspection  = "visual_inspection"
    terminal_inspection = "terminal_inspection"
    eol                = "eol"
    electrical_test    = "electrical_test"


class ReportImage(Base):
    __tablename__ = "report_images"

    id:              Mapped[uuid.UUID]          = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id:       Mapped[uuid.UUID]          = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    section:         Mapped[ImageSection]       = mapped_column(SAEnum(ImageSection), nullable=False)
    slot_key:        Mapped[str | None]         = mapped_column(String(60))
    sort_order:      Mapped[int]                = mapped_column(SmallInteger, default=0, nullable=False)
    file_url:        Mapped[str]                = mapped_column(Text, nullable=False)
    file_name:       Mapped[str | None]         = mapped_column(String(255))
    mime_type:       Mapped[str]                = mapped_column(String(50), default="image/jpeg")
    file_size_bytes: Mapped[int | None]         = mapped_column(Integer)
    orig_width:      Mapped[int | None]         = mapped_column(Integer)
    orig_height:     Mapped[int | None]         = mapped_column(Integer)
    proc_width:      Mapped[int | None]         = mapped_column(Integer)
    proc_height:     Mapped[int | None]         = mapped_column(Integer)
    is_reused:       Mapped[bool]               = mapped_column(Boolean, default=False, nullable=False)
    source_image_id: Mapped[uuid.UUID | None]   = mapped_column(ForeignKey("report_images.id", ondelete="SET NULL"))
    caption:         Mapped[str | None]         = mapped_column(String(255))
    uploaded_at:     Mapped[datetime]           = mapped_column(DateTime(timezone=True), server_default=func.now())

    report:       Mapped["Report"]              = relationship("Report", back_populates="images")
    source_image: Mapped["ReportImage | None"]  = relationship("ReportImage", remote_side="ReportImage.id", foreign_keys=[source_image_id])
