from unittest.mock import AsyncMock

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

    async def test_upload_rejects_oversized_file(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ):
        oversized_content = b"%PDF-" + b"0" * (10 * 1024 * 1024 + 100)
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.pdf", oversized_content, "application/pdf")},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 413
        assert "File too large" in resp.json()["detail"]

    async def test_upload_rejects_invalid_magic_bytes(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("malicious.pdf", b"NOT_A_REAL_PDF", "application/pdf")},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 400
        assert "magic bytes" in resp.json()["detail"]

    async def test_upload_success(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            "app.services.document_service.ingest_pdf",
            AsyncMock(return_value=3),
        )
        resp = await client.post(
            "/api/v1/documents/upload",
            files={
                "file": ("handbook.pdf", b"%PDF-1.4 test content", "application/pdf")
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "handbook.pdf"
        assert data["title"] == "Handbook"
        assert data["chunk_count"] == 3

        # Verify listed in documents
        list_resp = await client.get("/api/v1/documents/", headers=admin_auth_headers)
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "handbook.pdf"
        assert docs[0]["chunk_count"] == 3

    async def test_upload_ingestion_failure_rollback(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            "app.services.document_service.ingest_pdf",
            AsyncMock(side_effect=RuntimeError("Qdrant index connection failure")),
        )
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("broken.pdf", b"%PDF-1.4 test content", "application/pdf")},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 500
        assert "Failed to process and index document" in resp.json()["detail"]

        # Verify database was rolled back: no documents exist
        list_resp = await client.get("/api/v1/documents/", headers=admin_auth_headers)
        assert list_resp.status_code == 200
        assert list_resp.json() == []


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
