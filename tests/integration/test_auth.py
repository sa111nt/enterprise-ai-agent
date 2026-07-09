import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "newpass123",
                "first_name": "New",
                "last_name": "Employee",
                "position": "Intern",
                "hire_date": "2024-06-01",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["first_name"] == "New"
        assert "id" in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_employee):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_employee.email,
                "password": "testpass123",
                "first_name": "Dup",
                "last_name": "User",
                "position": "Tester",
                "hire_date": "2024-01-01",
            },
        )
        assert resp.status_code == 409

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-valid",
                "password": "testpass123",
                "first_name": "Bad",
                "last_name": "Email",
                "position": "Tester",
                "hire_date": "2024-01-01",
            },
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient, test_employee):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": test_employee.email, "password": "testpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_employee):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": test_employee.email, "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "pass"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRefresh:
    async def test_refresh_success(self, client: AsyncClient, test_employee):
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": test_employee.email, "password": "testpass123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.jwt.token"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestMe:
    async def test_me_authenticated(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["first_name"] == "Test"

    async def test_me_no_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert resp.status_code == 401
