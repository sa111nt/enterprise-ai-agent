"""ORM models package — import all models here for Alembic autogenerate."""

from app.models.base import Base, TimestampMixin
from app.models.contact import Contact
from app.models.department import Department
from app.models.document import Document
from app.models.employee import Employee, EmployeeRole
from app.models.onboarding import OnboardingProgress, OnboardingTask, ProgressStatus

__all__ = [
    "Base",
    "TimestampMixin",
    "Contact",
    "Department",
    "Document",
    "Employee",
    "EmployeeRole",
    "OnboardingProgress",
    "OnboardingTask",
    "ProgressStatus",
]
