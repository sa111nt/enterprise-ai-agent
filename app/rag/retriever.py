import logging

from qdrant_client import AsyncQdrantClient

from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)


async def search_documents(
    query: str,
    client: AsyncQdrantClient,
    collection_name: str,
    top_k: int = 5,
    score_threshold: float = 0.7,
) -> list[dict]:
    embeddings = get_embeddings()
    query_vector = await embeddings.aembed_query(query)

    results = await client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
    )

    found = []
    for point in results:
        payload = point.payload or {}
        found.append(
            {
                "text": payload.get("text", ""),
                "score": point.score,
                "document_id": payload.get("document_id"),
                "document_title": payload.get("document_title", ""),
                "page": payload.get("page", 0),
                "chunk_index": payload.get("chunk_index", 0),
            }
        )

    logger.info(
        "Search query returned %d results (top_k=%d, threshold=%.2f)",
        len(found),
        top_k,
        score_threshold,
    )
    return found
