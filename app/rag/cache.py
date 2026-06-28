import json
import logging
import uuid

import numpy as np
import redis.asyncio as aioredis

from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.95
CACHE_TTL_SECONDS = 86400  # 24 hours


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    dot = np.dot(vec_a, vec_b)
    norm = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


class SemanticCache:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def get(self, query: str) -> str | None:
        embeddings = get_embeddings()
        query_vec = np.array(await embeddings.aembed_query(query))

        # Collect all cache keys
        keys: list[str] = []
        async for key in self.redis.scan_iter(match="sem_cache:*"):
            keys.append(key)

        if not keys:
            logger.debug("Semantic cache: empty, no keys found")
            return None

        # Fetch all cached embeddings
        pipe = self.redis.pipeline()
        for key in keys:
            pipe.hgetall(key)
        results = await pipe.execute()

        # Find best match
        best_answer: str | None = None
        best_score = 0.0

        for data in results:
            if not data:
                continue
            cached_vec = np.array(json.loads(data["embedding"]))
            score = _cosine_similarity(query_vec, cached_vec)
            if score >= SIMILARITY_THRESHOLD and score > best_score:
                best_score = score
                best_answer = data["answer"]

        if best_answer is not None:
            logger.info(
                "Semantic cache HIT (score=%.4f, threshold=%.2f)",
                best_score,
                SIMILARITY_THRESHOLD,
            )
        else:
            logger.debug("Semantic cache MISS (best_score=%.4f)", best_score)

        return best_answer

    async def set(self, query: str, answer: str) -> None:
        embeddings = get_embeddings()
        query_vec = await embeddings.aembed_query(query)

        key = f"sem_cache:{uuid.uuid4().hex}"
        await self.redis.hset(
            key,
            mapping={
                "query": query,
                "embedding": json.dumps(query_vec),
                "answer": answer,
            },
        )
        await self.redis.expire(key, CACHE_TTL_SECONDS)
        logger.info("Semantic cache SET: key=%s, ttl=%ds", key, CACHE_TTL_SECONDS)
