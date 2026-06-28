from sqlalchemy import func, select
from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal
from app.models.department import Department
from app.models.employee import Employee


@tool
async def department_info(department_name: str) -> str:
    """Get information about a company department by name.

    Use this tool when the user asks about a specific department,
    its head, number of employees, or description.
    The department_name can be a partial match (e.g. "IT", "Marketing").
    """
    async with AsyncSessionLocal() as session:
        pattern = f"%{department_name}%"
        stmt = select(Department).where(Department.name.ilike(pattern))
        result = await session.execute(stmt)
        department = result.scalar_one_or_none()

        if department is None:
            return f"Department matching '{department_name}' not found."

        count_stmt = (
            select(func.count())
            .select_from(Employee)
            .where(Employee.department_id == department.id)
        )
        emp_count = (await session.execute(count_stmt)).scalar_one()

        head_name = (
            f"{department.head.first_name} {department.head.last_name}"
            if department.head
            else "Not assigned"
        )

        return (
            f"Department: {department.name}\n"
            f"Description: {department.description or 'N/A'}\n"
            f"Head: {head_name}\n"
            f"Number of employees: {emp_count}"
        )
