from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Department(TimestampMixin, Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Head of department (nullable to break circular FK with employees)
    head_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", use_alter=True, name="fk_department_head"),
        nullable=True,
    )

    head = relationship(
        "Employee",
        foreign_keys=[head_id],
        lazy="selectin",
    )
    employees = relationship(
        "Employee",
        back_populates="department",
        foreign_keys="Employee.department_id",
        lazy="selectin",
    )
    contacts = relationship(
        "Contact",
        back_populates="department",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name!r}>"
