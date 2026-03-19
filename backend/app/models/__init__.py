"""
models/__init__.py
Exporta todos los modelos ORM para que Alembic los detecte automáticamente.
"""
from app.models.user             import User
from app.models.report           import Report
from app.models.report_image     import ReportImage
from app.models.electrical_test  import ElectricalTestCatalog
from app.models.test_result      import TestResult
from app.models.audit_log        import ReportAuditLog

__all__ = [
    "User", "Report", "ReportImage",
    "ElectricalTestCatalog", "TestResult", "ReportAuditLog",
]
