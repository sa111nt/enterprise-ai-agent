import logging
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.qdrant import get_qdrant_client
from app.models.document import Document
from app.rag.ingestion import ingest_pdf
from app.schemas.document import DocumentRead, UploadResponse

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPE = "application/pdf"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
PDF_MAGIC_BYTES = b"%PDF-"


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upload(self, file: UploadFile) -> UploadResponse:
        if file.content_type != ALLOWED_CONTENT_TYPE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only PDF files are accepted, got '{file.content_type}'",
            )

        content = await file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large. Maximum size is 10 MB",
            )

        if not content.startswith(PDF_MAGIC_BYTES):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file: missing %PDF- header magic bytes",
            )

        filename = file.filename or "untitled.pdf"
        title = Path(filename).stem.replace("_", " ").replace("-", " ").title()

        # Save to temp file for PyPDFLoader
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Create DB record
            document = Document(filename=filename, title=title, chunk_count=0)
            self.session.add(document)
            await self.session.flush()
            await self.session.refresh(document)

            # Run ingestion pipeline
            try:
                client = get_qdrant_client()
                chunk_count = await ingest_pdf(
                    file_path=tmp_path,
                    document_id=document.id,
                    document_title=title,
                    client=client,
                    collection_name=settings.qdrant_collection,
                )
            except Exception as exc:
                logger.error(
                    "Failed to ingest document '%s' (id=%d): %s",
                    filename,
                    document.id,
                    exc,
                    exc_info=True,
                )
                await self.session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process and index document: {exc}",
                ) from exc

            # Update chunk count
            document.chunk_count = chunk_count
            await self.session.flush()
            await self.session.refresh(document)

            logger.info(
                "Document '%s' uploaded: id=%d, chunks=%d",
                filename,
                document.id,
                chunk_count,
            )

            return UploadResponse(
                document_id=document.id,
                filename=filename,
                title=title,
                chunk_count=chunk_count,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def list_documents(self) -> list[DocumentRead]:
        stmt = select(Document).order_by(Document.created_at.desc())
        result = await self.session.execute(stmt)
        documents = result.scalars().all()
        return [DocumentRead.model_validate(doc) for doc in documents]
