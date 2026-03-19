"""models/electrical_test.py"""
import uuid
from sqlalchemy import String, SmallInteger, Boolean, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class CheckType(str, enum.Enum):
    no_continuity = "no_continuity"
    continuity    = "continuity"
    resistance    = "resistance"


class ElectricalTestCatalog(Base):
    __tablename__ = "electrical_tests_catalog"

    id:               Mapped[uuid.UUID]     = mapped_column(primary_key=True, default=uuid.uuid4)
    code:             Mapped[str]           = mapped_column(String(20), unique=True, nullable=False)
    sort_order:       Mapped[int]           = mapped_column(SmallInteger, nullable=False)
    section_num:      Mapped[int]           = mapped_column(SmallInteger, nullable=False)
    section_title:    Mapped[str]           = mapped_column(String(120), nullable=False)
    sub_code:         Mapped[str]           = mapped_column(String(20), nullable=False)
    sub_title:        Mapped[str]           = mapped_column(String(200), nullable=False)
    check_type:       Mapped[CheckType]     = mapped_column(SAEnum(CheckType), nullable=False)
    terminal_pos:     Mapped[str | None]    = mapped_column(String(10))
    terminal_neg:     Mapped[str | None]    = mapped_column(String(10))
    voltage_source:   Mapped[str | None]    = mapped_column(String(20))
    expected_result:  Mapped[str | None]    = mapped_column(String(80))
    step_description: Mapped[str | None]    = mapped_column(Text)
    pdf_page:         Mapped[int]           = mapped_column(SmallInteger, nullable=False)
    pdf_position:     Mapped[str]           = mapped_column(String(10), nullable=False)  # left|right|bottom
    has_design_req:   Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    design_req_text:  Mapped[str | None]    = mapped_column(String(100))
    is_active:        Mapped[bool]          = mapped_column(Boolean, default=True, nullable=False)

    results: Mapped[list["TestResult"]] = relationship("TestResult", back_populates="catalog", lazy="noload")
