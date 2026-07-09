"""Seed script — populate database with test data for development."""

import asyncio
import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.contact import Contact
from app.models.department import Department
from app.models.employee import Employee, EmployeeRole
from app.models.onboarding import OnboardingProgress, OnboardingTask, ProgressStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_departments(session: AsyncSession) -> dict[str, Department]:
    departments_data = [
        {
            "name": "Engineering",
            "description": "Software development and infrastructure",
        },
        {
            "name": "Human Resources",
            "description": "People operations, hiring, and employee relations",
        },
        {
            "name": "Marketing",
            "description": "Brand management, campaigns, and communications",
        },
        {
            "name": "Finance",
            "description": "Accounting, budgeting, and financial planning",
        },
    ]

    departments = {}
    for data in departments_data:
        stmt = select(Department).where(Department.name == data["name"])
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            departments[data["name"]] = existing
            continue
        dept = Department(**data)
        session.add(dept)
        await session.flush()
        await session.refresh(dept)
        departments[data["name"]] = dept
    return departments


async def seed_employees(
    session: AsyncSession,
    departments: dict[str, Department],
) -> dict[str, Employee]:
    employees_data = [
        {
            "first_name": "Admin",
            "last_name": "User",
            "email": "admin@company.com",
            "password_hash": hash_password("admin123"),
            "position": "System Administrator",
            "hire_date": datetime.date(2023, 1, 15),
            "role": EmployeeRole.admin,
            "department_id": departments["Engineering"].id,
        },
        {
            "first_name": "Alice",
            "last_name": "Johnson",
            "email": "alice@company.com",
            "password_hash": hash_password("password123"),
            "position": "Senior Software Engineer",
            "hire_date": datetime.date(2023, 3, 1),
            "department_id": departments["Engineering"].id,
        },
        {
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@company.com",
            "password_hash": hash_password("password123"),
            "position": "Marketing Manager",
            "hire_date": datetime.date(2024, 6, 15),
            "department_id": departments["Marketing"].id,
        },
        {
            "first_name": "Carol",
            "last_name": "Williams",
            "email": "carol@company.com",
            "password_hash": hash_password("password123"),
            "position": "HR Specialist",
            "hire_date": datetime.date(2024, 9, 1),
            "department_id": departments["Human Resources"].id,
        },
    ]

    employees = {}
    for data in employees_data:
        stmt = select(Employee).where(Employee.email == data["email"])
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            employees[data["email"]] = existing
            continue
        emp = Employee(**data)
        session.add(emp)
        await session.flush()
        await session.refresh(emp)
        employees[data["email"]] = emp

    # Set managers (Alice reports to Admin, Bob and Carol report to Alice)
    admin = employees["admin@company.com"]
    alice = employees["alice@company.com"]
    alice.manager_id = admin.id
    employees["bob@company.com"].manager_id = alice.id
    employees["carol@company.com"].manager_id = alice.id

    # Set department heads
    departments["Engineering"].head_id = admin.id
    departments["Human Resources"].head_id = employees["carol@company.com"].id
    departments["Marketing"].head_id = employees["bob@company.com"].id

    await session.flush()
    return employees


async def seed_onboarding_tasks(session: AsyncSession) -> list[OnboardingTask]:
    tasks_data = [
        {
            "title": "Complete security training",
            "description": "Pass the online security awareness course",
            "order": 1,
            "deadline_days": 7,
        },
        {
            "title": "Set up development environment",
            "description": "Install required tools, configure VPN access",
            "order": 2,
            "deadline_days": 3,
        },
        {
            "title": "Read employee handbook",
            "description": "Review company policies and code of conduct",
            "order": 3,
            "deadline_days": 14,
        },
        {
            "title": "Meet your team",
            "description": "Schedule introductory meetings with team members",
            "order": 4,
            "deadline_days": 7,
        },
        {
            "title": "First 1-on-1 with manager",
            "description": "Schedule and complete your first check-in with your direct manager",
            "order": 5,
            "deadline_days": 14,
        },
    ]

    tasks = []
    for data in tasks_data:
        stmt = select(OnboardingTask).where(OnboardingTask.title == data["title"])
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            tasks.append(existing)
            continue
        task = OnboardingTask(**data)
        session.add(task)
        await session.flush()
        await session.refresh(task)
        tasks.append(task)
    return tasks


async def seed_onboarding_progress(
    session: AsyncSession,
    employees: dict[str, Employee],
    tasks: list[OnboardingTask],
) -> None:
    # Bob (new employee) — completed 2 of 5 tasks
    bob = employees["bob@company.com"]
    for i, task in enumerate(tasks):
        stmt = select(OnboardingProgress).where(
            OnboardingProgress.employee_id == bob.id,
            OnboardingProgress.task_id == task.id,
        )
        if (await session.execute(stmt)).scalar_one_or_none():
            continue
        progress = OnboardingProgress(
            employee_id=bob.id,
            task_id=task.id,
            status=ProgressStatus.completed if i < 2 else ProgressStatus.pending,
            completed_at=datetime.datetime.now(datetime.UTC) if i < 2 else None,
        )
        session.add(progress)


async def seed_contacts(
    session: AsyncSession,
    departments: dict[str, Department],
) -> None:
    contacts_data = [
        {
            "name": "IT Help Desk",
            "role": "Technical Support",
            "email": "helpdesk@company.com",
            "phone": "+1-555-0100",
            "office": "Building A, Room 101",
            "department_id": departments["Engineering"].id,
        },
        {
            "name": "Jane Martinez",
            "role": "Payroll Specialist",
            "email": "jane.martinez@company.com",
            "phone": "+1-555-0201",
            "office": "Building B, Room 305",
            "department_id": departments["Finance"].id,
        },
        {
            "name": "Security Office",
            "role": "Physical Security",
            "email": "security@company.com",
            "phone": "+1-555-0300",
            "office": "Building A, Lobby",
        },
        {
            "name": "Michael Brown",
            "role": "Recruitment Lead",
            "email": "michael.brown@company.com",
            "phone": "+1-555-0401",
            "office": "Building C, Room 210",
            "department_id": departments["Human Resources"].id,
        },
    ]

    for data in contacts_data:
        stmt = select(Contact).where(Contact.email == data["email"])
        if (await session.execute(stmt)).scalar_one_or_none():
            continue
        session.add(Contact(**data))


async def main() -> None:
    async with AsyncSessionLocal() as session:
        logger.info("Seeding departments...")
        departments = await seed_departments(session)

        logger.info("Seeding employees...")
        employees = await seed_employees(session, departments)

        logger.info("Seeding onboarding tasks...")
        tasks = await seed_onboarding_tasks(session)

        logger.info("Seeding onboarding progress...")
        await seed_onboarding_progress(session, employees, tasks)

        logger.info("Seeding contacts...")
        await seed_contacts(session, departments)

        await session.commit()
        logger.info("Seed completed successfully")
        logger.info("Admin login: admin@company.com / admin123")


if __name__ == "__main__":
    asyncio.run(main())
