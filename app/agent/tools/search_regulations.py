from langchain_core.tools import tool

from app.config import settings
from app.core.qdrant import get_qdrant_client
from app.rag.retriever import search_documents


@tool
async def search_regulations(query: str) -> str:
    """Search company regulations, policies, and onboarding documents.

    Use this tool when the user asks about company rules, dress code,
    vacation policy, remote work guidelines, benefits, or any other
    information that would be found in official company documents.
    """
    client = get_qdrant_client()
    results = await search_documents(
        query=query,
        client=client,
        collection_name=settings.qdrant_collection,
    )

    if not results:
        return "No relevant documents found for this query."

    formatted = []
    for r in results:
        source = f"[{r['document_title']}, page {r['page'] + 1}]"
        formatted.append(f"{source}\n{r['text']}")

    return "\n\n---\n\n".join(formatted)
