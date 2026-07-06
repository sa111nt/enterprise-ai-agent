from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.onboarding import OnboardingProgress, OnboardingTask


@tool
async def onboarding_status(employee_id: int, config: RunnableConfig) -> str:
    """Check onboarding task completion status for a specific employee.

    Use this tool when the user asks about their onboarding progress,
    what tasks they still need to complete, or their onboarding checklist.
    Requires the numeric employee_id.
    """
    async with AsyncSessionLocal() as session:
        employee = await session.get(Employee, employee_id)
        if employee is None:
            return f"Employee with id={employee_id} not found."

        caller_id = config.get("configurable", {}).get("employee_id")
        caller_role = config.get("configurable", {}).get("employee_role")

        if caller_role != "admin" and caller_id != employee.id:
            return "You do not have permission to view onboarding status for this employee."

        stmt = (
            select(OnboardingTask, OnboardingProgress)
            .outerjoin(
                OnboardingProgress,
                (OnboardingProgress.task_id == OnboardingTask.id)
                & (OnboardingProgress.employee_id == employee_id),
            )
            .order_by(OnboardingTask.order)
        )
        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            return "No onboarding tasks defined in the system."

        lines = [f"Onboarding status for {employee.first_name} {employee.last_name}:\n"]

        completed = 0
        for task, progress in rows:
            status = progress.status.value if progress else "pending"
            marker = "[DONE]" if status == "completed" else "[PENDING]"
            deadline = f"(deadline: {task.deadline_days} days from hire)"
            lines.append(f"{marker} {task.title} — {status} {deadline}")
            if status == "completed":
                completed += 1

        lines.append(f"\nProgress: {completed}/{len(rows)} tasks completed")
        return "\n".join(lines)
