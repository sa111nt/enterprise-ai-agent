import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestDocumentUpload:
    async def test_upload_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", b"fake-pdf-content", "application/pdf")},
        )
        assert resp.status_code == 401

    async def test_upload_forbidden_for_regular_employee(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", b"fake-pdf-content", "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin privileges required"

    async def test_upload_rejects_non_pdf(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"plain text", "text/plain")},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]


@pytest.mark.asyncio
class TestDocumentList:
    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/documents/")
        assert resp.status_code == 401

    async def test_list_empty(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        resp = await client.get("/api/v1/documents/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []
