from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.employee import Employee


class Thread(Base, TimestampMixin):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)

    employee: Mapped["Employee"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<Thread id={self.id} employee_id={self.employee_id}>"
