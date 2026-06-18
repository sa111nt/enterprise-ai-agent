import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OnboardingTask(TimestampMixin, Base):
    """Template task that every new employee must complete."""

    __tablename__ = "onboarding_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadline_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Number of days from hire_date to complete this task",
    )

    progress_entries = relationship(
        "OnboardingProgress",
        back_populates="task",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<OnboardingTask id={self.id} title={self.title!r}>"


class ProgressStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"


class OnboardingProgress(TimestampMixin, Base):
    """Tracks individual employee's progress on an onboarding task."""

    __tablename__ = "onboarding_progress"
    __table_args__ = (
        UniqueConstraint("employee_id", "task_id", name="uq_employee_task"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("onboarding_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ProgressStatus] = mapped_column(
        default=ProgressStatus.pending,
        nullable=False,
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    employee = relationship(
        "Employee",
        back_populates="onboarding_progress",
    )
    task = relationship(
        "OnboardingTask",
        back_populates="progress_entries",
    )

    def __repr__(self) -> str:
        return (
            f"<OnboardingProgress employee_id={self.employee_id} "
            f"task_id={self.task_id} status={self.status.value!r}>"
        )
