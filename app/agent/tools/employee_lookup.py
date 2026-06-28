from sqlalchemy import or_, select
from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee


@tool
async def employee_lookup(identifier: str) -> str:
    """Look up an employee's profile by their numeric ID or full/partial name.

    Use this tool when the user asks about their own profile, their manager,
    hire date, position, department, or any personal employment data.
    The identifier can be a numeric employee ID (e.g. "5") or a name (e.g. "John").
    """
    async with AsyncSessionLocal() as session:
        # Search by numeric ID
        if identifier.strip().isdigit():
            employee = await session.get(Employee, int(identifier))
        else:
            # Search by name
            pattern = f"%{identifier}%"
            stmt = select(Employee).where(
                or_(
                    Employee.first_name.ilike(pattern),
                    Employee.last_name.ilike(pattern),
                )
            )
            result = await session.execute(stmt)
            employee = result.scalar_one_or_none()

        if employee is None:
            return f"Employee '{identifier}' not found."

        dept_name = employee.department.name if employee.department else "N/A"
        manager_name = (
            f"{employee.manager.first_name} {employee.manager.last_name}"
            if employee.manager
            else "N/A"
        )

        return (
            f"Employee ID: {employee.id}\n"
            f"Name: {employee.first_name} {employee.last_name}\n"
            f"Email: {employee.email}\n"
            f"Position: {employee.position}\n"
            f"Department: {dept_name}\n"
            f"Manager: {manager_name}\n"
            f"Hire Date: {employee.hire_date}\n"
            f"Status: {'Active' if employee.is_active else 'Inactive'}"
        )
