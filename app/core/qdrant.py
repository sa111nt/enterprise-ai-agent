import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_VECTOR_SIZE = 1536  # text-embedding-3-small

qdrant_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    global qdrant_client
    if qdrant_client is None:
        qdrant_client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        logger.info(
            "Qdrant client created (host=%s, port=%s)",
            settings.qdrant_host,
            settings.qdrant_port,
        )
    return qdrant_client


async def close_qdrant_client() -> None:
    global qdrant_client
    if qdrant_client is not None:
        await qdrant_client.close()
        qdrant_client = None
        logger.info("Qdrant client closed")


async def ensure_collection() -> None:
    client = get_qdrant_client()
    collections = await client.get_collections()
    existing = [c.name for c in collections.collections]

    if settings.qdrant_collection not in existing:
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=EMBEDDING_VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection '%s'", settings.qdrant_collection)
    else:
        logger.info("Qdrant collection '%s' already exists", settings.qdrant_collection)
