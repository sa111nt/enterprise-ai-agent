import logging
import uuid

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


async def ingest_pdf(
    file_path: str,
    document_id: int,
    document_title: str,
    client: AsyncQdrantClient,
    collection_name: str,
) -> int:
    # 1. Load PDF pages
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    logger.info(
        "Loaded %d pages from '%s' (document_id=%d)",
        len(pages),
        file_path,
        document_id,
    )

    # 2. Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages)

    if not chunks:
        logger.warning("No text chunks extracted from document_id=%d", document_id)
        return 0

    # 3. Generate embeddings
    embeddings = get_embeddings()
    texts = [chunk.page_content for chunk in chunks]
    vectors = await embeddings.aembed_documents(texts)

    # 4. Build Qdrant points with metadata
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "document_id": document_id,
                "document_title": document_title,
                "text": text,
                "page": chunk.metadata.get("page", 0),
                "chunk_index": i,
            },
        )
        for i, (chunk, text, vector) in enumerate(zip(chunks, texts, vectors))
    ]

    # 5. Upsert into Qdrant
    await client.upsert(collection_name=collection_name, points=points)
    logger.info(
        "Stored %d chunks in Qdrant collection '%s' for document_id=%d",
        len(points),
        collection_name,
        document_id,
    )

    return len(points)
