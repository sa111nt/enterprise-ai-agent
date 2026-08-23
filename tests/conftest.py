import datetime
import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.database import get_async_db
from app.core.redis import close_redis_pool, get_redis_client
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.base import Base
from app.models.employee import Employee, EmployeeRole

PG_ROOT_URL = settings.database_url
PG_TEST_URL = os.getenv(
    "TEST_DATABASE_URL",
    settings.database_url.rsplit("/", 1)[0] + "/agent_test",
)

_test_db_ready: bool = False


@pytest_asyncio.fixture(scope="function")
async def pg_session_factory():
    global _test_db_ready
    engine = create_async_engine(PG_TEST_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    if not _test_db_ready:
        root_engine = create_async_engine(PG_ROOT_URL, isolation_level="AUTOCOMMIT")
        async with root_engine.connect() as conn:
            row = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'agent_test'")
            )
            if not row.fetchone():
                await conn.execute(text("CREATE DATABASE agent_test"))
        await root_engine.dispose()
        _test_db_ready = True

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(pg_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with pg_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(pg_session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_employee(db_session: AsyncSession) -> Employee:
    employee = Employee(
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        position="QA Engineer",
        hire_date=datetime.date(2024, 1, 1),
        role=EmployeeRole.employee,
    )
    db_session.add(employee)
    await db_session.commit()
    await db_session.refresh(employee)
    return employee


@pytest_asyncio.fixture(scope="function")
async def admin_employee(db_session: AsyncSession) -> Employee:
    employee = Employee(
        first_name="Admin",
        last_name="Tester",
        email="admin@example.com",
        password_hash=hash_password("adminpass123"),
        position="System Administrator",
        hire_date=datetime.date(2023, 1, 1),
        role=EmployeeRole.admin,
    )
    db_session.add(employee)
    await db_session.commit()
    await db_session.refresh(employee)
    return employee


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_employee: Employee) -> dict[str, str]:
    token = create_access_token({"sub": test_employee.email})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def admin_auth_headers(admin_employee: Employee) -> dict[str, str]:
    token = create_access_token({"sub": admin_employee.email})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_redis():
    client = get_redis_client()
    try:
        await client.flushdb()
    except Exception:
        pass
    yield
    try:
        await client.flushdb()
        await close_redis_pool()
    except Exception:
        pass
