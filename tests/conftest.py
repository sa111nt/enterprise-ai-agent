import datetime
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_async_db
from app.core.redis import close_redis_pool
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.base import Base
from app.models.employee import Employee, EmployeeRole

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=pool.StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

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


class FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def exists(self, *keys: str) -> int:
        return sum(1 for k in keys if k in self._data)

    async def setex(self, key: str, time: int, value: Any) -> bool:
        self._data[key] = value
        return True

    async def incr(self, key: str) -> int:
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = val
        return val

    async def expire(self, key: str, time: int) -> bool:
        return True

    async def get(self, key: str) -> Any:
        return self._data.get(key)

    async def aclose(self) -> None:
        pass


@pytest_asyncio.fixture(scope="function", autouse=True)
def mock_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: fake)
    monkeypatch.setattr("app.api.dependencies.get_redis_client", lambda: fake)
    monkeypatch.setattr("app.services.auth_service.get_redis_client", lambda: fake)
    monkeypatch.setattr("app.services.agent_service.get_redis_client", lambda: fake)
    return fake


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_redis():
    yield
    try:
        await close_redis_pool()
    except Exception:
        pass
