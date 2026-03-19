"""models/test_result.py"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class TestResultEnum(str, enum.Enum):
    OK      = "OK"
    NG      = "NG"
    pending = "pending"


class TestResult(Base):
    __tablename__ = "test_results"

    id:               Mapped[uuid.UUID]         = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id:        Mapped[uuid.UUID]         = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    catalog_id:       Mapped[uuid.UUID]         = mapped_column(ForeignKey("electrical_tests_catalog.id"), nullable=False)
    result:           Mapped[TestResultEnum]    = mapped_column(SAEnum(TestResultEnum), default=TestResultEnum.pending, nullable=False)
    measurement_val:  Mapped[str | None]        = mapped_column(String(40))
    is_ng_override:   Mapped[bool]              = mapped_column(Boolean, default=False, nullable=False)
    image_left_id:    Mapped[uuid.UUID | None]  = mapped_column(ForeignKey("report_images.id", ondelete="SET NULL"))
    image_right_id:   Mapped[uuid.UUID | None]  = mapped_column(ForeignKey("report_images.id", ondelete="SET NULL"))
    is_reused:        Mapped[bool]              = mapped_column(Boolean, default=False, nullable=False)
    source_result_id: Mapped[uuid.UUID | None]  = mapped_column(ForeignKey("test_results.id", ondelete="SET NULL"))
    observation_text: Mapped[str]               = mapped_column(Text, default="No anomalies were observed in the manual test.")
    recorded_at:      Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:       Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    report:        Mapped["Report"]                 = relationship("Report",                back_populates="test_results")
    catalog:       Mapped["ElectricalTestCatalog"]  = relationship("ElectricalTestCatalog", back_populates="results", lazy="selectin")
    image_left:    Mapped["ReportImage | None"]     = relationship("ReportImage",           foreign_keys=[image_left_id],  lazy="selectin")
    image_right:   Mapped["ReportImage | None"]     = relationship("ReportImage",           foreign_keys=[image_right_id], lazy="selectin")
    source_result: Mapped["TestResult | None"]      = relationship("TestResult",            remote_side="TestResult.id", foreign_keys=[source_result_id])
