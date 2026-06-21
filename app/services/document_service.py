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


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upload(self, file: UploadFile) -> UploadResponse:
        if file.content_type != ALLOWED_CONTENT_TYPE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only PDF files are accepted, got '{file.content_type}'",
            )

        filename = file.filename or "untitled.pdf"
        title = Path(filename).stem.replace("_", " ").replace("-", " ").title()

        # Save to temp file for PyPDFLoader
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Create DB record
            document = Document(filename=filename, title=title, chunk_count=0)
            self.session.add(document)
            await self.session.flush()
            await self.session.refresh(document)

            # Run ingestion pipeline
            client = get_qdrant_client()
            chunk_count = await ingest_pdf(
                file_path=tmp_path,
                document_id=document.id,
                document_title=title,
                client=client,
                collection_name=settings.qdrant_collection,
            )

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
