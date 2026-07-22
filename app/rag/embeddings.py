from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from app.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        openai_api_key=SecretStr(settings.openai_api_key)
        if settings.openai_api_key
        else None,
    )
