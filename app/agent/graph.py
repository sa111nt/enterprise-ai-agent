import logging

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import create_react_agent

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import all_tools
from app.config import settings

logger = logging.getLogger(__name__)

_graph: CompiledGraph | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def initialize_graph() -> None:
    global _graph, _checkpointer

    conn_string = settings.database_url.replace("+asyncpg", "")
    _checkpointer = AsyncPostgresSaver.from_conn_string(conn_string)
    await _checkpointer.__aenter__()
    await _checkpointer.setup()
    logger.info("PostgreSQL checkpointer initialized")

    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        streaming=True,
    )

    _graph = create_react_agent(
        model=model,
        tools=all_tools,
        state_modifier=SYSTEM_PROMPT,
        checkpointer=_checkpointer,
    )
    logger.info("LangGraph ReAct agent compiled with %d tools", len(all_tools))


def get_graph() -> CompiledGraph:
    if _graph is None:
        raise RuntimeError(
            "Agent graph not initialized. Call initialize_graph() first."
        )
    return _graph


async def shutdown_graph() -> None:
    global _graph, _checkpointer
    if _checkpointer is not None:
        await _checkpointer.__aexit__(None, None, None)
        logger.info("PostgreSQL checkpointer closed")
    _graph = None
    _checkpointer = None
