import enum

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class EmployeeRole(str, enum.Enum):
    employee = "employee"
    admin = "admin"


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    position: Mapped[str] = mapped_column(String(150), nullable=False)
    hire_date: Mapped[Date] = mapped_column(Date, nullable=False)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[EmployeeRole] = mapped_column(
        default=EmployeeRole.employee,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"),
        nullable=True,
    )
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )

    department = relationship(
        "Department",
        back_populates="employees",
        foreign_keys=[department_id],
        lazy="selectin",
    )
    manager = relationship(
        "Employee",
        remote_side="Employee.id",
        foreign_keys=[manager_id],
        lazy="selectin",
    )
    onboarding_progress = relationship(
        "OnboardingProgress",
        back_populates="employee",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.id} email={self.email!r}>"
