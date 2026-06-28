from sqlalchemy import or_, select
from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal
from app.models.contact import Contact


@tool
async def company_contacts(query: str) -> str:
    """Search the company contacts directory by name, role, or department.

    Use this tool when the user asks for contact information,
    phone numbers, emails, or office locations of company staff.
    """
    async with AsyncSessionLocal() as session:
        pattern = f"%{query}%"
        stmt = (
            select(Contact)
            .where(
                or_(
                    Contact.name.ilike(pattern),
                    Contact.role.ilike(pattern),
                )
            )
            .limit(10)
        )
        result = await session.execute(stmt)
        contacts = result.scalars().all()

        if not contacts:
            return f"No contacts found matching '{query}'."

        lines = []
        for c in contacts:
            dept_name = c.department.name if c.department else "N/A"
            entry = (
                f"Name: {c.name}\n"
                f"  Role: {c.role}\n"
                f"  Email: {c.email}\n"
                f"  Phone: {c.phone or 'N/A'}\n"
                f"  Office: {c.office or 'N/A'}\n"
                f"  Department: {dept_name}"
            )
            lines.append(entry)

        return "\n\n".join(lines)
