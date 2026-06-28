import json
import logging
import uuid
from collections.abc import AsyncGenerator

from langchain_core.messages import HumanMessage

from app.agent.graph import get_graph
from app.agent.tools import PERSONAL_DATA_TOOLS
from app.core.redis import get_redis_client
from app.models.employee import Employee
from app.rag.cache import SemanticCache

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self) -> None:
        self.cache = SemanticCache(get_redis_client())

    async def stream(
        self,
        message: str,
        thread_id: str | None,
        employee: Employee,
    ) -> AsyncGenerator[dict, None]:
        thread_id = thread_id or uuid.uuid4().hex

        # 1. Check semantic cache
        cached_answer = await self.cache.get(message)
        if cached_answer is not None:
            yield {
                "event": "cache_hit",
                "data": json.dumps({"content": cached_answer}),
            }
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "thread_id": thread_id,
                        "contains_personal_data": False,
                    }
                ),
            }
            return

        # 2. Build input with employee context
        enriched = (
            f"[Current user: {employee.first_name} {employee.last_name}, "
            f"employee_id={employee.id}]\n\n{message}"
        )
        input_messages = {"messages": [HumanMessage(content=enriched)]}
        config = {"configurable": {"thread_id": thread_id}}

        # 3. Stream agent response
        graph = get_graph()
        full_response = ""
        tools_called: set[str] = set()

        async for event in graph.astream_events(input_messages, config, version="v2"):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    full_response += chunk.content
                    yield {
                        "event": "token",
                        "data": json.dumps({"content": chunk.content}),
                    }

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tools_called.add(tool_name)
                yield {
                    "event": "tool_start",
                    "data": json.dumps({"tool": tool_name}),
                }

            elif kind == "on_tool_end":
                yield {
                    "event": "tool_end",
                    "data": json.dumps({"tool": event.get("name", "")}),
                }

        # 4. Determine privacy flag
        contains_personal_data = bool(tools_called & PERSONAL_DATA_TOOLS)

        # 5. Cache if no personal data
        if not contains_personal_data and full_response:
            await self.cache.set(message, full_response)

        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "thread_id": thread_id,
                    "contains_personal_data": contains_personal_data,
                }
            ),
        }
