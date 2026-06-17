import logging

from qdrant_client import AsyncQdrantClient

from app.config import settings

logger = logging.getLogger(__name__)

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
